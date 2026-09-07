#!/usr/bin/env python3
"""Loopback-only cookie importer for Lightpanda CDP.

No cookie values are logged or written. The caller must explicitly provide a
current HTTPS origin and its cookies after the extension confirmation step.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import websocket

HOST = "127.0.0.1"
PORT = 8765
CDP = "ws://127.0.0.1:9222/"
EXTENSION_ORIGIN = "chrome-extension://"
CDP_LOCK = threading.RLock()
_CDP_SOCKET = None
_CDP_TRANSPORT = None
_CDP_SESSION_ID = None
_CDP_TARGET_ID = None
_CDP_ORIGIN = None
BLOCKED_IDP_HOSTS = {
    "accounts.google.com", "login.microsoftonline.com", "appleid.apple.com",
    "login.live.com", "auth0.com", "github.com",
}


def valid_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment or parsed.username or parsed.password:
        return False
    if hostname in BLOCKED_IDP_HOSTS or any(hostname.endswith("." + blocked) for blocked in BLOCKED_IDP_HOSTS):
        return False
    if hostname in {"localhost", "localhost.localdomain"}:
        return False
    try:
        address = ipaddress.ip_address(hostname)
        if not address.is_global:
            return False
    except ValueError:
        pass
    return True


def origin_hostname(origin: str) -> str:
    parsed = urlparse(origin)
    return (parsed.hostname or "").lower().rstrip(".")


def domain_matches_host(cookie_domain: str, host: str) -> bool:
    domain = str(cookie_domain or "").lower().lstrip(".").rstrip(".")
    target = str(host or "").lower().rstrip(".")
    return bool(domain and target and (domain == target or target.endswith("." + domain)))


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
    allowed = {"name", "value", "domain", "path", "secure", "httpOnly", "sameSite", "expires", "priority", "url"}
    item = {k: v for k, v in cookie.items() if k in allowed}
    item["url"] = origin
    item.setdefault("path", "/")
    # Browser extension cookie records can contain unsupported nulls.
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
                raise RuntimeError("Lightpanda CDP request failed")
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


def set_cookies(origin: str, cookies: list[dict]) -> int:
    global _CDP_SOCKET, _CDP_TRANSPORT, _CDP_SESSION_ID, _CDP_TARGET_ID, _CDP_ORIGIN
    if not valid_origin(origin):
        raise ValueError("origin refused: HTTPS target origin required")
    if not isinstance(cookies, list) or not cookies or len(cookies) > 500:
        raise ValueError("cookie list refused")
    converted = [cookie_for_cdp(c, origin) for c in cookies if isinstance(c, dict) and c.get("name")]
    if not converted:
        raise ValueError("no valid cookies")

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
        _CDP_TRANSPORT.request(
            "Network.setCookies",
            {"cookies": converted},
            session_id=_CDP_SESSION_ID,
        )
        result = _CDP_TRANSPORT.request(
            "Network.getCookies",
            {"urls": [origin + "/"]},
            session_id=_CDP_SESSION_ID,
        )
        names = {str(item.get("name")) for item in result.get("cookies", [])}
        if not all(str(item["name"]) in names for item in converted):
            raise RuntimeError("Lightpanda cookie verification failed")
        return len(converted)


class Handler(BaseHTTPRequestHandler):
    server_version = "LightpandaSessionBridge/0.1"

    def log_message(self, _format: str, *_args) -> None:
        # Never log requests: request bodies may contain cookies.
        return

    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        request_origin = self.headers.get("Origin", "")
        if request_origin.startswith(EXTENSION_ORIGIN):
            self.send_header("Access-Control-Allow-Origin", request_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_json(204, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"ok": True, "service": "lightpanda-session-bridge"})
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/session/import":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise ValueError("body refused")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            count = set_cookies(payload.get("origin", ""), payload.get("cookies", []))
            self.send_json(200, {"ok": True, "cookie_count": count})
        except Exception:
            # Do not return exception details: they can contain request data.
            self.send_json(400, {"ok": False, "error": "session import refused"})


def self_test() -> int:
    assert valid_origin("https://a6api.com")
    assert not valid_origin("https://accounts.google.com")
    assert not valid_origin("http://a6api.com")
    assert cookie_for_cdp({"name": "x", "value": "y", "storeId": "secret"}, "https://a6api.com")["name"] == "x"
    assert "storeId" not in cookie_for_cdp({"name": "x", "value": "y", "storeId": "secret"}, "https://a6api.com")
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
