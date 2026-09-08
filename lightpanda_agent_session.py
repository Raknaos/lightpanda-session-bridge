#!/usr/bin/env python3
"""Single-connection authenticated agent session for Lightpanda.

Lightpanda scopes the cookie jar per CDP connection: cookies injected by the
relay (its own connection) are invisible to an agent socket. The working
pattern is therefore: ONE connection does pull -> inject -> navigate -> act.

Cookie values are pulled from the logged-in desktop browser (Comet) over
loopback CDP and injected into Lightpanda over loopback CDP. Values are never
logged, printed, or persisted.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import websocket

LP_CDP = "ws://127.0.0.1:9222/"
COMET_CDP = "http://127.0.0.1:9223"


class LightpandaAgentSession:
    """Authenticated browsing session inside Lightpanda for automation."""

    def __init__(self, origin: str = "https://dev.to", debug_port: int = 9223):
        self.origin = origin.rstrip("/")
        self.host = urllib.parse.urlparse(self.origin).hostname
        self.debug_port = debug_port
        self.ws = websocket.create_connection(LP_CDP, timeout=60, suppress_origin=True)
        self.mid = 0
        self.tid: str | None = None
        self.sid: str | None = None

    # ---------- low level ----------
    def _cmd(self, method: str, params: dict | None = None, session: bool = False) -> dict:
        self.mid += 1
        payload = {"id": self.mid, "method": method, "params": params or {}}
        if session and self.sid:
            payload["sessionId"] = self.sid  # flatten mode: top-level field
        self.ws.send(json.dumps(payload))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.mid:
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error']}")
                return r.get("result", {})

    # ---------- cookies from the desktop browser ----------
    def pull_cookies_from_comet(self) -> list[dict]:
        tabs = json.loads(urllib.request.urlopen(f"{COMET_CDP}/json/list").read())
        tab = next((t for t in tabs if t.get("type") == "page" and self.host in t.get("url", "")), None)
        if not tab:
            req = urllib.request.Request(
                f"{COMET_CDP}/json/new?" + urllib.parse.quote(self.origin, safe=""), method="PUT")
            tab = json.loads(urllib.request.urlopen(req, timeout=10).read())
            time.sleep(6)
            tabs = json.loads(urllib.request.urlopen(f"{COMET_CDP}/json/list").read())
            tab = next(t for t in tabs if t.get("type") == "page" and self.host in t.get("url", ""))
        ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
        try:
            ws.send(json.dumps({"id": 1, "method": "Network.getCookies",
                                "params": {"urls": [self.origin + "/"]}}))
            while True:
                r = json.loads(ws.recv())
                if r.get("id") == 1:
                    return r.get("result", {}).get("cookies", [])
        finally:
            ws.close()

    # ---------- session import on THIS connection ----------
    def import_session(self, cookies: list[dict]) -> int:
        self.tid = self._cmd("Target.createTarget", {"url": self.origin})["targetId"]
        self.sid = self._cmd("Target.attachToTarget",
                             {"targetId": self.tid, "flatten": True})["sessionId"]
        time.sleep(5)
        old = self._cmd("Network.getCookies",
                        {"urls": [self.origin + "/"]}, session=True).get("cookies", [])
        for c in old:
            self._cmd("Network.deleteCookies",
                      {"name": c["name"], "domain": c.get("domain", self.host)}, session=True)
        n = 0
        for c in cookies:
            dom = c.get("domain") or ("." + self.host)
            params = {"name": c["name"], "value": c["value"],
                      "domain": dom if dom.startswith(".") else "." + self.host,
                      "path": c.get("path", "/"), "url": self.origin + "/"}
            if c.get("httpOnly"):
                params["httpOnly"] = True
            if c.get("secure"):
                params["secure"] = True
            r = self._cmd("Network.setCookie", params, session=True)
            if r.get("success"):
                n += 1
        return n

    # ---------- navigation / actions ----------
    def goto(self, url: str, wait: float = 10.0) -> None:
        """Navigate and wait. Do NOT poll readyState during load: evaluating on a
        navigating context returns None and can poison subsequent evaluates."""
        self._cmd("Page.navigate", {"url": url}, session=True)
        time.sleep(wait)

    def js(self, expr: str, await_promise: bool = False, tries: int = 5, delay: float = 2.0):
        """Evaluate with retry-on-None (a navigating context yields null results)."""
        p: dict = {"expression": expr, "returnByValue": True}
        if await_promise:
            p["awaitPromise"] = True
        for _ in range(tries):
            r = self._cmd("Runtime.evaluate", p, session=True)
            v = r.get("result", {}).get("result", {}).get("value")
            if v is not None:
                return v
            time.sleep(delay)
        return None

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    s = LightpandaAgentSession("https://dev.to")
    try:
        cookies = s.pull_cookies_from_comet()
        print("cookies Comet:", [c["name"] for c in cookies])
        n = s.import_session(cookies)
        print("injectés:", n)
        s.goto("https://dev.to/settings")
        print("title:", s.js("document.title"))
        print("user-status:", s.js("document.body.getAttribute('data-user-status')"))
    finally:
        s.close()
