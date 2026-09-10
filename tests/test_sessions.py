import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'relay'))
import server


class _FakeTransport:
    """Records every CDP call (content AND order) and simulates a page context
    whose localStorage is wiped by each navigation, like Lightpanda's."""
    def __init__(self):
        self.cookies = []
        self.calls = []
        self.scripts = []
        self.storage_writes = 0
        self.storage_count = 0    # cles presentes dans la page simulee
        self.missing_keys = 0     # >0 = ecriture partielle (le bug a6api)

    def methods(self):
        return [m for m, _ in self.calls]

    def request(self, method, params=None, session_id=None):
        params = params or {}
        self.calls.append((method, params))
        if method == "Page.navigate":
            self.storage_writes = 0   # a real navigation drops the page state
            return {"ok": True, "result": {}}
        if method == "Page.addScriptToEvaluateOnNewDocument":
            self.scripts.append(params.get("source", ""))
            return {"ok": True, "result": {"identifier": "1"}}
        if method == "Network.setCookies":
            self.cookies = list(params.get("cookies", []))
            return {"ok": True, "result": {}}
        if method == "Network.getCookies":
            urls = params.get("urls") or []
            if urls:
                hosts = [u.split("//", 1)[-1].rstrip("/") for u in urls]
                matched = [c for c in self.cookies
                           if any(c.get("domain", "").lstrip(".") in h or h.endswith(c.get("domain", "").lstrip("."))
                                  for h in hosts)]
                return {"cookies": matched}
            return {"cookies": list(self.cookies)}
        if method == "Runtime.evaluate":
            expr = params.get("expression", "")
            # Verification par cle (celle du correctif) : le nombre de cles
            # encore absentes de la page.
            if "localStorage.getItem" in expr:
                return {"result": {"value": self.missing_keys}}
            if "localStorage.setItem" in expr:
                self.storage_writes += 1
                try:
                    body = expr.split("const data = ", 1)[1].split("; for (const k", 1)[0]
                    self.storage_count = len(json.loads(body))
                except Exception:
                    self.storage_count = 1
                return {"result": {"value": self.storage_count}}
            if "Object.keys(localStorage).length" in expr:
                return {"result": {"value": max(1, self.storage_writes)}}
            return {"result": {"value": 0}}
        return {"ok": True, "result": {}}

class SessionManagerTests(unittest.TestCase):
    """Tests for /v1/sessions (list) and /v1/sessions/clear (remove)."""

    def setUp(self):
        # Isolate from the real ~/.config/lightpanda-bridge: a test must never
        # write the user's actual session state.
        self._tmp = tempfile.mkdtemp(prefix="lp-bridge-test-")
        self._env = os.environ.get("LP_BRIDGE_CONFIG_DIR")
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self._tmp
        self._settle = server._NAV_SETTLE_SECONDS
        server._NAV_SETTLE_SECONDS = 0
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False
        # Mock the CDP transport so set_session only exercises memory bookkeeping
        self._fake = _FakeTransport()
        self._orig_transport = getattr(server, "_CDP_TRANSPORT", None)
        self._orig_session_id = getattr(server, "_CDP_SESSION_ID", None)
        server._CDP_TRANSPORT = self._fake
        server._CDP_SESSION_ID = "fake-session"
        # Reset global strict default if a previous test flipped it
        if hasattr(server, "_DEFAULT_STRICT_HOST_COOKIES"):
            server._DEFAULT_STRICT_HOST_COOKIES = False

    def tearDown(self):
        server._NAV_SETTLE_SECONDS = self._settle
        if self._env is None:
            os.environ.pop("LP_BRIDGE_CONFIG_DIR", None)
        else:
            os.environ["LP_BRIDGE_CONFIG_DIR"] = self._env
        shutil.rmtree(self._tmp, ignore_errors=True)
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False
        if self._orig_transport is not None:
            server._CDP_TRANSPORT = self._orig_transport
        if self._orig_session_id is not None:
            server._CDP_SESSION_ID = self._orig_session_id

    # ---------- list_sessions ----------

    def test_list_sessions_empty(self):
        self.assertEqual(server.list_sessions(), [])

    def test_list_sessions_sanitized_no_cookie_values(self):
        server._SYNCED_SESSIONS["https://dev.to"] = [
            {"name": "session", "value": "SECRET", "domain": ".dev.to"},
            {"name": "uid", "value": "TOP-SECRET", "domain": ".dev.to"},
        ]
        out = server.list_sessions()
        self.assertEqual(len(out), 1)
        entry = out[0]
        self.assertEqual(entry["host"], "dev.to")
        self.assertEqual(entry["cookie_count"], 2)
        raw = json.dumps(out)
        self.assertNotIn("SECRET", raw)
        self.assertNotIn("value", raw)

    def test_list_sessions_expiry_metadata(self):
        import time as _time
        soon = _time.time() + 3600
        server._SYNCED_SESSIONS["https://a.com"] = [
            {"name": "x", "domain": "a.com", "expires": soon}
        ]
        out = server.list_sessions()
        self.assertEqual(out[0]["host"], "a.com")
        self.assertFalse(out[0]["expired"])
        self.assertAlmostEqual(out[0]["expires"], soon, delta=2)

    def test_list_sessions_expired_flag(self):
        server._SYNCED_SESSIONS["https://b.com"] = [
            {"name": "x", "domain": "b.com", "expires": 100.0}
        ]
        out = server.list_sessions()
        self.assertTrue(out[0]["expired"])
        self.assertEqual(out[0]["expires"], 100.0)

    # ---------- set_session bookkeeping ----------

    def test_set_session_records_synced(self):
        ok = server.set_session("https://dev.to", [
            {"name": "s", "value": "v", "domain": ".dev.to", "httpOnly": True, "secure": True}
        ])
        # set_session returns success bool; memory bookkeeping is what we assert
        self.assertIn("https://dev.to", server._SYNCED_SESSIONS)
        self.assertEqual(len(server._SYNCED_SESSIONS["https://dev.to"]), 1)
        self.assertIsNotNone(server._LAST_SESSION)

    def test_clear_origin_removes_memory(self):
        server.set_session("https://dev.to", [
            {"name": "s", "value": "v", "domain": ".dev.to"}
        ])
        server.set_session("https://example.com", [
            {"name": "g", "value": "v", "domain": ".example.com"}
        ])
        removed = server.clear_sessions("https://dev.to")
        self.assertGreaterEqual(removed, 1)
        self.assertNotIn("https://dev.to", server._SYNCED_SESSIONS)
        self.assertIn("https://example.com", server._SYNCED_SESSIONS)
        self.assertEqual(server.clear_sessions("https://nope.invalid"), 0)

    def test_clear_all_memory(self):
        for origin in ("https://example.com", "https://dev.to", "https://x.com"):
            server.set_session(origin, [{"name": "n", "value": "v", "domain": origin.split("//")[1]}])
        n = server.clear_sessions(None)  # None = all
        self.assertGreaterEqual(n, 3)
        self.assertEqual(server._SYNCED_SESSIONS, {})


class SameSiteNormalizationTests(unittest.TestCase):
    """cookie_for_cdp must map Chrome/CDF values onto Lightpanda's accepted casing."""

    def test_case_mapping(self):
        f = server.cookie_for_cdp
        c = lambda ss: f({"name": "n", "value": "v", "domain": "d.com", "sameSite": ss}, "https://d.com")
        self.assertEqual(c("lax")["sameSite"], "Lax")
        self.assertEqual(c("LAX")["sameSite"], "Lax")
        self.assertEqual(c("strict")["sameSite"], "Strict")
        self.assertEqual(c("no_restriction")["sameSite"], "None")
        self.assertEqual(c("none")["sameSite"], "None")

    def test_expires_dropped(self):
        # Lightpanda silently rejects cookies carrying `expires`
        out = server.cookie_for_cdp(
            {"name": "n", "value": "v", "domain": "d.com", "expires": "1790000000"},
            "https://d.com")
        self.assertNotIn("expires", out)

    def test_wildcard_default_allowed(self):
        out = server.cookie_for_cdp(
            {"name": "n", "value": "v", "domain": ".example.com"},
            "https://app.example.com")
        self.assertEqual(out["domain"], ".example.com")

    def test_parent_wildcard_cookie_allowed_by_default(self):
        # Idée 3 de la PR refusée: pas de strict host-only par défaut —
        # les cookies parent-domain (".example.com" pour app.example.com)
        # sont essentiels aux vraies sessions.
        out = server.cookie_for_cdp(
            {"name": "n", "value": "v", "domain": ".example.com"},
            "https://app.example.com")
        self.assertEqual(out["domain"], ".example.com")


class PersistenceTests(unittest.TestCase):
    """A relay restart / reboot / watchdog restart must NOT lose the session.

    This is the bug users reported: the popup said "Relais en ligne" and
    "Aucun cookie trouve pour cette page" while the session was actually gone
    from the relay's memory, so every later call ran unauthenticated."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="lp-bridge-test-")
        self._env = os.environ.get("LP_BRIDGE_CONFIG_DIR")
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self._tmp
        self._settle = server._NAV_SETTLE_SECONDS
        server._NAV_SETTLE_SECONDS = 0
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False
        self._fake = _FakeTransport()
        server._CDP_TRANSPORT = self._fake
        server._CDP_SESSION_ID = "fake-session"

    def tearDown(self):
        server._NAV_SETTLE_SECONDS = self._settle
        if self._env is None:
            os.environ.pop("LP_BRIDGE_CONFIG_DIR", None)
        else:
            os.environ["LP_BRIDGE_CONFIG_DIR"] = self._env
        shutil.rmtree(self._tmp, ignore_errors=True)
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False

    def _sync(self):
        return server.set_session("https://a6api.com", [
            {"name": "session", "value": "v", "domain": ".a6api.com",
             "httpOnly": True, "secure": True}
        ], {"user": "42", "token": "t"})

    def _fake_restart(self):
        """Simulate a relay process restart: memory gone, disk kept."""
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False

    def test_set_session_persists_state(self):
        self._sync()
        state_path = Path(self._tmp) / "session.json"
        self.assertTrue(state_path.exists())
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["origin"], "https://a6api.com")
        self.assertEqual([c["name"] for c in saved["cookies"]], ["session"])
        self.assertEqual(saved["storage"]["user"], "42")

    def test_restart_restores_session(self):
        self._sync()
        self._fake_restart()
        self.assertEqual(server._SYNCED_SESSIONS, {})   # rien en memoire
        self.assertTrue(server._restore_persisted_session())
        self.assertEqual([s["origin"] for s in server.list_sessions()], ["https://a6api.com"])
        self.assertEqual(server._SYNCED_SESSIONS["https://a6api.com"][0]["name"], "session")

    def test_restart_replays_storage_and_durable_script(self):
        self._sync()
        self._fake_restart()
        self._fake.calls.clear()
        self._fake.scripts.clear()
        self.assertTrue(server._restore_persisted_session())
        self.assertIn("Network.setCookies", self._fake.methods())
        self.assertIn("Page.navigate", self._fake.methods())
        self.assertGreaterEqual(self._fake.storage_writes, 1)
        # durable: the snapshot is re-applied on every future document
        self.assertEqual(len(self._fake.scripts), 1)
        self.assertIn("localStorage.setItem", self._fake.scripts[0])
        self.assertIn("user", self._fake.scripts[0])

    def test_list_sessions_restores_without_agent_call(self):
        self._sync()
        self._fake_restart()
        self.assertEqual([s["host"] for s in server.list_sessions()], ["a6api.com"])

    def test_restore_is_idempotent(self):
        self._sync()
        self._fake_restart()
        self.assertTrue(server._restore_persisted_session())
        self.assertFalse(server._restore_persisted_session())

    def test_clear_all_erases_persisted_state(self):
        self._sync()
        state_path = Path(self._tmp) / "session.json"
        self.assertTrue(state_path.exists())
        server.clear_sessions(None)
        self.assertFalse(state_path.exists(), "clear doit aussi effacer le disque")
        server._PERSISTED_LOADED = False
        self.assertFalse(server._restore_persisted_session())

    def test_injection_order_navigate_before_storage(self):
        self._sync()
        methods = self._fake.methods()
        self.assertLess(methods.index("Network.setCookies"), methods.index("Page.navigate"))
        first_set = next(i for i, m in enumerate(methods) if m == "Runtime.evaluate")
        last_nav = len(methods) - 1 - methods[::-1].index("Page.navigate")
        self.assertLess(last_nav, first_set,
                        "naviguer APRES l'injection localStorage la efface")

    @unittest.skipIf(os.name == "nt", "permissions POSIX")
    def test_state_file_is_owner_only(self):
        self._sync()
        mode = stat.S_IMODE(os.stat(Path(self._tmp) / "session.json").st_mode)
        self.assertEqual(mode & 0o077, 0, f"session.json doit etre 0600, vu {oct(mode)}")


class CookieScopeTests(unittest.TestCase):
    """The reported bug: 'pas de cookie pour ce site alors qu'il y en a'."""

    def test_non_secure_cookie_survives_conversion(self):
        out = server.cookie_for_cdp(
            {"name": "n", "value": "v", "domain": ".a6api.com", "secure": False},
            "https://a6api.com")
        self.assertEqual(out["name"], "n")
        self.assertEqual(out["value"], "v")
        self.assertFalse(out.get("secure", False))

    def test_manifest_host_permissions_cover_http(self):
        # Sans http://*/* dans host_permissions, chrome.cookies masque les
        # cookies non-secure: le popup voyait zero cookie pour le site.
        manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("https://*/*", manifest["host_permissions"])
        self.assertIn("http://*/*", manifest["host_permissions"])
        self.assertIn("cookies", manifest["permissions"])


class PopupDiagnosisTests(unittest.TestCase):
    """Le popup ne doit plus annoncer 'aucun cookie' pour un probleme de scope."""

    def setUp(self):
        self.js = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")

    def test_popup_falls_back_to_domain_query(self):
        self.assertIn("getAll({ domain:", self.js)
        self.assertIn("errCookiesOutOfScope", self.js)

    def test_out_of_scope_message_translated_everywhere(self):
        # L'i18n du popup est inline (table I18N) : une clé utilisee mais non
        # traduite s'afficherait en anglais sur 9 langues sur 10.
        self.assertGreaterEqual(self.js.count("errCookiesOutOfScope:"), 10)
        self.assertNotIn('errCookiesOutOfScope: ""', self.js)


class StorageVerificationTests(unittest.TestCase):
    """Le dernier maillon de la chaine a6api.

    Mesure faite par l'autre session : 17 cles sur 29 arrivees dans Lightpanda,
    `user` parmi les perdues -> chaque appel authentifie repondait 407
    New-Api-User, alors que l'import annoncait un succes. C'est exactement ce
    qui donnait l'impression qu'« une session ne marche qu'apres un 2e Sync ».
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="lp-bridge-test-")
        self._env = os.environ.get("LP_BRIDGE_CONFIG_DIR")
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self._tmp
        self._settle = server._NAV_SETTLE_SECONDS
        server._NAV_SETTLE_SECONDS = 0
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False
        self._fake = _FakeTransport()
        server._CDP_TRANSPORT = self._fake
        server._CDP_SESSION_ID = "fake-session"

    def tearDown(self):
        server._NAV_SETTLE_SECONDS = self._settle
        if self._env is None:
            os.environ.pop("LP_BRIDGE_CONFIG_DIR", None)
        else:
            os.environ["LP_BRIDGE_CONFIG_DIR"] = self._env
        shutil.rmtree(self._tmp, ignore_errors=True)
        server._SYNCED_SESSIONS.clear()
        server._LAST_SESSION = None
        server._PERSISTED_LOADED = False
        server._PERSISTED_APPLIED = False

    def _sync(self):
        return server.set_session("https://a6api.com", [
            {"name": "session", "value": "v", "domain": ".a6api.com",
             "httpOnly": True, "secure": True}
        ], {"user": "42", "token": "t"})

    def test_complete_snapshot_returns_verified_count(self):
        cookies, storage = self._sync()
        self.assertEqual(cookies, 1)
        self.assertEqual(storage, 2)

    def test_partial_snapshot_is_a_loud_failure(self):
        self._fake.missing_keys = 1
        with self.assertRaises(RuntimeError) as ctx:
            self._sync()
        self.assertIn("incomplete", str(ctx.exception))

    def test_failure_names_the_ratio_not_just_a_generic_error(self):
        self._fake.missing_keys = 2
        with self.assertRaises(RuntimeError) as ctx:
            self._sync()
        self.assertIn("0/2", str(ctx.exception))
        # 4 tentatives d'ecriture ; le transport simule remet le compteur a 0
        # a chaque navigation (relance de la page entre deux tentatives).
        self.assertGreaterEqual(self._fake.storage_writes, 3)

    def test_partial_snapshot_still_persists_so_a_resync_can_finish(self):
        self._fake.missing_keys = 1
        with self.assertRaises(RuntimeError):
            self._sync()
        self.assertTrue((Path(self._tmp) / "session.json").exists())
        self.assertEqual(server.list_sessions()[0]["host"], "a6api.com")


class PopupStorageReportingTests(unittest.TestCase):
    """Le popup ne doit plus transformer un transfert partiel en succes."""

    def setUp(self):
        self.js = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")

    def test_success_message_reports_storage_keys(self):
        self.assertGreaterEqual(self.js.count("success: (count, keys)"), 10)

    def test_extraction_failure_and_partial_transfer_translated(self):
        self.assertGreaterEqual(self.js.count("errStorageExtract:"), 10)
        self.assertGreaterEqual(self.js.count("errPartialStorage:"), 10)
        self.assertNotIn("errStorageExtract: ''", self.js)

    def test_extraction_is_retried_and_its_error_is_not_swallowed(self):
        self.assertIn("for (let attempt = 0; attempt < 2; attempt++)", self.js)
        self.assertIn("if (storageError && !storage)", self.js)
        self.assertIn("result.storage_count < storageKeys", self.js)


if __name__ == "__main__":
    unittest.main()
