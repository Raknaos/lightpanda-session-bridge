# -*- coding: utf-8 -*-
"""Two more update-path findings, pinned by tests that go red without the fix.

1. `_backup` did `rmtree(backup_root)` BEFORE rebuilding it. A failure during
   the copy - ENOSPC, EPERM, or a file lock, which is the NORMAL case on Windows
   when Chrome holds popup.js open - left the install with no undo point at all,
   and the live tree had not been touched by anything. The old generation must
   survive until the new one is complete.

2. `apply_update`, `rollback_update` and `check_update` took no lock. The relay
   is a ThreadingHTTPServer and three callers reach this module concurrently: the
   popup, an agent holding the token, and `--apply-update`. One thread's
   rmtree could delete the directory another was mirroring from.

Both tests use the real functions against scratch dirs; no network, no live
install.
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "relay"))

import updater  # noqa: E402


class BackupSurvivesAFailedCopy(unittest.TestCase):
    """Finding 1: the undo point must outlive a failed backup."""

    def setUp(self):
        self.ext = tempfile.mkdtemp(prefix="lp-bk-ext-")
        self.config = tempfile.mkdtemp(prefix="lp-bk-cfg-")
        for name in ("manifest.json", "popup.js"):
            with open(os.path.join(self.ext, name), "w", encoding="utf-8") as fh:
                fh.write("{}" if name.endswith(".json") else "// gen1\n")
        self._env = {k: os.environ.get(k) for k in
                     ("LP_BRIDGE_EXTENSION_DIR", "LP_BRIDGE_CONFIG_DIR")}
        os.environ["LP_BRIDGE_EXTENSION_DIR"] = self.ext
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self.config
        self.addCleanup(self._restore)
        self.backup_root = os.path.join(self.config, updater.BACKUP_DIRNAME)

    def _restore(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.ext, ignore_errors=True)
        shutil.rmtree(self.config, ignore_errors=True)

    def _seed_previous_generation(self):
        os.makedirs(self.backup_root, exist_ok=True)
        shutil.copy2(os.path.join(self.ext, "popup.js"),
                     os.path.join(self.backup_root, "popup.js"))
        with open(os.path.join(self.backup_root, updater.BACKUP_META),
                  "w", encoding="utf-8") as fh:
            json.dump({"version": "0.7.5", "commit": "abc1234"}, fh)

    def test_failed_copy_leaves_the_previous_generation_intact(self):
        """The disk fills up mid-copy: generation 1 must still be there."""
        self._seed_previous_generation()

        real_copy2 = shutil.copy2

        def flaky(src, dst, *a, **k):
            raise OSError(28, "No space left on device")

        with unittest.mock.patch.object(updater.shutil, "copy2", flaky):
            with self.assertRaises(OSError):
                updater._backup(self.ext)

        self.assertTrue(os.path.isdir(self.backup_root),
                        "le point de retour a ete detruit par un echec de copie")
        meta_path = os.path.join(self.backup_root, updater.BACKUP_META)
        self.assertTrue(os.path.exists(meta_path), "meta.json generation 1 perdu")
        with open(meta_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["version"], "0.7.5")

    def test_failed_copy_leaves_no_staging_directory_behind(self):
        """A half-written staging dir would be mistaken for the next backup."""
        self._seed_previous_generation()
        with unittest.mock.patch.object(
                updater.shutil, "copy2",
                side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(OSError):
                updater._backup(self.ext)
        for leftover in (self.backup_root + ".new", self.backup_root + ".old"):
            self.assertFalse(os.path.isdir(leftover),
                             "residu de staging: %s" % leftover)

    def test_successful_backup_replaces_the_previous_generation(self):
        """The swap still happens - this is not 'never touch the old one'."""
        self._seed_previous_generation()
        with open(os.path.join(self.ext, "popup.js"), "w", encoding="utf-8") as fh:
            fh.write("// gen2\n")
        updater._backup(self.ext)
        with open(os.path.join(self.backup_root, "popup.js"), encoding="utf-8") as fh:
            self.assertIn("gen2", fh.read())
        for leftover in (self.backup_root + ".new", self.backup_root + ".old"):
            self.assertFalse(os.path.isdir(leftover))


class BackupRecordsWhatItCanRestore(unittest.TestCase):
    """Finding 3: the undo point's own bookkeeping was wrong.

    `_mirror` SKIPS BUILD_INFO by design (it belongs to the tree being replaced,
    not to the source), so the backup never carried `.build-info.json`: a
    rollback restored a tree whose provenance was blank. And `installed_info()`
    was re-read AFTER the mirror, so `meta.json` described the NEW install rather
    than the one the backup can restore.
    """

    def setUp(self):
        self.ext = tempfile.mkdtemp(prefix="lp-bi-ext-")
        self.config = tempfile.mkdtemp(prefix="lp-bi-cfg-")
        with open(os.path.join(self.ext, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"manifest_version": 3, "name": "x", "version": "0.7.6"}, fh)
        with open(os.path.join(self.ext, "popup.js"), "w", encoding="utf-8") as fh:
            fh.write("// live\n")
        self._env = {k: os.environ.get(k) for k in
                     ("LP_BRIDGE_EXTENSION_DIR", "LP_BRIDGE_CONFIG_DIR")}
        os.environ["LP_BRIDGE_EXTENSION_DIR"] = self.ext
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self.config
        self.addCleanup(self._restore)

    def _restore(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.ext, ignore_errors=True)
        shutil.rmtree(self.config, ignore_errors=True)

    def _write_build_info(self, tag="v0.7.6"):
        with open(os.path.join(self.ext, updater.BUILD_INFO), "w",
                  encoding="utf-8") as fh:
            json.dump({"repo": "r", "commit": "deadbeef", "tag": tag,
                       "source": "release"}, fh)

    def test_backup_carries_the_build_info_of_the_saved_version(self):
        self._write_build_info()
        updater._backup(self.ext)
        carried = os.path.join(self.config, updater.BACKUP_DIRNAME, updater.BUILD_INFO)
        self.assertTrue(os.path.isfile(carried),
                        ".build-info.json absent du backup: un rollback "
                        "restaurerait une version sans provenance")
        with open(carried, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["tag"], "v0.7.6")

    def test_backup_without_build_info_still_succeeds(self):
        """A first-ever install has no provenance file; that is not an error."""
        updater._backup(self.ext)
        meta = updater.read_backup_meta()
        self.assertEqual(meta.get("version"), "0.7.6")
        self.assertIsNone(meta.get("commit"))

    def test_meta_describes_the_saved_tree_not_the_new_one(self):
        """meta.version must be the version the backup can restore.

        apply_update calls `_backup(ext_dir)` and then `_mirror(root, ext_dir)`:
        the live tree is replaced right after the snapshot. Anything read after
        that mirror describes 9.9.9, which the backup cannot restore.
        """
        # the live tree is v0.7.5; the backup must record 0.7.5
        with open(os.path.join(self.ext, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"manifest_version": 3, "name": "x", "version": "0.7.5"}, fh)
        self._write_build_info(tag="v0.7.5")

        real_mirror = updater._mirror

        def backup_then_live_tree_is_replaced(src, dst):
            real_mirror(src, dst)
            # the mirror into staging completed; now apply_update's own mirror
            # would land in ext_dir. Simulate the live tree moving on.
            if os.path.abspath(dst) != os.path.abspath(
                    os.path.join(self.config, updater.BACKUP_DIRNAME + ".new")):
                return
            with open(os.path.join(self.ext, "manifest.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"manifest_version": 3, "name": "x", "version": "9.9.9"}, fh)
            with open(os.path.join(self.ext, updater.BUILD_INFO), "w",
                      encoding="utf-8") as fh:
                json.dump({"commit": "cafe", "tag": "v9.9.9", "source": "release"}, fh)

        with unittest.mock.patch.object(updater, "_mirror",
                                       backup_then_live_tree_is_replaced):
            updater._backup(self.ext)

        meta = updater.read_backup_meta()
        self.assertEqual(meta.get("version"), "0.7.5",
                         "meta.json decrit l'installee, pas celle du backup")
        self.assertEqual(meta.get("tag"), "v0.7.5")
        backup_manifest = os.path.join(self.config, updater.BACKUP_DIRNAME,
                                       "manifest.json")
        with open(backup_manifest, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["version"], "0.7.5")


class UpdatePathIsSerialized(unittest.TestCase):
    """Finding 2: one writer at a time across apply / rollback / check."""

    def test_every_public_entry_point_takes_the_lock(self):
        import ast
        src = (REPO_ROOT / "relay" / "updater.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        locked = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in ("apply_update", "rollback_update", "check_update"):
                continue
            has = any(
                isinstance(sub, (ast.With, ast.AsyncWith))
                and any(isinstance(it.context_expr, ast.Name)
                        and it.context_expr.id == "_UPDATE_LOCK"
                        for it in sub.items)
                for sub in ast.walk(node))
            locked[node.name] = has
        self.assertEqual(sorted(locked), ["apply_update", "check_update", "rollback_update"])
        for name, has in sorted(locked.items()):
            self.assertTrue(has, "%s ne prend pas _UPDATE_LOCK" % name)

    def test_the_lock_is_reentrant(self):
        """apply_update calls check_update: a plain Lock would deadlock."""
        self.assertIsInstance(updater._UPDATE_LOCK, type(threading.RLock()))

    def test_a_second_thread_actually_blocks(self):
        """Not decoration: a held lock must keep a second caller out."""
        entered = threading.Event()
        release = threading.Event()
        ran = threading.Event()

        def holder():
            with updater._UPDATE_LOCK:
                entered.set()
                release.wait(5)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(5), "le premier thread n'a jamais pris le verrou")

        def intruder():
            with updater._UPDATE_LOCK:
                ran.set()

        second = threading.Thread(target=intruder)
        second.start()
        time.sleep(0.3)
        self.assertFalse(ran.is_set(),
                         "un second thread est passe pendant que le verrou etait tenu")
        release.set()
        thread.join(5)
        second.join(5)
        self.assertTrue(ran.is_set(), "le second thread n'a jamais pu entrer")

    def test_nested_check_update_does_not_deadlock(self):
        """The reentrancy the RLock exists for, exercised for real."""
        with unittest.mock.patch.object(updater, "extension_dir", return_value=""):
            with updater._UPDATE_LOCK:
                # would raise RuntimeError, not deadlock, if the lock were plain
                result = updater.check_update()
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()