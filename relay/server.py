#!/usr/bin/env python3
"""Loopback-only session importer for Lightpanda CDP.

No credentials, passwords, or tokens are logged. The caller must explicitly
provide a valid public HTTPS origin, its cookies, and optional storage entries.
"""
from __future__ import annotations

import argparse
import hmac
import ipaddress
import json
import os
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import websocket

# updater.py sits next to this file; make the import work whether the relay is
# started as `python relay/server.py` or imported by the test suite.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import updater  # noqa: E402  (local module)

HOST = "127.0.0.1"
PORT = 8765
CDP = "ws://127.0.0.1:9222/"
CDP_LOCK = threading.RLock()
_CDP_SOCKET = None
_CDP_TRANSPORT = None
_CDP_SESSION_ID = None
_CDP_TARGET_ID = None
_CDP_ORIGIN = None
_DNS_CACHE: dict = {}
_DNS_CACHE_TTL = 60.0
BLOCKED_IDP_HOSTS = {
    # Actual identity-provider LOGIN endpoints only. Regular sites users log
    # into (github.com, gitlab.com, x.com, ...) are legitimate sync targets —
    # the whole point of the bridge is handing SITE sessions to agents.
    "accounts.google.com", "login.microsoftonline.com", "appleid.apple.com",
    "login.live.com", "auth0.com",
}
# Suffixes that must never be treated as registrable parent domains (cookie domain)
PUBLIC_SUFFIXES = {
    "com", "org", "net", "io", "co", "fr", "de", "uk", "us", "eu", "ru", "cn",
    "app", "dev", "ai", "cloud", "page", "site", "tech", "store", "online", "xyz",
    "com.au", "co.uk", "com.br", "co.jp", "com.cn", "co.in", "com.mx", "co.za",
}

def _load_secret() -> str:
    """Load the shared secret from the local secret file or env var.
    The secret file lives OUTSIDE the repo (~/.config/lightpanda-bridge/secret)
    so it is never committed. The extension stores the same value under the
    chrome.storage key 'lpBridgeToken'."""
    env = os.environ.get("LP_BRIDGE_SECRET")
    if env:
        return env
    path = _secret_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            value = fh.read().strip()
            if value:
                if os.name != "nt":
                    try:
                        if (os.stat(path).st_mode & 0o077) != 0:
                            _harden_path(path)
                    except OSError:
                        pass
                return value
    except FileNotFoundError:
        pass
    # Generate a fresh random secret and persist it owner-only from creation
    # (write-then-chmod leaves a window where the file is world-readable).
    import secrets
    value = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _harden_path(os.path.dirname(path), directory=True)
        _write_owner_only(path, value)
    except OSError:
        pass
    return value


def _config_dir() -> str:
    """Cross-platform per-user config path, never inside the repo."""
    return os.environ.get("LP_BRIDGE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".config", "lightpanda-bridge"
    )


def _secret_path() -> str:
    return os.path.join(_config_dir(), "secret")


def _session_state_path() -> str:
    return os.path.join(_config_dir(), "session.json")


def _harden_path(path: str, directory: bool = False) -> None:
    """Best-effort owner-only permissions for a secret-bearing path.

    POSIX: 0700/0600. Windows: NTFS ACL (chmod is mostly cosmetic there), so
    the file is re-ACL'd to the current user only. Never raises."""
    mode = 0o700 if directory else 0o600
    try:
        os.chmod(path, mode)
    except OSError:
        pass
    if os.name != "nt":
        return
    try:
        import subprocess
        user = os.environ.get("USERNAME") or ""
        if not user:
            return
        grant = f"{user}:(F)"
        if directory:
            grant = f"{user}:(OI)(CI)(F)"
        subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", grant],
                       capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def _write_owner_only(path: str, text: str) -> None:
    """Create/replace a file readable only by its owner (no chmod race)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    _harden_path(path)


def _persist_session(state: dict | None) -> None:
    """Remember the last synced session on disk so a relay restart, a reboot
    or a crashed watchdog cannot silently drop the user's authentication.

    Cookie values are written to a 0600 owner-only file outside the repo and
    are never logged. Passing None erases the file."""
    path = _session_state_path()
    try:
        if state is None:
            if os.path.exists(path):
                os.remove(path)
            return
        os.makedirs(_config_dir(), exist_ok=True)
        _harden_path(_config_dir(), directory=True)
        _write_owner_only(path, json.dumps(state))
    except OSError:
        pass


def _load_persisted_session() -> dict | None:
    """Read back a session persisted by a previous relay process."""
    try:
        with open(_session_state_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if (isinstance(data, dict) and isinstance(data.get("origin"), str)
            and isinstance(data.get("cookies"), list) and data["cookies"]):
        return data
    return None


def _pinned_extension_path() -> str:
    return os.path.join(_config_dir(), "pinned_extension_id")


EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")
OFFICIAL_EXTENSION_ID = "fcigkjkchglchhohedljlenopbkgnino"
_PINNED_EXTENSION_ID: str | None = None


def extract_extension_id(origin: str) -> str | None:
    """Extract a clean 32-character Chrome extension ID from an origin, or None."""
    if not origin or not origin.startswith("chrome-extension://"):
        return None
    raw = origin[len("chrome-extension://"):].rstrip("/")
    ext_id = raw.split("/")[0].split(":")[0].lower()
    if EXTENSION_ID_RE.fullmatch(ext_id):
        return ext_id
    return None


def _load_pinned_extension_id() -> str | None:
    """Load the pinned extension ID from disk cache, memory, or fallback to official ID.
    If LP_BRIDGE_TOFU=1 is explicitly set, allows open first-caller TOFU."""
    global _PINNED_EXTENSION_ID
    if _PINNED_EXTENSION_ID is not None:
        return _PINNED_EXTENSION_ID
    path = _pinned_extension_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            val = fh.read().strip().lower()
            if EXTENSION_ID_RE.fullmatch(val):
                _PINNED_EXTENSION_ID = val
                return val
    except (FileNotFoundError, OSError):
        pass
    if os.environ.get("LP_BRIDGE_TOFU") == "1":
        return None
    return OFFICIAL_EXTENSION_ID


def _save_pinned_extension_id(ext_id: str) -> None:
    """Persist the pinned extension ID to disk."""
    global _PINNED_EXTENSION_ID
    _PINNED_EXTENSION_ID = ext_id
    path = _pinned_extension_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _harden_path(os.path.dirname(path), directory=True)
        _write_owner_only(path, ext_id)
    except OSError:
        pass


def _clear_pinned_extension_cache() -> None:
    """Reset the pinned extension ID in memory (useful for testing)."""
    global _PINNED_EXTENSION_ID
    _PINNED_EXTENSION_ID = None


def _get_allowed_extension_ids() -> set[str]:
    """Return set of explicitly allowed extension IDs from env var."""
    allowed = set()
    env_ids = os.environ.get("LP_BRIDGE_ALLOWED_EXTENSION_IDS", "")
    if env_ids:
        for item in env_ids.split(","):
            cleaned = item.strip().lower()
            if EXTENSION_ID_RE.fullmatch(cleaned):
                allowed.add(cleaned)
    return allowed


def is_valid_extension_origin(origin: str, auto_pin: bool = False) -> bool:
    """Validate origin against pinned or explicitly allowed extension IDs.
    If auto_pin is True and no extension is pinned yet, pin the extension ID
    on first use (TOFU - Trust On First Use)."""
    ext_id = extract_extension_id(origin)
    if not ext_id:
        return False
    pinned = _load_pinned_extension_id()
    if not pinned:
        # Only the bootstrap handshake (auto_pin=True) may admit an unknown
        # extension: with LP_BRIDGE_TOFU=1 the previous code returned True for
        # ANY chrome-extension:// origin on non-pinning endpoints too.
        if auto_pin:
            _save_pinned_extension_id(ext_id)
            return True
        return False
    allowed = _get_allowed_extension_ids()
    return ext_id == pinned or ext_id in allowed


def _is_global_hostname(hostname: str) -> bool:
    """Resolve DNS and confirm every answer is a global (non-loopback,
    non-private, non-link-local, non-reserved) IP. Rejects split-horizon and
    public-suffix wildcard tricks (nip.io, localtest.me, .localhost)."""
    if not hostname:
        return False
    # Reject obvious non-canonical numeric encodings before DNS
    lowered = hostname.lower()
    # IPv4-mapped IPv6 forms handled by ipaddress below; reject hex/octal/dword ints
    if lowered.startswith(("0x", "0o", "0b")):
        return False
    # Reject non-canonical numeric IPv4 representations (e.g. octal leading zeros like 0177.0.0.1)
    parts = lowered.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts) and any(len(p) > 1 and p.startswith("0") for p in parts):
        return False
    # Reject any hostname ending with a public-suffix wildcard service
    for suffix in (".nip.io", ".localhost", ".local", ".internal", ".lan", ".home.arpa"):
        if lowered.endswith(suffix):
            return False
    try:
        now = time.time()
        cached = _DNS_CACHE.get(hostname)
        if cached and (now - cached[0]) < _DNS_CACHE_TTL:
            return cached[1]
        infos = socket.getaddrinfo(hostname, None)
        if not infos:
            return False
        for info in infos:
            try:
                address = ipaddress.ip_address(info[4][0])
            except ValueError:
                return False
            if not address.is_global:
                _DNS_CACHE[hostname] = (now, False)
                return False
        _DNS_CACHE[hostname] = (now, True)
        return True
    except socket.gaierror:
        return False


def valid_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    raw_hostname = parsed.hostname or ""
    hostname = raw_hostname.lower().rstrip(".")
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment or parsed.username or parsed.password:
        return False
    if not hostname:
        return False
    # Normalize IDNA: reject confusable non-ASCII hostnames outright
    try:
        hostname.encode("ascii")
    except UnicodeEncodeError:
        return False
    if hostname in BLOCKED_IDP_HOSTS or any(hostname.endswith("." + blocked) for blocked in BLOCKED_IDP_HOSTS):
        return False
    if hostname in {"localhost", "localhost.localdomain"}:
        return False
    # Canonical numeric forms (IPv4-mapped IPv6 included) rejected here
    try:
        address = ipaddress.ip_address(hostname)
        if not address.is_global:
            return False
        return True
    except ValueError:
        pass
    # Hostnames must be strictly DNS-safe: letters, digits, hyphen, dots only
    import re
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*", hostname):
        return False
    return _is_global_hostname(hostname)


def origin_hostname(origin: str) -> str:
    parsed = urlparse(origin)
    return (parsed.hostname or "").lower().rstrip(".")


def domain_matches_host(cookie_domain: str, host: str) -> bool:
    domain = str(cookie_domain or "").lower().lstrip(".").rstrip(".")
    target = str(host or "").lower().rstrip(".")
    if not domain or not target:
        return False
    if domain == target:
        return True
    if not target.endswith("." + domain):
        return False
    # Never allow a public suffix as cookie domain: a cookie can't be set for
    # Domain=com (x.com), Domain=co.uk (a.co.uk), Domain=io, etc. A registrable
    # domain like 'a6api.com' is fine even though it ends with '.com'.
    if domain in PUBLIC_SUFFIXES:
        return False
    return True


def cookie_for_cdp(cookie: dict, origin: str) -> dict:
    if not isinstance(cookie, dict) or not cookie.get("name"):
        raise ValueError("invalid cookie")
    host = origin_hostname(origin)
    cookie_domain = str(cookie.get("domain") or host)
    if not domain_matches_host(cookie_domain, host):
        raise ValueError("cookie domain does not match target origin")
    supplied_url = str(cookie.get("url") or "")
    if supplied_url:
        parsed_url = urlparse(supplied_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != host:
            raise ValueError("cookie url does not match target origin")
    # Strip unsupported or risky internal Chrome attributes
    allowed = {"name", "value", "domain", "path", "secure", "httpOnly", "sameSite", "expires", "url"}
    item = {k: v for k, v in cookie.items() if k in allowed}

    # Handle __Host- prefix strict RFC compliance:
    # Cookies with __Host- prefix MUST have path='/' and NO domain attribute set in CDP
    if str(item.get("name", "")).startswith("__Host-"):
        item["path"] = "/"
        item.pop("domain", None)
    else:
        item.setdefault("path", "/")

    # __Secure- prefixed cookies MUST be Secure (RFC 6265bis)
    if str(item.get("name", "")).startswith("__Secure-"):
        item["secure"] = True

    item["url"] = origin

    # Lightpanda drops cookies set with an `expires` attribute (verified: cookies
    # with expires silently vanish from its jar, breaking the whole session).
    # Omit it: the injected cookie becomes a session cookie for the runtime,
    # which is the correct lifetime for a transferred session anyway.
    item.pop("expires", None)

    # Normalize sameSite enum for Lightpanda CDP:
    # Chrome extension API returns lowercase: 'unspecified', 'no_restriction', 'lax', 'strict'
    # CDP expects: 'Strict', 'Lax', 'None' (InvalidEnumTag error if lowercase or unknown)
    if "sameSite" in item:
        raw_ss = str(item["sameSite"]).lower()
        if raw_ss in ("strict",):
            item["sameSite"] = "Strict"
        elif raw_ss in ("lax",):
            item["sameSite"] = "Lax"
        elif raw_ss in ("none", "no_restriction"):
            # sameSite=None requires Secure per RFC 6265bis; enforce it
            item["sameSite"] = "None"
            item["secure"] = True
        else:
            del item["sameSite"]

    return {k: v for k, v in item.items() if v is not None}


class CdpTransport:
    def __init__(self, socket):
        self.socket = socket
        self.next_id = 0

    def request(self, method: str, params: dict | None = None, session_id: str | None = None) -> dict:
        self.next_id += 1
        payload = {"id": self.next_id, "method": method, "params": params or {}}
        if session_id:
            payload["sessionId"] = session_id
        self.socket.send(json.dumps(payload))
        while True:
            response = json.loads(self.socket.recv())
            if response.get("id") != self.next_id:
                continue
            if "error" in response:
                raise RuntimeError(f"Lightpanda CDP request failed: {response['error']}")
            return response.get("result", {})


def attach_page(transport: CdpTransport, url: str) -> tuple[str, str]:
    targets = transport.request("Target.getTargets").get("targetInfos", [])
    pages = [item for item in targets if item.get("type") == "page"]
    if pages:
        target_id = pages[0]["targetId"]
    else:
        target_id = transport.request("Target.createTarget", {"url": url})["targetId"]
    session_id = transport.request(
        "Target.attachToTarget", {"targetId": target_id, "flatten": True}
    )["sessionId"]
    return target_id, session_id


# Last synced session, MEMORY ONLY (never written to disk). If Lightpanda
# restarts, the daemon re-injects it automatically so the session survives.
_LAST_SESSION: dict | None = None
# Every synced session this daemon run: origin -> converted cookie list
# (values kept in memory only, never logged, never returned by the API).
_SYNCED_SESSIONS: dict[str, list[dict]] = {}


def _ensure_connection(origin: str) -> None:
    """Open the CDP connection if needed. The connection is NEVER discarded on
    origin change: Lightpanda scopes its cookie jar per connection, so tearing
    it down would wipe every previously synced session."""
    global _CDP_SOCKET, _CDP_TRANSPORT, _CDP_SESSION_ID, _CDP_TARGET_ID
    if _CDP_TRANSPORT is not None:
        return
    if _CDP_SOCKET is not None:
        try:
            _CDP_SOCKET.close()
        except Exception:
            pass
    _CDP_SOCKET = websocket.create_connection(CDP, timeout=15, suppress_origin=True)
    _CDP_TRANSPORT = CdpTransport(_CDP_SOCKET)
    _CDP_TARGET_ID, _CDP_SESSION_ID = attach_page(_CDP_TRANSPORT, origin)


def _connection_resync() -> None:
    """Reconnect to Lightpanda (e.g. after a restart) and replay the last
    synced session from memory so agents keep their authenticated context."""
    global _CDP_SOCKET, _CDP_TRANSPORT, _CDP_SESSION_ID, _CDP_TARGET_ID
    with CDP_LOCK:
        origin = _LAST_SESSION["origin"] if _LAST_SESSION else "https://example.com"
        _CDP_SOCKET = None
        _CDP_TRANSPORT = None
        _CDP_SESSION_ID = None
        _CDP_TARGET_ID = None
        _ensure_connection(origin)
        if _LAST_SESSION:
            # Cookies AND localStorage must both be replayed: with cookies only,
            # every console call comes back 407 (the SPA builds its
            # New-Api-User header from localStorage["user"]).
            _apply_session(origin, _LAST_SESSION["cookies"],
                           _LAST_SESSION.get("storage"))


# Bounds that protect the relay from an abusive payload - NOT a statement about
# what a real application may store. The old "key < 128 chars, value < 16384"
# pair looked generous until x.com showed up with 194-character keys
# (rweb.sessionBinding.hashClaim:<base64>): the filter dropped them in SILENCE,
# Lightpanda received 5 of the 7 keys, and the popup's honest counter read
# "5/7 keys" forever - re-syncing could never fix it, because the two keys were
# removed before the very first write attempt.
MAX_KEY_CHARS = 1024        # real keys are namespaced and long, not 128 chars
MAX_VALUE_CHARS = 262144    # 256 KiB per value: SPAs cache whole blobs
MAX_TOTAL_CHARS = 1500000   # stays under the 2 MB /v1/session/import body cap


def _short_key(name: str, limit: int = 60) -> str:
    """Truncate a key NAME for reporting.

    Key names are metadata - as safe to report as a cookie name. VALUES are
    session secrets: they are never logged, returned or written to disk.
    """
    name = str(name)
    return name if len(name) <= limit else name[:limit] + "..."


def _storage_plan(storage: dict) -> tuple[dict, list]:
    """Split a snapshot into (entries to transfer, entries refused + reason).

    Nothing is ever dropped in silence. A refused entry comes back BY NAME with
    its size and the reason, so the caller can report what is missing instead of
    a ratio that can never reach 100%.
    """
    if not isinstance(storage, dict):
        return {}, []
    entries: dict = {}
    refused: list = []
    total = 0
    for key, value in storage.items():
        name = str(key)
        text = str(value)
        if len(name) > MAX_KEY_CHARS:
            refused.append((_short_key(name), len(name), "key name too long"))
        elif len(text) > MAX_VALUE_CHARS:
            refused.append((_short_key(name), len(text), "value too large"))
        elif total + len(text) > MAX_TOTAL_CHARS:
            refused.append((_short_key(name), len(text), "snapshot too large"))
        else:
            entries[name] = text
            total += len(text)
    return entries, refused


def _storage_entries(storage: dict) -> dict:
    """Sanitize a localStorage snapshot: bounded key/value sizes only."""
    return _storage_plan(storage)[0]


def _register_storage_restore(storage: dict) -> bool:
    """Make localStorage survive EVERY later navigation of this target.

    Lightpanda keeps localStorage in the page context, so injecting it and then
    navigating wipes it (the 'user' key vanished -> every authenticated call
    came back 407 "New-Api-User header not provided"). Re-registering a
    document-start restore is the durable fix: the snapshot is re-applied on
    each new document instead of relying on one lucky injection.
    """
    entries = _storage_entries(storage)
    if not entries:
        return False
    source = ("(function(){try{var d=" + json.dumps(entries) +
              ";for(var k in d){try{localStorage.setItem(k,d[k]);}catch(e){}}"
              "}catch(e){}})();")
    try:
        _CDP_TRANSPORT.request(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": source},
            session_id=_CDP_SESSION_ID,
        )
        return True
    except Exception:
        return False


# Delay allowed for the page context to settle after a navigation before
# localStorage is written (tests set it to 0).
_NAV_SETTLE_SECONDS = 1.5

# Keys the snapshot still expected / the page still lacked after the last
# injection. NAMES only - values are session secrets and are never kept here.
_LAST_STORAGE_EXPECTED = 0
_LAST_STORAGE_MISSING: list = []
_LAST_STORAGE_APPLIED_COUNT = 0
# [name, size, reason] for every key the size bounds refused (reported, never
# dropped in silence). Names only.
_LAST_STORAGE_REFUSED: list = []


def _missing_from_verify(raw) -> list:
    """Normalize the page's verification result into a list of missing NAMES.

    Accepts the legacy integer form too (0 = complete), so an older or simpler
    transport can never turn a complete transfer into a false failure.
    """
    if isinstance(raw, bool):
        return []
    if isinstance(raw, int):
        return [] if raw == 0 else ["<unknown>"] * max(raw, 1)
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return ["<unreadable>"]
    if isinstance(data, dict):
        miss = data.get("missing")
        if isinstance(miss, list):
            return [str(x) for x in miss if str(x)]
        count = data.get("missing_count")
        if isinstance(count, int):
            return [] if count == 0 else ["<unknown>"] * count
        return ["<unreadable>"]
    if isinstance(data, list):
        return [str(x) for x in data if str(x)]
    if isinstance(data, int):
        return [] if data == 0 else ["<unknown>"] * max(data, 1)
    return ["<unreadable>"]


def _apply_session(origin: str, cookies: list[dict], storage: dict | None = None) -> int:
    """Push a session onto the live Lightpanda page: cookies, then storage.

    Order is load-bearing: navigate FIRST, inject localStorage AFTER (a
    navigation after the injection wipes it), then register the document-start
    restore so no later navigation can lose it either."""
    _ensure_connection(origin)
    _CDP_TRANSPORT.request(
        "Network.setCookies", {"cookies": cookies}, session_id=_CDP_SESSION_ID
    )
    try:
        _CDP_TRANSPORT.request(
            "Page.navigate", {"url": origin + "/"}, session_id=_CDP_SESSION_ID
        )
        time.sleep(_NAV_SETTLE_SECONDS)
    except Exception:
        pass
    if isinstance(storage, dict) and storage:
        count = _inject_storage(origin, storage)
        _register_storage_restore(storage)
        return count
    return 0


def _inject_storage(origin: str, storage: dict) -> int:
    """Set localStorage keys on the live page and return how many were VERIFIED.

    Must run AFTER the page is on the target origin (see _apply_session).

    Verification is per key on purpose. "Some keys landed" is not success: a
    SPA that rebuilds an auth header from localStorage (a6api reads
    localStorage["user"] to send New-Api-User) answers 401/407 the moment ONE
    key is missing. That was the real shape of the bug reported as "the session
    only works after a second sync": 17 of 29 keys landed, `user` was among the
    dropped ones, and the write still reported success. Returns -1 when the
    snapshot is still incomplete after the retries.
    """
    global _LAST_STORAGE_MISSING
    entries = _storage_entries(storage)
    if not entries:
        return 0
    entries_json = json.dumps(entries)
    keys_json = json.dumps(sorted(entries))
    write_expr = ("(() => { try { const data = " + entries_json + "; "
                  "for (const k of Object.keys(data)) { try { "
                  "localStorage.setItem(k, data[k]); } catch (e) {} } "
                  "return Object.keys(data).length; } catch (e) { return -1; } })()")
    # Keys the snapshot still needs: an empty list means the transfer is
    # complete. The NAMES come back (never the values) so a failure can say
    # exactly which key is missing instead of a bare ratio.
    verify_expr = ("(() => { try { const want = " + keys_json + "; const miss = []; "
                   "for (const k of want) { if (localStorage.getItem(k) === null) "
                   "miss.push(k); } return JSON.stringify({ missing: miss }); } "
                   "catch (e) { return JSON.stringify({ missing: want }); } })()")
    for attempt in range(4):
        try:
            _CDP_TRANSPORT.request(
                "Runtime.evaluate",
                {"expression": write_expr, "returnByValue": True},
                session_id=_CDP_SESSION_ID,
            )
            res = _CDP_TRANSPORT.request(
                "Runtime.evaluate",
                {"expression": verify_expr, "returnByValue": True},
                session_id=_CDP_SESSION_ID,
            )
            missing = _missing_from_verify(res.get("result", {}).get("value", -1))
            if not missing:
                _LAST_STORAGE_MISSING = []
                return len(entries)
            _LAST_STORAGE_MISSING = missing
        except Exception as err:
            _LAST_STORAGE_MISSING = ["<verify failed: %s>" % err]
            pass
        # A navigation replays a previously registered document-start restore
        # and gives the page a fresh, clean context to write into.
        if attempt == 0:
            try:
                _CDP_TRANSPORT.request(
                    "Page.navigate", {"url": origin + "/"}, session_id=_CDP_SESSION_ID
                )
                time.sleep(_NAV_SETTLE_SECONDS)
            except Exception:
                pass
        time.sleep(0.5)
    return -1


def set_session(origin: str, cookies: list[dict], storage: dict | None = None) -> tuple[int, int]:
    global _LAST_SESSION
    if not valid_origin(origin):
        raise ValueError("origin refused: HTTPS target origin required")
    if not isinstance(cookies, list) or not cookies or len(cookies) > 500:
        raise ValueError("cookie list refused")
    converted = [cookie_for_cdp(c, origin) for c in cookies if isinstance(c, dict) and c.get("name")]
    if not converted:
        raise ValueError("no valid cookies")

    storage_count = 0
    global _LAST_STORAGE_APPLIED_COUNT
    global _LAST_STORAGE_REFUSED
    _LAST_STORAGE_APPLIED_COUNT = 0

    # Sanitize BEFORE the live page is touched. A key the relay cannot carry has
    # to fail fast AND by name: the x.com bug was a silent removal here, which
    # showed up as a permanent "5/7 keys" that no re-sync could ever clear.
    safe_storage, refused_storage = _storage_plan(storage or {})
    _LAST_STORAGE_REFUSED = ["%s [%s, %d chars]" % (n, w, sz)
                             for n, sz, w in refused_storage]
    if refused_storage:
        detail = ", ".join("%s [%s, %d chars]" % (n, w, sz)
                           for n, sz, w in refused_storage[:5])
        raise RuntimeError("localStorage key(s) refused by relay: " + detail)

    with CDP_LOCK:
        _ensure_connection(origin)

        storage_count = _apply_session(origin, converted, safe_storage)
        _LAST_STORAGE_APPLIED_COUNT = max(storage_count, 0)

        # Verification via Network.getCookies
        result = _CDP_TRANSPORT.request(
            "Network.getCookies",
            {"urls": [origin + "/", f"https://{origin_hostname(origin)}/"]},
            session_id=_CDP_SESSION_ID,
        )
        names = {str(item.get("name")) for item in result.get("cookies", [])}
        if not names:
            # Fallback verification without urls filter
            fallback = _CDP_TRANSPORT.request("Network.getCookies", {}, session_id=_CDP_SESSION_ID)
            names = {str(item.get("name")) for item in fallback.get("cookies", [])}
        if not any(str(item["name"]) in names for item in converted):
            raise RuntimeError("Lightpanda cookie verification failed: no cookies found")

        # Remember the session for automatic resync after a Lightpanda restart
        # AND persist it, so a relay restart / reboot / watchdog restart no
        # longer forces the user to click "Synchroniser" again.
        _LAST_SESSION = {"origin": origin, "cookies": converted, "storage": safe_storage}
        _SYNCED_SESSIONS[origin] = converted
        _persist_session(_LAST_SESSION)

        # A half-transferred localStorage snapshot is worse than a visible
        # failure: cookies + some keys look "synced" while every authenticated
        # call returns 401/407. Bookkeeping is done (a resync can finish the
        # job), but the caller is told the truth.
        expected_storage = len(safe_storage)
        global _LAST_STORAGE_EXPECTED
        _LAST_STORAGE_EXPECTED = expected_storage
        if expected_storage and storage_count != expected_storage:
            # ``x/y keys verified (missing: <names>)``: the names are what makes
            # this actionable. Without them the same mystery ratio came back on
            # every single sync.
            missing_detail = ""
            if _LAST_STORAGE_MISSING:
                missing_detail = " (missing: %s)" % ", ".join(
                    _short_key(k, 40) for k in _LAST_STORAGE_MISSING[:5]
                )
            raise RuntimeError(
                "localStorage transfer incomplete: %d/%d keys verified%s"
                % (max(storage_count, 0), expected_storage, missing_detail)
            )

        return len(converted), storage_count


_PERSISTED_LOADED = False
_PERSISTED_APPLIED = False


def _restore_persisted_session() -> bool:
    """Bring back the session saved by a previous relay process.

    Two separate steps on purpose: the state is LOADED once (so /v1/sessions
    reports it immediately) and APPLIED whenever Lightpanda is reachable, with
    a retry on every call until it succeeds. Before this, a relay restart left
    a "healthy" relay (attached: false) with an empty cookie jar, and agent
    calls silently ran unauthenticated - the exact failure users saw as
    "the session disappeared between two runs".
    """
    global _LAST_SESSION, _PERSISTED_LOADED, _PERSISTED_APPLIED
    if not _PERSISTED_LOADED:
        _PERSISTED_LOADED = True
        if not _LAST_SESSION:
            state = _load_persisted_session()
            if state:
                _LAST_SESSION = state
                _SYNCED_SESSIONS.setdefault(state["origin"], state["cookies"])
    if _PERSISTED_APPLIED or not _LAST_SESSION:
        return False
    try:
        with CDP_LOCK:
            _apply_session(_LAST_SESSION["origin"], _LAST_SESSION["cookies"],
                           _LAST_SESSION.get("storage"))
        _PERSISTED_APPLIED = True
        return True
    except Exception:
        return False


def proxy_cdp(method: str, params: dict | None = None) -> dict:
    """Execute a CDP command on the daemon's persistent connection.

    Agents MUST go through this proxy: Lightpanda scopes its cookie jar per
    CDP connection, so a socket opened by an agent would see none of the
    synced session cookies. One connection, owned by the relay, shared by all."""
    if not method or not isinstance(method, str) or not re_fullmatch_method(method):
        raise ValueError("invalid CDP method")
    if params is not None and not isinstance(params, dict):
        raise ValueError("invalid CDP params")
    blocked = ("Browser.close", "Target.disposeBrowserContext", "Network.deleteCookies")
    if method in blocked:
        raise ValueError("method refused by proxy")
    with CDP_LOCK:
        try:
            _ensure_connection("https://example.com")
            _restore_persisted_session()
            return _CDP_TRANSPORT.request(method, params, session_id=_CDP_SESSION_ID)
        except (websocket.WebSocketException, OSError, RuntimeError):
            # Connection lost (Lightpanda restarted?) -> resync + one retry
            _connection_resync()
            return _CDP_TRANSPORT.request(method, params, session_id=_CDP_SESSION_ID)


def list_sessions() -> list[dict]:
    """Sanitized view of synced sessions: origin, cookie count, expiry metadata.
    Never returns cookie values."""
    try:
        _restore_persisted_session()
    except Exception:
        pass
    out = []
    for origin, cookies in _SYNCED_SESSIONS.items():
        host = origin_hostname(origin)
        now = time.time()
        expiries = [c.get("expires", -1) for c in cookies
                    if isinstance(c, dict) and isinstance(c.get("expires", -1), (int, float)) and c.get("expires", -1) > 0]
        next_expiry = min(expiries) if expiries else None
        out.append({
            "origin": origin,
            "host": host,
            "cookie_count": len(cookies),
            "expires": next_expiry,
            "expired": bool(next_expiry and next_expiry < now),
        })
    return out


def clear_sessions(origin: str | None = None) -> int:
    """Remove cookies from Lightpanda for one origin or every synced origin.
    Returns the number of origins cleared."""
    with CDP_LOCK:
        targets = [origin] if origin else list(_SYNCED_SESSIONS.keys())
        cleared = 0
        for org in targets:
            host = origin_hostname(org)
            try:
                res = _CDP_TRANSPORT.request(
                    "Network.getCookies",
                    {"urls": [org + "/", f"https://{host}/"]},
                    session_id=_CDP_SESSION_ID,
                ) if _CDP_TRANSPORT else {"cookies": []}
            except Exception:
                try:
                    _ensure_connection(org)
                    res = _CDP_TRANSPORT.request(
                        "Network.getCookies",
                        {"urls": [org + "/", f"https://{host}/"]},
                        session_id=_CDP_SESSION_ID,
                    )
                except Exception:
                    res = {"cookies": []}
            removed = 0
            for c in res.get("cookies", []):
                try:
                    _CDP_TRANSPORT.request(
                        "Network.deleteCookies",
                        {"name": c["name"], "domain": c.get("domain", host)},
                        session_id=_CDP_SESSION_ID,
                    )
                    removed += 1
                except Exception:
                    pass
            was_synced = org in _SYNCED_SESSIONS
            _SYNCED_SESSIONS.pop(org, None)
            if _LAST_SESSION and _LAST_SESSION.get("origin") == org:
                globals()["_LAST_SESSION"] = None
            if removed or was_synced:
                cleared += 1
        # Erase the persisted copy too: "Tout retirer" must mean it is gone,
        # not that it comes back at the next restart.
        if globals().get("_LAST_SESSION") is None:
            _persist_session(None)
        return cleared


def re_fullmatch_method(method: str) -> bool:
    import re as _re
    return bool(_re.fullmatch(r"[A-Za-z]+\.[A-Za-z]+", method))


class Handler(BaseHTTPRequestHandler):
    # Neutral banner: the enum response is readable by any local process, so it
    # carries no product name or version.
    server_version = "loopback-relay"
    sys_version = ""

    def log_message(self, _format: str, *_args) -> None:
        return

    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # CORS is only reflected for valid chrome-extension:// callers (the popup needs
        # it to read responses). Web pages and untrusted extensions never get CORS.
        request_origin = self.headers.get("Origin", "")
        if request_origin.startswith("chrome-extension://") and is_valid_extension_origin(request_origin):
            self.send_header("Access-Control-Allow-Origin", request_origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Token")
            # Private Network Access opt-in: only ever advertised to the pinned
            # extension, never to a web page probing 127.0.0.1.
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        """Require the shared bridge token on every state-changing call.
        The extension stores the same value under chrome.storage 'lpBridgeToken'."""
        supplied = self.headers.get("X-Bridge-Token", "")
        expected = _load_secret()
        if not expected or not supplied:
            return False
        return hmac.compare_digest(supplied, expected)

    def _check_extension_caller(self) -> bool:
        """Caller must be the pinned chrome extension (the popup) or local CLI tooling
        (no Origin header). Any web page origin (https://...) or untrusted extension is refused."""
        request_origin = self.headers.get("Origin", "")
        if not request_origin:
            return True
        return is_valid_extension_origin(request_origin, auto_pin=False)

    def _require_extension_origin(self) -> bool:
        """STRICT variant for secret-delivering endpoints: an Origin header
        from the pinned chrome-extension:// is mandatory (TOFU on first call).
        Requests with no Origin (curl, CLI tools, malware probes) or from
        untrusted extensions are refused so the shared secret can never be exfiltrated."""
        request_origin = self.headers.get("Origin", "")
        if not request_origin:
            return False
        return is_valid_extension_origin(request_origin, auto_pin=True)

    def do_OPTIONS(self) -> None:
        if not self._check_extension_caller():
            self.send_json(403, {"ok": False, "error": "origin refused"})
            return
        self.send_json(204, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            # Sanitized health: no active origin, no PII, no page URL.
            self.send_json(200, {
                "ok": True,
                "service": "lightpanda-session-bridge",
                "attached": _CDP_SESSION_ID is not None
            })
        elif self.path == "/v1/bootstrap":
            # One-time pairing handshake: delivers the shared secret to the
            # official extension so it can authenticate /v1/session/import.
            # STRICT extension origin required (web pages and Origin-less
            # local processes get 403: they must never read the secret).
            if not self._require_extension_origin():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            self.send_json(200, {"ok": True, "token": _load_secret()})
        elif self.path == "/v1/sessions":
            # Sanitized list of synced sessions (no cookie values, no URLs).
            # Requires valid extension or CLI caller and the shared token.
            if not self._check_extension_caller():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            if not self._authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            sessions = list_sessions()
            self.send_json(200, {"ok": True, "sessions": sessions, "count": len(sessions)})
        elif self.path == "/v1/update/check":
            # Read-only: which version is deployed, and does GitHub have a
            # newer release (or a newer commit on main)? Versions and hashes
            # only - no secret, no cookie, nothing about a browsing session.
            # No token required so the background badge can poll it; the caller
            # still has to be the pinned extension (or local CLI tooling).
            if not self._check_extension_caller():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            try:
                self.send_json(200, updater.check_update())
            except Exception as err:
                self.send_json(200, {"ok": False, "error": str(err) or "update check failed"})
        elif self.path == "/v1/session/inspect":
            # Removed: leaked cookie names, origin, page URL/title to any caller.
            self.send_json(404, {"ok": False, "error": "not found"})
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/v1/sessions/clear":
            # Remove synced cookies from Lightpanda: one origin or all.
            # Requires valid extension or CLI caller and the shared token (state-changing).
            if not self._check_extension_caller():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            if not self._authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 10_000:
                    raise ValueError("body refused")
                origin = None
                if length > 0:
                    self.connection.settimeout(10)
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    origin = payload.get("origin") or None
                    if origin is not None:
                        if not isinstance(origin, str) or not valid_origin(origin):
                            raise ValueError("origin refused")
                cleared = clear_sessions(origin)
                self.send_json(200, {"ok": True, "cleared": cleared})
            except Exception as err:
                self.send_json(400, {"ok": False, "error": str(err) or "clear refused"})
            return
        if self.path == "/v1/cdp":
            # CDP proxy for agents: executes on the daemon's persistent
            # connection (the ONLY connection that holds the synced sessions).
            # Local-only tooling: no Origin means no web page can call it.
            # State-changing CDP requires the shared token like /import.
            if not self._check_extension_caller():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            if not self._authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("body refused")
                self.connection.settimeout(30)
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result = proxy_cdp(payload.get("method", ""), payload.get("params"))
                self.send_json(200, {"ok": True, "result": result})
            except Exception as err:
                self.send_json(400, {"ok": False, "error": str(err) or "cdp call refused"})
            return
        if self.path == "/v1/update/apply":
            # Download the newest release (or the newest main commit) from
            # GitHub and write it into the live unpacked extension directory.
            # State-changing and filesystem-touching: pinned origin AND the
            # shared token, exactly like /v1/session/import.
            if not self._check_extension_caller():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            if not self._authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            try:
                source = "auto"
                length = int(self.headers.get("Content-Length", "0"))
                if length > 2_000:
                    raise ValueError("body refused")
                if length > 0:
                    self.connection.settimeout(10)
                    payload = json.loads(self.rfile.read(length).decode("utf-8")) or {}
                    source = payload.get("source") or "auto"
                if source not in ("auto", "release", "main"):
                    raise ValueError("unknown update source")
                self.send_json(200, updater.apply_update(source))
            except Exception as err:
                self.send_json(400, {"ok": False, "error": str(err) or "update refused"})
            return
        if self.path == "/v1/update/rollback":
            # Undo the last update from the backup made before it ran.
            if not self._check_extension_caller():
                self.send_json(403, {"ok": False, "error": "origin refused"})
                return
            if not self._authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            try:
                self.send_json(200, updater.rollback_update())
            except Exception as err:
                self.send_json(400, {"ok": False, "error": str(err) or "rollback refused"})
            return
        if self.path != "/v1/session/import":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        if not self._check_extension_caller():
            self.send_json(403, {"ok": False, "error": "origin refused"})
            return
        if not self._authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise ValueError("body refused")
            # Enforce a read timeout so slow/stalled bodies cannot exhaust threads.
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            cookies = payload.get("cookies", [])
            origin = payload.get("origin", "")
            storage = payload.get("storage")
            cookie_count, storage_count = set_session(origin, cookies, storage)
            self.send_json(200, {
                "ok": True,
                "cookie_count": cookie_count,
                "storage_count": storage_count,
                "storage_expected": _LAST_STORAGE_EXPECTED,
                "storage_refused": list(_LAST_STORAGE_REFUSED),
                "origin": origin
            })
        except Exception as err:
            # The counts and the missing NAMES ride along with the failure, so
            # the popup can build a translated, specific message instead of
            # showing the relay's raw text.
            self.send_json(400, {
                "ok": False,
                "error": str(err) or "session import refused",
                "storage_count": _LAST_STORAGE_APPLIED_COUNT,
                "storage_expected": _LAST_STORAGE_EXPECTED,
                "storage_missing": list(_LAST_STORAGE_MISSING[:5]),
                "storage_refused": list(_LAST_STORAGE_REFUSED),
            })


def self_test() -> int:
    # Global public HTTPS hosts
    assert valid_origin("https://a6api.com")
    assert valid_origin("https://mail.google.com")
    assert valid_origin("https://console.runpod.io")
    # Blocked IdPs, http scheme, localhost/loopback, private IPs
    assert not valid_origin("https://accounts.google.com")
    assert not valid_origin("http://a6api.com")
    assert not valid_origin("https://localhost")
    assert not valid_origin("https://127.0.0.1")
    assert not valid_origin("https://10.0.0.4")
    assert not valid_origin("https://192.168.1.5")
    # Non-canonical numeric encodings of loopback/private (SSRF bypasses)
    assert not valid_origin("https://127.1")
    assert not valid_origin("https://2130706433")
    assert not valid_origin("https://0x7f000001")
    assert not valid_origin("https://0177.0.0.1")
    assert not valid_origin("https://[::ffff:127.0.0.1]")
    # Wildcard public-suffix / split-horizon services
    assert not valid_origin("https://foo.127.0.0.1.nip.io")
    assert not valid_origin("https://localtest.me")
    assert not valid_origin("https://foo.localhost")
    # Non-ASCII confusable hostnames (IDNA)
    assert not valid_origin("https://аccounts.google.com")
    # Cookie domain validation
    assert domain_matches_host("a6api.com", "a6api.com")
    assert domain_matches_host("a6api.com", "sub.a6api.com")
    assert not domain_matches_host("com", "x.com")
    assert not domain_matches_host("co.uk", "a.co.uk")
    assert cookie_for_cdp({"name": "x", "value": "y", "storeId": "secret"}, "https://a6api.com")["name"] == "x"
    assert "storeId" not in cookie_for_cdp({"name": "x", "value": "y", "storeId": "secret"}, "https://a6api.com")
    # __Secure- and sameSite=None cookies must be forced Secure
    c = cookie_for_cdp({"name": "__Secure-x", "value": "y", "domain": "a6api.com"}, "https://a6api.com")
    assert c.get("secure") is True
    c2 = cookie_for_cdp({"name": "x", "value": "y", "sameSite": "no_restriction", "domain": "a6api.com"}, "https://a6api.com")
    assert c2.get("secure") is True and c2.get("sameSite") == "None"
    # Extension ID extraction and validation
    assert extract_extension_id("chrome-extension://fcigkjkchglchhohedljlenopbkgnino") == "fcigkjkchglchhohedljlenopbkgnino"
    assert extract_extension_id("chrome-extension://fcigkjkchglchhohedljlenopbkgnino/") == "fcigkjkchglchhohedljlenopbkgnino"
    assert extract_extension_id("chrome-extension://invalid-id") is None
    assert extract_extension_id("https://example.com") is None
    assert extract_extension_id("") is None
    # Unknown extension is only admitted by the bootstrap handshake.
    # Sandbox the config dir: auto_pin writes the pin, and a self-test must
    # never overwrite the user's real pinned extension id.
    import tempfile
    sandbox = tempfile.mkdtemp(prefix="lp-bridge-selftest-")
    prev_cfg = os.environ.get("LP_BRIDGE_CONFIG_DIR")
    os.environ["LP_BRIDGE_CONFIG_DIR"] = sandbox
    os.environ["LP_BRIDGE_TOFU"] = "1"
    _clear_pinned_extension_cache()
    try:
        assert not is_valid_extension_origin("chrome-extension://aaaabbbbccccddddeeeeffffgggghhhh", auto_pin=False)
        assert is_valid_extension_origin("chrome-extension://aaaabbbbccccddddeeeeffffgggghhhh", auto_pin=True)
    finally:
        os.environ.pop("LP_BRIDGE_TOFU", None)
        if prev_cfg is None:
            os.environ.pop("LP_BRIDGE_CONFIG_DIR", None)
        else:
            os.environ["LP_BRIDGE_CONFIG_DIR"] = prev_cfg
        _clear_pinned_extension_cache()
        import shutil as _shutil
        _shutil.rmtree(sandbox, ignore_errors=True)
    # --- updater (the "Update" button in the popup) -----------------------
    assert updater.parse_version("v0.4.3") == (0, 4, 3, "")
    assert updater.parse_version("0.5.0-rc1") == (0, 5, 0, "rc1")
    assert updater.parse_version("nonsense") is None
    assert updater.is_newer("0.5.0", "0.4.3")
    assert not updater.is_newer("0.4.3", "0.4.3")
    assert not updater.is_newer("0.4.2", "0.4.3")
    assert updater.is_newer("0.5.0", "0.5.0-rc1")        # a final beats its rc
    assert updater.is_newer("0.5.0-rc2", "0.5.0-rc1")
    assert not updater.is_newer("0.4.3", "nonsense")     # unparsable never wins

    # An archive that tries to leave its own directory, or that carries an
    # absolute path, must be refused before anything is written.
    import io as _io
    import tarfile as _tar
    import zipfile as _zip
    _tmpdir = tempfile.mkdtemp(prefix="lp-bridge-selftest-archive-")
    try:
        _zip_path = os.path.join(_tmpdir, "bad.zip")
        with _zip.ZipFile(_zip_path, "w") as _z:
            _z.writestr("../../evil.txt", "x")
        _tar_path = os.path.join(_tmpdir, "bad.tar.gz")
        with _tar.open(_tar_path, "w:gz") as _t:
            for _name in ("../evil.txt", "/abs/evil.txt"):
                _member = _tar.TarInfo(_name)
                _member.size = 1
                _t.addfile(_member, _io.BytesIO(b"x"))
        for _path in (_zip_path, _tar_path):
            try:
                updater.extract_archive(_path, os.path.join(_tmpdir, "out"))
                raise AssertionError("a traversal archive was accepted")
            except RuntimeError as _err:
                assert "traversal" in str(_err) or "absolute" in str(_err), str(_err)
        assert not os.path.exists(os.path.join(os.path.dirname(_tmpdir), "evil.txt"))
        # A tree with no extension/manifest.json is refused before any write.
        _empty = os.path.join(_tmpdir, "empty")
        os.makedirs(_empty, exist_ok=True)
        try:
            updater.locate_extension_root(_empty)
            raise AssertionError("an archive without the extension was accepted")
        except RuntimeError:
            pass
    finally:
        _shutil.rmtree(_tmpdir, ignore_errors=True)

    print("security self-test: ok")
    return 0


class RelayServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a SECOND process bind an already-listening
    # port, which silently produced two relays: one owning the synced sessions,
    # the other answering "attached: false" to every agent. Keep it exclusive.
    allow_reuse_address = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--check-update", action="store_true",
                        help="print the GitHub update status as JSON and exit")
    parser.add_argument("--apply-update", action="store_true",
                        help="install the newest release/commit into the extension dir")
    parser.add_argument("--rollback-update", action="store_true",
                        help="restore the tree saved by the previous update")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.check_update:
        print(json.dumps(updater.check_update(force=True), indent=2, ensure_ascii=True))
        return 0
    if args.apply_update:
        print(json.dumps(updater.apply_update(), indent=2, ensure_ascii=True))
        return 0
    if args.rollback_update:
        print(json.dumps(updater.rollback_update(), indent=2, ensure_ascii=True))
        return 0
    try:
        server = RelayServer((HOST, args.port), Handler)
    except OSError as err:
        # Address already in use: a relay is already serving this port (the
        # watchdog and the scheduled task can race). Exiting 0 keeps Task
        # Scheduler from restart-looping the task forever.
        if getattr(err, "errno", None) in (48, 98, 10048) or "in use" in str(err).lower():
            print(f"[relay] port {args.port} already served by another relay; nothing to do")
            return 0
        raise
    print(f"[relay] listening on http://{HOST}:{args.port}")  # ASCII only: cp1252 consoles
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
