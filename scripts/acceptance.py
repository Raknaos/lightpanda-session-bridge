# -*- coding: utf-8 -*-
"""Acceptance gate: the whole product, not one piece of it.

Every real failure this project shipped came from a seam that the unit tests
could not see - they each tested a piece in isolation:

  * v0.4.3  a bump left `updates.xml` behind;
  * v0.5.0  the update path was never run against the real GitHub redirect;
  * v0.5.2  the CDN hostname was missing from the allow-list, so every install
            aborted at "update redirect refused";
  * v0.5.4  the popup grew past Chrome's 600px cap and the update button was
            sliced off the bottom - it existed, nobody could click it;
  * v0.5.5  the main channel sent `Accept: application/octet-stream` to
            api.github.com, which answers 415 before sending a byte;
  * + a reload script whose 33-character extension id opened an error page and
    printed success, and a mirror that rewrote every file because the checkout
    wrote CRLF while GitHub serves LF.

So this script checks the seams, in the order they bite: the repo must be
self-consistent before anything is committed, and the live system must actually
do the thing afterwards.

    python scripts/acceptance.py              # repo checks + live checks
    python scripts/acceptance.py --local      # repo checks only (no network)
    python scripts/acceptance.py --live       # live checks only
    python scripts/acceptance.py --quiet      # only the failures and the verdict

Exit code is the number of failures (0 = go). A SKIP never fails: it means the
service for that check is not running on this machine, and it says so by name.

Never prints a cookie value, a token or a page URL: names, counts, versions and
HTTP codes only.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
EXT = REPO / "extension"
CONFIG = pathlib.Path(os.path.expanduser("~"), ".config", "lightpanda-bridge")
RELAY = "http://127.0.0.1:8765"
COMET_CDP = "http://127.0.0.1:9223"
LIGHTPANDA_CDP = "http://127.0.0.1:9222"
LANGS = ["en", "fr", "es", "de", "zh", "ja", "it", "pt", "ar", "ru"]

sys.path.insert(0, str(REPO / "relay"))


def use_github_token():
    """Borrow gh's token for this process when it is available.

    Anonymous GitHub allows 60 requests/hour per IP, and the gate makes several
    calls per run - enough to exhaust the quota and turn every later check into
    a false failure. `gh auth token` is read, never printed.
    """
    if os.environ.get("LP_BRIDGE_GITHUB_TOKEN"):
        return "env"
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, timeout=30)
    except Exception:
        return "none"
    token = (out.stdout or b"").decode("utf-8", errors="replace").strip()
    if out.returncode or not token:
        return "none"
    os.environ["LP_BRIDGE_GITHUB_TOKEN"] = token
    return "gh"


def rate_limited(err) -> bool:
    text = str(err).lower()
    return "rate limit" in text or "403" in text and "limit" in text

RESULTS = []  # (status, name, detail)


def record(status, name, detail=""):
    RESULTS.append((status, name, detail))


def check(name):
    """Decorator: run one check, turn an exception into a FAIL, print as we go."""
    def wrap(fn):
        def run(*args, **kwargs):
            try:
                status, detail = fn(*args, **kwargs)
            except Exception as err:  # a crashing check is a failing check
                status, detail = "FAIL", "%s: %s" % (type(err).__name__, err)
            record(status, name, detail)
            if status == "FAIL" or (status == "SKIP" and not QUIET):
                colour = {"FAIL": "\033[31m", "SKIP": "\033[33m"}.get(status, "")
                print("%s%-4s\033[0m %-38s %s" % (colour, status, name, detail))
            elif not QUIET:
                print("\033[32mok  \033[0m %-38s %s" % (name, detail))
            return status == "FAIL"
        return run
    return wrap


def git(*args):
    out = subprocess.run(["git", "-C", str(REPO)] + list(args), capture_output=True, text=True)
    return out.stdout.strip()


_TAG_CACHE = {}


def released(version: str) -> bool:
    """Has this version been tagged, i.e. published?

    Local tags are not enough: releases are created with `gh release create`,
    which tags on the remote only, so `git tag` here stopped at v0.4.2 while the
    remote already had v0.5.5 - and a check built on local tags alone would have
    quietly turned into a SKIP forever. The remote is asked once per run.
    """
    if "tags" not in _TAG_CACHE:
        tags = set(git("tag").split())
        confirmer = subprocess.run(["git", "-C", str(REPO), "fetch", "--tags", "--quiet"],
                                   capture_output=True, timeout=90)
        if confirmer.returncode == 0:
            tags |= set(git("tag").split())
        _TAG_CACHE["tags"] = tags
        _TAG_CACHE["reliable"] = confirmer.returncode == 0
        _TAG_CACHE["detail"] = "" if confirmer.returncode == 0 else " (remote tags unreachable)"
    return ("v%s" % version) in _TAG_CACHE["tags"]


def manifest():
    return json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))


def relay_call(method, path, payload=None, headers=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(RELAY + path, data=data, method=method,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read().decode() or "{}")
        except Exception:
            return err.code, {}


def pinned_id():
    return (CONFIG / "pinned_extension_id").read_text(encoding="utf-8").strip()


def bridge_token():
    return (CONFIG / "secret").read_text(encoding="utf-8").strip()


def bridge_headers(extra=None):
    head = {"Content-Type": "application/json",
            "Origin": "chrome-extension://" + pinned_id(),
            "X-Bridge-Token": bridge_token()}
    head.update(extra or {})
    return head


# ---------------------------------------------------------------------------
# 1. the repo is self-consistent
# ---------------------------------------------------------------------------

@check("versions agree everywhere")
def versions_agree():
    version = manifest()["version"]
    problems = []
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    if 'version = "%s"' % version not in pyproject:
        problems.append("pyproject.toml")
    xml = (REPO / "updates.xml").read_text(encoding="utf-8")
    if xml.count(version) != 2:
        problems.append("updates.xml (%d/2)" % xml.count(version))
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    if ("## [%s]" % version) not in changelog:
        problems.append("CHANGELOG.md")
    if not (REPO / "docs" / "releases" / ("%s.md" % version)).exists():
        problems.append("docs/releases/%s.md" % version)
    zip_name = (REPO / "scripts" / "build_release_zip.py").read_text(encoding="utf-8")
    if "lightpanda-session-bridge-{version}.zip" not in zip_name:
        problems.append("build_release_zip.py")
    if problems:
        return "FAIL", "manifest=%s but %s" % (version, ", ".join(problems))
    return "ok", "v%s in manifest, pyproject, updates.xml, CHANGELOG, notes" % version


@check("shipped tree is LF everywhere")
def shipped_tree_lf():
    bad = []
    for path in sorted(EXT.rglob("*")):
        if not path.is_file() or path.suffix.lower() in (".png", ".woff2", ".ico"):
            continue
        if b"\r\n" in path.read_bytes():
            bad.append(path.relative_to(EXT).as_posix())
    if bad:
        return "FAIL", "CRLF in %s" % ", ".join(bad[:4])
    return "ok", "no CRLF in the shipped tree"


@check("no scaffolding in the shipped tree")
def no_scaffolding():
    junk = [p.relative_to(EXT).as_posix() for p in EXT.rglob("*")
            if p.is_file() and (p.name.startswith("_") or p.suffix in (".py", ".map", ".log"))]
    if junk:
        return "FAIL", "would ship: %s" % ", ".join(junk[:5])
    return "ok", "%d files, nothing foreign" % len([p for p in EXT.rglob("*") if p.is_file()])


@check("build provenance matches the manifest")
def provenance_matches():
    path = EXT / ".build-info.json"
    if not path.exists():
        return "SKIP", "no local install on this machine (gitignored artifact)"
    info = json.loads(path.read_text(encoding="utf-8"))
    if info.get("version") != manifest()["version"]:
        import updater
        if updater.is_newer(manifest()["version"], info.get("version") or "0.0.0"):
            return "SKIP", ("repo ships v%s, v%s is installed: release and install pending%s"
                            % (manifest()["version"], info.get("version"), _TAG_CACHE.get("detail", "")))
        return "FAIL", "installed %s, manifest %s" % (info.get("version"), manifest()["version"])
    return "ok", "installed v%s from %s (%s)" % (info["version"], info.get("source"), (info.get("commit") or "")[:8])


@check("no extension id differs from the pin")
def ids_agree():
    """A 33-character id is the typo class that already cost a day (a reload
    script that opened an error page and reported success). Only tracked text
    files are judged, and an obvious fixture - four identical characters in a
    row, like the aaaa... ids the tests use - is not a wrong id."""
    pin = pinned_id()
    if not re.match(r"^[a-p]{32}$", pin):
        return "FAIL", "the pin itself is not 32 chars: %d" % len(pin)
    tracked = git("ls-files").split()
    binary = (".png", ".woff2", ".ico", ".zip", ".pdf", ".lock")
    offenders = []
    for rel in tracked:
        path = REPO / rel
        if path.suffix.lower() in binary or "neo-upstream" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for found in set(re.findall(r"\b([a-p]{31,36})\b", text)):
            if found == pin or re.search(r"([a-p])\1{3}", found):
                continue
            offenders.append("%s:%s car" % (rel, len(found)))
    if offenders:
        return "FAIL", "id literal that is not the pin - %s" % ", ".join(sorted(set(offenders))[:4])
    return "ok", "every id literal in %d tracked files is the pinned 32-char id" % len(tracked)


@check("the shared secret is absent from the repo")
def secret_absent():
    secret = bridge_token()
    if len(secret) < 8:
        return "SKIP", "no shared secret on this machine"
    leaked = []
    for path in REPO.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            if secret.encode() in path.read_bytes():
                leaked.append(path.relative_to(REPO).as_posix())
        except OSError:
            continue
    if leaked:
        return "FAIL", "secret found in %s" % ", ".join(leaked[:3])
    return "ok", "not in any tracked or untracked file"


@check("every language has the same strings")
def i18n_parity():
    js = (EXT / "popup.js").read_text(encoding="utf-8")
    block = js[js.index("const I18N"):js.index("function t(")] if "const I18N" in js else js
    # each language is one object literal: `en: {` ... `},`
    key_sets = {}
    for lang in LANGS:
        m = re.search(r"\n  %s: \{(.*?)\n  \},?\n" % lang, block, re.S)
        if not m:
            return "FAIL", "language %s not found" % lang
        key_sets[lang] = set(re.findall(r"^\s{4}(\w+):", m.group(1), re.M))
    base = key_sets["en"]
    for lang, keys in key_sets.items():
        missing, extra = base - keys, keys - base
        if missing or extra:
            return "FAIL", "%s missing=%s extra=%s" % (lang, sorted(missing)[:3], sorted(extra)[:3])
    used = set(re.findall(r"\bt\('([A-Za-z0-9_]+)'", js))
    unknown = used - base
    if unknown:
        return "FAIL", "popup.js calls t('%s') with no translation" % sorted(unknown)[0]
    return "ok", "%d keys x %d languages" % (len(base), len(LANGS))


@check("every element popup.js touches exists in popup.html")
def dom_ids_exist():
    js = (EXT / "popup.js").read_text(encoding="utf-8")
    html = (EXT / "popup.html").read_text(encoding="utf-8")
    wanted = set(re.findall(r"getElementById\(\s*'([A-Za-z0-9_-]+)'", js))
    wanted |= set(re.findall(r"querySelector\(\s*'#([A-Za-z0-9_-]+)'", js))
    present = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
    missing = sorted(wanted - present)
    if missing:
        return "FAIL", "popup.html has no #%s" % ", #".join(missing[:4])
    return "ok", "%d ids referenced, all present" % len(wanted)


@check("python files compile")
def python_compiles():
    bad = []
    for path in list(REPO.rglob("*.py")):
        if ".git" in path.parts:
            continue
        out = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                             capture_output=True, text=True)
        if out.returncode:
            bad.append(path.relative_to(REPO).as_posix())
    if bad:
        return "FAIL", ", ".join(bad[:4])
    return "ok", "every .py compiles"


def project_python() -> str:
    """The interpreter the project is meant to run under.

    `python scripts/acceptance.py` inherits whatever interpreter was typed, and a
    bare python on this machine can lack `websocket-client`: two test modules
    then fail to import and the suite silently reports 56 tests instead of 111.
    The venv is the reference whenever it exists.
    """
    name = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    candidate = REPO / ".venv" / name
    return str(candidate) if candidate.exists() else sys.executable


@check("the unit suite passes")
def unit_suite():
    interpreter = project_python()
    out = subprocess.run([interpreter, "-m", "unittest", "discover", "-s", "tests"],
                         cwd=str(REPO), capture_output=True, timeout=900)
    text = (out.stdout or b"").decode("utf-8", "replace") + (out.stderr or b"").decode("utf-8", "replace")
    summary = [ln for ln in text.splitlines()
               if ln.startswith("Ran ") or ln.startswith("OK") or ln.startswith("FAILED")]
    where = ".venv" if ".venv" in interpreter else pathlib.Path(interpreter).name
    missing = "ModuleNotFoundError" in text or "ImportError" in text
    if out.returncode:
        detail = " | ".join(summary[-2:]) or "unittest failed"
        if missing:
            detail += " (a module cannot import: pip install -r requirements.txt)"
        return "FAIL", "%s [%s]" % (detail, where)
    return "ok", "%s [%s]" % (" | ".join(summary[-2:]), where)


@check("the popup still fits Chrome's 600px cap")
def popup_fits():
    script = REPO / "scripts" / "diagnostics" / "preview_popup.py"
    if not script.exists():
        return "SKIP", "preview_popup.py missing"
    out = subprocess.run([sys.executable, str(script), "--state", "available", "--no-shot"],
                         capture_output=True, text=True, timeout=300)
    if "no Chrome" in (out.stderr or "") or "no Chrome" in (out.stdout or ""):
        return "SKIP", "no Chrome/Edge on this machine"
    first = [ln.strip() for ln in out.stdout.splitlines() if "default state" in ln]
    if out.returncode:
        return "FAIL", (first or ["preview exited %d" % out.returncode])[0]
    return "ok", first[0] if first else "fits"


# ---------------------------------------------------------------------------
# 2. the live system does the thing
# ---------------------------------------------------------------------------

@check("relay answers /health")
def relay_health():
    with urllib.request.urlopen(RELAY + "/health", timeout=8) as resp:
        data = json.loads(resp.read().decode())
    if not data.get("ok"):
        return "FAIL", "health said %s" % data
    return "ok", "service=%s attached=%s" % (data.get("service"), data.get("attached"))


@check("relay refuses an unauthorised or foreign caller")
def relay_auth():
    code_no_token, _ = relay_call("GET", "/v1/sessions", headers={"Origin": "chrome-extension://" + pinned_id()})
    code_foreign, _ = relay_call("GET", "/v1/sessions", headers={"Origin": "https://evil.example"})
    code_ok, _ = relay_call("GET", "/v1/sessions", headers=bridge_headers())
    if code_ok != 200:
        return "FAIL", "authorised call answered %d" % code_ok
    if code_no_token != 401:
        return "FAIL", "no token answered %d, expected 401" % code_no_token
    if code_foreign != 403:
        return "FAIL", "foreign origin answered %d, expected 403" % code_foreign
    return "ok", "401 without token, 403 foreign origin, 200 with both"


@check("the update check reads GitHub")
def update_check():
    code, data = relay_call("GET", "/v1/update/check", headers=bridge_headers())
    if code != 200 or not data.get("ok"):
        detail = str(data.get("error") or "")
        if data.get("error_kind") == "rate_limit" or "rate limit" in detail.lower():
            return "SKIP", ("%s - the relay calls GitHub anonymously; put a token in "
                            "~/.config/lightpanda-bridge/github_token to lift it" % detail)
        return "FAIL", "HTTP %d %s" % (code, detail)
    if data.get("current_version") != manifest()["version"]:
        return "FAIL", "relay sees %s, repo has %s" % (data.get("current_version"), manifest()["version"])
    if data.get("update_available"):
        return "ok", "update offered: %s -> %s" % (
            (data.get("current_commit") or "")[:8], (data.get("latest_commit") or "")[:8])
    return "ok", "up to date at v%s (%s)" % (data.get("current_version"), (data.get("current_commit") or "")[:8])


@check("the release asset downloads and matches its sidecar")
def release_asset():
    import updater
    try:
        return _release_asset(updater)
    except Exception as err:
        if rate_limited(err):
            return "SKIP", "GitHub quota exhausted: %s" % err
        raise


def _release_asset(updater):
    release = updater.latest_release()
    if not release:
        return "FAIL", "no release found"
    zip_asset = next((a for a in release["assets"] if a["name"].endswith(".zip")), None)
    sha_asset = next((a for a in release["assets"] if a["name"].endswith(".sha256")), None)
    if not zip_asset or not sha_asset:
        return "FAIL", "release %s has no zip+sha256 pair" % release["tag"]
    blob = updater._fetch(zip_asset["url"], accept="application/octet-stream")
    digest = hashlib.sha256(blob).hexdigest()
    published = updater._fetch(sha_asset["url"], accept="application/octet-stream").decode().split()[0]
    if digest != published:
        return "FAIL", "sha256 %s != published %s" % (digest[:12], published[:12])
    return "ok", "%s %d KiB, sha256 matches the sidecar" % (release["tag"], len(blob) // 1024)


@check("the main channel can fetch its tarball")
def main_tarball():
    """The 415 that broke this channel was answered before a single byte of the
    archive moved. So the check reads the first kilobyte through the same
    _fetch (same allow-list, same Accept rule) with a limit smaller than the
    archive: arriving at "artifact too large" means GitHub streamed it, which is
    exactly what a 415 forbids."""
    import updater
    try:
        head = updater.latest_commit()
    except Exception as err:
        if rate_limited(err):
            return "SKIP", "GitHub quota exhausted: %s" % err
        raise
    if not head:
        return "FAIL", "cannot read main"
    url = "%s/repos/%s/tarball/%s" % (updater.API, updater.REPO, head["sha"])
    try:
        blob = updater._fetch(url, accept="application/octet-stream", limit=64_000)
    except RuntimeError as err:
        if "too large" in str(err):
            return "ok", "commit %s: GitHub streamed past 64 KiB (no 415)" % head["short"]
        raise
    return "ok", "commit %s: first %d KiB accepted" % (head["short"], len(blob) // 1024)


@check("Lightpanda answers on CDP")
def lightpanda_up():
    with urllib.request.urlopen(LIGHTPANDA_CDP + "/json/version", timeout=8) as resp:
        data = json.loads(resp.read().decode())
    return "ok", (data.get("Browser") or "connected")


@check("the relay's CDP proxy executes")
def cdp_proxy():
    code, data = relay_call("POST", "/v1/cdp", {"method": "Runtime.evaluate",
                                                "params": {"expression": "21*2", "returnByValue": True}},
                            headers=bridge_headers(), timeout=60)
    if code != 200 or not data.get("ok"):
        return "FAIL", "HTTP %d %s" % (code, data.get("error"))
    value = json.dumps(data.get("result") or data)[:80]
    if "42" not in value:
        return "FAIL", "expected 42 in %s" % value
    return "ok", "Runtime.evaluate answered 42 on the daemon's connection"


@check("a session round-trips through the real import")
def session_roundtrip():
    # example.com: a real, resolvable, public https origin. The relay refuses a
    # private or unresolvable one on purpose (anti-SSRF), and `.invalid` does not
    # resolve - the first version of this check failed for that reason.
    origin = "https://example.com"
    code, data = relay_call("POST", "/v1/session/import", {
        "origin": origin,
        "cookies": [{"name": "acceptance_probe", "value": "1", "domain": "example.com",
                     "path": "/", "expires": 0, "httpOnly": False, "secure": False, "sameSite": "Lax"}],
        "storage": {"acceptance_probe": "1"},
    }, headers=bridge_headers(), timeout=120)
    if code != 200 or not data.get("ok"):
        return "FAIL", "import answered HTTP %d %s" % (code, data.get("error"))
    listed = relay_call("GET", "/v1/sessions", headers=bridge_headers())
    origins = [s.get("origin") for s in (listed[1].get("sessions") or [])]
    cleared = relay_call("POST", "/v1/sessions/clear", {"origin": origin}, headers=bridge_headers())
    if origin not in origins:
        return "FAIL", "imported but not listed (%s)" % origins
    if cleared[0] != 200:
        return "FAIL", "could not clear the probe session"
    return "ok", "cookies+storage imported, listed, then cleared"


@check("the extension in Comet serves the repo version")
def extension_live_version():
    import websocket
    with urllib.request.urlopen(COMET_CDP + "/json/version", timeout=5) as resp:
        ws_url = json.loads(resp.read().decode())["webSocketDebuggerUrl"]
    ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)
    seq = [0]

    def cmd(method, params=None, session=None):
        seq[0] += 1
        msg = {"id": seq[0], "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        ws.send(json.dumps(msg))
        while True:
            data = json.loads(ws.recv())
            if data.get("id") == seq[0]:
                return data

    try:
        target = cmd("Target.createTarget",
                     {"url": "chrome-extension://%s/popup.html" % pinned_id()}).get("result", {}).get("targetId")
        sid = cmd("Target.attachToTarget", {"targetId": target, "flatten": True}).get("result", {}).get("sessionId")
        seen = None
        for _ in range(10):
            seen = cmd("Runtime.evaluate", {"expression": "chrome && chrome.runtime && chrome.runtime"
                                                          ".getManifest ? chrome.runtime.getManifest().version : null",
                                            "returnByValue": True}, session=sid).get("result", {}).get("result", {}).get("value")
            if seen:
                break
        cmd("Target.closeTarget", {"targetId": target})
    finally:
        ws.close()
    if not seen:
        return "FAIL", "the popup does not answer at the pinned id"
    if seen != manifest()["version"]:
        if not released(manifest()["version"]):
            return "SKIP", ("Comet serves v%s, the repo ships v%s (not released yet): reload after "
                            "the release, scripts/reload_extension.py%s"
                            % (seen, manifest()["version"], _TAG_CACHE.get("detail", "")))
        return "FAIL", "loaded v%s, repo has v%s - run scripts/reload_extension.py" % (seen, manifest()["version"])
    return "ok", "popup serves v%s" % seen


@check("the last install is logged without secrets")
def audit_log():
    path = CONFIG / "update.log"
    if not path.exists():
        return "SKIP", "no install recorded yet on this machine"
    lines = [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines() if row.strip()]
    if not lines:
        return "FAIL", "update.log exists but is empty"
    last = lines[-1]
    for forbidden in ("cookie", "token", "secret", "url", "origin", "headers", "value"):
        if forbidden in last:
            return "FAIL", "the log line carries %r" % forbidden
    return "ok", "%d install(s), last v%s at %s" % (len(lines), last.get("version"), last.get("at"))


@check("the pinned id matches the declared one")
def pin_matches_declaration():
    """The relay pins whatever extension paired first; updates.xml declares the
    id Chrome's auto-update uses. If they drift, one of the two copied ids is
    wrong - which is exactly how a 33-character id survived in two scripts."""
    import cdp_utils
    declared = cdp_utils.declared_extension_id()
    if not re.match(r"^[a-p]{32}$", declared):
        return "FAIL", "updates.xml declares %r" % declared
    try:
        pinned = pinned_id()
    except OSError:
        return "SKIP", "no pin on this machine yet"
    if pinned != declared:
        return "FAIL", "pin %d car vs updates.xml %d car" % (len(pinned), len(declared))
    return "ok", "pin and updates.xml agree (%s...%s)" % (pinned[:4], pinned[-4:])


@check("the auto-update manifest points at a live asset")
def updates_xml_live():
    """v0.3.3 shipped a security patch that the auto-update channel never
    distributed because updates.xml still named the previous zip. The string is
    checked against the manifest above; this checks the URL actually resolves."""
    xml = (REPO / "updates.xml").read_text(encoding="utf-8")
    url = re.search(r"codebase='([^']+)'", xml).group(1)
    if "lightpanda-session-bridge-%s.zip" % manifest()["version"] not in url:
        return "FAIL", "the url names another version: %s" % url.rsplit("/", 1)[-1]
    if not released(manifest()["version"]):
        return "SKIP", ("release v%s is not published yet - the url cannot resolve before it is%s"
                        % (manifest()["version"], _TAG_CACHE.get("detail", "")))
    request = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "lightpanda-session-bridge-acceptance"})
    # /releases/latest/download/ can answer 404 for a minute right after the
    # release is published, so retry before calling it broken - a permanent 404
    # still fails.
    import time
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                size = int(resp.headers.get("Content-Length") or 0)
                resp.read(2048)
            if resp.status == 200 and size >= 50_000:
                return "ok", "%s resolves, %d KiB" % (url.rsplit("/", 1)[-1], size // 1024)
            last = "HTTP %s, %d bytes" % (resp.status, size)
        except urllib.error.HTTPError as err:
            last = "HTTP %s %s" % (err.code, err.reason)
        if attempt < 2:
            time.sleep(6)
    return "FAIL", "%s (three attempts)" % last
    return "ok", "%s resolves, %d KiB" % (url.rsplit("/", 1)[-1], size // 1024)


@check("exactly one relay listens on the port")
def single_relay():
    """A second, session-less relay once answered alongside the real one on
    Windows, because SO_REUSEADDR let it bind the same port; agents then saw an
    empty jar while /health still said ok."""
    try:
        # bytes, decoded tolerantly: netstat writes cp850 on a French Windows and
        # text=True dies in the reader thread, leaving stdout None
        raw = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=30).stdout
    except Exception:
        return "SKIP", "netstat unavailable"
    if raw is None:
        return "SKIP", "netstat gave no output"
    out = raw.decode("utf-8", errors="replace")
    listeners = [ln for ln in out.splitlines() if ":8765" in ln and "LISTENING" in ln.upper()]
    pids = {ln.split()[-1] for ln in listeners}
    if len(listeners) == 0:
        return "FAIL", "nothing listens on 8765"
    if len(pids) > 1:
        return "FAIL", "%d processes listening on 8765: %s" % (len(pids), sorted(pids))
    return "ok", "one listener (pid %s)" % sorted(pids)[0]


@check("Comet and the relay agree on the pinned id")
def double_check_pin():
    code, data = relay_call("GET", "/v1/update/check",
                            headers={"Origin": "chrome-extension://" + pinned_id()})
    if code != 200:
        return "FAIL", "the relay refused the pinned origin (%d)" % code
    return "ok", "relay accepts %s...%s" % (pinned_id()[:4], pinned_id()[-4:])


LOCAL = [versions_agree, shipped_tree_lf, no_scaffolding, provenance_matches, ids_agree,
         pin_matches_declaration,
         secret_absent, i18n_parity, dom_ids_exist, python_compiles, unit_suite, popup_fits]
LIVE = [relay_health, single_relay, relay_auth, update_check, release_asset, main_tarball,
        lightpanda_up, cdp_proxy, session_roundtrip, extension_live_version, updates_xml_live,
        audit_log, double_check_pin]


def main():
    global QUIET
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="repo checks only")
    ap.add_argument("--live", action="store_true", help="live checks only")
    ap.add_argument("--quiet", action="store_true", help="print failures and the verdict only")
    args = ap.parse_args()
    QUIET = args.quiet

    if not args.local:
        source = use_github_token()
        if not args.quiet:
            print("GitHub auth: %s\n" % ("gh token" if source == "gh" else
                                          "environment" if source == "env" else
                                          "anonymous (60/h - the gate may skip on quota)"))
    todo = LIVE if args.live else (LOCAL if args.local else LOCAL + LIVE)
    print("acceptance: %d checks (%s)\n" % (len(todo), "live" if args.live else "local" if args.local else "local + live"))
    for fn in todo:
        fn()

    failures = [r for r in RESULTS if r[0] == "FAIL"]
    skips = [r for r in RESULTS if r[0] == "SKIP"]
    print("\n%d checks: %d ok, %d failed, %d skipped" %
          (len(RESULTS), len(RESULTS) - len(failures) - len(skips), len(failures), len(skips)))
    for _, name, detail in failures:
        print("  FAIL %s - %s" % (name, detail))
    for _, name, detail in skips:
        print("  skip %s - %s" % (name, detail))
    if failures:
        print("\nNOT READY: fix the failures above before committing or releasing.")
    else:
        print("\nREADY: every check passed.")
    return len(failures)


if __name__ == "__main__":
    QUIET = False
    sys.exit(main())
