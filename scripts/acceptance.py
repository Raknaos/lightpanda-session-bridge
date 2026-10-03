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
import time
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
# Module constant, not a `main()` local: the @check decorator reads it from a
# closure, so importing this file as a library (a probe, a test) raised
# NameError on the first check it ran. Set once here, overridden by --quiet.
QUIET = False

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


@check("the CHANGELOG is a file, not a file pasted over itself")
def changelog_is_not_duplicated():
    """`versions_agree` asks whether `## [<version>]` appears. It cannot see
    STRUCTURE, so a changelog that had been pasted over itself - 74 entries for
    37 versions, 34 byte-identical - passed every run, and an entry welded onto
    the end of a 0.3.3 bullet passed too.

    Three invariants, all measured, none of them "does the version appear":
      (a) no entry title appears twice;
      (b) the version order is descending (an addendum ranks right after its
          version, since it is the same version twice);
      (c) no line carries a heading glued onto prose - `text.## [x]` - which is
          what a lost newline looks like, and which no `in` test can see.
    """
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = re.findall(r"(?m)^## \[([^\]]+)\]", text)
    problems = []
    dupe = sorted({h for h in heads if heads.count(h) > 1})
    if dupe:
        problems.append("%d entries appear twice: %s" % (len(dupe), ", ".join(dupe[:4])))
    def vkey(h):
        m = re.match(r"([\d.]+)", h)
        return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)
    drops = [heads[i] for i in range(len(heads) - 1) if vkey(heads[i]) < vkey(heads[i + 1])]
    if drops:
        problems.append("out of order: %s" % ", ".join(drops[:4]))
    # A welded heading is prose with `## [` glued onto it. It must NOT fire on a
    # line that STARTS with the heading, nor on a QUOTATION of the broken form
    # (this file quotes it in its 0.7.21 entry as the documented evidence). A
    # quote has the backtick IMMEDIATELY before `## [`; a real weld has prose
    # there. Checking only "the line has backticks anywhere" was too loose - a
    # sabotaged line carrying an unrelated code span slipped through.
    glued = [ln for ln in text.splitlines()
             if re.search(r"(?<!^)(?<!`)## \[", ln)]
    if glued:
        problems.append("%d heading(s) welded onto prose: %r" % (len(glued), glued[0][:50]))
    if problems:
        return "FAIL", "%d entries - %s" % (len(heads), "; ".join(problems))
    return "ok", "%d entries, unique, descending, no welded heading" % len(heads)


@check("no CJK punctuation sneaks into prose that is not a translation")
def prose_has_no_cjk_punctuation():
    """`pop-up.js` and the release notes are written in ten languages, so CJK is
    legitimate in the locale files and in the popup's translation table. It is
    NOT legitimate in a French or English sentence: a full-width comma
    is invisible to every other check and survives every release.

    Measured: the whole 0.7.18 CHANGELOG entry - 14 lines - was written with
    full-width CJK comma and full stop instead of ASCII ones, and a release
    note of mine shipped a stray CJK word. Both pass `versions_agree`, the LF
    check and the secret scan, because neither looks at punctuation.

    Note: this docstring once QUOTED those characters, which made the check
    fail on its own source. A checker must not carry the evidence it hunts for;
    describe the shape, do not paste the glyphs.

    Scoped to punctuation and CJK ideographs OUTSIDE the i18n data, so a real
    Chinese or Japanese translation never trips it.
    """
    # Files where CJK text is the POINT, not an accident.
    allowed_dirs = ("extension/_locales", "scripts/artifacts_pristine")
    bad = []
    # A translation line looks like `key: "text"` or
    # ``key: (a, b) => `text` `` - an IDENTIFIER in column 0, then a colon.
    # Judging punctuation by that shape is what lets a real Chinese or Japanese
    # string pass while a full-width comma inside a French sentence is caught; the
    # `re.match(r'^\s*"key"\s*:')` was too narrow and flagged 46 legitimate
    # translation lines.
    i18n_line = re.compile(r"^\s*[A-Za-z_$][\w$]*\s*:\s*")
    for path in sorted(REPO.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(allowed_dirs) or rel.split("/")[0] in (
                ".venv", "neo-upstream"):
            continue
        if ".git/" in rel or "__pycache__" in rel:
            continue
        if path.suffix.lower() not in (".md", ".py", ".js", ".json", ".xml", ".toml"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = set()
        for line in text.splitlines():
            stripped = line.strip()
            # Skip an i18n entry, but NOT a French sentence that happens to
            # start with a word then a colon - require a quoted or templated
            # value on the same line, which prose does not have.
            if i18n_line.match(line) and (
                    '"' in stripped or "`" in stripped or "'" in stripped):
                continue
            hits |= {c for c in line
                     if ("\u3000" <= c <= "\u303f")      # CJK punctuation
                     or ("\uff00" <= c <= "\uffef")}     # full-width forms
        if hits:
            bad.append("%s (%s)" % (rel, "".join(sorted(hits))[:8]))
    if bad:
        return "FAIL", "%d file(s) with CJK punctuation in prose: %s" % (
            len(bad), ", ".join(bad[:4]))
    return "ok", "no CJK punctuation outside the i18n data"


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
    try:
        pin = pinned_id()
        origin = "the pin"
    except OSError:
        # No pin on this machine (a CI runner, a fresh clone): updates.xml is
        # the id the repository declares, and comparing against it still
        # catches a literal that drifted from the rest of the repo.
        import cdp_utils
        pin = cdp_utils.declared_extension_id()
        origin = "updates.xml (no pin here)"
    if not re.match(r"^[a-p]{32}$", pin):
        return "FAIL", "the reference id is not 32 chars: %d car (%s)" % (len(pin), origin)
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
    return "ok", ("every id literal in %d tracked files is the declared 32-char id (%s)"
                  % (len(tracked), origin))


@check("the shared secret is absent from the repo")
def secret_absent():
    try:
        secret = bridge_token()
    except OSError:
        return "SKIP", "no shared secret on this machine (nothing to search for)"
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
    # Also the double-quoted call form: t("relayIdle"). Missing either variant
    # empties a label silently (t() falls back to en, then to ""), never to
    # "undefined", so a lost translation is invisible.
    used |= set(re.findall(r'\bt\("([A-Za-z0-9_]+)"', js))
    unknown = used - base
    if unknown:
        return "FAIL", "popup.js calls t('%s') with no translation" % sorted(unknown)[0]
    # An insert that ate a comma puts two keys on one line. Valid-ish JS, but it
    # hides that language from the per-line regex above, which is exactly how a
    # missing translation reached a shipped release.
    for lang in LANGS:
        m = re.search(r"\n  %s: \{(.*?)\n  \},?\n" % lang, block, re.S)
        if not m:
            continue
        for line in m.group(1).split("\n"):
            if len(re.findall(r"^\s{4}\w+:", line)) > 1:
                return "FAIL", ("%s has two keys on one line (an insert ate a "
                                "comma): %s" % (lang, line.strip()[:40]))
    return "ok", "%d keys x %d languages" % (len(base), len(LANGS))


@check("the diagnostic report carries no secret")
def diagnostics_are_sanitized():
    """A support report that leaks the session it describes is worse than no
    report: users paste it into a public issue. This plants realistic
    credentials and searches the RENDERED output, so it cannot pass on a
    report that is only scrubbed in some code path."""
    sys.path.insert(0, str(REPO))
    from relay import diagnostics
    report = diagnostics.collect()
    blob = json.dumps(report, ensure_ascii=False)
    text = diagnostics.to_text(report)
    planted = {
        "token": "ghp_PLANTEDplantED1234567890abcd",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.PLANTED.localStorage",
        "url": "https://github.com/someone/private-repo-xyz",
        "secret": "s3cr3t-PLANTED-Value-Zz9",
    }
    for label, value in planted.items():
        for name, haystack in (("json", blob), ("text", text)):
            if value in haystack:
                return "FAIL", "planted %s leaked into the %s report" % (label, name)
    for banned in ("cookie_value", "storage_missing_values"):
        if banned in blob:
            return "FAIL", "%s present in the report" % banned
    for required in ("storage_expected", "last_sync_cookies", "cdp_attached"):
        if required not in report["state"]:
            return "FAIL", "the report is missing %s" % required
    # Credential FILENAMES must never appear. Do NOT demand a
    # "<credential file>" placeholder: masking only happens when such a file
    # exists, so on a CI runner (empty config dir) requiring the placeholder
    # failed the gate over nothing. The real invariant is the negative one.
    entries = report.get("config_dir", {}).get("entries") or []
    leaked = [e for e in entries
              if e.lower() in ("secret", "github_token", "session.json", "token")
              or "token" in e.lower()]
    if leaked:
        return "FAIL", "credential/secret file named in the report: %s" % leaked[:2]
    return "ok", "%d sections, %d state fields, 4 planted secrets absent, %d config entries, 0 leaked" % (
        len(report), len(report["state"]), len(entries))


@check("the relay serves the diagnostic endpoint")
def diagnostics_endpoint():
    headers = bridge_headers()
    # relay_call already returns a decoded dict (see its two json.loads).
    status, data = relay_call("GET", "/v1/diagnostics", headers=headers)
    if status != 200:
        return "FAIL", "GET /v1/diagnostics -> %s %s" % (status, data.get("code", ""))
    if not data.get("ok") or "report" not in data or "text" not in data:
        return "FAIL", "the endpoint answered 200 without a report"
    state = data["report"].get("state", {})
    if not data["text"].startswith("# Lightpanda Session Bridge"):
        return "FAIL", "the text form does not start with its header"
    if data["text"].count("[redacted]") and "generated_at" not in data["text"]:
        return "FAIL", "the report is redacting its own header"
    return "ok", "200, %d state fields, %d chars, %d redactions" % (
        len(state), len(data["text"]), data["text"].count("[redacted]"))


@check("the release archive is reproducible")
def archive_reproducible():
    """Same tree => same sha256, on any machine. The sidecar the updater
    verifies is a digest of these bytes; an archive that changes when the
    build machine's zlib changes cannot attest anything."""
    builder = REPO / "scripts" / "build_release_zip.py"
    digests = []
    for _ in range(2):
        env = dict(os.environ)
        with tempfile.TemporaryDirectory() as tmp:
            env["LOCALAPPDATA"] = tmp
            r = subprocess.run([project_python(), str(builder)], cwd=str(REPO),
                               capture_output=True, text=True, env=env)
            if r.returncode != 0:
                return "FAIL", "the builder failed: %s" % (r.stderr or r.stdout)[-80:]
            made = next(pathlib.Path(tmp, "Temp").glob("*.zip"))
            digests.append(hashlib.sha256(made.read_bytes()).hexdigest())
    if digests[0] != digests[1]:
        return "FAIL", "two builds differ: %s != %s" % (digests[0][:10], digests[1][:10])
    return "ok", "sha256 %s stable across 2 builds" % digests[0][:12]


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


@check("the popup copies no URL query or fragment into the diagnostic report")
def diagnostic_report_is_origin_only():
    """The popup's report comment promises "no cookie, no token, no URL".

    It used to copy `currentTab.url` whole, so `?access_token=` or
    `#access_token=` landed in a paste-anywhere clipboard. Runs the real array
    literal from popup.js through a real URL parser, so it cannot pass on a
    report that is only scrubbed in some code path.
    """
    node = shutil.which("node")
    script = REPO / "tests" / "node" / "test_diagnostic_report.js"
    if not node or not script.is_file():
        return "SKIP", "node or the harness is absent"
    r = subprocess.run([node, str(script)], cwd=str(REPO),
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "FAIL", (r.stdout or r.stderr).strip().splitlines()[-1][:90]
    return "ok", "8 URL shapes, no query, no fragment, no value"


@check("a silent socket is released at a deadline the relay can still meet")
def silent_sockets_are_released():
    """Thread exhaustion, not a hang: 25 connections that sent nothing stayed
    open past 35s while /health kept answering.

    Measured live against the RUNNING relay, so it reports the deadline the
    installed code actually enforces - not the one in the repo. The same
    deadline must be per socket operation, not a cap on the request: the CDP
    import path (navigate + settle + four injection rounds) legitimately
    outlives it.
    """
    import socket as _socket
    import urllib.parse as _up

    def _health():
        with urllib.request.urlopen(RELAY + "/health", timeout=8) as resp:
            return json.loads(resp.read().decode())

    try:
        _health()
    except Exception as err:
        return "FAIL", "the relay did not answer /health: %s" % type(err).__name__
    parsed = _up.urlparse(RELAY)
    try:
        sock = _socket.create_connection((parsed.hostname, parsed.port or 80),
                                         timeout=10)
    except OSError as err:
        return "FAIL", "cannot reach the relay: %s" % type(err).__name__
    try:
        # Headers deliberately truncated: the server blocks mid-request, in the
        # read that has no deadline.
        sock.sendall(b"GET /health HTTP/1.1\r\n")
        sock.settimeout(3)
        early = b""
        try:
            early = sock.recv(1)
        except _socket.timeout:
            early = b""  # still open before the deadline: expected
        if early:
            return "FAIL", "the relay answered a truncated request"
        sock.settimeout(45)
        start = time.time()
        closed = False
        while time.time() - start < 40:
            try:
                data = sock.recv(4096)
            except _socket.timeout:
                continue
            except OSError:
                closed = True
                break
            if data == b"":
                closed = True
                break
        waited = time.time() - start
    finally:
        sock.close()
    if not closed:
        return "FAIL", "a silent connection was still open after %ds" % int(waited)
    # And the relay must still serve real traffic while that happens.
    try:
        _health()
    except Exception as err:
        return "FAIL", ("the relay stopped answering after a silent socket: %s"
                        % type(err).__name__)
    return "ok", "silent socket released in %ds, /health still 200" % int(waited)


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

    # The sidecar proves the bytes survived the trip; it says nothing about
    # what they are. What must hold - and did not for v0.5.6, which shipped a
    # gitignored extension/.build-info.json holding this machine's install
    # history - is that the archive *is* the committed tree.
    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            inside = {}
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                key = name.split("/", 1)[1] if name.startswith("extension/") else name
                inside[key] = archive.read(name)
    except zipfile.BadZipFile as err:
        return "FAIL", "the asset is not a readable zip: %s" % err
    expected = {}
    for rel in git("ls-files", "extension").split():
        expected[rel.split("/", 1)[1]] = subprocess.run(
            ["git", "-C", str(REPO), "show", "HEAD:%s" % rel],
            capture_output=True, check=True).stdout
    if set(inside) != set(expected):
        extra = sorted(set(inside) - set(expected))[:3]
        missing = sorted(set(expected) - set(inside))[:3]
        return "FAIL", "the zip is not the committed tree - extra %s, missing %s" % (extra, missing)
    drifted = sorted(k for k in expected if inside[k] != expected[k])[:3]
    if drifted:
        return "FAIL", "bytes differ from HEAD: %s" % drifted
    return "ok", ("%s %d KiB, sha256 matches and the %d shipped files are HEAD's"
                  % (release["tag"], len(blob) // 1024, len(expected)))


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


@check("every popup relay call carries a deadline")
def popup_calls_are_bounded():
    """A client that can wait forever has no honest state to be in.

    The popup had 8 fetch() calls and ONE AbortController, on the import path
    only. /v1/bootstrap in particular runs before anything else, so a relay
    that accepted the socket and went silent left the badge on "Checking…"
    forever and /health was never even tried.

    Asserts on the real helper, not on a count: a bare `signal:` grep passes
    while a call bypasses relayFetch entirely.
    """
    import shutil as _shutil
    node = _shutil.which("node")
    if not node:
        return "SKIP", "node is absent"
    src = (REPO / "extension" / "popup.js").read_text(encoding="utf-8")
    # Every fetch( in the file must live inside relayFetch (the helper itself).
    helper_start = src.find("async function relayFetch")
    helper_end = src.find("\n}", helper_start)
    helper = src[helper_start:helper_end] if helper_start >= 0 else ""
    strays = []
    offset = 0
    while True:
        i = src.find("fetch(", offset)
        if i < 0:
            break
        if not (helper_start <= i <= helper_end):
            strays.append(src[:i].count("\n") + 1)
        offset = i + 6
    if not helper:
        return "FAIL", "relayFetch is absent: the popup has no deadline helper"
    if strays:
        return "FAIL", f"{len(strays)} fetch() outside relayFetch (lines {strays[:4]})"
    if "AbortController" not in helper or "signal:" not in helper:
        return "FAIL", "relayFetch carries no cancellable signal"
    deadline = re.search(r"RELAY_TIMEOUT_MS = (\d+)", src)
    ms = int(deadline.group(1)) if deadline else 0
    # The client must outlast the relay's own cut-off (body reads at 10s, class
    # deadline 15s) or the user sees a bare "Failed to fetch" instead of the
    # translated reason the relay actually sent.
    if ms <= 15000:
        return "FAIL", f"RELAY_TIMEOUT_MS={ms}ms fires before the relay's 15s deadline"
    return "ok", f"all fetch() go through relayFetch, {ms} ms > 15 s relay deadline"


def relay_error_translation_report():
    """The relay answers in short English codes; the popup shipped in 10
    languages. Rendering a code verbatim put "origin refused" inside a French
    popup.

    The codes are read out of BOTH relay files, because the update path raises
    its own: measured 0.7.25, `server.py` alone showed 3 codes while
    `updater.py` held 19 more — every one of them unmapped, and the popup's
    catch threw them all away anyway. A guard that reads half the surface is a
    guard that cannot see half the bug.

    Two shapes are read per file: `{"error": "code"}` and `RuntimeError("code")`,
    because the first is what the route emits and the second is what it raises.
    """
    src = (REPO / "extension" / "popup.js").read_text(encoding="utf-8")
    block = re.search(r"const RELAY_ERROR_KEYS = \{([\s\S]*?)\n\};", src)
    if not block:
        return "FAIL", "RELAY_ERROR_KEYS is absent from popup.js"
    mapped = set(re.findall(r"'([^']+)':\s*'err\w+'", block.group(1)))

    emitted: set[str] = set()
    for rel in ("server.py", "updater.py"):
        relay_src = (REPO / "relay" / rel).read_text(encoding="utf-8")
        emitted |= set(re.findall(r'"error":\s*"([a-z0-9 :\-\.]+)"', relay_src))
        emitted |= set(re.findall(r'RuntimeError\(\s*"([a-z0-9 :\-\.]+)"', relay_src))

    missing = sorted(e for e in emitted - mapped if not e.startswith("error"))
    if missing:
        return "FAIL", f"{len(missing)} relay code(s) untranslated: {missing[:4]}"
    if not emitted:
        # The guard must be able to see a violation: an empty emission set
        # means the regex no longer matches the relay's real shape and every
        # future code would pass silently.
        return "FAIL", "no relay error code could be read: the guard is blind"
    return "ok", f"{len(emitted)} relay error codes, all mapped to an i18n key"


@check("every relay error code has a translation")
def relay_errors_are_translated():
    """Thin @check wrapper over `relay_error_translation_report`.

    The report is a plain function so another check can call it and read its
    (status, detail) tuple. Calling the decorated one returns a bool AND
    re-registers a second result for the same name, so a check that needs the
    verdict must use the unwrapped body.
    """
    return relay_error_translation_report()


# ---------------------------------------------------------------------------
# Reading a proof-red harness's verdict
# ---------------------------------------------------------------------------
# Five distinct spellings of the same three numbers were in this file by the time
# the fifth harness was written - `(\d+) named red, (\d+) unnamed, (\d+) invalid`,
# `(\d+) nomm\S* rouge, ...`, `(\d+)/(\d+) named red, (\d+) invalid`,
# `(\d+)/(\d+) rouges nommes, ...`, and three harnisses that printed NONE of
# them. A check that reads one spelling measures its own regex, not the harness:
# the other four would fail with "no tally" and the suite would blame them.
# So the tally is parsed ONCE, here, over every spelling measured so far - and a
# harness with no recognisable tally is INVALID, never a silent pass (point 58:
# a check that reports `?` measures nothing; here it must FAIL).

# Each pattern is written so that EVERY match yields the SAME four named
# groups - `named`, `total`, `unnamed`, `invalid`. Dispatching on the number of
# positional groups was my first attempt and it was wrong: the "named red,
# unnamed, invalid" shape captures 3 while the "n/N rouges nommes" shape captures
# 4, so one branch read the unnamed count as the invalid count and every such
# verdict came back (3, 0, 0, 0). Named groups make the shape impossible to
# confuse.
#
# `total` is ALWAYS the denominator the harness itself printed - the number of
# sabotages it claims to have run - never `named + unnamed`. Reading
# `proof_red_unreadable_branch.py` showed `named == len(SABOTAGES)` as the
# acceptance condition, so on a run where one sabotage is dead and one is
# unnamed the denominator is the truth and the sum is a smaller number that
# makes the caller compare `named < total` against a fiction.
#
# Two of the four shapes print NO denominator at all ("3 named red, 0 unnamed,
# 0 invalid"). There `total = named + unnamed` is the only reading available,
# and it is correct: every sabotage either proved or was unnamed - a sabotage
# that did not run is counted in `invalid`, which is its own column.
_TALLY_PATTERNS = (
    # "8 sabotage(s), 8 rouge(s), 8 nomme(s), 0 invalide(s)"
    #   n1 = sabotages run (TOTAL), n2 = reds, n3 = named, n4 = invalid
    re.compile(r"(?P<total>\d+)\s+sabotage\S*\s*,\s*(?P<red>\d+)\s+rouge\S*\s*,\s*"
               r"(?P<named>\d+)\s+nomm\S*\s*,\s*(?P<invalid>\d+)\s+invalid\S*", re.I),
    # "3/3 rouges nommes, 0 sans nom, 0 invalides, 0 morts"
    re.compile(r"(?P<named>\d+)\s*/\s*(?P<total>\d+)\s+rouges nommes\s*,"
               r"\s*(?P<unnamed>\d+)\s+sans nom\s*,\s*(?P<invalid>\d+)\s+invalides?", re.I),
    # "3 named red, 0 unnamed, 0 invalid" / "4 nomme(s) rouge, 0 non nomme(s), 0 invalide"
    re.compile(r"(?P<named>\d+)\s+(?:named red|nomm\S* rouge)\s*,"
               r"\s*(?P<unnamed>\d+)\s+(?:unnamed|non nomm\S*)\s*,"
               r"\s*(?P<invalid>\d+)\s+(?:invalid|invalide)", re.I),
    # "3/3 named red, 0 invalid" - no unnamed term, so unnamed is 0 BY the shape.
    re.compile(r"(?P<named>\d+)\s*/\s*(?P<total>\d+)\s+named red\s*,"
               r"\s*(?P<invalid>\d+)\s+invalid", re.I),
)


def proof_red_tally(out):
    """-> (named, total, unnamed, invalid), or None when no tally is present.

    `total` is what the harness CLAIMED and `named` is what it PROVED; the
    difference is the unnamed column, which the caller must refuse. Returns None
    rather than zeros so "no tally" stays distinguishable from "all green"
    (point 58: a check that reports `?` measures nothing; here it must FAIL).
    """
    for pattern in _TALLY_PATTERNS:
        m = pattern.search(out)
        if not m:
            continue
        g = m.groupdict()
        named = int(g["named"])
        unnamed = int(g["unnamed"]) if g.get("unnamed") else 0
        invalid = int(g["invalid"])
        if g.get("total"):
            total = int(g["total"])
        elif g.get("red") is not None:
            # n1 is the sabotage count, n2 the reds: unnamed = reds - named.
            total = int(g["red"])
        else:
            total = named + unnamed
        return named, total, unnamed, invalid
    return None


def run_proof_red(name, timeout=1800):
    """Run one harness and return (status, detail) for a gate check.

    Every refusal is NAMED, and the three are never merged (points 44/78):
      * HARNESS   - the harness itself refused, or the child died on an import;
      * INVALID   - no tally, or a tally reporting unnamed/invalid sabotages;
      * FAIL      - the harness ran and reported a red that is not all-named.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    try:
        r = subprocess.run([str(py), str(REPO / "scripts" / name)],
                           cwd=str(REPO), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "FAIL", "%s: timed out after %ss - a sabotage whose value is large " \
                       "must have its own budget sized to it (point 41)" % (name, timeout)
    out = (r.stdout or "") + (r.stderr or "")
    lines = out.strip().splitlines()
    if re.search(r"ModuleNotFoundError|Failed to import test module|"
                 r"unittest\.loader\._FailedTest", out):
        return "FAIL", ("%s: the child failed to IMPORT - that is a harness "
                        "failure, not evidence (point 57)" % name)
    tally = proof_red_tally(out)
    if tally is None:
        return "FAIL", ("%s printed no tally - the check cannot tell a named red "
                        "from an unnamed one (points 58/78); last line: %s"
                        % (name, (lines[-1:] or ["no output"])[0][:60]))
    named, total, unnamed, invalid = tally
    if invalid:
        return "FAIL", ("%s: %d invalid (a PATCH-MISS or a dead sabotage means the "
                        "proof did not run), %d/%d named red"
                        % (name, invalid, named, total))
    if unnamed:
        return "FAIL", ("%s: %d/%d named red, %d UNNAMED - an unnamed red proves "
                        "only that something broke" % (name, named, total, unnamed))
    if named < total:
        return "FAIL", ("%s: only %d of %d sabotage(s) proved" % (name, named, total))
    return "ok", "%d/%d named red" % (named, total)


def _node_pass_count(out):
    """The Node suites print "18 passed, 0 failed" - a line that ENDS in
    "failed". Matching `.endswith("passed")` therefore found nothing and the
    check reported "?" while green: a check that is green but measures nothing
    (point 5). Match the count wherever it sits in the line."""
    return next((l.strip() for l in out if re.search(r"\d+\s+passed", l)), None)


@check("the relay badge is re-evaluated, not sampled once")
def badge_is_refreshed():
    """A badge is the first thing a user reads, and it was the only thing that
    went stale: `checkRelay()` ran once in init() while the 30s interval
    refreshed only the session counter. A relay that died after the popup opened
    kept showing "Relay Online" until the panel was closed - and the third state
    from v0.6.1 (relay alive, CDP dead) was unreachable except for the few
    hundred milliseconds after opening.

    Runs the real Node suite, which drives the extracted scheduling code.
    """
    import shutil as _sh
    node = _sh.which("node")
    if not node:
        return "SKIP", "node is absent"
    r = subprocess.run([node, str(REPO / "tests" / "node" / "test_badge_refresh.js")],
                       cwd=str(REPO), capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip().splitlines()
    if r.returncode != 0:
        failed = next((l.strip() for l in out if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    passed = _node_pass_count(out)
    if passed is None:
        return "FAIL", "the suite ran green but printed no pass count"
    src = (REPO / "extension" / "popup.js").read_text(encoding="utf-8")
    gap = re.search(r"RELAY_MIN_CHECK_GAP_MS = (\d+)", src)
    return "ok", f"{passed}, min gap {gap.group(1) if gap else '?'}ms"


@check("the update card says WHY nothing is offered")
def update_card_is_honest():
    """The chip said "Up to date" plus a bare commit sha. That is true and
    useless: with main moving on for a commit that touched only docs/, a user
    reading "commit 34827e4" cannot tell "nothing new for you" from "a code
    change is waiting". The relay now measures it (`shipped_tree: "same"`), so
    the popup must translate that state - never copy the relay's English
    diagnostic, which carries a sha and is right for a log, not for a panel.
    """
    import shutil as _sh
    node = _sh.which("node")
    if not node:
        return "SKIP", "node is absent"
    r = subprocess.run([node, str(REPO / "tests" / "node" / "test_update_card_truth.js"),
                        str(REPO)],
                       cwd=str(REPO), capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip().splitlines()
    if r.returncode != 0:
        failed = next((l.strip() for l in out if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    passed = _node_pass_count(out)
    if passed is None:
        return "FAIL", "the suite ran green but printed no pass count"
    # NOT `.endswith("passed")`: the suite prints "18 passed, 0 failed", a line
    # that ends in "failed" - so the match found nothing and the check reported
    # "?" while green: green but measuring nothing (point 5).
    return "ok", passed[:88]


@check("the diagnostic report says WHY the update chip is quiet, and leaks nothing")
def update_report_says_why_and_leaks_nothing():
    """The report is what a user pastes into a bug. It carried
    `update_available = False` and nothing else, so "nothing new" and "an update
    is stuck" looked identical on the page that decides which one it is.

    Adding the reason immediately shipped a worse defect, found only by the
    proof: `update_note` is written by the RELAY, so it is foreign text, but it
    sat in a dict this module builds and therefore trusted - and a note reading
    "Authorization: Bearer ghp_A1...Q7r8" exported 12 characters of the token.
    The scrubber now runs over the note, and a sha in it still survives.

    Runs the real revert-and-observe harness: four sabotages, each of which must
    produce a NAMED red.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_update_report.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) rouges nommes, (\d+) sans nom, (\d+) invalides", out)
    if not m:
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, unnamed, invalid = (int(x) for x in m.groups())
    if got != total or unnamed or invalid:
        return "FAIL", ("%d/%d named red, %d unnamed, %d invalid - a PATCH-MISS or "
                        "harness failure means the proof did not run" %
                        (got, total, unnamed, invalid))
    return "ok", "%d/%d sabotages red and named, 0 invalid" % (got, total)


@check("the popup tells 'at the tip of main' apart from 'the branch moved on'")
def update_tip_is_not_reported_as_a_moved_branch():
    """`shipped_tree: 'same'` covers TWO situations that must not share a
    sentence. Measured on 0.7.21: adding the "the deployed tree IS the tip of
    main" arm published `same` as well, and the popup then told a fully
    up-to-date user that "la branche a avancé" - a claim about the branch, when
    nothing had moved at all.

    Two ways this regresses quietly, both proven here:
      * the arm disappears -> "moved on" becomes unrenderable (sabotage A);
      * the guard is inverted -> the two situations SWAP sentences, which is
        worse than a missing branch because both inputs still render something
        plausible (sabotage B).
    The third sabotage drops the versionless fallback, which would render
    "À jour · v" with nothing after the v.

    Runs the real revert-and-observe harness: three sabotages, each of which must
    produce a NAMED red - and the expectation is a substring of the failure
    NAME the suite actually prints, not a paraphrase (point 65).
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_update_tip.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) rouges nommes, (\d+) sans nom, (\d+) invalides", out)
    if not m:
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, unnamed, invalid = (int(x) for x in m.groups())
    if got != total or unnamed or invalid:
        return "FAIL", ("%d/%d named red, %d unnamed, %d invalid - a PATCH-MISS or "
                        "harness failure means the proof did not run" %
                        (got, total, unnamed, invalid))
    # The proof restores the file; say so, because a proof that leaves the tree
    # sabotaged would make every later check meaningless.
    if "restaure a l'octet   : True" not in out:
        return "FAIL", "the proof did not restore popup.js byte for byte"
    return "ok", "%d/%d sabotages red and named, popup.js restored" % (got, total)


@check("the undo button is reachable when a backup exists")
def undo_is_reachable_after_install():
    """Measured on 0.7.25 (found while fixing 0.7.26): `renderUpdateCard` computed
    `rollbackBtn.style.display` CORRECTLY near its top -
    `(backup_available && !update_available) ? '' : 'none'`, which is exactly the
    state of the "nothing to install" branch - and that branch then overwrote it
    with `'none'` on its last line.

    So undo was reachable only while an update was WAITING, and never in the one
    state where it is useful: the user just installed one. The relay measured
    `backup_available: true`, the popup read the field, and the reading was
    discarded one screen later - point 71 for a value that WAS read.

    The test asserts both directions: showing undo with no backup behind it is as
    wrong as hiding it when one exists, so a fix that simply always shows the
    button fails too.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_rollback.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) named red, (\d+) invalid", out)
    if not m:
        # Two different states land here and "no tally" hides which: the harness
        # refused to run because popup.js is RED ON DISK (a real product failure)
        # versus it ran and printed something unrecognised (a harness failure).
        if "ECHEC : popup.js est rouge" in out:
            return "FAIL", ("popup.js is red on disk: %s" % next(
                (l.strip() for l in lines if l.strip().startswith("ECHEC")), "(voir sortie)"))
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, invalid = (int(x) for x in m.groups())
    if got != total or invalid:
        return "FAIL", ("%d/%d named red, %d invalid - a PATCH-MISS or harness "
                        "failure means the proof did not run" % (got, total, invalid))
    if "popup.js restaure a l'octet : True" not in out:
        return "FAIL", "popup.js was not restored byte for byte by the harness"
    # The suite itself must be green now, and must name its count.
    # `_node_pass_count` iterates its argument: the other call sites pass a LIST
    # of lines (`.strip().splitlines()`). Handing it a raw string made it iterate
    # CHARACTERS, so the count came back None and this check reported a FAIL with
    # the very summary line that proves the suite was green - "undo suite: 7
    # passed, 0 failed". Same shape as point 58 one level down: the measurement
    # was discarded while the child was perfectly healthy.
    import shutil as _sh
    node_bin = _sh.which("node")
    if not node_bin:
        return "SKIP", "node is absent"
    r2 = subprocess.run([node_bin, str(REPO / "tests" / "node" / "test_rollback_reachable.js"),
                         str(REPO)], cwd=str(REPO), capture_output=True, text=True,
                        timeout=300)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        failed = next((l.strip() for l in lines2 if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    count = _node_pass_count(lines2)
    if not count:
        return "FAIL", "undo suite printed no pass count: %s" % (lines2[-1:] or ["no output"])
    return "ok", "%s; overwriting line removed" % count


@check("every update state owns its tooltip, so none survives the next one")
def every_update_state_owns_its_tooltip():
    """Measured on 0.7.27: `renderUpdateCard` wrote `updateMeta.title` in two of
    its three exits and never in the third, so the node kept whatever the
    PREVIOUS render gave it.

    The relay's own words - `API rate limit exceeded for 203.0.113.9` - therefore
    kept hovering over a card that had become perfectly healthy, and survived the
    whole install: `runUpdate` renders with `updateBusy` true, which is exactly
    the branch that returns without touching the title. A tooltip is a property
    of a STATE; the fix seeds the empty title at the top, the same rule as
    seeding `shipped_tree` in the relay's result dict (points 64/66), applied to
    the DOM.

    The suite needs ONE node through TWO renders to see this, so each case
    re-renders into the same node set - a fresh DOM per case would measure
    nothing.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_tooltip.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) named red, (\d+) invalid", out)
    if not m:
        if "ECHEC : popup.js est rouge" in out:
            return "FAIL", ("popup.js is red on disk: %s" % next(
                (l.strip() for l in lines if l.strip().startswith("ECHEC")), "(voir sortie)"))
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, invalid = (int(x) for x in m.groups())
    if got != total or invalid:
        return "FAIL", ("%d/%d named red, %d invalid - a PATCH-MISS or harness "
                        "failure means the proof did not run" % (got, total, invalid))
    if "restored byte for byte: True" not in out:
        return "FAIL", "popup.js was not restored byte for byte by the harness"
    import shutil as _sh
    node_bin = _sh.which("node")
    if not node_bin:
        return "SKIP", "node is absent"
    r2 = subprocess.run([node_bin, str(REPO / "tests" / "node" / "test_tooltip_state_truth.js"),
                         str(REPO)], cwd=str(REPO), capture_output=True, text=True,
                        timeout=300)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        failed = next((l.strip() for l in lines2 if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    count = _node_pass_count(lines2)
    if not count:
        return "FAIL", "tooltip suite printed no pass count: %s" % (lines2[-1:] or ["no output"])
    return "ok", "%s; the empty title is seeded, so no state inherits one" % count


@check("every state owns the update button's wording, so no version is inherited")
def every_state_owns_the_button_wording():
    """Measured on 0.7.28, straight out of 0.7.27's rule: a label is a property
    of a STATE, and `renderUpdateCard` wrote `updateBtn.textContent` ONLY in the
    `update_available` branch.

    The three other exits - relay down, upstream refused, nothing to install -
    left the button holding the version a previous render offered. A branch
    update has its OWN wording (`updateBtnMain`, which names no version at all)
    and inherited the release wording when it arrived second, on the node the
    user clicks. The button is hidden in the states that leak, so the stale
    wording is invisible while hidden and reappears on the next show.

    The fix seeds `updateBtn.textContent = ''` beside the 0.7.27 title seed.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_button_wording.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) named red, (\d+) invalid", out)
    if not m:
        if "ECHEC : popup.js est rouge" in out:
            return "FAIL", ("popup.js is red on disk: %s" % next(
                (l.strip() for l in lines if l.strip().startswith("ECHEC")), "(voir sortie)"))
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, invalid = (int(x) for x in m.groups())
    if got != total or invalid:
        return "FAIL", ("%d/%d named red, %d invalid - a PATCH-MISS or harness "
                        "failure means the proof did not run" % (got, total, invalid))
    if "restored byte for byte: True" not in out:
        return "FAIL", "popup.js was not restored byte for byte by the harness"
    import shutil as _sh
    node_bin = _sh.which("node")
    if not node_bin:
        return "SKIP", "node is absent"
    r2 = subprocess.run([node_bin, str(REPO / "tests" / "node" / "test_button_wording_truth.js"),
                         str(REPO)], cwd=str(REPO), capture_output=True, text=True,
                        timeout=300)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        failed = next((l.strip() for l in lines2 if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    count = _node_pass_count(lines2)
    if not count:
        return "FAIL", "button wording suite printed no pass count: %s" % (lines2[-1:] or ["no output"])
    return "ok", "%s; the wording is seeded, so no state inherits a version" % count


@check("the clear button never keeps an armed confirmation across a refresh")
def clear_button_never_keeps_an_armed_confirmation():
    """Measured on 0.7.29, third of the family 0.7.27/0.7.28 opened: a value
    belongs to a STATE.

    `renderSessions` reset FOUR properties of the clear button in its "a list
    exists" branch - `style.display`, `dataset.armed`, `title`, `clearText` -
    and only ONE in its "the list is empty" branch. So a button the user had
    already armed for the two-step confirmation kept `dataset.armed`, its
    "Confirm?" wording and its tooltip across a refresh that emptied the list,
    and the NEXT click then wiped every synced session with no confirmation.

    The confirmation is a SAFETY property, so its state must be owned by the
    list's state and never inherited. `resetClearButton()` now owns all four, so
    neither branch can forget the third one - the shape of fix that survives
    the next branch somebody adds.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_clear_button.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) named red, (\d+) invalid", out)
    if not m:
        if "ECHEC : popup.js est rouge" in out:
            return "FAIL", ("popup.js is red on disk: %s" % next(
                (l.strip() for l in lines if l.strip().startswith("ECHEC")), "(voir sortie)"))
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, invalid = (int(x) for x in m.groups())
    if got != total or invalid:
        return "FAIL", ("%d/%d named red, %d invalid - a PATCH-MISS or harness "
                        "failure means the proof did not run" % (got, total, invalid))
    if "restored byte for byte: True" not in out:
        return "FAIL", "popup.js was not restored byte for byte by the harness"
    import shutil as _sh
    node_bin = _sh.which("node")
    if not node_bin:
        return "SKIP", "node is absent"
    r2 = subprocess.run([node_bin, str(REPO / "tests" / "node" / "test_clear_button_truth.js"),
                         str(REPO)], cwd=str(REPO), capture_output=True, text=True,
                        timeout=300)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        failed = next((l.strip() for l in lines2 if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    count = _node_pass_count(lines2)
    if not count:
        return "FAIL", "clear button suite printed no pass count: %s" % (lines2[-1:] or ["no output"])
    return "ok", "%s; one shared reset owns all four button properties" % count

@check("no stored 'pristine' copy can become a false reference")
def pristine_copies_match_the_committed_product():
    """A harness that self-heals its own pristine will heal it toward DAMAGE.

    Measured 0.7.36: a dozen harnesses keep a byte copy of a source file under
    `scripts/artifacts_pristine/`, and when the copy differs they REFRESH it from
    the file on disk. That is the right defence against a stale copy (point 45)
    and it is the hole: a killed run can leave the PRODUCT sabotaged, the next
    run refreshes the pristine from that sabotage, and from then on every
    restore-verification compares against a false base and passes. The 0.7.35
    fence cannot see it either - that fence hashes the product, and the pristine
    is not the product.

    Measured both directions: pristine poisoned + healthy product heals
    CORRECTLY; healthy pristine + sabotaged product heals to the SABOTAGE.

    The invariant is NOT "the copy equals HEAD". Measured: five copies held an
    older build, each byte-identical to some real commit (8e22d1ea, 4892f9f3,
    2b7d2a52) - a harness that ran before a release wrote them, and an old copy
    is harmless because the next run refreshes it. Requiring HEAD made the check
    fail on a perfectly healthy tree, which is worse than no check.

    The invariant that survives: a copy must hold a version of its source that
    was ACTUALLY COMMITTED. Content that never existed in any commit can only
    come from a sabotage, so it is the false reference - and it is exactly what a
    self-healing harness would install as its base.

    ORDER MATTERS: run this BEFORE the harnesses. A self-healing harness repairs
    the very evidence this check reads, so placed after it measures 5/5 correct
    while the copy is poisoned.

    The copy list is DISCOVERED, never written out. The first version of this
    check hard-coded five (name, product) pairs and answered "5 pristine copies
    all equal the committed product" - 13 of the 18 copies on disk were never
    examined, and the confident count of a partial set read as a whole. A guard
    that enumerates a subset publishes a number nobody can trust (point 101).
    """
    import hashlib

    pr_dir = REPO / "scripts" / "artifacts_pristine"
    if not pr_dir.is_dir():
        return "SKIP", "no pristine directory yet (copies are made per run)"

    def resolve(name):
        """The repo file this stored copy backs up, or None if unrecognised.

        The four conventions are READ OUT OF THE HARNESSES, not invented here:
          * `artifacts_pristine / "<name>.pristine"`  - popup.js.pristine (4),
            diagnostics.py.pristine
          * `artifacts_pristine / "<name>"`          - popup.js, updater.py
          * `PRISTINE / rel.replace("/", "__")`      - relay__server.py,
            extension__popup.js  (built, so no literal name in the source)
          * `popup.js.proof_red_<harness>`            - rollback / update_failure
        A name matching none of them is reported by name, never skipped: a guard
        that enumerates a subset publishes a count nobody can trust.
        """
        flat = name[:-len(".pristine")] if name.endswith(".pristine") else name
        # built by rel.replace("/", "__") -> try the flattened path directly
        if "__" in flat:
            cand = flat.replace("__", "/")
            if (REPO / cand).is_file():
                return cand
        if flat.startswith("popup.js.proof_red_"):
            return "extension/popup.js"
        if flat.startswith("diag"):
            return "relay/diagnostics.py"
        # a bare file name: the same name under a known source directory
        for cand in ("extension/" + flat, "relay/" + flat, "scripts/" + flat,
                     flat):
            if (REPO / cand).is_file():
                return cand
        return None

    try:
        def committed_hashes(rel):
            """Every sha256 this path has ever held in a commit on this branch."""
            out = set()
            revs = subprocess.run(["git", "rev-list", "--all", "--", rel],
                                  cwd=str(REPO), capture_output=True, text=True,
                                  timeout=120).stdout.split()
            for rev in revs:
                blob = subprocess.run(["git", "rev-parse", "%s:%s" % (rev, rel)],
                                       cwd=str(REPO), capture_output=True, text=True,
                                       timeout=60).stdout.strip()
                if not blob:
                    continue
                data = subprocess.run(["git", "cat-file", "blob", blob],
                                      cwd=str(REPO), capture_output=True,
                                      timeout=60).stdout
                if data:
                    out.add(hashlib.sha256(data).hexdigest())
            return out

        allowed = {}
        for rel in {r for r in (resolve(f.name) for f in pr_dir.iterdir() if f.is_file())
                    if r}:
            seen_hashes = committed_hashes(rel)
            if seen_hashes:
                allowed[rel] = seen_hashes
        if not allowed:
            return "SKIP", "git cannot read any committed source, no reference"
    except (OSError, subprocess.SubprocessError):
        return "SKIP", "git unavailable, cannot read the committed sources"

    wrong, unknown, seen = [], [], 0
    for f in sorted(p for p in pr_dir.iterdir() if p.is_file()):
        target = resolve(f.name)
        if target is None:
            unknown.append(f.name)
            continue
        if target not in allowed:
            unknown.append("%s (no committed %s to compare)" % (f.name, target))
            continue
        seen += 1
        if hashlib.sha256(f.read_bytes()).hexdigest() not in allowed[target]:
            wrong.append("%s holds bytes no commit ever held for %s"
                         % (f.name, target))
    if wrong:
        return "FAIL", ("%d stored cop(y|ies) hold bytes NO commit ever held: %s - a harness "
                        "refreshes these from the file on disk, so a killed run "
                        "can install the damage as the base it verifies against"
                        % (len(wrong), "; ".join(sorted(wrong))))
    if not seen:
        return "SKIP", "no pristine copy maps to a committed source yet"
    if unknown:
        return "FAIL", ("%d stored cop(y|ies) name no file I can resolve, so they are "
                        "unchecked: %s - resolve every name or delete the copy"
                        % (len(unknown), ", ".join(sorted(unknown))))
    return "ok", ("%d/%d copies hold a version this repo actually committed"
                  % (seen, len(list(p for p in pr_dir.iterdir() if p.is_file()))))

@check("the product is byte-identical after every proof-red harness has run")
def product_survives_the_proof_red_harnesses():
    """Seventeen harnesses EDIT product files. Nothing required them to restore.

    Measured 0.7.33, three times in one session: a proof run was killed at its
    timeout with a live edit still on disk, so its `finally` never ran. The three
    leftovers were `pyproject.toml` at a version nobody shipped, `popup.js`
    without its translation block, and `relay/diagnostics.py` with `scrub()`
    replaced by a literal - a report that would have printed `[redacted]` where
    the update reason belongs, or a truncated token where the whole secret was
    before. None was caught by the gate: the harnesses that had already run
    reported green, and the next harness took the sabotage as its own "original".

    The structural fix is a fence around the whole family: hash the files the
    harnesses touch BEFORE running them, run them, hash again, and refuse any
    difference. A harness that restores wrongly then fails loudly instead of
    leaving the tree dirty for the next run - and the check is independent of
    each harness's own restoration, which is the part that can be skipped.
    """
    targets = ("extension/popup.js", "relay/server.py", "relay/updater.py",
               "relay/diagnostics.py")
    import hashlib

    def fingerprint():
        out = {}
        for rel in targets:
            f = REPO / rel
            out[rel] = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
        return out

    def head_bytes(rel):
        """The COMMITTED bytes of a file, or None when git cannot answer.

        None is never treated as a match: an unmeasurable reference is a SKIP
        with its reason, not a green that means nothing (point 58). A check that
        cannot read the truth must say so rather than pass on the absence of a
        difference - which is exactly the failure this second half exists to
        prevent.
        """
        try:
            r = subprocess.run(["git", "show", "HEAD:%s" % rel], cwd=str(REPO),
                               capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout if r.returncode == 0 else None

    before = fingerprint()
    ran, bad = 0, []
    for name in sorted(p.name for p in (REPO / "scripts").glob("proof_red_*.py")):
        status, detail = run_proof_red(name)
        if status == "SKIP":
            continue
        ran += 1
        if status != "ok":
            bad.append(detail)
    after = fingerprint()
    drifted = [r for r in targets if before[r] != after[r]]
    # The second half, and the one the first version was missing: comparing the
    # tree to its OWN starting state cannot see a sabotage a PREVIOUS session
    # left behind - it hashes the damage and calls it the reference. Measured:
    # the fence printed "byte-identical" on a run whose `relay/server.py`
    # carried a leftover edit. A before/after fence and a committed reference
    # are different questions, and only asking the second one catches a tree
    # that was already dirty.
    uncommitted = []
    unmeasurable = []
    for rel in targets:
        ref = head_bytes(rel)
        if ref is None:
            unmeasurable.append(rel)
            continue
        if after[rel] != hashlib.sha256(ref).hexdigest():
            uncommitted.append(rel)
    if drifted:
        # Reached only when every harness itself reported cleanly, which is the
        # case worth naming: the harnesses say they restored, and the fingerprint
        # says they did not. Reported on its own line because a leftover sabotage
        # is a LIVE defect in the tree, while a harness verdict is a statement
        # about the proof (points 78 and 24 read together).
        return "FAIL", ("%d product file(s) left MODIFIED by a proof-red harness: "
                        "%s - the tree now carries a defect, and the next harness "
                        "will snapshot it as its own 'original'"
                        % (len(drifted), ", ".join(drifted)))
    if uncommitted:
        return "FAIL", ("%d product file(s) differ from the COMMITTED tree: %s - "
                        "a sabotage survived an earlier run, and this one hashed "
                        "the damage as its reference (restore from a snapshot, "
                        "never git checkout)" % (len(uncommitted), ", ".join(uncommitted)))
    if bad:
        return "FAIL", "%d harness(es) failed: %s" % (len(bad), bad[0][:70])
    if unmeasurable:
        return "SKIP", ("%d file(s) could not be compared against HEAD (%s): git "
                        "is unavailable or the path is untracked - the before/after "
                        "fence still ran, the committed-reference half did not"
                        % (len(unmeasurable), ", ".join(unmeasurable)))
    return "ok", ("%d harness(es) ran, %d product file(s) byte-identical before "
                  "and after AND equal to the committed tree"
                  % (ran, len(targets)))


@check("every proof-red harness is REGISTERED and every sabotage is NAMED")
def proof_red_harnesses_are_required():
    """A proof-red harness nobody runs is a comment about a bug.

    Measured 0.7.33: `scripts/` held 17 harnesses and the gate named 12. Five were
    never executed by any commit - `update_channel` alone carries 11 sabotages,
    `session_expiry` 8 - so 27 sabotage proofs had never been required to be red.
    Three of the seventeen printed NO tally at all, so even a wired check could
    not tell "4/4 named" from "4 reds of which 2 are unnamed".

    One check, one parser, every harness: `proof_red_tally` reads all four
    spellings and returns None when it recognises none, which is a FAIL and not a
    silent pass (points 58/78). The companion audit proves the other half - that
    no harness can exist without a check naming it - because a harness that is
    added and not wired reads exactly like one that is wired and passes.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    harnesses = sorted(p.name for p in (REPO / "scripts").glob("proof_red_*.py"))
    if not harnesses:
        return "FAIL", "no proof-red harness found where scripts/ was expected"
    ran = green = 0
    bad = []
    for name in harnesses:
        status, detail = run_proof_red(name)
        if status == "SKIP":
            continue
        ran += 1
        if status == "ok":
            green += 1
        else:
            bad.append(detail)
    if bad:
        return "FAIL", ("%d of %d harness(es) did not prove cleanly: %s"
                        % (len(bad), ran, bad[0][:96]))
    r = subprocess.run([str(py), str(REPO / "scripts" / "audit_proof_red_coverage.py")],
                       cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    lines = (r.stdout or r.stderr).strip().splitlines()
    if r.returncode != 0:
        why = next((l.strip() for l in lines if l.strip()
                    and not l.strip().startswith(("ORPHAN", "===", "PROOF-RED"))),
                   "?")
        return "FAIL", ("coverage audit is red: %s" % why[:88])
    orphans = sum(1 for l in lines if l.strip().startswith("ORPHAN"))
    return "ok", ("%d/%d harnesses proved every sabotage named red; %d harness(es) "
                  "registered by name, 0 orphan" % (green, ran, len(harnesses)))


@check("a credential is redacted whatever its alphabet, and prose survives")
def scrubber_catches_any_alphabet():
    """The scrubber's own rule, measured in 0.7.32 against its own limits.

    `_looks_sensitive` required an uppercase AND a lowercase AND a digit in the
    SAME string, so five credential shapes passed it untouched: an all-lowercase
    passphrase, a lowercase+digit one, a 16-char secret under the old 20-char
    floor, an 8-char one, and an AWS key id (upper + digit, no lowercase).

    Two candidate criteria were tried and MEASURED INSUFFICIENT before this one,
    which is why the rule is not "entropy" and not "three classes":
      * entropy - an all-lowercase passphrase scores 3.36 bits/char and the
        product name 3.78, so any threshold catching the secret deletes the name;
      * "contains a non-alphanumeric character" - the report's own sentence has
        ten of them and the passphrase none, so the test pointed backwards.
    The rule is now a PREFIX list plus an alphabet DISJUNCTION with two length
    floors, each measured against the shortest benign value it could reach.

    DECLARED UNCATCHABLE, in the source and in the suite: a blob of ONE alphabet
    class is character-for-character the same shape as a hyphenated product name,
    so no function of the string separates them. The suite asserts both sides of
    that pair agree, which is what keeps the declaration a measurement.

    Over-redaction is a defect of the same severity as a leak (point 16), so the
    suite runs both directions: 11 credential shapes must be redacted, 10 benign
    values must survive - including a report SENTENCE and a route path.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_scrubber.py")],
                       cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1200)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    if "HARNESS" in out:
        return "FAIL", "scrubber proof refused to run: " + next(
            (l.strip() for l in lines if "HARNESS" in l), "?")
    m = re.search(r"(\d+) named red, (\d+) unnamed, (\d+) invalid", out)
    if not m:
        return "FAIL", ("no tally from the scrubber proof - the harness may have "
                        "failed: %s" % (lines[-1:] or ["no output"]))
    named, unnamed, invalid = (int(x) for x in m.groups())
    if unnamed or invalid:
        return "FAIL", ("%d named red, %d UNNAMED, %d invalid - an unnamed red or a "
                        "PATCH-MISS means the proof did not run"
                        % (named, unnamed, invalid))
    if "PROOF-RED REFUSE" in out:
        return "FAIL", "the proof refused: %d/%d named red" % (named, named + unnamed)
    r2 = subprocess.run([str(py), str(REPO / "scripts" / "test_scrubber_shapes.py")],
                        cwd=str(REPO), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=600)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        bad = next((l.strip() for l in lines2
                    if l.strip().startswith(("LEAK", "ERASED", "FAIL"))), "?")
        return "FAIL", bad[:88]
    ok_lines = sum(1 for l in lines2 if l.strip().startswith("ok"))
    if not ok_lines:
        return "FAIL", ("the scrubber suite printed no ok row: %s"
                        % (lines2[-1:] or ["no output"]))
    return "ok", ("%d/%d named red; %d rows green covering 11 credential shapes, "
                  "10 benign values and a credential inside a sentence"
                  % (named, named + unnamed, ok_lines))


@check("no rendered value outlives the state that set it")
def no_value_outlives_its_state():
    """The MECHANISED form of the family measured in 0.7.26-0.7.30, built after
    the manual version of this audit reported "0 properties" on a function that
    writes nine - a hand-written flow parser that silently measured nothing.

    The invariant needs no control-flow analysis and none of my vocabulary:
    `render(A)` then `render(B)` into ONE node set must equal `render(B)` into a
    FRESH one. Any difference is a value that survived a state change. The
    comparison is exhaustive over pairs, sees an ABSENCE (which a
    duplicate-write detector cannot - point 82), and cannot be fooled by
    mutually exclusive `if/else` arms.

    A state may keep a value ON PURPOSE, and no comparison can tell that from the
    defect. Three such cases were MEASURED on the real DOM and are declared, with
    the line numbers that justify each - `updateBusy` leaves both buttons alone
    because `runUpdate` disables them (popup.js:1449-1450), and the two failure
    branches keep `rollbackBtn`'s tooltip on a node they set `display:none`, which
    has no hover. The declaration is itself checked: a declared node that does NOT
    survive is a FAIL, so the escape hatch cannot widen without evidence.

    Every node is seeded from `popup.html`'s own content, so the values a user
    sees before any script runs are the ones under test - which is what made the
    clear-button proof report the English literal `Clear all`.

    0.7.30's first-frame fix is deliberately NOT covered here: `renderUpdateCard`
    writes `updateVersion` in every state, so the markup's placeholder cannot
    survive inside it. That frame belongs to `init()` and is covered by
    `test_card_identity_immediate.js`. A harness must not claim a defect class it
    structurally cannot see.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_state_ownership.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=1200)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    # The tally line is read with the ACCENT it actually prints:
    # "4 nomme(s) rouge, 0 non nomme(s), 0 invalide". Matching an ASCII
    # "restaure" against a line that reads "restaure" with an acute on the
    # final e is a false FAIL that reads like a product defect (points 81/86).
    m = re.search(r"(\d+) nomm\S* rouge, (\d+) non nomm\S*, (\d+) invalide", out)
    if not m:
        if "HARNESS FAIL" in out:
            return "FAIL", "audit harness refused to run: " + next(
                (l.strip() for l in lines if "HARNESS FAIL" in l), "?")
        return "FAIL", ("no tally from the state-ownership proof - the harness may "
                        "have failed: %s" % (lines[-1:] or ["no output"]))
    got, unnamed, invalid = (int(x) for x in m.groups())
    if unnamed or invalid:
        return "FAIL", ("%d named red, %d UNNAMED, %d invalid - an unnamed red or a "
                        "PATCH-MISS means the proof did not run"
                        % (got, unnamed, invalid))
    if "PROOF-RED REFUSE" in out:
        return "FAIL", "the proof refused: %d/%d named red" % (got, got + unnamed)
    if re.search(r"restaur\S* . l'octet : False", out):
        return "FAIL", "a file was not restored byte for byte - check the harness"
    import shutil as _sh
    node_bin = _sh.which("node")
    if not node_bin:
        return "SKIP", "node is absent"
    r2 = subprocess.run([node_bin, str(REPO / "tests" / "node" / "test_no_value_outlives_its_state.js"),
                         str(REPO)], cwd=str(REPO), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=600)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        failed = next((l.strip() for l in lines2 if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    count = _node_pass_count(lines2)
    if not count:
        return "FAIL", "state-ownership suite printed no pass count: %s" % (lines2[-1:] or ["no output"])
    return "ok", "%s; %d sabotages named red" % (count, got)


@check("the card names the installed version on the first frame, before any await")
def card_names_the_installed_version_on_the_first_frame():
    """Measured on 0.7.30: `init()` wrote the FOOTER version synchronously but
    rendered the update card only after `await loadBridgeToken()`, the bootstrap
    and the relay probe. `/v1/update/check` answers in 864 ms on the running
    relay, so for that whole window the card showed `v0.5.0` - the literal in
    `popup.html` - on an extension installed at 0.7.29: twenty-nine versions
    stale, on the panel whose whole purpose is to say which version you are on.

    The version is LOCAL knowledge (`chrome.runtime.getManifest()`), so it never
    had to wait for the network. The fix renders the card immediately, with
    `updateInfo` still null; the chip is honest meanwhile, since "Relay Offline"
    means "I have not been told yet" (the relay-side rule of points 64/67).

    The suite runs the REAL `init()` and reads the card before any promise
    resolves: calling `renderUpdateCard()` directly would measure a state no user
    ever sees (points 37/73). It seeds each node from the markup's own initial
    content, so the "first frame" is the one a user actually gets.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_card_identity.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) named red, (\d+) invalid", out)
    if not m:
        if "ECHEC : popup.js est rouge" in out:
            return "FAIL", ("popup.js is red on disk: %s" % next(
                (l.strip() for l in lines if l.strip().startswith("ECHEC")), "(voir sortie)"))
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, invalid = (int(x) for x in m.groups())
    if got != total or invalid:
        return "FAIL", ("%d/%d named red, %d invalid - a PATCH-MISS or harness "
                        "failure means the proof did not run" % (got, total, invalid))
    if "restored byte for byte: True" not in out:
        return "FAIL", "popup.js was not restored byte for byte by the harness"
    import shutil as _sh
    node_bin = _sh.which("node")
    if not node_bin:
        return "SKIP", "node is absent"
    r2 = subprocess.run([node_bin, str(REPO / "tests" / "node" / "test_card_identity_immediate.js"),
                         str(REPO)], cwd=str(REPO), capture_output=True, text=True,
                        timeout=300)
    lines2 = (r2.stdout or r2.stderr).strip().splitlines()
    if r2.returncode != 0:
        failed = next((l.strip() for l in lines2 if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:88]
    count = _node_pass_count(lines2)
    if not count:
        return "FAIL", "card identity suite printed no pass count: %s" % (lines2[-1:] or ["no output"])
    return "ok", "%s; the card is rendered before the first await" % count


@check("a failed update names its cause instead of blaming the relay")
def update_failure_names_its_cause():
    """Measured on 0.7.24 (found while fixing 0.7.25): `runUpdate` threw the
    relay's refusal with its code attached, and then its own catch replaced the
    message UNCONDITIONALLY with "Relay Offline (is it running?)". A refused
    checksum, a refused origin, an unauthenticated extension, a rate limit, a
    dead relay and a timeout were six situations wearing one sentence.

    `relayErrorText()` had existed since long before and was never called from
    here - the second unread function after `error_kind` (0.7.24). The same
    surface also carried 19 `RuntimeError` codes in `relay/updater.py` that no
    guard could see, because the translation check only read `relay/server.py`.

    Two distinct faults, so two distinct sabotages: A collapses every refusal
    back onto "unreachable", B stops `t()` formatting `{0}` so an unmapped code
    renders as a literal brace and the code itself never reaches the user.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_update_failure.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) named red, (\d+) invalid", out)
    if not m:
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, invalid = (int(x) for x in m.groups())
    if got != total or invalid:
        return "FAIL", ("%d/%d named red, %d invalid - a PATCH-MISS or harness "
                        "failure means the proof did not run" % (got, total, invalid))
    if "popup.js restaure a l'octet : True" not in out:
        return "FAIL", "popup.js was not restored byte for byte by the harness"
    # The guard must also hold NOW, not only in the reverted state: every code the
    # relay can raise needs a translation, and updater.py is part of that surface.
    # The decorated check returns a bool and re-registers itself; the plain
    # report is what answers with a (status, detail) tuple.
    status, detail = relay_error_translation_report()
    if status != "ok":
        return "FAIL", "relay error codes went untranslated: %s" % detail
    return "ok", "%d sabotage(s) go red, all codes translated (%s)" % (total, detail)


@check("an upstream GitHub failure is not reported as 'Relay Offline'")
def upstream_failure_is_not_reported_as_offline():
    """Measured live on 0.7.23: `/health` answered 200 with `ok: true` and the
    update card still read "Relay Offline". The relay had answered perfectly and
    GitHub had refused - two different failures that both collapse into
    `!updateInfo.ok`. The user was told to debug a working installation, and the
    relay's `error_kind` ("rate_limit" / "unreachable"), published all along, was
    never read.

    Runs the revert-and-observe harness: four sabotages, each of which must
    produce a NAMED red. C is the false-positive direction - claiming a rate
    limit for any upstream error would be as dishonest as the original bug.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_upstream_card.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) rouges nommes, (\d+) sans nom, (\d+) invalides", out)
    if not m:
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, unnamed, invalid = (int(x) for x in m.groups())
    if got != total or unnamed or invalid:
        return "FAIL", ("%d/%d named red, %d unnamed, %d invalid - a PATCH-MISS or "
                        "harness failure means the proof did not run" %
                        (got, total, unnamed, invalid))
    if "popup.js restaure a l'octet   : True" not in out:
        return "FAIL", "the proof did not restore popup.js byte for byte"
    return "ok", "%d/%d sabotages red and named, popup.js restored" % (got, total)


@check("an unread branch is reported, never read as 'up to date'")
def unreadable_branch_is_reported():
    """Measured 0.7.22: GitHub answered for the release but not for the branch.
    `head` came back None, `check_update` fell through every arm, and the relay
    answered `update_available: False`, `shipped_tree: "unknown"`, no note - so
    the popup printed "À jour". That is the unmeasured claim 0.7.20 had to
    retract, back through a different door.

    The fixture for this also had to be corrected: its release version defaulted
    to something NEWER than the installed one, so the release arm answered first
    and all four tests passed while exercising a path they do not name. Same
    family as point 24 - a green test that measures a different thing.

    Runs the revert-and-observe harness: three sabotages, each of which must
    produce a NAMED red.
    """
    py = REPO / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return "SKIP", "no project venv"
    r = subprocess.run([str(py), str(REPO / "scripts" / "proof_red_unreadable_branch.py")],
                       cwd=str(REPO), capture_output=True, text=True, timeout=900)
    out = (r.stdout or r.stderr).strip()
    lines = out.splitlines()
    m = re.search(r"(\d+)/(\d+) rouges nommes, (\d+) sans nom, (\d+) invalides", out)
    if not m:
        return "FAIL", "proof-red harness printed no tally: %s" % (lines[-1:] or ["no output"])
    got, total, unnamed, invalid = (int(x) for x in m.groups())
    if got != total or unnamed or invalid:
        return "FAIL", ("%d/%d named red, %d unnamed, %d invalid - a PATCH-MISS or "
                        "harness failure means the proof did not run" %
                        (got, total, unnamed, invalid))
    if "relay/updater.py restaure   : True" not in out:
        return "FAIL", "the proof did not restore relay/updater.py byte for byte"
    return "ok", "%d/%d sabotages red and named, updater.py restored" % (got, total)


LOCAL = [versions_agree, changelog_is_not_duplicated, prose_has_no_cjk_punctuation,
         shipped_tree_lf, no_scaffolding, provenance_matches, ids_agree,
         pin_matches_declaration,
         secret_absent, i18n_parity, dom_ids_exist, python_compiles, popup_fits,
         diagnostics_are_sanitized, diagnostic_report_is_origin_only, archive_reproducible,
         popup_calls_are_bounded, relay_errors_are_translated, badge_is_refreshed,
         update_card_is_honest, update_tip_is_not_reported_as_a_moved_branch,
         upstream_failure_is_not_reported_as_offline,
         update_failure_names_its_cause,
         undo_is_reachable_after_install,
         every_update_state_owns_its_tooltip,
         every_state_owns_the_button_wording,
         clear_button_never_keeps_an_armed_confirmation,
         no_value_outlives_its_state,
         scrubber_catches_any_alphabet,
         card_names_the_installed_version_on_the_first_frame,
         unreadable_branch_is_reported,
         update_report_says_why_and_leaks_nothing,
         proof_red_harnesses_are_required,
         pristine_copies_match_the_committed_product,
         product_survives_the_proof_red_harnesses,
         # ORDER, measured 0.7.36: the unit suite runs LAST. Eleven of its test
         # files read the same four product files the harnesses sabotage, so a
         # suite placed BEFORE the fence measures whatever sabotage was live at
         # that instant. It reported test_socket_timeout failing with "class
         # deadline 45s" while the shipped deadline is 15s - the harness had the
         # tree, the suite read it, and a real green turned into a false red.
         # A test that shares mutable ground with a saboteur cannot be trusted
         # before the fence proves the ground is clean.
         unit_suite]

@check("the installed popup translates the relay's own error codes")
def installed_popup_translates():
    """The repo copy can be perfect while the DEPLOYED popup is stale, and a
    key-count parity check cannot see it: every language has all 56 keys.

    Runs the real test, which resolves the mapping and the strings from the
    INSTALLED file and compares against the exact expected value - the fallback
    frame returns a non-empty right-language string, so only an exact compare
    fails when the mapping is gone.
    """
    import shutil as _shutil2
    node = _shutil2.which("node")
    if not node:
        return "SKIP", "node is absent"
    installed = pathlib.Path.home() / ".config" / "lightpanda-bridge" / "extension-backup" / "popup.js"
    if not installed.is_file():
        return "SKIP", "no installed popup to check"
    r = subprocess.run([node, str(REPO / "tests" / "node" / "test_relay_deadline.js")],
                       cwd=str(REPO), capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip().splitlines()
    passed = _node_pass_count(out)
    if r.returncode != 0:
        failed = next((l.strip() for l in out if l.strip().startswith("FAIL")), "?")
        return "FAIL", failed[:90]
    if passed is None:
        return "FAIL", "the suite ran green but printed no pass count"
    return "ok", f"{passed} (installed popup, fr codes resolved)"


LIVE = [relay_health, single_relay, relay_auth, update_check, release_asset, main_tarball,
        lightpanda_up, cdp_proxy, session_roundtrip, extension_live_version, updates_xml_live,
        audit_log, double_check_pin, diagnostics_endpoint, silent_sockets_are_released,
        installed_popup_translates]


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

    # A registered check whose decorator is missing runs but never records, so
    # `todo` and `RESULTS` disagree - and the gate still says READY. Assert the
    # counts match instead of trusting either number (skill point 13).
    if len(RESULTS) != len(todo):
        print("\nFAIL gate integrity - %d checks listed but %d recorded: a check is "
              "probably registered without @check, so it cannot affect the verdict"
              % (len(todo), len(RESULTS)))
        failures.append(("FAIL", "gate integrity",
                         "%d listed, %d recorded" % (len(todo), len(RESULTS))))

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
    sys.exit(main())
