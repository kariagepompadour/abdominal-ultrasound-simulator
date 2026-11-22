"""Behavior checks for the hosted session relay; no external network required."""

import json
import threading
import time
import unittest
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import web_server


class WebRelayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = web_server.WebHTTPServer(('127.0.0.1', 0), web_server.WebHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        with web_server.sessions_lock:
            web_server.sessions.clear()
            web_server.session_creation_times.clear()

    def request(self, path, method='GET', token=None, body=None, extra_headers=None):
        headers = dict(extra_headers or {})
        if token:
            headers['X-Simulator-Token'] = token
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        elif method == 'POST':
            data = b''
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read()) if 'json' in response.headers['Content-Type'] else response.read()
        except HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read())
            finally:
                exc.close()

    def create_session(self):
        status, data = self.request('/api/web/session', method='POST')
        self.assertEqual(status, 201)
        return data

    def approve_phone(self, pair):
        join_path = f"/api/web/join?sid={pair['sid']}"
        status, claim = self.request(join_path, 'POST', pair['pair_token'])
        self.assertEqual(status, 201)
        pending = self.request(f"/api/web/sensor?sid={pair['sid']}",
                               token=pair['pc_token'])[1]['pairing']
        self.assertEqual(pending['claim_id'], claim['claim_id'])
        self.assertEqual(pending['code'], claim['code'])
        status, _ = self.request(f"/api/web/pairing?sid={pair['sid']}", 'POST',
                                 pair['pc_token'],
                                 {'action': 'approve', 'claim_id': claim['claim_id']})
        self.assertEqual(status, 200)
        status, result = self.request(join_path, token=claim['claim_token'])
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'approved')
        return result['probe_token']

    def test_two_pairs_are_isolated_and_roles_are_enforced(self):
        first = self.create_session()
        second = self.create_session()
        first_probe = self.approve_phone(first)
        second_probe = self.approve_phone(second)
        packet = {'seq': 1, 'px': -2.0, 'py': 1.0, 'yaw': 18, 'pitch': 7, 'roll': -5, 'press': 0, 'freeze': 0}
        first_path = f"/api/web/sensor?sid={first['sid']}"
        second_path = f"/api/web/sensor?sid={second['sid']}"

        self.assertEqual(self.request(first_path, 'POST', first_probe, packet)[0], 200)
        self.assertEqual(self.request(first_path, token=first['pc_token'])[1]['yaw'], 18)
        self.assertEqual(self.request(second_path, token=second['pc_token'])[1], {})
        self.assertEqual(self.request(first_path, token=second['pc_token'])[0], 403)
        self.assertEqual(self.request(first_path, 'POST', first['pc_token'], packet)[0], 403)
        self.assertEqual(self.request(first_path, token=first_probe)[0], 403)

        # A phone reload restarts its counter; PC updates must still advance.
        reloaded = {**packet, 'seq': 0, 'yaw': -12}
        self.assertEqual(self.request(first_path, 'POST', first_probe, reloaded)[0], 200)
        self.assertEqual(self.request(first_path, token=first['pc_token'])[1]['yaw'], -12)
        self.assertEqual(self.request(first_path, token=first['pc_token'])[1]['seq'], 2)

        self.assertEqual(self.request(f"/api/web/zero?sid={first['sid']}", 'POST', first['pc_token'])[1]['zero_seq'], 1)
        self.assertEqual(self.request(f"/api/web/pos?sid={first['sid']}", 'POST', first['pc_token'], {'px': 3, 'py': 4})[1]['pc_pos']['px'], 3)
        self.assertEqual(self.request(second_path, 'POST', second_probe, packet)[1]['zero_seq'], 0)

    def test_static_allowlist_and_expiry(self):
        session = self.create_session()
        self.assertEqual(self.request('/key.pem')[0], 404)
        self.assertEqual(self.request('/local_tls/server-key.pem')[0], 404)
        self.assertEqual(self.request('/server.py')[0], 404)
        with web_server.sessions_lock:
            web_server.sessions[session['sid']]['last_seen'] = time.monotonic() - web_server.SESSION_TTL - 1
        self.assertEqual(self.request(f"/api/web/sensor?sid={session['sid']}", token=session['pc_token'])[0], 403)

    def test_cross_origin_session_creation_is_denied(self):
        status, _ = self.request('/api/web/session', method='POST',
                                 extra_headers={'Origin': 'https://another.example'})
        self.assertEqual(status, 403)
        self.assertEqual(len(web_server.sessions), 0)

    def test_session_creation_is_limited_and_unpaired_sessions_expire(self):
        first = self.create_session()
        for _ in range(web_server.MAX_SESSIONS_PER_CLIENT - 1):
            self.create_session()
        self.assertEqual(self.request('/api/web/session', method='POST')[0], 429)
        with web_server.sessions_lock:
            web_server.sessions[first['sid']]['created_at'] -= web_server.UNPAIRED_TTL + 1
        self.assertEqual(self.request(f"/api/web/sensor?sid={first['sid']}",
                                      token=first['pc_token'])[0], 403)
        self.assertEqual(self.request('/api/web/session', method='POST')[0], 201)

    def test_freeze_counter_and_exploring_state_are_validated(self):
        pair = self.create_session()
        probe_token = self.approve_phone(pair)
        path = f"/api/web/sensor?sid={pair['sid']}"
        packet = {'seq': 1, 'px': 0, 'py': 0, 'yaw': 0, 'pitch': 0, 'roll': 0,
                  'press': 0, 'freeze_count': 2, 'exploring': 1}
        self.assertEqual(self.request(path, 'POST', probe_token, packet)[0], 200)
        received = self.request(path, token=pair['pc_token'])[1]
        self.assertEqual(received['freeze_count'], 2)
        self.assertEqual(received['exploring'], 1)
        for invalid in ({'freeze_count': -1}, {'freeze_count': True}, {'exploring': True}):
            self.assertEqual(self.request(path, 'POST', probe_token,
                                          {**packet, **invalid})[0], 400)

    def test_qr_requires_pc_approval_and_reset_revokes_phone(self):
        pair = self.create_session()
        sensor_path = f"/api/web/sensor?sid={pair['sid']}"
        join_path = f"/api/web/join?sid={pair['sid']}"
        pairing_path = f"/api/web/pairing?sid={pair['sid']}"
        packet = {'seq': 1, 'px': 0, 'py': 0, 'yaw': 0, 'pitch': 0, 'roll': 0}
        self.assertNotIn('probe_token', pair)
        self.assertEqual(self.request(sensor_path, 'POST', pair['pair_token'], packet)[0], 403)
        claim = self.request(join_path, 'POST', pair['pair_token'])[1]
        self.assertEqual(self.request(sensor_path, 'POST', claim['claim_token'], packet)[0], 403)
        self.assertEqual(self.request(pairing_path, 'POST', pair['pc_token'],
                                      {'action': 'approve', 'claim_id': 'wrong'})[0], 409)
        self.assertEqual(self.request(join_path, 'POST', pair['pair_token'])[0], 409)
        rejected = self.request(pairing_path, 'POST', pair['pc_token'],
                                {'action': 'reject', 'claim_id': claim['claim_id']})[1]
        self.assertEqual(self.request(join_path, token=claim['claim_token'])[0], 403)
        self.assertEqual(self.request(join_path, 'POST', pair['pair_token'])[0], 403)
        pair['pair_token'] = rejected['pair_token']
        probe_token = self.approve_phone(pair)
        self.assertEqual(self.request(sensor_path, 'POST', probe_token, packet)[0], 200)
        self.assertEqual(self.request(join_path, 'POST', pair['pair_token'])[0], 403)
        reset = self.request(pairing_path, 'POST', pair['pc_token'], {'action': 'reset'})[1]
        self.assertEqual(self.request(sensor_path, 'POST', probe_token, packet)[0], 403)
        self.assertTrue(reset['pair_token'])

    def test_loading_web_page_does_not_create_a_session(self):
        self.assertEqual(self.request('/web')[0], 200)
        self.assertEqual(web_server.sessions, {})

    def test_global_creation_limit(self):
        original_limit = web_server.MAX_NEW_SESSIONS_PER_MINUTE
        try:
            web_server.MAX_NEW_SESSIONS_PER_MINUTE = 2
            self.create_session()
            self.create_session()
            self.assertEqual(self.request('/api/web/session', method='POST')[0], 429)
        finally:
            web_server.MAX_NEW_SESSIONS_PER_MINUTE = original_limit

    def test_unknown_sensor_fields_do_not_reach_pc(self):
        pair = self.create_session()
        probe_token = self.approve_phone(pair)
        path = f"/api/web/sensor?sid={pair['sid']}"
        packet = {'seq': 1, 'px': 0, 'py': 0, 'yaw': 0, 'pitch': 0, 'roll': 0,
                  'freeze_count': 1, 'unexpected': 'untrusted value'}
        self.assertEqual(self.request(path, 'POST', probe_token, packet)[0], 200)
        received = self.request(path, token=pair['pc_token'])[1]
        self.assertEqual(received['freeze_count'], 1)
        self.assertNotIn('unexpected', received)

    def test_security_headers_and_unread_body_close(self):
        with urlopen(self.base + '/web', timeout=3) as response:
            self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
            self.assertEqual(response.headers['Strict-Transport-Security'], 'max-age=31536000')
            self.assertIn('camera=()', response.headers['Permissions-Policy'])
        connection = HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=3)
        try:
            connection.request('POST', '/api/web/session', body=b'{"unexpected":true}',
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertEqual(response.getheader('Connection'), 'close')
            response.read()
        finally:
            connection.close()


if __name__ == '__main__':
    unittest.main()
