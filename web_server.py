"""Session-isolated HTTP relay for a future hosted v43 web version.

Run behind an HTTPS reverse proxy. This is a single-process prototype:
sessions are kept in memory and are not shared across server instances.
The existing LAN HTTPS server remains in server.py.
"""

import hmac
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
MAX_SESSIONS = 200
MAX_BODY = 2048
sessions = {}
sessions_lock = threading.Lock()


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def prune_sessions(now):
    expired = [sid for sid, entry in sessions.items() if now - entry['last_seen'] > SESSION_TTL]
    for sid in expired:
        del sessions[sid]


class WebHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

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
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)

    def send_json(self, status, value):
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
        if not entry or time.monotonic() - entry['last_seen'] > SESSION_TTL:
            return None
        if not token or not hmac.compare_digest(token, entry[role + '_token']):
            return None
        entry['last_seen'] = time.monotonic()
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
        if parsed.path != '/api/web/sensor':
            self.static(parsed.path)
            return
        try:
            query = parse_qs(parsed.query, max_num_fields=4)
        except ValueError:
            self.send_json(400, {'error': 'Invalid query'})
            return
        with sessions_lock:
            entry = self.session(query, 'pc')
            if not entry:
                self.send_json(403, {'error': 'Invalid session'})
                return
            packet = dict(entry['latest_data'])
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
                if len(sessions) >= MAX_SESSIONS:
                    self.send_json(503, {'error': 'Session capacity reached'})
                    return
                sid = secrets.token_urlsafe(18)
                pc_token = secrets.token_urlsafe(32)
                probe_token = secrets.token_urlsafe(32)
                sessions[sid] = {
                    'pc_token': pc_token, 'probe_token': probe_token,
                    'latest_data': {}, 'sensor_seq': 0, 'zero_seq': 0,
                    'pc_pos': {'seq': 0, 'px': 0.2, 'py': 0.5},
                    'last_seen': now,
                }
            self.send_json(201, {'sid': sid, 'pc_token': pc_token, 'probe_token': probe_token})
            return
        if parsed.path not in ('/api/web/sensor', '/api/web/pos', '/api/web/zero'):
            self.send_json(404, {'error': 'Not found'})
            return
        try:
            query = parse_qs(parsed.query, max_num_fields=4)
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
            with sessions_lock:
                entry = self.session(query, 'probe')
                if not entry:
                    self.send_json(403, {'error': 'Invalid session'})
                    return
                # Server-side sequence survives a phone page reload, whose
                # client-side counter starts again at zero.
                entry['sensor_seq'] += 1
                entry['latest_data'] = {**data, 'seq': entry['sensor_seq']}
                result = {'ok': True, 'zero_seq': entry['zero_seq'], 'pc_pos': dict(entry['pc_pos'])}
            self.send_json(200, result)
        except ValueError as exc:
            self.send_json(400, {'error': str(exc)})


class WebHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


def serve():
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8080'))
    httpd = WebHTTPServer((host, port), WebHandler)
    print(f'Web prototype listening on http://{host}:{port}/web', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    serve()
