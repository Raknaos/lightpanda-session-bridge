"""A sanitized support report the user can paste anywhere.

Why this module exists: a user whose sync fails sees a number in a popup and
nothing else. Getting from that screenshot to a cause meant guessing, reading
the relay's stdout by hand, and reproducing the failure by luck. Every minute
of that was spent with no artifact. This builds ONE deterministic report.

The hard rule, enforced by tests/test_diagnostics.py: no secret, no cookie
value, no token, no localStorage value and no browsing URL ever enters the
report. Metadata only - names, sizes, counts, versions, hashes, timings.

Every accessor below is defensive on purpose: the report must still be
producible when the thing being reported is broken.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import time
from typing import Any

# Absolute path of THIS file, used to recognise the daemon's own module even when
# it is registered under __main__ (see _sibling).
_THIS_FILE = os.path.abspath(__file__)

REDACTED = "[redacted]"


# --------------------------------------------------------------------------
# scrubbing - the guarantee lives here
# --------------------------------------------------------------------------

# Keys that may carry a credential. Matched as SUBSTRINGS on purpose, but the
# list must stay narrow: an earlier version also matched "cookie" and "storage",
# which silently deleted exactly the fields a support report exists for
# (``storage_expected``, ``last_sync_cookies``) because their names describe a
# COUNT, not the secret. A count is metadata and must survive.
_SECRET_KEYS = ("value", "token", "secret", "password", "authorization",
                "api_key", "apikey")


def _sensitive_key(key: str) -> bool:
    low = key.lower()
    return any(needle in low for needle in _SECRET_KEYS)


def _looks_sensitive(text: str) -> bool:
    """A full URL, or a high-entropy credential blob, is never echoed back.

    Deliberately NOT "long string": ``lightpanda-session-bridge``, a git SHA
    and an ISO timestamp are all long, non-secret strings. What separates a
    cookie value from metadata is entropy, not length.

    Values this module (or the audit writer) minted are exempt, checked before
    the entropy rules:
      * file fingerprints - the report's proof that the deployed extension is
        the repo's;
      * ISO-8601 timestamps - ``2026-09-14T18:15:40+0200`` is uppercase + digits
        and was being blanked, which silently removed WHEN each install
        happened, i.e. the ordering a support conversation needs.
    """
    if text.startswith(("http://", "https://", "ws://", "wss://")):
        return True
    if len(text) < 20:
        return False
    if "sha256:" in text:
        return False
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text):
        return False
    has_upper = any(c.isupper() for c in text)
    has_lower = any(c.islower() for c in text)
    has_digit = any(c.isdigit() for c in text)
    if has_upper and has_lower and has_digit:
        return True
    # base64-ish padding on a string that is not a plain identifier
    if any(c in "+/=~%@" for c in text) and not text.isidentifier():
        return True
    return False


def scrub(value: Any) -> Any:
    """Recursively drop anything that could carry a credential.

    Applied ONLY to data this module did not build itself - i.e. the install
    log, whose lines come from another writer. Blanking it over our own
    structured report was actively harmful: an entropy heuristic flagged the
    timestamp, the file fingerprints and the product name as "credentials" and
    deleted precisely the fields that make the report useful. Our own fields
    are chosen by us and are safe by construction.
    """
    if isinstance(value, str):
        return REDACTED if _looks_sensitive(value) else value
    if isinstance(value, dict):
        return {str(k): scrub(v) for k, v in value.items()
                if not _sensitive_key(str(k))}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    return value


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _fingerprint(path: str) -> str:
    """Presence + size + short digest: proves WHICH file, never its content.

    The result looks like ``900 B sha256:ae35d3da97e6``. It is deliberately NOT
    a full digest: a full sha256 of a file is itself an opaque high-entropy
    blob, and the scrubber would redact it - losing the single most useful
    field of the report ("is the deployed extension the one in the repo?").
    Twelve hex chars are enough to compare by eye and not a credential.
    """
    if not path:
        return "unset"
    try:
        if not os.path.exists(path):
            return "absent"
        with open(path, "rb") as fh:
            blob = fh.read()
    except OSError:
        return "unreadable"
    return "%d B sha256:%s" % (len(blob), hashlib.sha256(blob).hexdigest()[:12])


def _listing(directory: str, limit: int = 40) -> dict:
    """Which FILES exist - never their contents, and never a credential file's
    own name. ``secret`` and ``github_token`` are the two files a user would be
    shocked to see named in a report they paste into a public issue."""
    if not directory:
        return {"count": 0}
    try:
        names = sorted(n for n in os.listdir(directory) if not n.startswith("__"))
    except OSError as err:
        return {"error": type(err).__name__}
    shown = ["<credential file>" if _credential_name(n) else n for n in names]
    return {"count": len(names), "entries": shown[:limit]}


def _credential_name(name: str) -> bool:
    """Filename of anything that HOLDS a credential, not just something named
    like one. ``session.json`` is the file the relay persists cookie values
    into - a benign-looking name for the most sensitive thing in the config
    dir, and it only shows up once a session has been synced."""
    low = name.lower()
    return any(k in low for k in ("secret", "token", "credential", "cookie",
                                  "session", "state", "jar"))


def _short(value: Any, cap: int = 120) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= cap else text[:cap - 3] + "..."


def _age(timestamp: float) -> Any:
    if not timestamp:
        return None
    return int(max(0.0, time.time() - timestamp))


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# --------------------------------------------------------------------------
# the report
# --------------------------------------------------------------------------

def _same_file(a: str, b: str) -> bool:
    """True if two paths point at the same file, case-insensitively.

    Windows paths are case-insensitive and ``__file__`` arrives with whatever
    case the interpreter was launched with, so ``Server.py`` and ``server.py``
    are the same file there.
    """
    try:
        return (os.path.normcase(os.path.abspath(a))
                == os.path.normcase(os.path.abspath(b)))
    except (TypeError, ValueError):
        return False


def _sibling(name: str):
    """Return the ALREADY-IMPORTED instance of a module that sits next to us.

    Three traps, all measured here:

    1. ``relay/`` is not a package: the live process runs ``relay/server.py``
       with ``relay/`` as its import root (flat ``import updater``) while the
       tests import the package from the repo root (``from relay import
       updater``). Both spellings must work, from either direction.
    2. They must resolve to the SAME module object. Importing flat first and
       dotted second loads the file twice under two names: ``sys.modules`` then
       holds a ``server`` and a ``relay.server`` with independent globals. A
       report built from the wrong one reads empty state and answers "0 cookies"
       while the live relay holds 12.
    3. THE ONE THAT ACTUALLY BIT. In the live daemon ``server.py`` runs as the
       entry point, so its module is registered under ``__main__`` - and
       ``sys.modules`` holds NO ``server`` key at all. ``_sibling("server")``
       therefore imported a SECOND copy of the file and the report read that
       copy's globals: always empty. Measured live on 2026-10-02, while
       ``/health`` said ``attached: true, sessions: 1`` the very same
       ``/v1/diagnostics`` said ``cdp_attached: false, synced_origins: 0,
       cdp_transport: "NoneType"``. The support report - the one artefact a user
       pastes into a bug report - was describing a module that never ran.

    So: check ``__main__`` first and prefer it when it really is this file.
    """
    dotted = "relay." + name
    # __main__ wins only when it IS the module we were asked for. Comparing its
    # __file__ to our own diagnostics.py would never match; the sibling lives at
    # <our dir>/<name>.py, so compare against THAT.
    main_mod = sys.modules.get("__main__")
    if main_mod is not None:
        main_file = getattr(main_mod, "__file__", None)
        sibling_path = os.path.join(os.path.dirname(_THIS_FILE), name + ".py")
        if main_file and _same_file(main_file, sibling_path):
            return main_mod
    existing = sys.modules.get(dotted) or sys.modules.get(name)
    if existing is not None:
        return existing
    import importlib
    try:
        return importlib.import_module(name)
    except ImportError:
        return importlib.import_module(dotted)


def collect() -> dict:
    """Build the report. Public entry point, and the only thing an endpoint
    may return."""
    updater = _sibling("updater")
    relay = _sibling("server")

    ext_dir = _safe(updater.extension_dir, "") or ""
    # `session_state_path` lives in server.py (as `_session_state_path`), not in
    # updater.py, so the updater lookup below always returned None -> "" ->
    # _fingerprint("") == "unset". The report therefore claimed the session file
    # was absent on a machine where it existed, holding the cookies. Look in
    # both modules, and try the private spelling too - that is the one that is
    # actually defined.
    state_path = (getattr(relay, "_session_state_path", None)
                  or getattr(relay, "session_state_path", None)
                  or getattr(updater, "_session_state_path", None)
                  or getattr(updater, "session_state_path", None))
    state_path = _safe(state_path, None)
    state_path = state_path() if callable(state_path) else str(state_path or "")

    return {
        "schema": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "product": {
            "name": "lightpanda-session-bridge",
            "extension_dir": _short(ext_dir, 90),
            "extension_fingerprint": _fingerprint(
                os.path.join(ext_dir, "manifest.json")) if ext_dir else "unset",
            "deployed_version": _safe(_deployed_version, "unknown"),
            "deployed_commit": _safe(_deployed_commit, "unknown"),
        },
        "host": {
            "os": "%s %s" % (platform.system(), platform.release()),
            "machine": platform.machine(),
            "python": "%d.%d.%d" % sys.version_info[:3],
            "interpreter": os.path.basename(sys.executable),
        },
        "config_dir": _listing(_safe(relay._config_dir, "")),
        "artifacts": {
            "session_state": _fingerprint(state_path),
            "manifest": _fingerprint(os.path.join(ext_dir, "manifest.json")) if ext_dir else "unset",
            "build_info": _fingerprint(os.path.join(ext_dir, ".build-info.json")) if ext_dir else "unset",
        },
        "state": _state(relay, updater),
        "install_log": _install_log(updater),
    }


def _deployed_version() -> str:
    info = _check_update()
    return str(info.get("current_version") or "unknown")


def _deployed_commit() -> str:
    info = _check_update()
    commit = str(info.get("current_commit") or "")
    # `str(None)[:12]` is "None", not a hash: on a fresh checkout or a CI runner
    # there is no installed commit yet and check_update returns None for it, so
    # the report said deployed_commit = None and a test asserting a hex sha
    # failed on CI while passing locally. "unknown" is the honest answer.
    return commit[:12] if re.fullmatch(r"[0-9a-f]{7,40}", commit) else "unknown"


def _check_update() -> dict:
    try:
        data = _sibling("updater").check_update()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _state(relay, updater) -> dict:
    """Live relay state - the part that actually explains a failed sync."""
    origin = getattr(relay, "_CDP_ORIGIN", None)
    last = getattr(relay, "_LAST_SESSION", None) or {}
    return {
        "cdp_attached": getattr(relay, "_CDP_SESSION_ID", None) is not None,
        "cdp_transport": type(getattr(relay, "_CDP_TRANSPORT", None)).__name__,
        "lightpanda_origin": _short(relay.origin_hostname(origin) if origin else None),
        "synced_origins": len(getattr(relay, "_SYNCED_SESSIONS", {})),
        "storage_expected": getattr(relay, "_LAST_STORAGE_EXPECTED", 0),
        "storage_applied": getattr(relay, "_LAST_STORAGE_APPLIED_COUNT", 0),
        "storage_missing": len(getattr(relay, "_LAST_STORAGE_MISSING", []) or []),
        "persisted_applied": getattr(relay, "_PERSISTED_APPLIED", False),
        "last_sync_origin": _short(last.get("origin")),
        "last_sync_cookies": len(last.get("cookies") or []),
        # A bare boolean cannot explain a stuck chip: `False` means both
        # "nothing new" and "an update is pending but unreachable". The relay
        # now measures WHY (shipped_tree) and says it (note), so the report
        # carries the reason, not just the verdict.
        **_update_facts(),
    }


def _update_facts() -> dict:
    """The measured update state, as facts - never a computed opinion.

    `note` is the relay's own wording and contains a git sha: right for a
    diagnostic a user pastes into a bug, wrong for a UI (the popup translates
    `update_state` instead).
    """
    data = _check_update()
    return {
        "update_available": data.get("update_available"),
        "update_state": data.get("shipped_tree"),          # same / differs / unknown
        # `note` is written by the RELAY, not by this module, so it is foreign
        # text and must go through the scrubber like the install log does.
        # Measured: a note reading "Authorization: Bearer ghp_A1...Q7r8" shipped
        # 12 characters of the token in a report meant to be pasted in public,
        # because a field this module builds is trusted by construction - and
        # this one is not ours.
        "update_note": scrub(data.get("note") or "") or None,
        "update_version": data.get("current_version"),
        "update_commit": _short(data.get("current_commit")),
        "update_latest": _short(data.get("latest_commit")),
    }


def _install_log(updater) -> list:
    """Install audit lines. The writer already forbids secrets; scrub anyway."""
    path = _safe(getattr(updater, "audit_path", None), None)
    path = path() if callable(path) else str(path or "")
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = [ln for ln in fh.readlines() if ln.strip()]
    except OSError:
        return []
    # Parse PER LINE. `updater.audit()` appends with an unsynchronised open() and
    # a single write, so a power cut or a concurrent append leaves a truncated
    # last line; the old list comprehension parsed all ten or none, so one torn
    # line silently returned [] and the report lost its entire install history.
    records = []
    for ln in lines[-10:]:
        try:
            records.append(json.loads(ln))
        except ValueError:
            continue
    return scrub(records)


def to_text(report: dict) -> str:
    """Human-readable form. Same data, nothing added, nothing leaked."""
    lines = ["# Lightpanda Session Bridge - diagnostic",
             "generated_at = %s" % report.get("generated_at", "?"), ""]
    for section in ("product", "host", "config_dir", "artifacts", "state"):
        value = report.get(section)
        if isinstance(value, dict) and value:
            lines.append("[%s]" % section)
            for key, item in value.items():
                lines.append("  %s = %s" % (key, _flat(item)))
            lines.append("")
    log = report.get("install_log") or []
    if log:
        lines.append("[install_log] %d entrees (dernieres)" % len(log))
        for entry in log:
            lines.append("  %s" % _flat(entry))
    return "\n".join(lines).strip() + "\n"


def _flat(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
