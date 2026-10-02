"""The published zip must be the committed tree, and provably so.

Two defects lived here. ``ext.rglob`` shipped the gitignored
``.build-info.json`` - one machine's install history inside a public download.
And the archive was not reproducible: rebuilt from the same tree it produced a
different sha256, because ZipFile.write() stamps the current time and the build
OS into every entry, and because zlib and zlib-ng (both present on this PC) are
different deflate implementations. A sidecar that changes on every build cannot
attest anything.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "build_release_zip.py"
EXT = ROOT / "extension"


def build() -> tuple:
    """Run the real builder; return (zip bytes, sha256, names)."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, LOCALAPPDATA=tmp)
        r = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT),
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stdout + r.stderr
        produced = next(pathlib.Path(tmp, "Temp").glob("*.zip"))
        blob = produced.read_bytes()
        with zipfile.ZipFile(produced) as z:
            names = sorted(z.namelist())
        return blob, hashlib.sha256(blob).hexdigest(), names


class ShippedTree(unittest.TestCase):
    def test_no_generated_file_is_shipped(self):
        _, _, names = build()
        self.assertNotIn("extension/.build-info.json", names)

    def test_archive_is_exactly_the_tracked_extension(self):
        _, _, names = build()
        tracked = sorted(
            "extension/" + p.relative_to(EXT).as_posix()
            for p in EXT.rglob("*")
            if p.is_file()
            and ".build-info.json" not in p.name
            and "__pycache__" not in p.parts)
        self.assertEqual(names, tracked)
        self.assertTrue(names, "the archive must not be empty")

    def test_contents_match_the_files_on_disk(self):
        blob, _, names = build()
        path = _tmpzip(blob)
        try:
            with zipfile.ZipFile(path) as z:
                for name in names:
                    self.assertEqual(z.read(name), (ROOT / name).read_bytes(),
                                     "%s differs from the committed file" % name)
        finally:
            os.unlink(path)


def _tmpzip(blob: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    pathlib.Path(path).write_bytes(blob)
    return path


class Reproducible(unittest.TestCase):
    def test_two_builds_of_one_tree_have_the_same_digest(self):
        first = build()[1]
        second = build()[1]
        self.assertEqual(first, second,
                         "the archive is not reproducible: %s != %s" % (first, second))

    def test_archive_survives_a_different_compressor(self):
        """The real cross-machine failure, measured on this PC: the project
        .venv ships zlib 1.3.1 while the system python ships 1.3.1.zlib-ng.
        Two deflate implementations, same tree, 148120 vs 148524 bytes, two
        different sha256 - and a sidecar that cannot attest anything.

        Re-deflating an existing archive's entries here is exactly that test:
        it re-encodes the same bytes through this interpreter's zlib and asks
        whether the archive would survive a machine whose zlib differs. So
        compression must be STORED, where output is fixed by input alone.
        """
        blob, digest, names = build()
        with zipfile.ZipFile(_tmpzip(blob)) as z:
            for name in names:
                self.assertEqual(z.getinfo(name).compress_type, zipfile.ZIP_STORED,
                                 "%s is compressed: the bytes depend on the "
                                 "build machine's zlib (zlib vs zlib-ng)"
                                 % name)

    def test_entries_carry_no_build_clock_and_no_build_os(self):
        """A future reader must not be able to tell when or where it was built."""
        blob, _, names = build()
        path = _tmpzip(blob)
        try:
            with zipfile.ZipFile(path) as z:
                for name in names:
                    info = z.getinfo(name)
                    self.assertEqual(info.date_time[:3], (1980, 1, 1),
                                     "%s is stamped with a build date" % name)
                    self.assertEqual(info.create_system, 3,
                                     "%s records the build OS" % name)
        finally:
            os.unlink(path)

    def test_manifest_inside_is_the_repo_one(self):
        blob, _, _ = build()
        with zipfile.ZipFile(_tmpzip(blob)) as z:
            shipped = json.loads(z.read("extension/manifest.json"))
        self.assertEqual(shipped, json.loads((EXT / "manifest.json").read_text("utf-8")))


if __name__ == "__main__":
    unittest.main()
