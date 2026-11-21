"""Behavior checks for the hosted session relay; no external network required."""

import json
import threading
import time
import unittest
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

    def test_two_pairs_are_isolated_and_roles_are_enforced(self):
        first = self.create_session()
        second = self.create_session()
        packet = {'seq': 1, 'px': -2.0, 'py': 1.0, 'yaw': 18, 'pitch': 7, 'roll': -5, 'press': 0, 'freeze': 0}
        first_path = f"/api/web/sensor?sid={first['sid']}"
        second_path = f"/api/web/sensor?sid={second['sid']}"

        self.assertEqual(self.request(first_path, 'POST', first['probe_token'], packet)[0], 200)
        self.assertEqual(self.request(first_path, token=first['pc_token'])[1]['yaw'], 18)
        self.assertEqual(self.request(second_path, token=second['pc_token'])[1], {})
        self.assertEqual(self.request(first_path, token=second['pc_token'])[0], 403)
        self.assertEqual(self.request(first_path, 'POST', first['pc_token'], packet)[0], 403)
        self.assertEqual(self.request(first_path, token=first['probe_token'])[0], 403)

        # A phone reload restarts its counter; PC updates must still advance.
        reloaded = {**packet, 'seq': 0, 'yaw': -12}
        self.assertEqual(self.request(first_path, 'POST', first['probe_token'], reloaded)[0], 200)
        self.assertEqual(self.request(first_path, token=first['pc_token'])[1]['yaw'], -12)
        self.assertEqual(self.request(first_path, token=first['pc_token'])[1]['seq'], 2)

        self.assertEqual(self.request(f"/api/web/zero?sid={first['sid']}", 'POST', first['pc_token'])[1]['zero_seq'], 1)
        self.assertEqual(self.request(f"/api/web/pos?sid={first['sid']}", 'POST', first['pc_token'], {'px': 3, 'py': 4})[1]['pc_pos']['px'], 3)
        self.assertEqual(self.request(second_path, 'POST', second['probe_token'], packet)[1]['zero_seq'], 0)

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


if __name__ == '__main__':
    unittest.main()
