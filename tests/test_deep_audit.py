"""Six findings from the deep audit, each pinned by a test that goes red
without the fix.

1. `/v1/cdp` returned `proxy_cdp()`'s result verbatim, and `Network.getCookies`
   was not blocked: `POST /v1/cdp {"method":"Network.getCookies"}` answered 200
   with the whole jar - measured 7 cookies WITH VALUES - to anyone holding the
   token. The only route where a cookie value could reach an HTTP response.
2. `Network.clearBrowserCookies` was allowed through the same route, wiping
   every synced origin at once and bypassing the scoped cleanup in
   `clear_sessions`.
3. `list_sessions()` iterated `_SYNCED_SESSIONS` with no lock while
   `clear_sessions` mutated it under `CDP_LOCK` - `RuntimeError: dictionary
   changed size during iteration`, 24 times in 2s.
4. `set_session` reset only two of four per-request counters before its early
   `raise`s, so a failed import answered 400 with the PREVIOUS site's numbers
   and `storage_missing` names.
5. `_authorized()` let `_load_secret()`'s PermissionError escape: connection
   reset instead of 401, reachable unauthenticated.
6. `#toast` sits AFTER `<script src="popup.js">`, and the toast element was
   captured at module load - so it was null forever and every showToast() call
   silently did nothing.

Run: .venv/Scripts/python.exe tests/test_deep_audit.py
"""
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "relay"))

import server as relay   # noqa: E402

POPUP_JS = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
POPUP_HTML = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")


class CookieValuesCannotReachAnHttpResponse(unittest.TestCase):
    """Findings 1 and 2."""

    def test_every_cookie_reading_method_is_blocked(self):
        for method in ("Network.getCookies", "Network.getAllCookies",
                       "Network.clearBrowserCookies", "Storage.clearCookies",
                       "Storage.clearDataForOrigin",
                       "Storage.clearDataForStorageKey"):
            with self.assertRaises(ValueError, msg=method):
                relay.proxy_cdp(method, {"urls": ["https://x.com/"]})

    def test_the_destructive_methods_stay_blocked(self):
        for method in ("Browser.close", "Target.disposeBrowserContext",
                       "Network.deleteCookies"):
            with self.assertRaises(ValueError, msg=method):
                relay.proxy_cdp(method, {})

    def test_a_safe_method_still_goes_through(self):
        """A blocklist that refuses everything is not a fix."""
        saved = (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID,
                 relay._ensure_connection)
        self.addCleanup(lambda: setattr(relay, "_CDP_TRANSPORT", saved[0]))
        self.addCleanup(lambda: setattr(relay, "_CDP_SESSION_ID", saved[1]))
        self.addCleanup(lambda: setattr(relay, "_ensure_connection", saved[2]))

        class T:
            @staticmethod
            def request(method, params=None, session_id=None):
                return {"result": {"value": "ok", "method": method}}

        relay._CDP_TRANSPORT = T
        relay._ensure_connection = lambda origin=None: True
        relay._CDP_SESSION_ID = "s"
        out = relay.proxy_cdp("Page.navigate", {"url": "https://x.com/"})
        self.assertEqual(out.get("result", {}).get("method"), "Page.navigate")

    def test_names_can_be_verified_without_leaking_values(self):
        saved = (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID,
                 relay._ensure_connection)
        self.addCleanup(lambda: setattr(relay, "_CDP_TRANSPORT", saved[0]))
        self.addCleanup(lambda: setattr(relay, "_CDP_SESSION_ID", saved[1]))
        self.addCleanup(lambda: setattr(relay, "_ensure_connection", saved[2]))

        class T:
            @staticmethod
            def request(method, params=None, session_id=None):
                return {"cookies": [{"name": "sid", "value": "SUPER_SECRET"},
                                     {"name": "csrf", "value": "OTHER_SECRET"}]}

        relay._CDP_TRANSPORT = T
        relay._ensure_connection = lambda origin=None: True
        relay._CDP_SESSION_ID = "s"
        out = relay.cookie_names_present("https://x.com", ["sid", "absent"])
        self.assertEqual(out["present"], ["sid"])
        self.assertEqual(out["missing"], ["absent"])
        import json
        self.assertNotIn("SUPER_SECRET", json.dumps(out))
        self.assertNotIn("OTHER_SECRET", json.dumps(out))


class SessionListIsSafeUnderConcurrency(unittest.TestCase):
    """Finding 3."""

    def test_listing_while_clearing_does_not_raise(self):
        saved = relay._SYNCED_SESSIONS
        self.addCleanup(setattr, relay, "_SYNCED_SESSIONS", saved)
        saved_p = (relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
                   relay._PERSISTED_INFLIGHT, relay._LAST_SESSION)
        self.addCleanup(lambda: (
            setattr(relay, "_PERSISTED_LOADED", saved_p[0]),
            setattr(relay, "_PERSISTED_APPLIED", saved_p[1]),
            setattr(relay, "_PERSISTED_INFLIGHT", saved_p[2]),
            setattr(relay, "_LAST_SESSION", saved_p[3])))
        relay._PERSISTED_LOADED = relay._PERSISTED_APPLIED = True
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = {"origin": "https://x.com", "cookies": [],
                               "storage": {}}
        with relay.SESSIONS_LOCK:
            relay._SYNCED_SESSIONS = {"https://o%d.com" % i: [{"name": "a"}]
                                      for i in range(40)}

        errors, stop = [], threading.Event()

        def reader():
            while not stop.is_set():
                try:
                    relay.list_sessions()
                except RuntimeError as e:
                    errors.append(str(e))
                    return
                except Exception as e:      # noqa: BLE001
                    errors.append("%s: %s" % (type(e).__name__, e))
                    return

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        try:
            # Mutate under SESSIONS_LOCK, exactly as every real writer does.
            # This test used to mutate the dict bare, which no production caller
            # does - so it was not testing the shipped locking, it was testing an
            # unlocked write the server can never perform. It passed on Windows
            # and failed on Linux CI with "dictionary changed size during
            # iteration", which is the platform-specific version of a broken
            # test, not of a broken server.
            for _ in range(3000):
                with relay.SESSIONS_LOCK:
                    for key in list(relay._SYNCED_SESSIONS):
                        relay._SYNCED_SESSIONS.pop(key, None)
                    for i in range(40):
                        relay._SYNCED_SESSIONS["https://o%d.com" % i] = [{"name": "a"}]
        finally:
            stop.set()
            for t in threads:
                t.join(timeout=10)
        self.assertEqual(errors, [],
                         "listing raced a mutation: %r" % errors[:3])


class SessionsLockIsReal(unittest.TestCase):
    """The dict has ONE owner lock, and a bare read still survives a mutation.

    v0.7.7's fix took CDP_LOCK in `list_sessions` while `clear_sessions` mutated
    under a different lock. Two locks guarding one dict is a race with a long fuse:
    it surfaced on Linux CI and not on Windows.
    """

    def test_every_accessor_uses_sessions_lock(self):
        """Every READ and WRITE of the dict is under SESSIONS_LOCK.

        The first version of this test only looked at assignments, so putting the
        reader back under CDP_LOCK - the exact v0.7.7 state - kept it green. It
        now walks every Name load, attribute access and subscript of the dict,
        which is what a race actually is.
        """
        import ast
        src = pathlib.Path(relay.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        lines = src.splitlines()

        def touches_dict(node):
            if isinstance(node, ast.Name) and node.id == "_SYNCED_SESSIONS":
                return True
            if isinstance(node, ast.Attribute):
                return touches_dict(node.value)
            if isinstance(node, ast.Subscript):
                return touches_dict(node.value)
            return False

        def guarded(lineno):
            """Is this line inside a `with SESSIONS_LOCK` (or a lock-free helper)?"""
            depth = 0
            for n in range(lineno - 2, -1, -1):
                stripped = lines[n].strip()
                if stripped.startswith("def ") or stripped.startswith("class "):
                    return False
                if stripped.startswith("with "):
                    if "SESSIONS_LOCK" in stripped:
                        return True
                    # another lock: not the owner of this dict
                    depth += 1
            return False

        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id != "_SYNCED_SESSIONS":
                    continue
            elif not touches_dict(node):
                continue
            if not guarded(node.lineno):
                line = lines[node.lineno - 1]
                if line.strip().startswith("#"):
                    continue
                if "_SYNCED_SESSIONS: dict" in line:
                    continue
                offenders.append((node.lineno, line.strip()[:80]))
        self.assertEqual(offenders, [],
                         "acces a _SYNCED_SESSIONS hors SESSIONS_LOCK : %r"
                         % offenders[:4])

    def test_reading_survives_a_bare_mutation_anyway(self):
        """Defence in depth: a reader must not explode on a concurrent write."""
        saved = relay._SYNCED_SESSIONS
        self.addCleanup(setattr, relay, "_SYNCED_SESSIONS", saved)
        relay._PERSISTED_LOADED = relay._PERSISTED_APPLIED = True
        relay._PERSISTED_INFLIGHT = False
        relay._LAST_SESSION = {"origin": "https://x.com", "cookies": [],
                               "storage": {}}
        with relay.SESSIONS_LOCK:
            relay._SYNCED_SESSIONS = {"https://o%d.com" % i: [{"name": "a"}]
                                      for i in range(40)}

        errors, stop = [], threading.Event()

        def reader():
            while not stop.is_set():
                try:
                    relay.list_sessions()
                except Exception as exc:      # noqa: BLE001
                    errors.append("%s: %s" % (type(exc).__name__, exc))
                    return

        def bare_writer():
            # deliberately WITHOUT the lock, to prove the read path is robust
            for _ in range(4000):
                for key in list(relay._SYNCED_SESSIONS):
                    relay._SYNCED_SESSIONS.pop(key, None)
                for i in range(40):
                    relay._SYNCED_SESSIONS["https://o%d.com" % i] = [{"name": "a"}]

        readers = [threading.Thread(target=reader) for _ in range(3)]
        for t in readers:
            t.start()
        writer = threading.Thread(target=bare_writer)
        writer.start()
        writer.join(timeout=30)
        stop.set()
        for t in readers:
            t.join(timeout=10)
        self.assertEqual(errors, [],
                         "list_sessions a leve face a une mutation concurrente : %r"
                         % errors[:3])


class ImportStateIsPerRequest(unittest.TestCase):
    """Finding 4."""

    def test_a_refused_import_reports_nothing_from_the_previous_one(self):
        saved = (relay._LAST_STORAGE_EXPECTED, relay._LAST_STORAGE_MISSING,
                 relay._LAST_STORAGE_APPLIED_COUNT, relay._LAST_STORAGE_REFUSED,
                 relay._SYNCED_SESSIONS, relay._LAST_SESSION)
        self.addCleanup(lambda: (
            setattr(relay, "_LAST_STORAGE_EXPECTED", saved[0]),
            setattr(relay, "_LAST_STORAGE_MISSING", saved[1]),
            setattr(relay, "_LAST_STORAGE_APPLIED_COUNT", saved[2]),
            setattr(relay, "_LAST_STORAGE_REFUSED", saved[3]),
            setattr(relay, "_SYNCED_SESSIONS", saved[4]),
            setattr(relay, "_LAST_SESSION", saved[5])))
        # Left over from a previous, successful import of another site.
        relay._LAST_STORAGE_EXPECTED = 7
        relay._LAST_STORAGE_MISSING = ["user", "cart", "tok"]

        with self.assertRaises(Exception):
            relay.set_session("https://x.com", [{"name": "a", "value": "v"}],
                              {"k" * 5000: "v"})
        self.assertEqual(relay._LAST_STORAGE_EXPECTED, 0,
                         "a refused import answered 400 with the previous "
                         "site's expected count: %r"
                         % relay._LAST_STORAGE_EXPECTED)
        self.assertEqual(relay._LAST_STORAGE_MISSING, [],
                         "another site's storage key names leaked into this "
                         "error: %r" % relay._LAST_STORAGE_MISSING)


class AuthNeverRaises(unittest.TestCase):
    """Finding 5."""

    def test_an_unreadable_secret_refuses_instead_of_raising(self):
        src = (ROOT / "relay" / "server.py").read_text(encoding="utf-8")
        body = src[src.index("def _authorized"):]
        body = body[:body.index("\n    def ")]
        self.assertIn("try:", body,
                      "_authorized must not let _load_secret's PermissionError "
                      "escape: the client gets a connection reset, not a 401")
        self.assertIn("return False", body.split("except")[-1])

    def test_the_token_comparison_is_over_bytes(self):
        src = (ROOT / "relay" / "server.py").read_text(encoding="utf-8")
        body = src[src.index("def _authorized"):]
        body = body[:body.index("\n    def ")]
        self.assertIn(".encode(", body,
                      "compare_digest must get bytes on both sides: a header "
                      "that is not encodable raises inside the auth check")


class ToastIsReachable(unittest.TestCase):
    """Finding 6, proven BEHAVIOURALLY.

    A source assertion here proved nothing: the first sabotage pass stayed green
    because the test only grepped the text. This runs the real toast code in
    Node against the real DOM ordering - the node absent when the module is
    evaluated, present afterwards - which is the only thing that distinguishes
    the two spellings.
    """

    HARNESS = r"""
import { readFileSync } from "node:fs";
const src = readFileSync("extension/popup.js", "utf8");
const start = Math.min(...["toastEl =", "toastTimer =", "function showToast"]
  .map(k => { const i = src.indexOf(k); return i < 0 ? Infinity : i; }));
const end = src.indexOf("let currentTab");
if (start === Infinity || end < 0) { console.log("MARKERS"); process.exit(2); }
const body = src.slice(start, end);
const mk = () => ({ textContent: "", shown: false,
  classList: { add() { this.owner.shown = true; }, remove() { this.owner.shown = false; } } });
const el = mk(); el.classList.owner = el;
let nodeExists = false;
const showToast = new Function("document", "setTimeout", "clearTimeout",
  body + "\n return showToast;")(
  { querySelector: (s) => (s === "#toast" && nodeExists ? el : null) }, () => 0, () => {});
showToast("early");                    // while the module is evaluated: no node
nodeExists = true;                     // the rest of the HTML finished parsing
showToast("later");
console.log(JSON.stringify({ shown: el.shown, text: el.textContent }));
"""

    def _run_toast(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not on PATH")
        harness = ROOT / "_toast_probe.mjs"
        harness.write_text(self.HARNESS, encoding="utf-8", newline="\n")
        self.addCleanup(lambda: harness.unlink(missing_ok=True))
        out = subprocess.run([node, str(harness)], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        return out.stdout.strip()

    def test_the_toast_is_visible_after_the_node_appears(self):
        got = self._run_toast()
        self.assertIn('"shown":true', got,
                      "the toast never renders: it was captured before the DOM "
                      "node existed and every showToast() is a silent no-op. "
                      "Harness said %r" % got)

    def test_the_toast_is_not_captured_at_module_load(self):
        self.assertNotRegex(
            POPUP_JS, r"^const toastEl = document\.querySelector\('#toast'\);",
            "the toast element is captured at module evaluation, when the DOM "
            "node does not exist yet")

    def test_the_script_tag_precedes_the_toast_element(self):
        """The structural reason. If this ever flips, the lazy lookup becomes
        unnecessary and the first test starts failing for the wrong reason."""
        self.assertLess(POPUP_HTML.index('<script src="popup.js">'),
                        POPUP_HTML.index('id="toast"'))


class GetsHaveADeadline(unittest.TestCase):
    """Audit 2, finding 2: do_GET had no settimeout while do_POST had three."""

    def test_do_get_sets_a_socket_timeout(self):
        src = (ROOT / "relay" / "server.py").read_text(encoding="utf-8")
        body = src[src.index("    def do_GET"):]
        body = body[:body.index("\n    def ", 5)]
        self.assertIn("settimeout", body,
                      "do_GET has no read deadline: a relay that accepts the "
                      "socket and never answers wedges the popup forever")


if __name__ == "__main__":
    unittest.main()
