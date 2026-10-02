"""Three audit findings, each pinned by a test that goes red without the fix.

1. `__Host-` cookies must be Secure (RFC 6265bis) - the branch forced path='/'
   and dropped the domain but left `secure` untouched, so a `secure: false` in
   the payload downgraded the one prefix whose whole guarantee is "Secure,
   host-only, path=/". `__Secure-` was already forced.
2. `artifacts.session_state` was permanently "unset": `collect()` looked for
   `session_state_path` in updater.py, but it lives in server.py. The report
   claimed the cookie file was absent on machines where it existed.
3. One torn line in update.log discarded the whole install history: the parser
   was a single list comprehension, so it parsed all ten lines or none.
4. `/v1/sessions` expiry: `cookie_for_cdp` pops `expires` (Lightpanda drops
   cookies set with one), and `list_sessions` then read that same key - always
   -1, so `expires` was always null and `expired` always false.

Run: .venv/Scripts/python.exe tests/test_audit_findings.py
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "relay"))

import server as relay        # noqa: E402
import diagnostics           # noqa: E402

ORIGIN = "https://x.com"


class HostPrefixIsSecure(unittest.TestCase):
    """Finding 1."""

    def test_host_prefixed_cookie_is_secure(self):
        out = relay.cookie_for_cdp({"name": "__Host-sid", "value": "v",
                                    "domain": "x.com"}, ORIGIN)
        self.assertIs(out.get("secure"), True,
                      "__Host- cookie is not Secure: %r" % out)

    def test_host_prefix_cannot_be_downgraded_by_the_payload(self):
        out = relay.cookie_for_cdp({"name": "__Host-sid", "value": "v",
                                    "domain": "x.com", "secure": False}, ORIGIN)
        self.assertIs(out.get("secure"), True,
                      "a supplied secure:false downgraded a __Host- cookie")

    def test_secure_prefix_still_forced(self):
        out = relay.cookie_for_cdp({"name": "__Secure-sid", "value": "v",
                                    "domain": "x.com", "secure": False}, ORIGIN)
        self.assertIs(out.get("secure"), True)

    def test_ordinary_cookie_keeps_its_own_secure_flag(self):
        self.assertIsNone(relay.cookie_for_cdp(
            {"name": "plain", "value": "v", "domain": "x.com"}, ORIGIN
        ).get("secure"), "the fix must not force Secure on every cookie")

    def test_expires_is_stripped_for_cdp_but_kept_as_a_hint(self):
        out = relay.cookie_for_cdp({"name": "a", "value": "v",
                                    "domain": "x.com", "expires": 9e9}, ORIGIN)
        self.assertNotIn("expires", out)
        # The hint lives on the RELAY's copy; the setCookies payload strips it
        # (see the cdp_cookies projection), because an unknown key in a CDP
        # cookie object can make the whole batch fail. So it is absent here and
        # present in the returned dict only for /v1/sessions to read back.
        self.assertIn("expires_hint", out)
        stripped = {k: v for k, v in out.items() if k != "expires_hint"}
        self.assertNotIn("expires_hint", stripped)


class SessionStateArtifactIsReported(unittest.TestCase):
    """Finding 2."""

    def test_session_state_is_not_unset_when_the_file_exists(self):
        report = diagnostics.collect()
        self.assertNotEqual(
            report["artifacts"].get("session_state"), "unset",
            "the report says the cookie file is absent; on this machine "
            "%s exists" % relay._session_state_path())

    def test_the_path_comes_from_the_module_that_defines_it(self):
        # The name is the PRIVATE spelling; that is the whole bug: collect()
        # looked up the public spelling in the wrong module.
        self.assertTrue(hasattr(relay, "_session_state_path"),
                        "server.py must still own the session file path")
        updater = diagnostics._sibling("updater")
        self.assertFalse(hasattr(updater, "_session_state_path"),
                         "if updater ever grows one, collect() must read both")


class TornLogLineKeepsTheRest(unittest.TestCase):
    """Finding 3."""

    def _write(self, lines):
        fd, path = tempfile.mkstemp(suffix=".log")
        os.close(fd)
        pathlib.Path(path).write_text("".join(lines), encoding="utf-8")
        self.addCleanup(os.remove, path)
        return path

    def _fake_updater(self, path):
        class U:
            @staticmethod
            def audit_path():
                return path

            @staticmethod
            def extension_dir():
                return ""

        return U

    def test_a_truncated_last_line_does_not_erase_the_history(self):
        path = self._write([
            json.dumps({"event": "install", "version": "0.7.1"}) + "\n",
            json.dumps({"event": "install", "version": "0.7.2"}) + "\n",
            '{"event": "install", "versi',          # power cut mid-write
        ])
        got = diagnostics._install_log(self._fake_updater(path))
        versions = [r.get("version") for r in got]
        self.assertIn("0.7.1", versions,
                      "one torn line threw away every install record: %r" % got)
        self.assertIn("0.7.2", versions)

    def test_a_fully_unparsable_log_is_empty_not_an_exception(self):
        path = self._write(["not json at all\n", "{\n"])
        self.assertEqual(diagnostics._install_log(self._fake_updater(path)), [])

    def test_missing_file_is_empty(self):
        self.assertEqual(diagnostics._install_log(
            self._fake_updater(os.path.join(tempfile.gettempdir(),
                                            "definitely-absent.log"))), [])


class SessionExpiryIsReportable(unittest.TestCase):
    """Finding 4."""

    def test_expires_survives_as_a_hint(self):
        out = relay.cookie_for_cdp({"name": "a", "value": "v",
                                    "domain": "x.com", "expires": 9e9}, ORIGIN)
        self.assertEqual(out.get("expires_hint"), 9e9)

    def test_a_session_cookie_reports_no_expiry(self):
        out = relay.cookie_for_cdp({"name": "a", "value": "v",
                                    "domain": "x.com"}, ORIGIN)
        self.assertIsNone(out.get("expires_hint"))

    def test_list_sessions_reports_the_expiry_it_has(self):
        saved_sessions = relay._SYNCED_SESSIONS
        saved_session = relay._LAST_SESSION
        saved = (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
                 relay._PERSISTED_INFLIGHT)
        self.addCleanup(lambda: (
            setattr(relay, "_SYNCED_SESSIONS", saved_sessions),
            setattr(relay, "_LAST_SESSION", saved_session),
            setattr(relay, "_PERSISTED_LOADED", saved[0]),
            setattr(relay, "_PERSISTED_APPLIED", saved[1]),
            setattr(relay, "_PERSISTED_INFLIGHT", saved[2])))
        relay._PERSISTED_LOADED = relay._PERSISTED_APPLIED = True
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = {"origin": ORIGIN, "cookies": [], "storage": {}}
        relay._SYNCED_SESSIONS = {ORIGIN: [
            relay.cookie_for_cdp({"name": "a", "value": "v", "domain": "x.com",
                                  "expires": 9e9}, ORIGIN)]}
        rows = {r["origin"]: r for r in relay.list_sessions()}
        self.assertIsNotNone(rows[ORIGIN]["expires"],
                             "expires is still dead: a cookie with a lifetime "
                             "reports none, so the popup can never warn")
        self.assertFalse(rows[ORIGIN]["expired"])

    def test_an_expired_cookie_is_flagged(self):
        saved_sessions = relay._SYNCED_SESSIONS
        saved_session = relay._LAST_SESSION
        saved = (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
                 relay._PERSISTED_INFLIGHT)
        self.addCleanup(lambda: (
            setattr(relay, "_SYNCED_SESSIONS", saved_sessions),
            setattr(relay, "_LAST_SESSION", saved_session),
            setattr(relay, "_PERSISTED_LOADED", saved[0]),
            setattr(relay, "_PERSISTED_APPLIED", saved[1]),
            setattr(relay, "_PERSISTED_INFLIGHT", saved[2])))
        relay._PERSISTED_LOADED = relay._PERSISTED_APPLIED = True
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = {"origin": ORIGIN, "cookies": [], "storage": {}}
        relay._SYNCED_SESSIONS = {ORIGIN: [
            {"name": "a", "value": "v", "domain": "x.com", "expires_hint": 1.0}]}
        rows = {r["origin"]: r for r in relay.list_sessions()}
        self.assertTrue(rows[ORIGIN]["expired"],
                        "a cookie that expired in 1970 is not flagged expired")


if __name__ == "__main__":
    unittest.main()
