"""Session-isolated HTTP relay for the hosted web version.

Run behind an HTTPS reverse proxy. This is a single-process prototype:
sessions are kept in memory and are not shared across server instances.
The existing LAN HTTPS server remains in server.py.
"""

import hmac
import ipaddress
import json
import math
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
SESSION_TTL = 60 * 60
UNPAIRED_TTL = 3 * 60
CLAIM_TTL = 90
MAX_SESSIONS = 200
MAX_SESSIONS_PER_CLIENT = 20
MAX_NEW_SESSIONS_PER_MINUTE = 30
MAX_BODY = 2048
MAX_CONNECTIONS = 64
SENSOR_FIELDS = frozenset({
    'seq', 'px', 'py', 'yaw', 'pitch', 'roll', 'press', 'freeze',
    'freeze_count', 'exploring',
})
sessions = {}
session_creation_times = []
sessions_lock = threading.Lock()


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def prune_sessions(now):
    expired = [sid for sid, entry in sessions.items()
               if now - entry['last_seen'] > SESSION_TTL
               or (not entry['paired'] and now - entry['created_at'] > UNPAIRED_TTL)]
    for sid in expired:
        del sessions[sid]
    session_creation_times[:] = [t for t in session_creation_times if now - t < 60]


class WebHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def client_key(self):
        # Render adds X-Forwarded-For at its trusted ingress. Ignore it locally.
        if os.environ.get('RENDER') == 'true':
            forwarded = self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return self.client_address[0]

    def log_message(self, format, *args):
        # The phone pairing token never belongs in a URL or access log.
        pass

    def send_body(self, status, payload, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "connect-src 'self'; object-src 'none'; base-uri 'none'; "
                         "frame-ancestors 'none'; form-action 'none'")
        self.send_header('Strict-Transport-Security', 'max-age=31536000')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if self.close_connection:
            self.send_header('Connection', 'close')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)

    def send_json(self, status, value):
        # Error requests may have an unread body. Never parse it as another request.
        if status >= 400:
            self.close_connection = True
        self.send_body(status, json.dumps(value, allow_nan=False, separators=(',', ':')).encode(),
                       'application/json; charset=utf-8')

    def read_json(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise ValueError('JSON content type required')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError as exc:
            raise ValueError('Invalid content length') from exc
        if not 1 <= length <= MAX_BODY:
            raise ValueError('Invalid body length')
        try:
            value = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Invalid JSON') from exc
        if not isinstance(value, dict):
            raise ValueError('JSON object required')
        return value

    def session(self, query, role):
        sid = query.get('sid', [''])[0]
        token = self.headers.get('X-Simulator-Token', '')
        if len(sid) > 80 or len(token) > 80:
            return None
        entry = sessions.get(sid)
        now = time.monotonic()
        if not entry or now - entry['last_seen'] > SESSION_TTL or (
            not entry['paired'] and now - entry['created_at'] > UNPAIRED_TTL
        ):
            return None
        expected = entry.get(role + '_token')
        if not token or not expected or not hmac.compare_digest(token, expected):
            return None
        entry['last_seen'] = now
        return entry

    def static(self, path):
        files = {
            '/web': (ROOT / 'local_simulator.html', 'text/html; charset=utf-8'),
            '/vendor/qrcode.min.js': (ROOT / 'vendor' / 'qrcode.min.js', 'text/javascript; charset=utf-8'),
        }
        if path == '/':
            self.send_response(302)
            self.send_header('Location', '/web')
            self.send_header('Content-Length', '0')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        if path == '/healthz':
            self.send_json(200, {'ok': True})
            return
        item = files.get(path)
        if not item:
            self.send_json(404, {'error': 'Not found'})
            return
        file_path, content_type = item
        try:
            payload = file_path.read_bytes()
        except OSError:
            self.send_json(503, {'error': 'Asset unavailable'})
            return
        self.send_body(200, payload, content_type)

    def do_HEAD(self):
        self.static(urlsplit(self.path).path)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path not in ('/api/web/sensor', '/api/web/join'):
            self.static(parsed.path)
            return
        try:
            query = parse_qs(parsed.query, max_num_fields=4)
        except ValueError:
            self.send_json(400, {'error': 'Invalid query'})
            return
        with sessions_lock:
            if parsed.path == '/api/web/join':
                sid = query.get('sid', [''])[0]
                entry = sessions.get(sid)
                claim = entry.get('claim') if entry else None
                token = self.headers.get('X-Simulator-Token', '')
                now = time.monotonic()
                if (not claim or now - claim['created_at'] > CLAIM_TTL
                        or not token or not hmac.compare_digest(token, claim['token'])):
                    self.send_json(403, {'error': 'Pairing request expired'})
                    return
                result = {'status': claim['status']}
                if claim['status'] == 'approved':
                    result['probe_token'] = entry['probe_token']
                self.send_json(200, result)
                return
            entry = self.session(query, 'pc')
            if not entry:
                self.send_json(403, {'error': 'Invalid session'})
                return
            packet = dict(entry['latest_data'])
            claim = entry['claim']
            if claim and claim['status'] == 'pending' and time.monotonic() - claim['created_at'] <= CLAIM_TTL:
                packet['pairing'] = {'claim_id': claim['id'], 'code': claim['code']}
        self.send_json(200, packet)

    def do_POST(self):
        parsed = urlsplit(self.path)
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host', ''):
            self.send_json(403, {'error': 'Cross-origin request denied'})
            return
        if parsed.path == '/api/web/session':
            if self.headers.get('Content-Length', '0') != '0':
                self.send_json(400, {'error': 'Expected empty body'})
                return
            with sessions_lock:
                now = time.monotonic()
                prune_sessions(now)
                client = self.client_key()
                client_sessions = sum(entry['client'] == client for entry in sessions.values())
                if (len(session_creation_times) >= MAX_NEW_SESSIONS_PER_MINUTE
                        or client_sessions >= MAX_SESSIONS_PER_CLIENT):
                    self.send_json(429, {'error': 'Session creation rate limit reached'})
                    return
                if len(sessions) >= MAX_SESSIONS:
                    self.send_json(503, {'error': 'Session capacity reached'})
                    return
                sid = secrets.token_urlsafe(18)
                pc_token = secrets.token_urlsafe(32)
                pair_token = secrets.token_urlsafe(32)
                sessions[sid] = {
                    'pc_token': pc_token, 'pair_token': pair_token,
                    'probe_token': None, 'claim': None,
                    'latest_data': {}, 'sensor_seq': 0, 'zero_seq': 0,
                    'pc_pos': {'seq': 0, 'px': 0.2, 'py': 0.5},
                    'last_seen': now, 'created_at': now, 'paired': False, 'client': client,
                }
                session_creation_times.append(now)
            self.send_json(201, {'sid': sid, 'pc_token': pc_token, 'pair_token': pair_token})
            return
        if parsed.path not in ('/api/web/sensor', '/api/web/pos', '/api/web/zero',
                               '/api/web/join', '/api/web/pairing'):
            self.send_json(404, {'error': 'Not found'})
            return
        try:
            query = parse_qs(parsed.query, max_num_fields=4)
            if parsed.path == '/api/web/join':
                if self.headers.get('Content-Length', '0') != '0':
                    raise ValueError('Expected empty body')
                with sessions_lock:
                    entry = self.session(query, 'pair')
                    if not entry or entry['paired']:
                        self.send_json(403, {'error': 'Pairing invitation unavailable'})
                        return
                    claim = entry['claim']
                    now = time.monotonic()
                    if claim and now - claim['created_at'] <= CLAIM_TTL:
                        self.send_json(409, {'error': 'Another phone is awaiting approval'})
                        return
                    claim = {
                        'id': secrets.token_urlsafe(18),
                        'token': secrets.token_urlsafe(32),
                        'code': f'{secrets.randbelow(1000000):06d}',
                        'created_at': now, 'status': 'pending',
                    }
                    entry['claim'] = claim
                    result = {'claim_id': claim['id'], 'claim_token': claim['token'],
                              'code': claim['code']}
                self.send_json(201, result)
                return
            if parsed.path == '/api/web/pairing':
                data = self.read_json()
                action = data.get('action')
                if action not in ('approve', 'reject', 'reset'):
                    raise ValueError('Invalid pairing action')
                with sessions_lock:
                    entry = self.session(query, 'pc')
                    if not entry:
                        self.send_json(403, {'error': 'Invalid session'})
                        return
                    if action == 'reset':
                        entry['paired'] = False
                        entry['probe_token'] = None
                        entry['claim'] = None
                        entry['latest_data'] = {}
                        entry['pair_token'] = secrets.token_urlsafe(32)
                        entry['created_at'] = time.monotonic()
                        result = {'status': 'reset', 'pair_token': entry['pair_token']}
                    else:
                        claim = entry['claim']
                        if (not claim or claim['status'] != 'pending'
                                or time.monotonic() - claim['created_at'] > CLAIM_TTL
                                or data.get('claim_id') != claim['id']):
                            self.send_json(409, {'error': 'Pairing request unavailable'})
                            return
                        if action == 'approve':
                            entry['probe_token'] = secrets.token_urlsafe(32)
                            entry['pair_token'] = None
                            entry['paired'] = True
                            claim['status'] = 'approved'
                            result = {'status': 'approved'}
                        else:
                            entry['claim'] = None
                            entry['pair_token'] = secrets.token_urlsafe(32)
                            entry['created_at'] = time.monotonic()
                            result = {'status': 'rejected', 'pair_token': entry['pair_token']}
                self.send_json(200, result)
                return
            if parsed.path == '/api/web/zero':
                if self.headers.get('Content-Length', '0') != '0':
                    raise ValueError('Expected empty body')
                with sessions_lock:
                    entry = self.session(query, 'pc')
                    if not entry:
                        self.send_json(403, {'error': 'Invalid session'})
                        return
                    entry['zero_seq'] += 1
                    result = {'zero_seq': entry['zero_seq']}
                self.send_json(200, result)
                return
            data = self.read_json()
            if parsed.path == '/api/web/pos':
                if not all(finite_number(data.get(k)) for k in ('px', 'py')):
                    raise ValueError('Invalid position')
                with sessions_lock:
                    entry = self.session(query, 'pc')
                    if not entry:
                        self.send_json(403, {'error': 'Invalid session'})
                        return
                    pos = entry['pc_pos']
                    pos['seq'] += 1
                    pos['px'] = max(-8.5, min(8.5, float(data['px'])))
                    pos['py'] = max(-6.5, min(8.5, float(data['py'])))
                    result = {'ok': True, 'pc_pos': dict(pos)}
                self.send_json(200, result)
                return
            if not all(finite_number(data.get(k)) for k in ('px', 'py', 'yaw', 'pitch', 'roll')):
                raise ValueError('Invalid sensor values')
            if type(data.get('seq')) is not int or not 0 <= data['seq'] < (1 << 53):
                raise ValueError('Invalid sequence')
            if any(abs(data[k]) > 360 for k in ('yaw', 'pitch', 'roll')):
                raise ValueError('Orientation out of range')
            if data.get('press', 0) not in (0, 1) or data.get('freeze', 0) not in (0, 1):
                raise ValueError('Invalid control value')
            if type(data.get('exploring', 0)) is not int or data.get('exploring', 0) not in (0, 1):
                raise ValueError('Invalid exploration state')
            if 'freeze_count' in data and (
                type(data['freeze_count']) is not int or not 0 <= data['freeze_count'] < (1 << 53)
            ):
                raise ValueError('Invalid freeze count')
            with sessions_lock:
                entry = self.session(query, 'probe')
                if not entry:
                    self.send_json(403, {'error': 'Invalid session'})
                    return
                # Server-side sequence survives a phone page reload, whose
                # client-side counter starts again at zero.
                entry['sensor_seq'] += 1
                entry['latest_data'] = {key: value for key, value in data.items()
                                        if key in SENSOR_FIELDS}
                entry['latest_data']['seq'] = entry['sensor_seq']
                result = {'ok': True, 'zero_seq': entry['zero_seq'], 'pc_pos': dict(entry['pc_pos'])}
            self.send_json(200, result)
        except ValueError as exc:
            self.send_json(400, {'error': str(exc)})
        except TimeoutError:
            self.send_json(408, {'error': 'Request timed out'})


class WebHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self.connection_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.connection_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connection_slots.release()


def serve():
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8080'))
    httpd = WebHTTPServer((host, port), WebHandler)
    print(f'Web prototype listening on http://{host}:{port}/web', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    serve()
