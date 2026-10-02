"""Two update/storage findings, pinned by tests that go red without the fix.

1. Every import registered another document-start restore script and nothing ever
   called `Page.removeScriptToEvaluateOnNewDocument`, so the scripts stacked for
   the lifetime of the CDP session (measured: 3 imports -> 3 live scripts), each
   re-writing the whole localStorage snapshot on every future page load. And
   "Tout retirer" deleted the cookies but left the script alive, so the storage
   came back on the next navigation.
2. `meta.json` is written by `_backup()` INTO the backup directory;
   `rollback_update()` mirrors that directory into the live extension, and
   `_mirror` exempted only `.build-info.json` - so a rollback deposited a stray
   config file in the shipped tree, which the next update's prune then deleted as
   "not in the source tree". The filename was also hard-coded twice instead of
   living next to `BUILD_INFO`.

Run: .venv/Scripts/python.exe tests/test_restore_and_mirror.py
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "relay"))

import server as relay   # noqa: E402
import updater           # noqa: E402


class _FakeCdp:
    """Records every CDP method and hands out a fresh script identifier."""

    def __init__(self):
        self.calls = []
        self.live_scripts = set()
        self._n = 0

    def request(self, method, params=None, session_id=None):
        self.calls.append((method, params or {}))
        if method == "Page.addScriptToEvaluateOnNewDocument":
            self._n += 1
            ident = "script-%d" % self._n
            self.live_scripts.add(ident)
            return {"identifier": ident}
        if method == "Page.removeScriptToEvaluateOnNewDocument":
            self.live_scripts.discard(params.get("identifier"))
            return {}
        if method == "Network.getCookies":
            return {"cookies": [{"name": "sid", "value": "v", "domain": "x.com"}]}
        return {}

    def methods(self):
        return [m for m, _ in self.calls]


class RestoreScriptsDoNotStack(unittest.TestCase):
    def setUp(self):
        self.cdp = _FakeCdp()
        saved = (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID,
                 relay._ensure_connection, relay._STORAGE_RESTORE_ID,
                 relay._SYNCED_SESSIONS, relay._LAST_SESSION,
                 relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
                 relay._PERSISTED_INFLIGHT)
        self._saved = saved
        self.addCleanup(self._restore)
        relay._CDP_TRANSPORT = self.cdp
        relay._ensure_connection = lambda origin=None: True
        relay._CDP_SESSION_ID = "s"
        relay._STORAGE_RESTORE_ID = ""
        relay._SYNCED_SESSIONS = {}
        relay._LAST_SESSION = None
        relay._PERSISTED_LOADED = relay._PERSISTED_APPLIED = True
        relay._PERSISTED_INFLIGHT = False

    def _restore(self):
        (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID, relay._ensure_connection,
         relay._STORAGE_RESTORE_ID, relay._SYNCED_SESSIONS, relay._LAST_SESSION,
         relay._PERSISTED_LOADED, relay._PERSISTED_APPLIED,
         relay._PERSISTED_INFLIGHT) = self._saved

    def _import_once(self):
        self.cdp.calls.clear()
        try:
            relay.set_session("https://x.com", [{"name": "sid", "value": "v"}],
                              {"k": "v"})
        except Exception:
            pass    # storage verification needs a page; irrelevant here

    def test_repeated_imports_leave_exactly_one_live_script(self):
        for _ in range(3):
            self._import_once()
        self.assertEqual(
            len(self.cdp.live_scripts), 1,
            "%d restore scripts are live on the same target: every one of them "
            "re-writes the whole snapshot on every page load. Live: %r"
            % (len(self.cdp.live_scripts), sorted(self.cdp.live_scripts)))

    def test_each_new_import_retires_the_previous_script(self):
        self._import_once()
        self._import_once()
        self.assertIn("Page.removeScriptToEvaluateOnNewDocument",
                      self.cdp.methods(),
                      "no script is ever retired: they accumulate for the "
                      "lifetime of the CDP connection")

    def test_clearing_sessions_retires_the_restore_script(self):
        """The half-wipe: "Tout retirer" removed the cookies by name but the
        document-start script put the whole localStorage back on the next load."""
        self._import_once()
        self.assertEqual(len(self.cdp.live_scripts), 1)
        relay._SYNCED_SESSIONS = {"https://x.com": [{"name": "sid", "value": "v"}]}
        saved_persist = relay._persist_session
        relay._persist_session = lambda state: None
        self.addCleanup(setattr, relay, "_persist_session", saved_persist)

        self.cdp.calls.clear()
        relay.clear_sessions()
        self.assertEqual(self.cdp.live_scripts, set(),
                         "clear left %r registered: the storage comes back on "
                         "the next navigation" % sorted(self.cdp.live_scripts))
        self.assertEqual(relay._STORAGE_RESTORE_ID, "",
                         "the identifier is still held, so a later import would "
                         "try to retire a script that is already gone")

    def test_the_identifier_is_module_state_not_a_local(self):
        """The bug this pins: the assignment had no `global`, so it wrote a
        local and every import started from an empty slot."""
        self._import_once()
        self.assertTrue(relay._STORAGE_RESTORE_ID,
                        "the module-level slot stayed empty: a new import has "
                        "no idea which script to retire")


class MirrorKeepsItsOwnBookkeeping(unittest.TestCase):
    def test_meta_json_is_named_by_a_constant_next_to_build_info(self):
        self.assertEqual(updater.BACKUP_META, "meta.json")
        src = (ROOT / "relay" / "updater.py").read_text(encoding="utf-8")
        self.assertIn(updater.BACKUP_META, updater.MIRROR_KEEP,
                      "the backup's own meta file is not exempted from the "
                      "prune, so the next update deletes it as unknown")
        self.assertIn(updater.BUILD_INFO, updater.MIRROR_KEEP)

    def test_meta_json_is_not_hard_coded_at_its_use_sites(self):
        src = (ROOT / "relay" / "updater.py").read_text(encoding="utf-8")
        # once for the constant, and nowhere else
        self.assertEqual(src.count('"meta.json"'), 1,
                         "the filename is spelled out again: rename one site "
                         "and the exemption silently stops matching")
        self.assertNotIn('os.path.join(backup_root, "meta.json")', src)

    def test_a_stray_file_survives_a_prune(self):
        """Behavioural: mirror a tree into a destination holding meta.json."""
        import shutil
        import tempfile
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, ignore_errors=True)
        self.addCleanup(shutil.rmtree, dst, ignore_errors=True)
        pathlib.Path(src, "manifest.json").write_text("{}", encoding="utf-8")
        pathlib.Path(dst, "meta.json").write_text("{}", encoding="utf-8")
        pathlib.Path(dst, "popup.js").write_text("//old", encoding="utf-8")

        updater._mirror(src, dst)
        self.assertTrue((pathlib.Path(dst) / "meta.json").exists(),
                        "the prune deleted the backup metadata: the relay "
                        "loses its rollback bookkeeping")
        self.assertFalse((pathlib.Path(dst) / "popup.js").exists(),
                         "a stale shipped file survived the prune")


if __name__ == "__main__":
    unittest.main()
