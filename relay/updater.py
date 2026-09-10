"""Self-update for the unpacked extension, driven by the local relay.

Why the relay does it and not the extension: the extension is loaded
*unpacked* from a directory on disk, so Chrome will never update it by itself
(no Web Store, and the update_url manifest key only serves CRX builds). The
popup can only ask; a process with filesystem access must do the work. The
relay already runs on the user's machine, so it is that process.

Safety rules, in order of importance:
  * the download origin is compiled in (REPO) - never taken from the caller;
  * https only, GitHub hosts only, checked again after every redirect;
  * hard size cap, and the archive layout is validated before a byte is
    written into the live extension directory;
  * archive members are extracted one by one with zip-slip / traversal refused;
  * the current tree is copied to a backup outside the repo first, so any
    update can be undone with rollback();
  * nothing secret is ever read, logged or returned (versions and hashes only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = os.environ.get("LP_BRIDGE_UPDATE_REPO", "Raknaos/lightpanda-session-bridge")
BRANCH = os.environ.get("LP_BRIDGE_UPDATE_BRANCH", "main")
API = "https://api.github.com"
# Every host the download is allowed to end up on. GitHub answers a release
# asset request with a 302 to a signed CDN URL, and the CDN hostname has changed
# over the years, so all known ones are listed rather than trusting a wildcard:
# `release-assets.githubusercontent.com` is what it redirects to today
# (v0.5.2 fix - v0.5.1 failed here with "update redirect refused"), the other two
# are the historical targets. The check runs on the *final* URL, so a redirect
# can never walk the download off GitHub.
ALLOWED_HOSTS = {
    "api.github.com",
    "github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
BUILD_INFO = ".build-info.json"
BACKUP_DIRNAME = "extension-backup"
CACHE_TTL = 60.0
USER_AGENT = "lightpanda-session-bridge-updater"

_CACHE: dict = {"at": 0.0, "data": None}
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+]([0-9A-Za-z.\-]+))?$")


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------

def parse_version(text: str):
    """'v0.4.3' -> (0, 4, 3, ''); '0.5.0-beta.1' -> (0, 5, 0, 'beta.1')."""
    match = _VERSION_RE.match((text or "").strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)),
            match.group(4) or "")


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is strictly newer than `current`.

    A final release beats a pre-release of the same numbers (0.5.0 > 0.5.0-rc1),
    which is the ordering users expect from a release channel.
    """
    new, old = parse_version(candidate), parse_version(current)
    if new is None or old is None:
        return False
    if new[:3] != old[:3]:
        return new[:3] > old[:3]
    if bool(new[3]) != bool(old[3]):
        return not new[3]
    return new[3] > old[3]


# --------------------------------------------------------------------------
# local layout
# --------------------------------------------------------------------------

def config_dir() -> str:
    return os.environ.get("LP_BRIDGE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".config", "lightpanda-bridge"
    )


def repo_root() -> str:
    """The checkout this file ships in (relay/../)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extension_dir() -> str:
    """Where the live unpacked extension lives.

    LP_BRIDGE_EXTENSION_DIR wins, then <config>/config.json {"extension_dir"},
    then the sibling ./extension of the checkout this relay was started from.
    Returns "" when none of them holds a manifest.json.
    """
    candidates = []
    env = os.environ.get("LP_BRIDGE_EXTENSION_DIR")
    if env:
        candidates.append(env)
    try:
        with open(os.path.join(config_dir(), "config.json"), "r", encoding="utf-8") as fh:
            configured = (json.load(fh) or {}).get("extension_dir")
            if configured:
                candidates.append(configured)
    except (OSError, ValueError):
        pass
    candidates.append(os.path.join(repo_root(), "extension"))
    for path in candidates:
        if os.path.isfile(os.path.join(path, "manifest.json")):
            return os.path.abspath(path)
    return ""


def read_manifest(ext_dir: str) -> dict:
    with open(os.path.join(ext_dir, "manifest.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def installed_info(ext_dir: str = "") -> dict:
    """What is deployed right now: version from the manifest, provenance from
    the .build-info.json the updater writes on every install."""
    ext_dir = ext_dir or extension_dir()
    info = {"version": None, "manifest_version": None, "commit": None,
            "commit_short": None, "tag": None, "installed_at": None,
            "source": None, "directory": ext_dir}
    if not ext_dir:
        return info
    try:
        manifest = read_manifest(ext_dir)
    except (OSError, ValueError):
        return info
    info["version"] = manifest.get("version")
    info["manifest_version"] = manifest.get("manifest_version")
    try:
        with open(os.path.join(ext_dir, BUILD_INFO), "r", encoding="utf-8") as fh:
            build = json.load(fh) or {}
        for key in ("commit", "tag", "installed_at", "source"):
            if build.get(key):
                info[key] = build[key]
        info["commit_short"] = (info["commit"] or "")[:8] or None
    except (OSError, ValueError):
        pass
    return info


def backup_meta_path() -> str:
    return os.path.join(config_dir(), BACKUP_DIRNAME, "meta.json")


def read_backup_meta() -> dict:
    try:
        with open(backup_meta_path(), "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------

def _fetch(url: str, limit: int = MAX_ARCHIVE_BYTES, accept: str = "application/vnd.github+json"):
    """GET over https, from an allow-listed host only, capped in size.

    The allow-list is re-checked on the *final* URL so a redirect cannot walk
    the download onto an arbitrary origin.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RuntimeError("update source refused")
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": accept,
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise RuntimeError("update redirect refused")
        declared = int(response.headers.get("Content-Length") or 0)
        if declared > limit:
            raise RuntimeError("update artifact too large")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise RuntimeError("update artifact too large")
    return data


def _fetch_json(url: str):
    try:
        return json.loads(_fetch(url, limit=1_000_000).decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def latest_release(repo: str = REPO):
    data = _fetch_json(f"{API}/repos/{repo}/releases/latest")
    if not data or not data.get("tag_name"):
        return None
    assets = []
    for asset in data.get("assets") or []:
        url = asset.get("browser_download_url") or ""
        host = urllib.parse.urlparse(url).hostname
        if not url or host not in ALLOWED_HOSTS:
            continue
        assets.append({"name": asset.get("name") or "", "url": url,
                       "size": int(asset.get("size") or 0)})
    return {
        "tag": data["tag_name"],
        "version": (parse_version(data["tag_name"]) or (0, 0, 0, ""))[:3],
        "version_text": data["tag_name"].lstrip("vV"),
        "commit": data.get("target_commitish") or None,
        "published_at": data.get("published_at"),
        "html_url": data.get("html_url"),
        "assets": assets,
        "notes": (data.get("body") or "").strip()[:400],
    }


def latest_commit(repo: str = REPO, branch: str = BRANCH, tag: str | None = None):
    ref = tag or branch
    data = _fetch_json(f"{API}/repos/{repo}/commits/{urllib.parse.quote(ref)}")
    if not data or not data.get("sha"):
        return None
    commit = data.get("commit") or {}
    return {
        "sha": data["sha"],
        "short": data["sha"][:8],
        "date": ((commit.get("committer") or {}).get("date")),
        "message": (commit.get("message") or "").splitlines()[0][:120],
        "html_url": data.get("html_url"),
    }


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

def check_update(force: bool = False, repo: str = REPO) -> dict:
    """Compare what is deployed with GitHub. Read-only, cacheable."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < CACHE_TTL:
        return _CACHE["data"]

    ext_dir = extension_dir()
    result = {
        "ok": True,
        "repo": repo,
        "extension_dir": ext_dir or None,
        "writable": bool(ext_dir) and os.access(ext_dir, os.W_OK),
        "update_available": False,
        "source": None,
        "current_version": None,
        "current_commit": None,
        "current_tag": None,
        "latest_version": None,
        "latest_tag": None,
        "latest_commit": None,
        "baseline_unknown": False,
        "backup_available": bool(read_backup_meta().get("version")),
        "published_at": None,
        "url": None,
        "notes": "",
    }
    current = installed_info(ext_dir)
    result.update({
        "current_version": current["version"],
        "current_commit": current["commit"],
        "current_tag": current["tag"],
    })
    if not ext_dir:
        result.update({"ok": False, "error": "extension directory not found"})
        _CACHE.update({"at": now, "data": result})
        return result

    try:
        release = latest_release(repo)
    except Exception as err:  # network down, rate limited, ...
        result.update({"ok": False, "error": f"GitHub unreachable ({type(err).__name__})"})
        _CACHE.update({"at": now, "data": result})
        return result

    head = None
    try:
        head = latest_commit(repo)
    except Exception:
        head = None

    if release:
        result["latest_version"] = release["version_text"]
        result["latest_tag"] = release["tag"]
        result["published_at"] = release["published_at"]
        result["url"] = release["html_url"]
        result["notes"] = release["notes"]

    release_is_newer = bool(
        release and release["version_text"]
        and is_newer(release["version_text"], current["version"] or "0.0.0")
    )

    if release_is_newer:
        result.update({"update_available": True, "source": "release",
                       "from": current["version"], "to": release["version_text"]})
    elif head and current["commit"] and head["sha"] != current["commit"]:
        # Same release, but main moved on: offer the newest commit (dev channel).
        result.update({
            "update_available": True, "source": "main",
            "from": current["commit"][:8], "to": head["short"],
        })
    elif not current["commit"] and release:
        # No provenance (hand-installed, or an installer older than 0.5.0), so
        # the deployed tree *is* the release only by assumption. Offer the
        # tagged artifact - the immutable, checksum-verified one - never a
        # downgrade, and never a silent guess about what is on disk.
        installed = parse_version(current["version"] or "")
        published = parse_version(release["version_text"])
        if installed and published and installed[:3] <= published[:3]:
            result.update({
                "update_available": True, "source": "release",
                "baseline_unknown": True,
                "from": current["version"], "to": release["version_text"],
            })
        else:
            result.update({"update_available": True, "source": "main",
                           "baseline_unknown": True, "from": None,
                           "to": (head or {}).get("short")})
    elif head and not current["commit"]:
        # No release to fall back on: install main and record the commit so the
        # next check is exact.
        result.update({"update_available": True, "source": "main",
                       "baseline_unknown": True, "from": None, "to": head["short"]})

    if head:
        result["latest_commit"] = head["sha"]
        result["latest_commit_short"] = head["short"]
        result["latest_commit_message"] = head["message"]
        result["latest_commit_date"] = head["date"]

    _CACHE.update({"at": now, "data": result})
    return result


def clear_cache() -> None:
    _CACHE.update({"at": 0.0, "data": None})


# --------------------------------------------------------------------------
# archives
# --------------------------------------------------------------------------

def _safe_members(archive) -> list:
    """Reject absolute paths, drive letters and any traversal component."""
    names = []
    for member in archive:
        # zipfile.ZipInfo exposes .filename, tarfile.TarInfo exposes .name
        name = getattr(member, "name", None) or getattr(member, "filename", "") or ""
        name = name.replace("\\", "/")
        if not name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            raise RuntimeError("archive refused: absolute path")
        parts = [part for part in name.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise RuntimeError("archive refused: path traversal")
        names.append((member, "/".join(parts)))
    return names


def extract_archive(archive_path: str, dest: str) -> str:
    """Extract a .zip or .tar.gz into dest, refusing traversal. Returns dest."""
    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            for member, safe in _safe_members(archive.infolist()):
                if member.is_dir():
                    continue
                target = os.path.join(dest, *safe.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
        return dest
    with tarfile.open(archive_path, "r:*") as archive:
        for member, safe in _safe_members(archive.getmembers()):
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            target = os.path.join(dest, *safe.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)
    return dest


def locate_extension_root(root: str) -> str:
    """Find the directory that holds manifest.json in an extracted archive.

    Accepts the release layout (extension/ at the archive root) and the GitHub
    source archive layout (<repo>-<sha>/extension/), so both channels work.
    """
    if os.path.isfile(os.path.join(root, "manifest.json")):
        return root
    candidate = os.path.join(root, "extension")
    if os.path.isfile(os.path.join(candidate, "manifest.json")):
        return candidate
    children = [os.path.join(root, name) for name in sorted(os.listdir(root))]
    children = [path for path in children if os.path.isdir(path)]
    for child in children:
        candidate = os.path.join(child, "extension")
        if os.path.isfile(os.path.join(candidate, "manifest.json")):
            return candidate
    if len(children) == 1 and os.path.isfile(os.path.join(children[0], "manifest.json")):
        return children[0]
    raise RuntimeError("archive refused: no extension/manifest.json inside")


def validate_extension_tree(root: str) -> dict:
    """Refuse anything that is not this extension before touching the live dir."""
    manifest_path = os.path.join(root, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        raise RuntimeError("archive refused: unreadable manifest.json")
    if int(manifest.get("manifest_version") or 0) != 3:
        raise RuntimeError("archive refused: not a Manifest V3 extension")
    if "lightpanda" not in (manifest.get("name") or "").lower():
        raise RuntimeError("archive refused: unexpected extension name")
    if not parse_version(manifest.get("version") or ""):
        raise RuntimeError("archive refused: unparsable version")
    if not os.path.isfile(os.path.join(root, "popup.js")):
        raise RuntimeError("archive refused: incomplete tree")
    return manifest


def _same_file(left: str, right: str) -> bool:
    """Byte comparison that never holds two file handles beyond the loop."""
    try:
        if os.path.getsize(left) != os.path.getsize(right):
            return False
        with open(left, "rb") as a, open(right, "rb") as b:
            while True:
                chunk_a, chunk_b = a.read(65536), b.read(65536)
                if chunk_a != chunk_b:
                    return False
                if not chunk_a:
                    return True
    except OSError:
        return False


def _mirror(src_root: str, dst_root: str) -> tuple:
    """Make dst_root hold exactly the files of src_root (plus kept local files)."""
    copy, remove = [], []
    src_files = {}
    for folder, _dirs, files in os.walk(src_root):
        for name in files:
            absolute = os.path.join(folder, name)
            rel = os.path.relpath(absolute, src_root).replace(os.sep, "/")
            if rel == BUILD_INFO or rel.startswith("__pycache__/"):
                continue
            src_files[rel] = absolute

    for rel, absolute in sorted(src_files.items()):
        target = os.path.join(dst_root, *rel.split("/"))
        if os.path.commonpath([os.path.abspath(target), os.path.abspath(dst_root)]) != os.path.abspath(dst_root):
            raise RuntimeError("refused: write outside the extension directory")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.isfile(target) or not _same_file(target, absolute):
            shutil.copy2(absolute, target)
            copy.append(rel)

    for folder, _dirs, files in os.walk(dst_root):
        for name in files:
            absolute = os.path.join(folder, name)
            rel = os.path.relpath(absolute, dst_root).replace(os.sep, "/")
            if rel in src_files or rel == BUILD_INFO or rel.startswith("__pycache__/"):
                continue
            os.unlink(absolute)
            remove.append(rel)
    return copy, remove


def _backup(ext_dir: str) -> str:
    backup_root = os.path.join(config_dir(), BACKUP_DIRNAME)
    shutil.rmtree(backup_root, ignore_errors=True)
    os.makedirs(backup_root, exist_ok=True)
    _mirror(ext_dir, backup_root)
    info = installed_info(ext_dir)
    meta = {key: info.get(key) for key in ("version", "commit", "tag", "source")}
    meta["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(os.path.join(backup_root, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return backup_root


def _write_build_info(ext_dir: str, payload: dict) -> None:
    payload = dict(payload)
    payload["installed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    payload["repo"] = REPO
    with open(os.path.join(ext_dir, BUILD_INFO), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _checksum_from_assets(assets: list, zip_name: str):
    """Fetch the published sha256 sidecar for a release asset, if there is one."""
    sidecar = None
    for asset in assets:
        if asset["name"] in (zip_name + ".sha256", "SHA256SUMS", "SHA256SUMS.txt"):
            sidecar = asset
            break
    if not sidecar:
        return None
    try:
        text = _fetch(sidecar["url"], limit=64_000, accept="text/plain").decode("utf-8", "replace")
    except Exception:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == zip_name:
            return parts[0].lower()
        if len(parts) == 1 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return None


def apply_update(source: str = "auto", repo: str = REPO) -> dict:
    """Download and install the newest release (or main commit) from GitHub."""
    ext_dir = extension_dir()
    if not ext_dir:
        raise RuntimeError("extension directory not found")
    if not os.access(ext_dir, os.W_OK):
        raise RuntimeError("extension directory is not writable")

    status = check_update(force=True, repo=repo)
    if not status.get("ok"):
        raise RuntimeError(status.get("error") or "update check failed")
    source = status.get("source") if source in ("auto", None) else source
    if source not in ("release", "main"):
        raise RuntimeError("nothing to install: already up to date")

    release = latest_release(repo) if source == "release" else None
    archive_name, archive_url, accept, checksum, tag, commit = "", "", "application/octet-stream", None, None, None

    if source == "release":
        if not release:
            raise RuntimeError("release not found")
        zip_name = ""
        for asset in release["assets"]:
            if asset["name"].lower().endswith(".zip"):
                zip_name = asset["name"]
                archive_name, archive_url = asset["name"], asset["url"]
                checksum = _checksum_from_assets(release["assets"], zip_name)
                break
        if not archive_url:
            # No release asset: fall back to the source archive of the tag.
            tag = release["tag"]
            archive_name = f"source-{tag}.tar.gz"
            archive_url = f"{API}/repos/{repo}/tarball/{urllib.parse.quote(tag)}"
        tag = tag or release["tag"]
        commit = (latest_commit(repo, tag=tag) or {}).get("sha") or release.get("commit")
    else:
        head = latest_commit(repo)
        if not head:
            raise RuntimeError("main branch not found")
        commit = head["sha"]
        tag = None  # main-channel install: no tag to claim
        archive_name = f"source-{head['short']}.tar.gz"
        archive_url = f"{API}/repos/{repo}/tarball/{head['sha']}"

    raw = _fetch(archive_url, accept=accept)
    digest = hashlib.sha256(raw).hexdigest()
    if checksum and digest != checksum:
        raise RuntimeError("checksum mismatch: artifact refused")

    workdir = tempfile.mkdtemp(prefix="lp-bridge-update-")
    try:
        suffix = ".zip" if archive_name.lower().endswith(".zip") else ".tar.gz"
        archive_path = os.path.join(workdir, "artifact" + suffix)
        with open(archive_path, "wb") as fh:
            fh.write(raw)
        extract_dir = os.path.join(workdir, "extract")
        os.makedirs(extract_dir)
        extract_archive(archive_path, extract_dir)
        root = locate_extension_root(extract_dir)
        manifest = validate_extension_tree(root)

        previous = installed_info(ext_dir)
        backup_root = _backup(ext_dir)
        copy, remove = _mirror(root, ext_dir)
        _write_build_info(ext_dir, {
            "version": manifest.get("version"),
            "manifest_version": manifest.get("manifest_version"),
            "tag": tag,
            "commit": commit,
            "source": source,
            "artifact": archive_name,
            "sha256": digest,
            "release_url": (release or {}).get("html_url"),
            "previous": {key: previous.get(key) for key in ("version", "commit", "tag")},
        })
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    clear_cache()
    return {
        "ok": True,
        "source": source,
        "version": manifest.get("version"),
        "tag": tag,
        "commit": commit,
        "commit_short": (commit or "")[:8] or None,
        "artifact": archive_name,
        "sha256": digest,
        "checksum_verified": bool(checksum),
        "files_written": len(copy),
        "files_removed": len(remove),
        "previous": {key: previous.get(key) for key in ("version", "commit", "tag")},
        "backup": backup_root,
        "reload_required": True,
    }


def rollback_update() -> dict:
    """Restore the tree saved by the previous update (undo)."""
    ext_dir = extension_dir()
    if not ext_dir:
        raise RuntimeError("extension directory not found")
    backup_root = os.path.join(config_dir(), BACKUP_DIRNAME)
    meta = read_backup_meta()
    if not meta.get("version") or not os.path.isfile(os.path.join(backup_root, "manifest.json")):
        raise RuntimeError("no backup to restore")
    manifest = validate_extension_tree(backup_root)
    current = installed_info(ext_dir)
    copy, remove = _mirror(backup_root, ext_dir)
    _write_build_info(ext_dir, {
        "version": manifest.get("version"),
        "manifest_version": manifest.get("manifest_version"),
        "tag": meta.get("tag"),
        "commit": meta.get("commit"),
        "source": "rollback",
        "previous": {key: current.get(key) for key in ("version", "commit", "tag")},
    })
    shutil.rmtree(backup_root, ignore_errors=True)
    clear_cache()
    return {"ok": True, "version": manifest.get("version"), "tag": meta.get("tag"),
            "commit": meta.get("commit"), "files_written": len(copy),
            "files_removed": len(remove), "reload_required": True}
