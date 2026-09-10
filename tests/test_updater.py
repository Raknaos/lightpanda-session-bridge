# -*- coding: utf-8 -*-
"""Tests for the update path: GitHub -> relay -> live unpacked extension.

Nothing here touches the network: the GitHub calls are stubbed, so the tests
exercise the real download/verify/extract/backup/mirror/rollback code against a
synthetic release archive.
"""
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
import unittest.mock
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "relay"))

import updater  # noqa: E402

VERSION = "9.9.9"


def extension_tree(root, version=VERSION, popup_marker="new-popup"):
    """A minimal but valid unpacked-extension tree on disk."""
    os.makedirs(os.path.join(root, "icons"), exist_ok=True)
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "manifest_version": 3,
            "name": "Lightpanda Session Bridge",
            "version": version,
            "permissions": ["cookies", "alarms"],
        }, fh)
    with open(os.path.join(root, "popup.html"), "w", encoding="utf-8") as fh:
        fh.write(popup_marker)
    with open(os.path.join(root, "popup.js"), "w", encoding="utf-8") as fh:
        fh.write("// " + popup_marker + "\n")
    with open(os.path.join(root, "icons", "icon.png"), "wb") as fh:
        fh.write(b"\x89PNG")
    return root


def release_zip(version=VERSION, prefix="", popup_marker="new-popup"):
    """In-memory zip laid out exactly like `scripts/build_release_zip.py`."""
    buffer = io.BytesIO()
    staging = tempfile.mkdtemp(prefix="lp-bridge-test-zip-")
    try:
        extension_tree(os.path.join(staging, "extension"), version, popup_marker)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(pathlib.Path(staging).rglob("*")):
                if path.is_file():
                    rel = path.relative_to(staging).as_posix()
                    archive.write(path, prefix + rel)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return buffer.getvalue()


def release_tarball(version=VERSION, popup_marker="new-popup"):
    """GitHub's own source archive shape: <repo>-<sha>/extension/..."""
    buffer = io.BytesIO()
    staging = tempfile.mkdtemp(prefix="lp-bridge-test-tar-")
    try:
        top = os.path.join(staging, "lightpanda-session-bridge-deadbeef")
        extension_tree(os.path.join(top, "extension"), version, popup_marker)
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(top, arcname=os.path.basename(top))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return buffer.getvalue()


class UpdateTestCase(unittest.TestCase):
    """Gives every test its own extension dir and its own config dir."""

    def setUp(self):
        self.ext = tempfile.mkdtemp(prefix="lp-bridge-ext-")
        self.config = tempfile.mkdtemp(prefix="lp-bridge-cfg-")
        self._env = {key: os.environ.get(key) for key in
                     ("LP_BRIDGE_EXTENSION_DIR", "LP_BRIDGE_CONFIG_DIR")}
        os.environ["LP_BRIDGE_EXTENSION_DIR"] = self.ext
        os.environ["LP_BRIDGE_CONFIG_DIR"] = self.config
        updater.clear_cache()

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.ext, ignore_errors=True)
        shutil.rmtree(self.config, ignore_errors=True)
        updater.clear_cache()


class TestVersionOrdering(unittest.TestCase):
    def test_parses_and_rejects(self):
        self.assertEqual(updater.parse_version("v0.4.3"), (0, 4, 3, ""))
        self.assertEqual(updater.parse_version(" 1.2.10 "), (1, 2, 10, ""))
        self.assertEqual(updater.parse_version("0.5.0-rc1"), (0, 5, 0, "rc1"))
        self.assertIsNone(updater.parse_version("main"))
        self.assertIsNone(updater.parse_version(""))
        self.assertIsNone(updater.parse_version(None))

    def test_ordering(self):
        self.assertTrue(updater.is_newer("0.5.0", "0.4.3"))
        self.assertTrue(updater.is_newer("0.4.10", "0.4.9"))
        self.assertFalse(updater.is_newer("0.4.3", "0.4.3"))
        self.assertFalse(updater.is_newer("0.4.2", "0.4.3"))
        self.assertTrue(updater.is_newer("0.5.0", "0.5.0-rc1"))
        self.assertTrue(updater.is_newer("0.5.0-rc2", "0.5.0-rc1"))
        self.assertFalse(updater.is_newer("0.5.0-rc1", "0.5.0"))
        # An unparsable side must never win an update.
        self.assertFalse(updater.is_newer("nonsense", "0.4.3"))
        self.assertFalse(updater.is_newer("0.9.9", "nonsense"))


class TestArchiveSafety(UpdateTestCase):
    def test_zip_traversal_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../../evil.txt", "x")
        path = os.path.join(self.ext, "bad.zip")
        with open(path, "wb") as fh:
            fh.write(buffer.getvalue())
        with self.assertRaises(RuntimeError):
            updater.extract_archive(path, os.path.join(self.ext, "out"))

    def test_zip_absolute_path_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("/abs/evil.txt", "x")
        path = os.path.join(self.ext, "bad.zip")
        with open(path, "wb") as fh:
            fh.write(buffer.getvalue())
        with self.assertRaises(RuntimeError):
            updater.extract_archive(path, os.path.join(self.ext, "out"))

    def test_tar_traversal_refused(self):
        path = os.path.join(self.ext, "bad.tar.gz")
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo("../evil.txt")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(RuntimeError):
            updater.extract_archive(path, os.path.join(self.ext, "out"))

    def test_good_archives_accepted(self):
        for name, payload in (("release.zip", release_zip()),
                              ("source.tar.gz", release_tarball())):
            path = os.path.join(self.ext, name)
            with open(path, "wb") as fh:
                fh.write(payload)
            out = os.path.join(self.ext, "out-" + name)
            updater.extract_archive(path, out)
            root = updater.locate_extension_root(out)
            self.assertEqual(updater.validate_extension_tree(root)["version"], VERSION)


class TestLayout(UpdateTestCase):
    def test_release_zip_layout(self):
        out = os.path.join(self.ext, "out")
        updater.extract_archive(self._write("a.zip", release_zip()), out)
        self.assertTrue(os.path.isfile(os.path.join(updater.locate_extension_root(out), "manifest.json")))

    def test_github_tarball_layout(self):
        out = os.path.join(self.ext, "out")
        updater.extract_archive(self._write("a.tar.gz", release_tarball()), out)
        root = updater.locate_extension_root(out)
        self.assertEqual(os.path.basename(os.path.dirname(root)), "lightpanda-session-bridge-deadbeef")

    def test_tree_without_manifest_refused(self):
        bare = os.path.join(self.ext, "bare")
        os.makedirs(bare)
        with open(os.path.join(bare, "readme.txt"), "w") as fh:
            fh.write("hi")
        with self.assertRaises(RuntimeError):
            updater.locate_extension_root(bare)

    def test_wrong_manifest_refused(self):
        tree = os.path.join(self.ext, "other")
        extension_tree(tree)
        with open(os.path.join(tree, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"manifest_version": 3, "name": "Some Other Extension", "version": "1.0.0"}, fh)
        with self.assertRaises(RuntimeError):
            updater.validate_extension_tree(tree)

    def _write(self, name, payload):
        path = os.path.join(self.ext, name)
        with open(path, "wb") as fh:
            fh.write(payload)
        return path


class TestMirror(UpdateTestCase):
    def test_copy_prune_and_keep_build_info(self):
        src = extension_tree(os.path.join(self.ext, "src"), popup_marker="fresh")
        dst = extension_tree(os.path.join(self.ext, "dst"), version="0.0.1", popup_marker="stale")
        with open(os.path.join(dst, "obsolete.js"), "w") as fh:
            fh.write("gone")
        with open(os.path.join(dst, updater.BUILD_INFO), "w") as fh:
            fh.write('{"commit": "keep-me"}')
        copied, removed = updater._mirror(src, dst)
        self.assertNotIn("obsolete.js", os.listdir(dst))
        self.assertIn("obsolete.js", removed)
        self.assertIn("manifest.json", copied)
        with open(os.path.join(dst, updater.BUILD_INFO), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["commit"], "keep-me")
        with open(os.path.join(dst, "popup.html"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "fresh")

    def test_unchanged_files_are_not_rewritten(self):
        tree = extension_tree(os.path.join(self.ext, "same"))
        before = os.path.getmtime(os.path.join(tree, "manifest.json"))
        copied, _ = updater._mirror(tree, tree)
        self.assertEqual(copied, [])
        self.assertEqual(before, os.path.getmtime(os.path.join(tree, "manifest.json")))


class TestApplyAndRollback(UpdateTestCase):
    """End-to-end through apply_update(), with only the network stubbed."""

    def setUp(self):
        super().setUp()
        extension_tree(self.ext, version="0.4.3", popup_marker="deployed-old")
        os.makedirs(os.path.join(self.ext, "locales"), exist_ok=True)
        with open(os.path.join(self.ext, "locales", "stale.json"), "w") as fh:
            fh.write("{}")

    def _stub(self, payload, asset_name="lightpanda-session-bridge-9.9.9.zip",
              tag="v9.9.9", commit="a" * 40, commit_message="release 9.9.9",
              extra_assets=(), fetch_error=None):
        digest = hashlib.sha256(payload).hexdigest()
        assets = [{"name": asset_name, "url": "https://api.github.com/stub/asset"}] + list(extra_assets)
        release = {
            "tag": tag, "version_text": tag.lstrip("v"), "assets": assets,
            "html_url": "https://github.com/stub/release", "published_at": "2026-01-01T00:00:00Z",
            "notes": "notes", "commit": commit,
        }
        head = {"sha": commit, "short": commit[:7], "message": commit_message,
                "date": "2026-01-01T00:00:00Z", "html_url": "https://github.com/stub/commit"}
        served = {}

        def fake_fetch(url, limit=updater.MAX_ARCHIVE_BYTES, accept="application/vnd.github+json"):
            if fetch_error:
                raise fetch_error
            value = served.get(url)
            if value is None:
                if url.endswith(".sha256") or "SHA256SUMS" in url:
                    value = (digest + "  " + asset_name + "\n").encode()
                else:
                    value = payload
            return value

        saved = (updater.latest_release, updater.latest_commit, updater._fetch)
        updater.latest_release = lambda repo=updater.REPO: release
        updater.latest_commit = lambda repo=updater.REPO, branch=updater.BRANCH, tag=None: head
        updater._fetch = fake_fetch
        self.addCleanup(lambda: (setattr(updater, "latest_release", saved[0]),
                                 setattr(updater, "latest_commit", saved[1]),
                                 setattr(updater, "_fetch", saved[2])))
        return release, head, digest

    def test_release_install_writes_files_and_provenance(self):
        release, head, digest = self._stub(release_zip())
        result = updater.apply_update()
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "release")
        self.assertEqual(result["version"], VERSION)
        self.assertEqual(result["commit"], head["sha"])
        self.assertFalse(result["checksum_verified"])  # no sidecar published
        with open(os.path.join(self.ext, "popup.html"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "new-popup")
        self.assertFalse(os.path.exists(os.path.join(self.ext, "locales", "stale.json")))
        with open(os.path.join(self.ext, updater.BUILD_INFO), encoding="utf-8") as fh:
            build = json.load(fh)
        self.assertEqual(build["commit"], "a" * 40)
        self.assertEqual(build["tag"], "v9.9.9")
        self.assertEqual(build["sha256"], digest)
        self.assertEqual(build["previous"]["version"], "0.4.3")

    def test_checksum_sidecar_is_enforced(self):
        sidecar = {"name": "SHA256SUMS", "url": "https://api.github.com/stub/SHA256SUMS"}
        self._stub(release_zip(), extra_assets=(sidecar,))
        result = updater.apply_update()
        self.assertTrue(result["checksum_verified"])

    def test_wrong_checksum_refuses_the_artifact(self):
        sidecar = {"name": "SHA256SUMS", "url": "https://api.github.com/stub/SHA256SUMS"}

        def fake_fetch(url, limit=updater.MAX_ARCHIVE_BYTES, accept="application/vnd.github+json"):
            if "SHA256SUMS" in url:
                return ("b" * 64 + "  lightpanda-session-bridge-9.9.9.zip\n").encode()
            return release_zip()

        self._stub(release_zip(), extra_assets=(sidecar,))
        updater._fetch = fake_fetch
        with self.assertRaises(RuntimeError) as caught:
            updater.apply_update()
        self.assertIn("checksum", str(caught.exception))
        # The deployed tree must be untouched.
        with open(os.path.join(self.ext, "popup.html"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "deployed-old")

    def test_rollback_restores_the_previous_tree(self):
        self._stub(release_zip())
        updater.apply_update()
        with open(os.path.join(self.ext, "popup.html"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "new-popup")
        result = updater.rollback_update()
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "0.4.3")
        with open(os.path.join(self.ext, "popup.html"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "deployed-old")

    def test_rollback_without_backup_is_an_error(self):
        with self.assertRaises(RuntimeError):
            updater.rollback_update()

    def test_main_source_installs_the_commit_tarball(self):
        release, head, _ = self._stub(release_zip())
        # Same version as deployed, but main has moved on -> main channel.
        release["version_text"] = "0.4.3"
        release["tag"] = "v0.4.3"
        head["sha"] = "c" * 40
        head["short"] = "c" * 7
        payload = release_tarball(version="0.4.4", popup_marker="main-popup")

        def fake_fetch(url, limit=updater.MAX_ARCHIVE_BYTES, accept="application/vnd.github+json"):
            return payload

        updater._fetch = fake_fetch
        # Provenance says the deployed copy came from a, main is now c: that is
        # what makes this the main channel and not the equal-version release.
        with open(os.path.join(self.ext, updater.BUILD_INFO), "w", encoding="utf-8") as fh:
            json.dump({"commit": "a" * 40, "tag": "v0.4.3"}, fh)
        updater.clear_cache()
        result = updater.apply_update()
        self.assertEqual(result["source"], "main")
        self.assertIsNone(result["tag"])  # never claim a tag the code is not from
        self.assertEqual(result["commit"], "c" * 40)
        with open(os.path.join(self.ext, "popup.html"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "main-popup")


class TestDownloadGuards(unittest.TestCase):
    """_fetch: what the download path accepts, and what it must refuse.

    v0.5.1 shipped with the real GitHub CDN host missing from the allow-list, so
    every install died with "update redirect refused" (seen from the popup).
    These tests pin the behaviour against a fake HTTP layer instead of the
    network, so the guard can be changed without flying blind.
    """

    class _Response:
        def __init__(self, url, body=b"zip-bytes", content_length=None):
            self._url = url
            self._body = body
            self.headers = {}
            if content_length is not None:
                self.headers["Content-Length"] = str(content_length)

        def geturl(self):
            return self._url

        def read(self, size=-1):
            return self._body if size is None or size < 0 else self._body[:size]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _serve(self, response):
        return unittest.mock.patch.object(updater.urllib.request, "urlopen",
                                          lambda request, timeout=None: response)

    def test_current_cdn_host_is_accepted(self):
        url = ("https://release-assets.githubusercontent.com/github-production-release-asset/"
               "1/2?sp=r&sig=whatever")
        with self._serve(self._Response(url)):
            self.assertEqual(updater._fetch("https://api.github.com/stub/asset"), b"zip-bytes")

    def test_historical_cdn_hosts_are_accepted(self):
        for host in ("objects.githubusercontent.com", "github-releases.githubusercontent.com"):
            with self._serve(self._Response("https://%s/x" % host)):
                self.assertEqual(updater._fetch("https://api.github.com/stub/asset"), b"zip-bytes")

    def test_redirect_off_github_is_refused(self):
        with self._serve(self._Response("https://evil.example/asset.zip")):
            with self.assertRaises(RuntimeError) as caught:
                updater._fetch("https://api.github.com/stub/asset")
        self.assertIn("redirect refused", str(caught.exception))

    def test_redirect_to_plain_http_is_refused(self):
        with self._serve(self._Response("http://release-assets.githubusercontent.com/x")):
            with self.assertRaises(RuntimeError) as caught:
                updater._fetch("https://api.github.com/stub/asset")
        self.assertIn("redirect refused", str(caught.exception))

    def test_lookalike_host_is_refused(self):
        with self._serve(self._Response("https://release-assets.githubusercontent.com.evil.example/x")):
            with self.assertRaises(RuntimeError) as caught:
                updater._fetch("https://api.github.com/stub/asset")
        self.assertIn("redirect refused", str(caught.exception))

    def test_source_url_must_be_github_over_https(self):
        for url in ("http://api.github.com/x", "https://evil.example/x", "file:///etc/passwd"):
            with self.assertRaises(RuntimeError) as caught:
                updater._fetch(url)
            self.assertIn("source refused", str(caught.exception))

    def test_oversized_download_is_refused(self):
        url = "https://release-assets.githubusercontent.com/x"
        # Declared by the header ...
        with self._serve(self._Response(url, content_length=99)):
            with self.assertRaises(RuntimeError) as caught:
                updater._fetch("https://api.github.com/stub/asset", limit=10)
        self.assertIn("too large", str(caught.exception))
        # ... and when the header lies.
        with self._serve(self._Response(url, body=b"x" * 50)):
            with self.assertRaises(RuntimeError) as caught:
                updater._fetch("https://api.github.com/stub/asset", limit=10)
        self.assertIn("too large", str(caught.exception))

    def test_the_real_asset_host_is_in_the_allow_list(self):
        # Regression guard for the v0.5.1 bug, expressible without the network.
        self.assertIn("release-assets.githubusercontent.com", updater.ALLOWED_HOSTS)
        for host in updater.ALLOWED_HOSTS:
            self.assertFalse(host.startswith("*"), "no wildcard hosts: %s" % host)


class TestCheckUpdate(UpdateTestCase):
    def setUp(self):
        super().setUp()
        extension_tree(self.ext, version="0.4.3", popup_marker="deployed")

    def _stub(self, release_version, commit, installed_commit=None):
        if installed_commit:
            with open(os.path.join(self.ext, updater.BUILD_INFO), "w", encoding="utf-8") as fh:
                json.dump({"commit": installed_commit, "tag": "v" + release_version}, fh)
        release = None
        if release_version:
            release = {"tag": "v" + release_version, "version_text": release_version,
                       "assets": [], "html_url": "u", "published_at": "d", "notes": "", "commit": commit}
        head = {"sha": commit, "short": commit[:7], "message": "m", "date": "d", "html_url": "u"}
        updater.latest_release = lambda repo=updater.REPO: release
        updater.latest_commit = lambda repo=updater.REPO, branch=updater.BRANCH, tag=None: head
        self.addCleanup(updater.clear_cache)

    def test_newer_release_wins(self):
        self._stub("9.9.9", "a" * 40)
        status = updater.check_update(force=True)
        self.assertTrue(status["update_available"])
        self.assertEqual(status["source"], "release")
        self.assertEqual(status["latest_version"], "9.9.9")
        self.assertTrue(status["writable"])

    def test_nothing_to_do_when_release_matches_and_commit_is_known(self):
        self._stub("0.4.3", "a" * 40, installed_commit="a" * 40)
        status = updater.check_update(force=True)
        self.assertFalse(status["update_available"])
        self.assertIsNone(status["source"])
        self.assertFalse(status["baseline_unknown"])

    def test_new_commit_on_main_is_offered(self):
        self._stub("0.4.3", "b" * 40, installed_commit="a" * 40)
        status = updater.check_update(force=True)
        self.assertTrue(status["update_available"])
        self.assertEqual(status["source"], "main")

    def test_unknown_baseline_is_flagged(self):
        # Nothing published yet: the only honest thing to offer is the commit.
        self._stub(None, "b" * 40)
        status = updater.check_update(force=True)
        self.assertTrue(status["update_available"])
        self.assertTrue(status["baseline_unknown"])
        self.assertEqual(status["source"], "main")
        self.assertEqual(status["to"], "bbbbbbb")

    def test_unknown_baseline_prefers_the_verified_release(self):
        # Deployed 0.5.0 with no provenance, and the release is also 0.5.0:
        # offer the tagged zip (checksum-verifiable), not the main tarball.
        extension_tree(self.ext, version="0.5.0", popup_marker="deployed")
        self._stub("0.5.0", "b" * 40)
        status = updater.check_update(force=True)
        self.assertTrue(status["update_available"])
        self.assertEqual(status["source"], "release")
        self.assertTrue(status["baseline_unknown"])

    def test_unknown_baseline_never_offers_a_downgrade(self):
        # A dev checkout ahead of the last release: main channel, not the older
        # tagged artifact.
        extension_tree(self.ext, version="9.0.0", popup_marker="deployed")
        self._stub("0.5.0", "b" * 40)
        status = updater.check_update(force=True)
        self.assertTrue(status["update_available"])
        self.assertEqual(status["source"], "main")

    def test_github_unreachable_is_not_reported_as_up_to_date(self):
        def boom(repo=updater.REPO):
            raise OSError("network down")
        updater.latest_release = boom
        status = updater.check_update(force=True)
        self.assertFalse(status["ok"])
        self.assertFalse(status["update_available"])
        self.assertIn("unreachable", status["error"])

    def test_missing_extension_dir_is_reported(self):
        os.environ["LP_BRIDGE_EXTENSION_DIR"] = os.path.join(self.ext, "nope")
        # Neutralise the checkout fallback: this test is about "nowhere found".
        self.addCleanup(setattr, updater, "extension_dir", updater.extension_dir)
        updater.extension_dir = lambda: ""
        updater.latest_release = lambda repo=updater.REPO: None
        updater.latest_commit = lambda repo=updater.REPO, branch=updater.BRANCH, tag=None: None
        status = updater.check_update(force=True)
        self.assertFalse(status["ok"])
        self.assertIn("not found", status["error"])


class TestWiring(unittest.TestCase):
    """The button only exists if the three files agree."""

    def test_popup_card_and_handler_exist(self):
        html = (REPO_ROOT / "extension" / "popup.html").read_text(encoding="utf-8")
        js = (REPO_ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
        for element in ("update-card", "update-chip", "update-version", "update-meta",
                        "update-btn", "rollback-btn", "app-version"):
            self.assertIn('id="%s"' % element, html)
        for token in ("/v1/update/check", "/v1/update/apply", "/v1/update/rollback",
                      "chrome.runtime.reload()", "bridgeHeaders()"):
            self.assertIn(token, js)
        # The footer version is filled from the manifest at runtime, so a bump
        # never needs a second hand-edit of the HTML placeholder.
        self.assertIn("appVersion.textContent = 'v' + chrome.runtime.getManifest().version", js)

    def test_every_language_has_the_update_strings(self):
        js = (REPO_ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
        keys = ["updateLabel", "updateChecking", "updateUpToDate", "updateAvailable",
                "updateMainAvailable", "updateBtn", "updateBtnMain", "updateApplying",
                "updateApplied", "updateFailed", "updateRollback", "updateRolledBack",
                "updateBaseline", "updateChipNew", "updateChipOk", "sessionsClearShort",
                "clearConfirmShort"]
        for key in keys:
            self.assertEqual(js.count("\n    %s: " % key), 10, "%s is not in all 10 languages" % key)


class TestPopupLayout(unittest.TestCase):
    """Chrome caps a popup at 600px tall.

    The previous layout used `max-height: 580px` + `overflow: hidden` on the
    body, so the update card at the bottom was sliced in half and its buttons
    were unreachable. These tests pin the shape of the fix: a regression here
    is invisible in unit output and only shows up as an unusable button.
    """

    def setUp(self):
        self.html = (REPO_ROOT / "extension" / "popup.html").read_text(encoding="utf-8")
        self.js = (REPO_ROOT / "extension" / "popup.js").read_text(encoding="utf-8")

    def test_body_never_hides_overflow_behind_a_fixed_cap(self):
        block = re.search(r"html, body \{(.*?)\}",
                          self.html, re.S).group(1)
        self.assertNotIn("overflow: hidden", block,
                         "a hidden body plus a max-height is what clipped the buttons")
        self.assertIn("overflow-y: auto", block, "the body must be able to scroll")

    def test_collapsible_card_is_last(self):
        """Opening the session list must only grow the tail of the popup."""
        body = self.html[self.html.index('<div class="app-shell"'):]
        self.assertLess(body.index('id="update-card"'), body.index('id="sessions-card"'))

    def test_session_list_is_its_own_scroll_area(self):
        block = re.search(r"\.sessions-list \{(.*?)\}", self.html, re.S).group(1)
        self.assertIn("max-height", block)
        self.assertIn("overflow-y: auto", block)

    def test_clear_button_is_a_compact_pill_in_the_header(self):
        head = re.search(r'<div class="sessions-head">(.*?)</div>\n      </div>',
                         self.html, re.S).group(1)
        self.assertIn('id="sessions-clear"', head, "the clear button belongs in the header row")
        block = re.search(r"\.sessions-clear \{(.*?)\}", self.html, re.S).group(1)
        self.assertNotIn("width: 100%", block, "a full-width red bar on its own row was the ugly part")

    def test_clear_button_keeps_its_inner_span(self):
        """Writing textContent on the button replaced its <span> and detached it."""
        self.assertNotIn("sessionsClear.textContent =", self.js)
        self.assertIn("clearText.textContent = labelClear()", self.js)

    def test_update_card_shows_state_and_target_once(self):
        """The chip used to show the hash and the meta line repeated it."""
        card = self.js[self.js.index("function renderUpdateCard"):self.js.index("async function refreshUpdateStatus")]
        self.assertIn("updateChip.textContent = t('updateChipNew')", card)
        self.assertIn("updateChip.textContent = t('updateChipOk')", card)
        self.assertNotIn("t('updateUpToDate', deployed)", card,
                         "the chip must not repeat the version shown on the line below")

    def test_manifest_has_alarms_and_matching_versions(self):
        manifest = json.loads((REPO_ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("alarms", manifest["permissions"])
        version = manifest["version"]
        self.assertIn('version = "%s"' % version, (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        xml = (REPO_ROOT / "updates.xml").read_text(encoding="utf-8")
        self.assertIn("version='%s'" % version, xml)
        self.assertIn("lightpanda-session-bridge-%s.zip" % version, xml)

    def test_relay_exposes_the_three_routes(self):
        server = (REPO_ROOT / "relay" / "server.py").read_text(encoding="utf-8")
        for route in ("/v1/update/check", "/v1/update/apply", "/v1/update/rollback"):
            self.assertIn(route, server)
        self.assertIn("--check-update", server)
        self.assertIn("--rollback-update", server)

    def test_background_raises_the_badge(self):
        worker = (REPO_ROOT / "extension" / "background.js").read_text(encoding="utf-8")
        self.assertIn("setBadgeText", worker)
        self.assertIn("/v1/update/check", worker)
        self.assertIn("chrome.alarms", worker)



class TestGitHubAcceptHeader(unittest.TestCase):
    """v0.5.4 shipped a real bug: the main channel asked api.github.com for
    `application/octet-stream` and GitHub answered `415 Unsupported Media Type`
    before sending a single byte. Measured on 2026-09-10, for
    /repos/.../tarball/<sha>: octet-stream -> 415, vnd.github+json -> 200,
    no Accept header at all -> 200. The CDN that serves release assets does
    serve octet-stream, so the fix belongs in the choke point, not in a caller.
    """

    class _FakeResponse:
        status = 200
        headers = {"Content-Length": "2"}

        def __init__(self, url):
            self._url = url

        def geturl(self):
            return self._url

        def read(self, size=-1):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _capture(self, url, accept):
        seen = {}

        def fake_urlopen(request, timeout=None):
            seen["url"] = request.full_url
            seen["accept"] = request.get_header("Accept")
            return self._FakeResponse(request.full_url)

        with unittest.mock.patch.object(updater.urllib.request, "urlopen", fake_urlopen):
            updater._fetch(url, accept=accept)
        return seen

    def test_the_api_host_never_receives_a_binary_accept(self):
        api = "https://api.github.com/repos/Raknaos/lightpanda-session-bridge/tarball/main"
        seen = self._capture(api, "application/octet-stream")
        self.assertEqual(seen["accept"], updater.API_MEDIA_TYPE)

    def test_a_download_host_keeps_the_accept_the_caller_asked_for(self):
        cdn = "https://release-assets.githubusercontent.com/github-production-release-asset/x.zip"
        seen = self._capture(cdn, "application/octet-stream")
        self.assertEqual(seen["accept"], "application/octet-stream")

    def test_the_guard_lives_in_the_single_choke_point(self):
        src = (REPO_ROOT / "relay" / "updater.py").read_text(encoding="utf-8")
        body = src[src.index("def _fetch("):src.index("def _fetch_json(")]
        self.assertIn("if parsed.hostname in API_HOSTS:", body)
        self.assertIn("accept = API_MEDIA_TYPE", body)
        # and the main channel still asks for bytes: the guard upgrades it, so
        # no caller has to know which host an archive will come from.
        apply_body = src[src.index("def apply_update("):src.index("def rollback_update(")]
        self.assertIn('archive_name, archive_url, accept, checksum, tag, commit', apply_body)
        self.assertIn('"application/octet-stream"', apply_body)
        self.assertIn("_fetch(archive_url, accept=accept)", apply_body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
