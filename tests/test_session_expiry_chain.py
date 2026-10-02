"""The session expiry chain, link by link.

Measured, not read: importing a cookie whose `expires_hint` is 6 seconds in the
future, then polling the relay for 26s, `expires` was `-` on EVERY line and
`expired` was `false` on every line. The popup therefore rendered `1 cookies` for
the whole window - no countdown, never an expiry warning.

Four links were broken, and each one alone is enough to kill the feature:

  1. popup.js sent `cookies` (which carries `expirationDate`), never
     `expires_hint` - the key the relay actually reads.
  2. `cookie_for_cdp`'s allow-list did not include `expires_hint`, so even a
     correct payload had the key stripped on the way in.
  3. The filter kept `expires_hint` only when it was `> 0`, so a cookie that
     expired an hour ago lost its number and `expired` could never be true.
  4. `expired` and `cookies` were English literals in a ten-language popup.

Each test names ONE link, so a future edit that breaks a single link says which
one. The proof-red script reverts each in turn.

SELF-CONTAINED, and this is not decoration. The first version read the operator's
own `~/.config/lightpanda-bridge/secret` and posted to the RUNNING relay on port
8765, so CI failed with `FileNotFoundError` on a runner that has no such config -
five errors, none of them about the expiry. A shared machine service is not a
fixture: the suite serves the REAL Handler on an ephemeral port and owns its own
token.
"""
import http.client
import json
import pathlib
import sys
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "relay"))

import server  # noqa: E402

EXT_ID = "fcigkjkchglchhohedljlenopbkgnino"
TEST_TOKEN = "test-token-not-a-secret-0000"


def popup_js():
    return (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")


class _LiveRelay:
    """The real RelayServer + Handler on an ephemeral port, with our own token.

    Point 4 of the gate skill: the verifier must not consume a resource the
    product needs - we do not read the operator's secret and we do not stop the
    running relay. Point 25: save and restore EVERY global we replace, including
    the callable itself, which is the easy one to forget.
    """

    def __enter__(self):
        self._real_secret = server._load_secret
        server._load_secret = lambda: TEST_TOKEN
        self.srv = server.RelayServer(("127.0.0.1", 0), server.Handler)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()
        server._load_secret = self._real_secret
        return False

    def call(self, path, payload=None, timeout=25):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            headers = {"X-Bridge-Token": TEST_TOKEN,
                       "Origin": "chrome-extension://" + EXT_ID}
            body = None
            if payload is not None:
                body = json.dumps(payload)
                headers["Content-Type"] = "application/json"
            conn.request("POST" if payload is not None else "GET",
                         path, body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"raw": raw}
        finally:
            conn.close()


class TestTheChain(unittest.TestCase):
    """Each test names ONE link, so a regression says which one broke."""

    def setUp(self):
        self.popup = popup_js()

    def assertIn(self, needle, haystack, msg=""):
        # The default message embeds the whole 70KB popup.js and buries the
        # 70-character reason. Keep the reason.
        self.assertTrue(needle in haystack, msg)

    def assertNotIn(self, needle, haystack, msg=""):
        self.assertTrue(needle not in haystack, msg)

    # ---- link 1: the popup must forward what Chrome gives it ----------------
    def test_popup_forwards_chrome_expirationDate_as_expires_hint(self):
        """`chrome.cookies.getAll` yields `expirationDate`; the relay reads
        `expires_hint`. Without the rename, the number never leaves the popup."""
        self.assertIn("expirationDate", self.popup,
                      "le popup ne lit pas expirationDate de chrome.cookies")
        self.assertIn("expires_hint: typeof c.expirationDate", self.popup,
                      "expirationDate est lu mais pas renomme en expires_hint: "
                      "le relais lit expires_hint et verrait None")

    # ---- link 2: the relay must not strip the key on the way in -------------
    def test_relay_allows_expires_hint_through_the_allow_list(self):
        """The allow-list IS the drop point: a key absent from `allowed` never
        reaches `_SYNCED_SESSIONS`, so `list_sessions()` reads None forever no
        matter what the popup sends. Asserted through the real function, not a
        grep (point 37: a test of internal state must call the public path)."""
        kept = server.cookie_for_cdp(
            {"name": "p", "value": "v", "domain": "example.com",
             "expires_hint": time.time() + 3600}, "https://example.com")
        self.assertIn("expires_hint", kept,
                      "l'allow-list de cookie_for_cdp ne contient pas expires_hint: "
                      "la cle est supprimee a l'entree du relais")

    # ---- link 3: a past expiry must survive as a number ---------------------
    def test_relay_keeps_a_past_expiry_as_a_number(self):
        """A cookie that expired an hour ago must still carry the number, or
        `expired` can never become true. Gated on `> time.time()` instead, the
        number is dropped and a corpse is listed as alive."""
        past = time.time() - 3600
        kept = server.cookie_for_cdp(
            {"name": "p", "value": "v", "domain": "example.com",
             "expires_hint": past}, "https://example.com")
        self.assertIsInstance(kept.get("expires_hint"), float,
                              "un expires_hint deja passe est perdu: "
                              "`expired` ne pourra jamais devenir vrai")
        self.assertLess(kept["expires_hint"], time.time(),
                        "un expires_hint passe doit rester dans le passe")
        self.assertNotIn("expires", kept,
                         "`expires` doit rester absent: Lightpanda jette les "
                         "cookies qui portent un expires")

    # ---- link 4: the end-to-end result --------------------------------------
    def test_an_expiring_session_is_reported_as_expiring_then_expired(self):
        """The measurement that started this: a session expiring in 6s must be
        reported with a countdown, then flip to expired - without waiting for a
        client to poll. A flag that only changes because we re-imported is
        computed at import time, not from the stored expiry."""
        soon = time.time() + 6
        with _LiveRelay() as relay:
            status, resp = relay.call("/v1/session/import", {
                "origin": "https://example.com",
                "cookies": [{"name": "lp_expiry_probe", "value": "probe",
                             "domain": "example.com", "path": "/", "secure": True,
                             "httpOnly": False, "expires_hint": soon}]})
            self.assertEqual(status, 200,
                             "import refuse: %s" % json.dumps(resp)[:200])

            _, first = relay.call("/v1/sessions")
            sess = next((s for s in first.get("sessions", [])
                         if s.get("host") == "example.com"), None)
            self.assertIsNotNone(sess,
                                 "la session importee n'apparait pas dans la liste")
            self.assertIsInstance(sess.get("expires"), (int, float),
                                  "expires est absent: la popup n'affiche aucun "
                                  "compte a rebours (mesure: '-' sur 9 echantillons "
                                  "sur 26s)")
            self.assertFalse(sess.get("expired"),
                             "une session qui expire dans 6s est deja marquee morte")

            # Wait past the expiry with NO client call in between, so the flip can
            # only come from the server recomputing it from its own clock.
            left = soon - time.time()
            if left > 0:
                threading.Event().wait(left + 1.5)
            _, later = relay.call("/v1/sessions")
            sess2 = next((s for s in later.get("sessions", [])
                          if s.get("host") == "example.com"), None)
            self.assertTrue(sess2 and sess2.get("expired"),
                            "expired n'est jamais vrai apres le passage de "
                            "l'echeance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
