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
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import websocket

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
    "accounts.google.com", "login.microsoftonline.com", "appleid.apple.com",
    "login.live.com", "auth0.com", "github.com",
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
                return value
    except FileNotFoundError:
        pass
    # Generate a fresh random secret and persist it
    import secrets
    value = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(value)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return value


def _secret_path() -> str:
    """Cross-platform per-user config path, never inside the repo."""
    base = os.environ.get("LP_BRIDGE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".config", "lightpanda-bridge"
    )
    return os.path.join(base, "secret")


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


def set_session(origin: str, cookies: list[dict], storage: dict | None = None) -> tuple[int, int]:
    global _CDP_SOCKET, _CDP_TRANSPORT, _CDP_SESSION_ID, _CDP_TARGET_ID, _CDP_ORIGIN
    if not valid_origin(origin):
        raise ValueError("origin refused: HTTPS target origin required")
    if not isinstance(cookies, list) or not cookies or len(cookies) > 500:
        raise ValueError("cookie list refused")
    converted = [cookie_for_cdp(c, origin) for c in cookies if isinstance(c, dict) and c.get("name")]
    if not converted:
        raise ValueError("no valid cookies")

    storage_count = 0
    with CDP_LOCK:
        if _CDP_TRANSPORT is None or _CDP_ORIGIN != origin:
            if _CDP_SOCKET is not None:
                try:
                    _CDP_SOCKET.close()
                except Exception:
                    pass
            _CDP_SOCKET = websocket.create_connection(CDP, timeout=15, suppress_origin=True)
            _CDP_TRANSPORT = CdpTransport(_CDP_SOCKET)
            _CDP_TARGET_ID, _CDP_SESSION_ID = attach_page(_CDP_TRANSPORT, origin)
            _CDP_ORIGIN = origin

        # Inject cookies via Network.setCookies
        _CDP_TRANSPORT.request(
            "Network.setCookies",
            {"cookies": converted},
            session_id=_CDP_SESSION_ID,
        )

        # Inject localStorage if provided
        if isinstance(storage, dict) and storage:
            # Build safe js injection script
            entries_json = json.dumps({str(k): str(v) for k, v in storage.items() if len(str(k)) < 128 and len(str(v)) < 16384})
            expr = f"""(() => {{
                try {{
                    const data = {entries_json};
                    for (const [k, v] of Object.entries(data)) {{
                        localStorage.setItem(k, v);
                    }}
                    return Object.keys(data).length;
                }} catch (e) {{
                    return -1;
                }}
            }})()"""
            try:
                res = _CDP_TRANSPORT.request(
                    "Runtime.evaluate",
                    {"expression": expr, "returnByValue": True},
                    session_id=_CDP_SESSION_ID
                )
                val = res.get("result", {}).get("value", 0)
                if val > 0:
                    storage_count = val
            except Exception:
                pass

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

        return len(converted), storage_count


class Handler(BaseHTTPRequestHandler):
    server_version = "LightpandaSessionBridge/0.2"

    def log_message(self, _format: str, *_args) -> None:
        return

    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # CORS is only reflected for chrome-extension:// callers (the popup needs
        # it to read responses). Web pages never get CORS -> their cross-origin
        # POSTs die at the preflight. State changes additionally require the
        # shared X-Bridge-Token (see _authorized), so a rogue extension cannot
        # import/overwrite a session either.
        request_origin = self.headers.get("Origin", "")
        if request_origin.startswith("chrome-extension://"):
            self.send_header("Access-Control-Allow-Origin", request_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Token")
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
        """Caller must be a chrome extension (the popup) or local CLI tooling
        (no Origin header). Any web page origin (https://...) is refused."""
        request_origin = self.headers.get("Origin", "")
        if not request_origin:
            return True
        return request_origin.startswith("chrome-extension://")

    def _require_extension_origin(self) -> bool:
        """STRICT variant for secret-delivering endpoints: an Origin header
        starting with chrome-extension:// is mandatory. Requests with no
        Origin (curl, CLI tools, malware probes) are refused so the shared
        secret can never be exfiltrated by a plain local process."""
        request_origin = self.headers.get("Origin", "")
        return request_origin.startswith("chrome-extension://")

    def do_OPTIONS(self) -> None:
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
        elif self.path == "/v1/session/inspect":
            # Removed: leaked cookie names, origin, page URL/title to any caller.
            self.send_json(404, {"ok": False, "error": "not found"})
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
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
                "origin": origin
            })
        except Exception as err:
            self.send_json(400, {"ok": False, "error": str(err) or "session import refused"})


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
    print("security self-test: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    ThreadingHTTPServer((HOST, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
