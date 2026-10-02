"""The session expiry feature is wired at both ends and produces nothing.

Measured, not read: importing a cookie whose `expires_hint` is 6 seconds in the
future, then polling the relay every 3s for 26s, `expires` was `-` on EVERY line
and `expired` was `false` on every line. The popup therefore rendered
`1 cookies` for the whole window - no countdown, never an expiry warning.

The chain has four breaks, and each one alone is enough to make the feature
dead:

  1. popup.js never sends `expires_hint`. Chrome's `cookies.getAll` returns
     `expirationDate`, which the relay does not read.
  2. `cookie_for_cdp`'s allow-list does not include `expires_hint`, so even a
     correct payload would have the key stripped on the way in.
  3. `cookie_for_cdp` pops `expires` and derives `expires_hint` from it - from a
     key the popup does not send.
  4. `list_sessions()` reads `expires_hint`, so it always saw `None`.

These tests assert the chain, one link per test, so a future edit that breaks a
single link names which one. The proof-red script reverts each in turn.
"""
import json
import pathlib
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RELAY = "http://127.0.0.1:8765"
SECRET = pathlib.Path.home() / ".config" / "lightpanda-bridge" / "secret"
EXT_ID = "fcigkjkchglchhohedljlenopbkgnino"


def call(path, payload=None, timeout=25):
    token = SECRET.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(RELAY + path,
                                 method="POST" if payload is not None else "GET")
    req.add_header("X-Bridge-Token", token)
    req.add_header("Origin", "chrome-extension://" + EXT_ID)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8", "replace"))


import unittest


def popup_js():
    return (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")


def relay_js():
    return (ROOT / "relay" / "server.py").read_text(encoding="utf-8")


class TestTheChain(unittest.TestCase):
    """Each test names ONE link, so a regression says which one broke."""

    def setUp(self):
        self.popup = popup_js()
        self.relay = relay_js()
        self.origin = "https://example.com"

    def assertIn(self, needle, haystack, msg=""):
        # The default message embeds the whole 70KB popup.js and buries the
        # 70-character reason. Keep the reason.
        self.assertTrue(needle in haystack, msg)

    def assertNotIn(self, needle, haystack, msg=""):
        self.assertTrue(needle not in haystack, msg)

    def tearDown(self):
        call("/v1/sessions/clear", {"origin": self.origin})

    # ---- link 1: the popup must forward what Chrome gives it ----------------
    def test_popup_forwards_chrome_expirationDate_as_expires_hint(self):
        """`chrome.cookies.getAll` yields `expirationDate`; the relay reads
        `expires_hint`. Without the rename, the number never leaves the popup."""
        self.assertIn("expirationDate", self.popup,
                      "le popup ne lit pas expirationDate de chrome.cookies")
        # and it must be renamed, not merely read
        self.assertRegex(
            self.popup, r"expires_hint\s*:\s*[^,}]*expirationDate",
            "expirationDate est lu mais pas renomme en expires_hint: "
            "le relais lit expires_hint et verrait None")

    # ---- link 2: the relay must not strip the key on the way in -------------
    def test_relay_allows_expires_hint_through_the_allow_list(self):
        self.assertRegex(
            self.relay, r'allowed\s*=\s*\{[^}]*["\']expires_hint["\']',
            "l'allow-list de cookie_for_cdp ne contient pas expires_hint: "
            "la cle est supprimee a l'entree du relais")

    # ---- link 3: a past expiry must survive as a number ---------------------
    def test_relay_keeps_a_past_expiry_as_a_number(self):
        """A cookie that expired an hour ago must still carry the number, or
        `expired` can never become true."""
        past = time.time() - 3600
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');"
             "import server; import json;"
             "c = server.cookie_for_cdp({'name':'p','value':'v',"
             "'domain':'example.com','expires_hint': %r}, %r);"
             "print(json.dumps(c))"
             % (ROOT / "relay", ROOT / "relay", past, self.origin)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[:400])
        c = json.loads(out.stdout.strip())
        self.assertIsInstance(c.get("expires_hint"), float,
                              "un expires_hint deja passe est perdu: "
                              "`expired` ne pourra jamais devenir vrai")
        self.assertLess(c["expires_hint"], time.time(),
                        "un expires_hint passe doit rester dans le passe")
        # and it must NOT have been sent to Lightpanda as `expires`
        self.assertNotIn("expires", c,
                         "`expires` doit rester absent: Lightpanda jette les "
                         "cookies qui portent un expires")

    # ---- link 4: the end-to-end result --------------------------------------
    def test_an_expiring_session_is_reported_as_expiring_then_expired(self):
        """The measurement that started this: a session expiring in 6s must be
        reported with a countdown, then flip to expired - without waiting for a
        client to poll."""
        soon = time.time() + 6
        status, resp = call("/v1/session/import", {
            "origin": self.origin,
            "cookies": [{"name": "lp_expiry_probe", "value": "probe",
                         "domain": "example.com", "path": "/", "secure": True,
                         "httpOnly": False, "expires_hint": soon}]})
        self.assertEqual(status, 200, "import refuse: %s" % json.dumps(resp)[:200])

        _, first = call("/v1/sessions")
        sess = next((s for s in first.get("sessions", [])
                     if s["host"] == "example.com"), None)
        self.assertIsNotNone(sess, "la session importee n'apparait pas dans la liste")
        self.assertIsInstance(sess.get("expires"), (int, float),
                              "expires est absent: la popup n'affiche aucun compte "
                              "a rebours (mesure: '-' sur 9 echantillons sur 26s)")

        # Wait past the expiry WITHOUT any client polling, so the flip can only
        # come from the server computing it per request from its own clock.
        time.sleep(8)
        _, later = call("/v1/sessions")
        sess2 = next((s for s in later.get("sessions", [])
                      if s["host"] == "example.com"), None)
        self.assertTrue(sess2 and sess2.get("expired"),
                        "expired n'est jamais vrai apres le passage de l'echeance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
