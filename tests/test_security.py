import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'relay'))
import server


class SecurityTests(unittest.TestCase):
    def test_only_https_public_origins(self):
        self.assertTrue(server.valid_origin('https://a6api.com'))
        self.assertFalse(server.valid_origin('http://a6api.com'))
        self.assertFalse(server.valid_origin('https://accounts.google.com'))
        self.assertFalse(server.valid_origin('https://login.accounts.google.com'))
        self.assertFalse(server.valid_origin('https://a6api.com/path'))
        self.assertFalse(server.valid_origin('https://user:pass@a6api.com'))

    def test_cookie_filter_drops_extension_metadata(self):
        value = server.cookie_for_cdp({
            'name': 'session', 'value': 'redacted', 'domain': '.a6api.com',
            'storeId': 'private', 'hostOnly': True, 'session': True,
        }, 'https://a6api.com')
        self.assertEqual(value['name'], 'session')
        self.assertNotIn('storeId', value)
        self.assertNotIn('hostOnly', value)
        self.assertNotIn('session', value)

    def test_empty_or_oversized_cookie_lists_rejected(self):
        with self.assertRaises(ValueError):
            server.set_session('https://a6api.com', [])
        with self.assertRaises(ValueError):
            server.set_session('https://a6api.com', [{} for _ in range(501)])

    def test_private_and_identity_origins_are_rejected(self):
        for origin in (
            'https://localhost',
            'https://127.0.0.1',
            'https://10.0.0.4',
            'https://192.168.1.5',
            'https://accounts.google.com',
        ):
            self.assertFalse(server.valid_origin(origin), origin)

    def test_cookie_for_cdp_rejects_cookie_from_another_domain(self):
        with self.assertRaises(ValueError):
            server.cookie_for_cdp({
                'name': 'session', 'value': 'redacted', 'domain': '.other.example',
            }, 'https://a6api.com')
        with self.assertRaises(ValueError):
            server.cookie_for_cdp({
                'name': 'session', 'value': 'redacted', 'domain': '.a6api.com',
                'url': 'https://other.example/',
            }, 'https://a6api.com')

    def test_cdp_request_places_session_id_on_envelope(self):
        class FakeSocket:
            def __init__(self):
                self.sent = []
            def send(self, raw):
                self.sent.append(raw)
            def recv(self):
                request = __import__('json').loads(self.sent[-1])
                return __import__('json').dumps({'id': request['id'], 'result': {'ok': True}})
            def close(self):
                pass

        sock = FakeSocket()
        transport = server.CdpTransport(socket=sock)
        result = transport.request('Runtime.evaluate', {'expression': '1'}, session_id='SID-1')
        self.assertEqual(result, {'ok': True})
        payload = __import__('json').loads(sock.sent[0])
        self.assertEqual(payload['sessionId'], 'SID-1')

    def test_attach_page_creates_and_attaches_a_target(self):
        class FakeTransport:
            def __init__(self):
                self.calls = []
            def request(self, method, params=None, session_id=None):
                self.calls.append((method, params or {}, session_id))
                if method == 'Target.getTargets':
                    return {'targetInfos': []}
                if method == 'Target.createTarget':
                    return {'targetId': 'FID-1'}
                if method == 'Target.attachToTarget':
                    return {'sessionId': 'SID-1'}
                raise AssertionError(method)

        transport = FakeTransport()
        target_id, session_id = server.attach_page(transport, 'https://a6api.com')
        self.assertEqual((target_id, session_id), ('FID-1', 'SID-1'))
        self.assertEqual(transport.calls[0][0], 'Target.getTargets')
        self.assertEqual(transport.calls[1], ('Target.createTarget', {'url': 'https://a6api.com'}, None))
        self.assertEqual(transport.calls[2], ('Target.attachToTarget', {'targetId': 'FID-1', 'flatten': True}, None))

    def test_bootstrap_requires_strict_extension_origin(self):
        # Secret-delivering endpoint: ONLY a real chrome-extension:// Origin
        # may read the token. Web pages, Origin-less processes (curl/malware)
        # and CLI tools must all be refused.
        class FakeHandler(BaseFakeHandler):
            def __init__(self, origin):
                super().__init__({'Origin': origin} if origin else {})

        for origin in (None, 'https://evil.com', 'https://a6api.com', 'null'):
            handler = FakeHandler(origin)
            self.assertFalse(handler._require_extension_origin(), repr(origin))
        for origin in ('chrome-extension://fcigkjkchglchhohedljlenopbkgnino',
                       'chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'):
            handler = FakeHandler(origin)
            self.assertTrue(handler._require_extension_origin(), repr(origin))

    def test_import_accepts_extension_or_originless_caller(self):
        # /v1/session/import is guarded by the shared token; the caller check
        # is intentionally looser (extension OR local CLI without Origin),
        # because the token itself is the real gate for state changes.
        class FakeHandler(BaseFakeHandler):
            def __init__(self, origin):
                super().__init__({'Origin': origin} if origin else {})

        self.assertTrue(FakeHandler(None)._check_extension_caller())
        self.assertTrue(FakeHandler('chrome-extension://fcigkjkchglchhohedljlenopbkgnino')._check_extension_caller())
        self.assertFalse(FakeHandler('https://evil.com')._check_extension_caller())
        self.assertFalse(FakeHandler('null')._check_extension_caller())


class BaseFakeHandler:
    """Minimal stand-in exposing just the origin-check helpers."""
    def __init__(self, headers):
        self.headers = headers
    def _check_extension_caller(self):
        return server.Handler._check_extension_caller(self)
    def _require_extension_origin(self):
        return server.Handler._require_extension_origin(self)


if __name__ == '__main__':
    unittest.main()
