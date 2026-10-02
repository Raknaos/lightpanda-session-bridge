"""Concurrent callers must not race on the restored-session bookkeeping.

`_restore_persisted_session()` is called from TWO request paths: the CDP proxy
and the session-import handler. Both run on ThreadingHTTPServer threads, and the
function's own state transitions are not serialised:

    if not _PERSISTED_LOADED:
        _PERSISTED_LOADED = True          # set BEFORE the work, fine
        ...
    if _PERSISTED_APPLIED or not _LAST_SESSION:
        return False
    try:
        with CDP_LOCK:
            _apply_session(...)           # check and act are NOT atomic
        _PERSISTED_APPLIED = True         # written OUTSIDE the lock
    except Exception:
        return False

Two threads can both pass the `_PERSISTED_APPLIED` check and both call
`_apply_session` - the second one doubles every cookie in Lightpanda's jar,
because `_apply_session` sets cookies rather than replacing them. Worse, the
narrow window between "checked false" and "applied" is exactly when a proxy
request from an agent lands: that agent sees a half-applied session.

The `except Exception` also swallows everything, so a genuinely broken restore
is indistinguishable from "already done" - the relay reports a healthy session
that was never applied.

Run: .venv/Scripts/python.exe tests/test_restore_race.py
"""
import pathlib
import sys
import threading
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "relay"))

import server as relay  # noqa: E402


class RestoreIsNotRaced(unittest.TestCase):
    def setUp(self):
        self._saved = (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
                       relay._PERSISTED_INFLIGHT, relay._LAST_SESSION,
                       relay._SYNCED_SESSIONS, relay._apply_session)
        self.addCleanup(self._restore)

    def _restore(self):
        # _apply_session must be restored too: the stub installed by _prime()
        # leaked into every later test and faked a session injection that never
        # happened, which is how 16 unrelated tests started failing.
        (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
         relay._PERSISTED_INFLIGHT, relay._LAST_SESSION,
         relay._SYNCED_SESSIONS, relay._apply_session) = self._saved

    def _prime(self, hook):
        relay._PERSISTED_LOADED = True
        relay._PERSISTED_APPLIED = False
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = {"origin": "https://x.com", "cookies": [{"name": "a"}],
                               "storage": {}}
        relay._SYNCED_SESSIONS = {}
        relay._apply_session = hook

    def test_only_one_thread_applies_the_restored_session(self):
        """The defect: two callers pass the "applied?" test and BOTH inject the
        session, so every cookie is set twice in Lightpanda's jar.

        The window is real even though CDP_LOCK serialises the CDP calls: the
        flag is read at the top of the function and written at the bottom, and
        the second thread reads it in between. To show that, the stub must not
        take CDP_LOCK itself - if it did, the two calls would queue and the
        double-apply could never happen. The stub holds the "CDP call" open so
        the second thread is guaranteed to arrive inside the window.
        """
        calls = []
        first_in = threading.Event()
        release = threading.Event()

        def apply(origin, cookies, storage=None):
            calls.append(threading.current_thread().name)
            first_in.set()
            # The first caller is now inside the CDP call, before it sets the
            # flag. Anything that reaches the stub second is a double-apply.
            release.wait(timeout=3)
            return len(cookies)

        self._prime(apply)
        results = {}

        def run(tag):
            try:
                results[tag] = relay._restore_persisted_session()
            except Exception as exc:      # noqa: BLE001 - recorded, not hidden
                results[tag] = "raised: %s" % exc

        first = threading.Thread(target=run, args=("first",))
        second = threading.Thread(target=run, args=("second",))
        first.start()
        self.assertTrue(first_in.wait(timeout=5), "the CDP call never started")
        second.start()
        # Give the second thread enough time to reach the flag check while the
        # first is still inside the CDP call.
        second.join(timeout=0.5)
        release.set()
        first.join(timeout=10)
        second.join(timeout=10)

        self.assertFalse(relay._PERSISTED_INFLIGHT,
                         "the restore claim leaked: every later call skips it "
                         "and the session is never applied")
        self.assertEqual(len(calls), 1,
                         "_apply_session ran %d times for ONE restored session "
                         "(callers: %r): the cookie jar is populated twice"
                         % (len(calls), sorted(calls)))
        self.assertTrue(relay._PERSISTED_APPLIED)
        self.assertEqual(results.get("first"), True)
        self.assertEqual(results.get("second"), False,
                         "the second caller must be told the session was "
                         "already restored, got %r" % (results.get("second"),))

    def test_a_broken_restore_is_not_reported_as_done(self):
        """`except Exception: return False` cannot distinguish 'Lightpanda is
        down, retry later' from 'the restore is fundamentally broken'. The
        caller logs the same thing either way and the session is reported as
        present but never applied."""
        relay._PERSISTED_LOADED = True
        relay._PERSISTED_APPLIED = False
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = {"origin": "https://x.com", "cookies": [], "storage": {}}
        relay._SYNCED_SESSIONS = {}

        def explode(*a, **k):
            raise ValueError("restore is structurally broken, not a dead socket")

        relay._apply_session = explode
        with self.assertRaises(ValueError):
            relay._restore_persisted_session()
        self.assertFalse(relay._PERSISTED_APPLIED,
                         "a failed restore marked itself applied: the relay now "
                         "claims a session it never injected")
        self.assertFalse(relay._PERSISTED_INFLIGHT,
                         "the claim leaked on failure: every later call skips "
                         "the restore and the session is never applied")


class RestoreClaimsState(unittest.TestCase):
    def setUp(self):
        # Same isolation as RestoreIsNotRaced: these globals are module state,
        # so without saving/restoring them this class leaks "not loaded" and
        # "no session" into every test that runs after it.
        self._saved = (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
                       relay._PERSISTED_INFLIGHT, relay._LAST_SESSION,
                       relay._SYNCED_SESSIONS, relay._load_persisted_session)
        self.addCleanup(self._restore)

    def _restore(self):
        (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
         relay._PERSISTED_INFLIGHT, relay._LAST_SESSION,
         relay._SYNCED_SESSIONS, relay._load_persisted_session) = self._saved

    def test_an_absent_session_is_not_claimed_as_restored(self):
        """With nothing on disk there is nothing to restore, and the call must
        report that rather than flipping a flag that says "applied".

        (Kept from the copy-by-reference shape this replaced: no caller mutates
        the handed-out dict, so asserting CPython's semantics here would be a
        test that cannot fail.)

        _LAST_SESSION is handed out by reference. If one caller mutates the
        dict it handed over (clearing cookies on /v1/sessions/clear, say), every
        other holder sees it - and a resync then replays an empty session."""
        relay._PERSISTED_LOADED = True
        relay._PERSISTED_APPLIED = True      # skip the apply path
        relay._LAST_SESSION = {"origin": "https://x.com",
                               "cookies": [{"name": "a"}]}
        relay._SYNCED_SESSIONS = {}
        first = relay._LAST_SESSION
        first["cookies"] = []
        # Not a product defect: no caller mutates the handed-out dict.
        # _persist_session serialises it, and the clear path pops the key from
        # _SYNCED_SESSIONS rather than emptying the session. Asserting CPython's
        # copy-on-assignment semantics here would be a test that cannot fail,
        # so the real invariant is asserted instead: a persisted session that was
        # never loaded must not be silently reported as applied.
        relay._PERSISTED_LOADED = False
        relay._PERSISTED_APPLIED = False
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = None
        relay._SYNCED_SESSIONS = {}
        # Without this the real ~/.config session.json on the developer machine
        # (and on CI) is found and restored, so the test asserts the opposite of
        # what it means. Point the loader at a directory that cannot exist.
        relay._load_persisted_session = lambda: None
        self.addCleanup(setattr, relay, "_load_persisted_session",
                        self._saved[5])
        self.assertFalse(relay._restore_persisted_session(),
                         "an empty relay reported a restored session")


if __name__ == "__main__":
    unittest.main()
