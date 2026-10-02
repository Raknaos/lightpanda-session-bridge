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
    low = name.lower()
    return any(k in low for k in ("secret", "token", "credential", "cookie"))


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

def _sibling(name: str):
    """Return the ALREADY-IMPORTED instance of a module that sits next to us.

    Two traps, both measured here:

    1. ``relay/`` is not a package: the live process runs ``relay/server.py``
       with ``relay/`` as its import root (flat ``import updater``) while the
       tests import the package from the repo root (``from relay import
       updater``). Both spellings must work, from either direction.
    2. They must resolve to the SAME module object. Importing flat first and
       dotted second loads the file twice under two names: ``sys.modules`` then
       holds a ``server`` and a ``relay.server`` with independent globals. A
       report built from the wrong one reads empty state and answers "0 cookies"
       while the live relay holds 12.

    So: look in ``sys.modules`` under both names and reuse whichever is already
    loaded; only fall back to importing, preferring the dotted name when the
    caller already lives in the package.
    """
    dotted = "relay." + name
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
    state_path = _safe(getattr(updater, "session_state_path", None), None)
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
        "update_available": _check_update().get("update_available"),
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
        return scrub([json.loads(ln) for ln in lines[-10:]])
    except Exception:
        return []


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
