#!/usr/bin/env python3
"""Loopback-only session importer for Lightpanda CDP.

No credentials, passwords, or tokens are logged. The caller must explicitly
provide a valid public HTTPS origin, its cookies, and optional storage entries.
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
    allowed = {"name", "value", "domain", "path", "secure", "httpOnly", "sameSite", "expires", "url"}
    item = {k: v for k, v in cookie.items() if k in allowed}
    # Do not pass 'priority' or 'sourceScheme' as Lightpanda CDP rejects them with NotImplemented
    item["url"] = origin
    item.setdefault("path", "/")

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
            item["sameSite"] = "None"
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
        request_origin = self.headers.get("Origin", "")
        if request_origin.startswith(EXTENSION_ORIGIN):
            self.send_header("Access-Control-Allow-Origin", request_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_json(204, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {
                "ok": True,
                "service": "lightpanda-session-bridge",
                "active_origin": _CDP_ORIGIN,
                "attached": _CDP_SESSION_ID is not None
            })
        elif self.path == "/v1/session/inspect":
            with CDP_LOCK:
                if _CDP_TRANSPORT is None or _CDP_SESSION_ID is None:
                    self.send_json(200, {"active": False, "error": "no active session"})
                    return
                try:
                    res = _CDP_TRANSPORT.request("Network.getCookies", {}, session_id=_CDP_SESSION_ID)
                    cookies = res.get("cookies", [])
                    names = [c.get("name") for c in cookies]
                    eval_res = _CDP_TRANSPORT.request(
                        "Runtime.evaluate",
                        {"expression": "({ title: document.title, url: window.location.href })", "returnByValue": True},
                        session_id=_CDP_SESSION_ID
                    )
                    page_info = eval_res.get("result", {}).get("value", {})
                    self.send_json(200, {
                        "active": True,
                        "origin": _CDP_ORIGIN,
                        "cookie_count": len(cookies),
                        "cookie_names": names,
                        "page": page_info
                    })
                except Exception as e:
                    self.send_json(500, {"error": str(e)})
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
