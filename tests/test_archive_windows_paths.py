"""Windows-shaped archive attacks, which the existing traversal tests miss.

test_updater.py already proves `../../evil.txt` and `/abs/evil.txt` are refused.
The guard in `_safe_members` does more than those two tests ask for: it
normalises backslashes, refuses drive letters, and therefore also catches the
Windows-native shapes. None of that is asserted, so a future "simplification"
to a plain `name.startswith("/")` check would pass 56 updater tests and reopen
the hole on the one platform this ships on.

Nothing here touches the network or the live install: archives are built in a
temp dir and refused before extraction.

Run: .venv/Scripts/python.exe tests/test_archive_windows_paths.py
"""
import io
import os
import pathlib
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relay import updater  # noqa: E402


def build_zip(directory, names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name in names:
            archive.writestr(name, "x")
    path = os.path.join(directory, "probe.zip")
    with open(path, "wb") as fh:
        fh.write(buf.getvalue())
    return path


def build_tar(directory, names):
    path = os.path.join(directory, "probe.tar.gz")
    with tarfile.open(path, "w:gz") as archive:
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
    return path


# Each entry: (label, member name, must be refused)
HOSTILE = [
    ("windows drive letter",        "C:/evil.txt",              True),
    ("windows drive, backslash",    "C:\\evil.txt",             True),
    ("drive-relative",              "C:evil.txt",               True),
    ("UNC path",                    "//server/share/evil.txt",  True),
    ("backslash traversal",         "..\\evil.txt",             True),
    ("deep backslash traversal",    "a\\..\\..\\evil.txt",      True),
    ("mixed slash + backslash",     "a/..\\..\\evil.txt",       True),
    ("posix traversal",             "../../evil.txt",           True),
    ("posix absolute",              "/etc/evil.txt",            True),
    # Harmless entries the guard must NOT reject, or real archives break.
    ("plain relative",              "extension/manifest.json",  False),
    ("dot-prefixed file",           "./extension/popup.js",     False),
    ("deep but inside",             "a/b/c/extension/popup.js", False),
    ("dot in a name",               "extension/my.file.js",    False),
]


class WindowsShapedPathsAreRefused(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lp-archive-probe-")
        self.addCleanup(self._rmtree, self.tmp)

    @staticmethod
    def _rmtree(path):
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    def _assert_all(self, path):
        for label, _name, must_refuse in HOSTILE:
            with self.subTest(label):
                out = os.path.join(self.tmp, "out")
                try:
                    updater.extract_archive(path, out)
                    refused = False
                except RuntimeError:
                    refused = True
                if must_refuse:
                    self.assertTrue(refused,
                                    "%s was NOT refused" % label)
                else:
                    self.assertFalse(refused,
                                     "%s was wrongly refused" % label)

    def test_zip_members(self):
        for label, name, must_refuse in HOSTILE:
            with self.subTest(label):
                path = build_zip(self.tmp, [name])
                out = os.path.join(self.tmp, "out_" + name.replace("/", "_")
                                                      .replace("\\", "_")
                                                      .replace(":", ""))
                try:
                    updater.extract_archive(path, out)
                    refused = False
                except RuntimeError:
                    refused = True
                if must_refuse:
                    self.assertTrue(refused, "%s was NOT refused" % label)
                    # And nothing may have been written outside.
                    self.assertFalse(os.path.exists(
                        os.path.join(os.path.dirname(out), "evil.txt")))
                else:
                    self.assertFalse(refused, "%s was wrongly refused" % label)

    def test_tar_members(self):
        for label, name, must_refuse in HOSTILE:
            with self.subTest(label):
                path = build_tar(self.tmp, [name])
                out = os.path.join(self.tmp, "outt_" + label.replace(" ", "_"))
                try:
                    updater.extract_archive(path, out)
                    refused = False
                except RuntimeError:
                    refused = True
                if must_refuse:
                    self.assertTrue(refused, "%s was NOT refused" % label)
                else:
                    self.assertFalse(refused, "%s was wrongly refused" % label)

    def test_the_refusal_happens_before_anything_is_written(self):
        """Refusing per member, in order, would write the harmless members first.
        A validation pass must complete before the first byte lands, so a
        hostile archive leaves no partial tree behind."""
        path = build_zip(self.tmp, ["extension/ok.js", "../../evil.txt"])
        out = os.path.join(self.tmp, "partial")
        with self.assertRaises(RuntimeError):
            updater.extract_archive(path, out)
        self.assertFalse(os.path.isdir(out),
                         "a refused archive left a partially extracted tree")


class ExtractionStaysInsideDestination(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lp-archive-inside-")
        self.addCleanup(self._rmtree, self.tmp)
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.out, exist_ok=True)
        self.sentinel = os.path.join(self.tmp, "outside.txt")
        with open(self.sentinel, "w") as fh:
            fh.write("untouched")

    @staticmethod
    def _rmtree(path):
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    def test_a_traversal_archive_cannot_overwrite_a_file_outside(self):
        """The end-to-end claim: with a real file sitting next to the extraction
        dir, the hostile entry must not modify it."""
        path = build_zip(self.tmp, ["../outside.txt"])
        with self.assertRaises(RuntimeError):
            updater.extract_archive(path, self.out)
        with open(self.sentinel) as fh:
            self.assertEqual(fh.read(), "untouched",
                             "a refused archive overwrote a file outside dest")

    def test_a_valid_archive_lands_exactly_where_expected(self):
        """The other half - a guard that refuses everything is not a fix."""
        path = build_zip(self.tmp, ["extension/manifest.json", "extension/a.js"])
        updater.extract_archive(path, self.out)
        self.assertTrue(os.path.isfile(
            os.path.join(self.out, "extension", "manifest.json")))
        self.assertTrue(os.path.isfile(
            os.path.join(self.out, "extension", "a.js")))


if __name__ == "__main__":
    unittest.main()
