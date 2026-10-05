"""A cookie transfer that silently loses cookies must be REFUSED, by name.

MEASURED BLINDNESS (2026-10-05, this file's reason to exist):

`relay/server.py` L936 verified a sync with

    if not any(str(item["name"]) in names for item in converted):
        raise RuntimeError("Lightpanda cookie verification failed: no cookies found")

`any()` answers "did at least ONE cookie survive", so a sync where 3 of 5
cookies never reached the browser returned SUCCESS, and popup.js rendered
"OK Session synchronized (5 cookies, 0 keys)". Every authenticated request
then came back 401/407 with nothing on screen to explain it -- the exact
shape of the x.com "5/7 keys" bug, rebuilt for cookies.

Proof the suite was blind: mutating L936 `any` -> `all` (the obvious fix)
left all 269 tests GREEN. This file is that ratchet.

Fixed 2026-10-05: the at-least-one predicate is gone. The gap is now
computed as `_LAST_COOKIE_MISSING` (names, never values), refused AFTER
bookkeeping so an automatic resync can still finish the job -- the same
ordering the localStorage path already used.

Two layers, on purpose:
  1. behaviour  - a transport that can actually drop cookies, the way
     Lightpanda drops those whose domain/path do not match the target.
  2. source/AST - the forbidden at-least-one shape and the by-name gap in
     the real file. A behavioural test alone would pass if someone deleted
     the verification entirely (that is also "no partial transfer" when the
     fake drops nothing).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "relay"))
import server

SOURCE = (ROOT / "relay" / "server.py").read_text(encoding="utf-8")


class _LosingTransport:
    """The REAL `_apply_session` runs against this; cookies go missing.

    This is the real failure mode, not a synthetic one: Lightpanda applies
    cookies per domain/path, and a cookie the relay sends for a host the
    navigation does not match is silently dropped rather than rejected.

    Nothing here stubs the product. `_apply_session` is called for real, so
    the only thing under test is the verification that follows it.
    """

    def __init__(self, keep):
        self.keep = keep
        self.cookies = []
        self.calls = []

    def request(self, method, params=None, session_id=None):
        params = params or {}
        self.calls.append(method)
        if method == "Network.setCookies":
            sent = params.get("cookies", [])
            # Keep the first `keep` and DROP the rest, exactly like a browser
            # that refuses cookies whose domain/path does not match.
            self.cookies = list(sent)[: self.keep]
            return {"ok": True, "result": {}}
        if method == "Network.getCookies":
            urls = params.get("urls")
            if not urls:
                return {"cookies": list(self.cookies)}
            hosts = [u.split("//", 1)[-1].rstrip("/") for u in urls]
            matched = [c for c in self.cookies
                       if any(h.endswith(str(c.get("domain", "")).lstrip("."))
                              or h == str(c.get("domain", "")).lstrip(".")
                              for h in hosts)]
            return {"cookies": matched}
        if method == "Page.addScriptToEvaluateOnNewDocument":
            return {"ok": True, "result": {"identifier": "1"}}
        if method == "Runtime.evaluate":
            return {"ok": True, "result": {"result": {"value": 0}}}
        return {"ok": True, "result": {}}


class PartialCookieTransferTests(unittest.TestCase):
    """LAYER 1 - the behaviour the user sees."""

    def setUp(self):
        import os
        import shutil
        import tempfile

        self._tmp = tempfile.mkdtemp(prefix="lp-cookie-loss-")
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self._tmp
        self._settle = server._NAV_SETTLE_SECONDS
        server._NAV_SETTLE_SECONDS = 0
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        self._saved = (server._CDP_TRANSPORT, server._CDP_SESSION_ID,
                       server._ensure_connection, server._persist_session)
        server._CDP_SESSION_ID = "fake"
        server._ensure_connection = lambda origin=None: True
        # `_apply_session` is deliberately NOT stubbed: it is the code that
        # calls Network.setCookies, so stubbing it left the jar permanently
        # empty and made the happy path fail for harness reasons, not product ones.
        server._persist_session = lambda session: None

    def tearDown(self):
        (server._CDP_TRANSPORT, server._CDP_SESSION_ID, server._ensure_connection,
         server._persist_session) = self._saved
        server._NAV_SETTLE_SECONDS = self._settle
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _five_cookies(self):
        return [{"name": "c%d" % i, "value": "v", "domain": ".dev.to"}
                for i in range(5)]

    def _sync_with(self, keep):
        server._CDP_TRANSPORT = _LosingTransport(keep)
        return server.set_session("https://dev.to", self._five_cookies())

    def test_complete_transfer_still_succeeds(self):
        """The happy path must stay green -- the point is not 'always refuse'."""
        ok = self._sync_with(keep=5)
        self.assertTrue(ok, "a complete 5/5 transfer must still be accepted")

    def test_partial_transfer_is_refused(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._sync_with(keep=2)
        self.assertNotEqual(str(ctx.exception), "",
                            "a refusal with no reason is not actionable")

    def test_single_cookie_kept_of_five_is_refused(self):
        """`any()` passes this: one survivor is enough for it to say OK."""
        with self.assertRaises(RuntimeError):
            self._sync_with(keep=1)

    def test_refusal_names_the_lost_cookies(self):
        """Same lesson as the storage path: names are what make it actionable."""
        try:
            self._sync_with(keep=2)
            self.fail("2/5 cookies must not be reported as a successful sync")
        except RuntimeError as exc:
            message = str(exc)
            for name in ("c2", "c3", "c4"):
                self.assertIn(name, message,
                              "refusal must name %s; got %r" % (name, message))

    def test_refusal_reports_the_ratio(self):
        try:
            self._sync_with(keep=2)
            self.fail("2/5 cookies must not be reported as a successful sync")
        except RuntimeError as exc:
            self.assertIn("2/5", str(exc))

    def test_no_cookies_at_all_is_refused(self):
        """The pre-existing `any()` guard already covered this one."""
        with self.assertRaises(RuntimeError):
            self._sync_with(keep=0)

    def test_refusal_still_books_the_session_for_a_resync(self):
        """A refused partial sync MUST still be remembered.

        `relay/server.py` L947-950 states the intent explicitly: "Bookkeeping
        is done (a resync can finish the job), but the caller is told the
        truth." Ordering matters -- a transfer that is refused WITHOUT being
        remembered is exactly the "it only works after I click sync twice"
        symptom. So this asserts the bookkeeping happens, not that it is
        suppressed.
        """
        with self.assertRaises(RuntimeError):
            self._sync_with(keep=2)
        self.assertIn("https://dev.to", server._SYNCED_SESSIONS)
        self.assertEqual(5, len(server._SYNCED_SESSIONS["https://dev.to"]))

    def test_refusal_exposes_the_missing_names_for_the_popup(self):
        """Same lesson as the storage path: names are what make it actionable.

        The storage branch publishes `_LAST_STORAGE_MISSING` so popup.js can
        say which keys failed. Without a cookie twin, a stuck "2/5 cookies"
        comes back on every sync with no way to act on it -- the exact defect
        L903-904 describes for storage.
        """
        with self.assertRaises(RuntimeError):
            self._sync_with(keep=2)
        missing = getattr(server, "_LAST_COOKIE_MISSING", None)
        self.assertIsNotNone(
            missing, "relay/server.py has no _LAST_COOKIE_MISSING: a refused "
                     "cookie transfer cannot tell the caller which cookies failed")
        self.assertEqual(["c2", "c3", "c4"], list(missing))


class VerificationPredicateIsAggregateTests(unittest.TestCase):
    """LAYER 2 - the cause, read from the real file.

    A behavioural test cannot tell "refuses partial" from "has no
    verification at all", so the predicate itself is asserted here.
    """

    def test_cookie_verification_is_not_an_at_least_one_predicate(self):
        """`any()` was the blind spot: "did AT LEAST ONE cookie survive?".

        Asserted as a forbidden shape rather than a required one: `all(...)`,
        a set difference and a missing-list comprehension are all correct, so
        pinning any single spelling would break on a legitimate refactor. What
        must never come back is the at-least-one reading, because that is what
        let a 2/5 sync report success.
        """
        import ast

        offenders = []
        for node in ast.walk(ast.parse(SOURCE)):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "any":
                continue
            for arg in node.args:
                src = ast.unparse(arg)
                if ("name" in src) and ("names" in src or "converted" in src):
                    offenders.append((node.lineno, src))

        self.assertEqual(
            [], offenders,
            "cookie verification regressed to an at-least-one predicate; "
            "a sync that lost cookies would be reported as a success: %s"
            % offenders)

    def test_the_cookies_that_did_not_arrive_are_computed_by_name(self):
        """The gap must be a list of NAMES, never a bare ratio.

        A ratio alone is what produced the "same mystery number on every
        sync" complaint: the caller could not act on `2/5`. This is the cookie
        twin of `_LAST_STORAGE_MISSING`.
        """
        import ast

        assignments = []
        for node in ast.walk(ast.parse(SOURCE)):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name)
                       and t.id == "_LAST_COOKIE_MISSING"
                       for t in node.targets):
                continue
            assignments.append(ast.unparse(node.value))

        by_name = [src for src in assignments
                   if "name" in src and "not in" in src]
        self.assertTrue(
            by_name,
            "relay/server.py never derives _LAST_COOKIE_MISSING from the "
            "expected names; assignments found: %s" % (assignments,))


if __name__ == "__main__":
    unittest.main()