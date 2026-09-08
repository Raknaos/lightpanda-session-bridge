"""Authenticated agent SDK for Lightpanda — works out of the box.

Agents execute CDP through the relay's persistent connection (/v1/cdp proxy):
Lightpanda scopes its cookie jar per CDP connection, so this is the only way
an agent sees the sessions synced by the extension. The token is read from
the same file the extension pairs with (~/.config/lightpanda-bridge/secret).

Usage (zero configuration beyond `python bridge.py start`):

    from bridge_agent import AuthenticatedSession

    s = AuthenticatedSession()                # connects through the relay
    s.open("https://dev.to/settings")         # any site synced from the browser
    print(s.js("document.body.getAttribute('data-user-status')"))
    s.close()
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

RELAY = os.environ.get("LPB_RELAY", "http://127.0.0.1:8765")


def _secret_path() -> str:
    base = os.environ.get("LP_BRIDGE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".config", "lightpanda-bridge")
    return os.path.join(base, "secret")


class RelayError(RuntimeError):
    pass


class AuthenticatedSession:
    """CDP executed on the relay's connection — sessions already synced by the
    browser extension (or bridge_session transfer) are live in this context."""

    def __init__(self, relay: str = RELAY):
        self.relay = relay
        token_path = _secret_path()
        try:
            with open(token_path, encoding="utf-8") as fh:
                self.token = fh.read().strip()
        except FileNotFoundError:
            self.token = os.environ.get("LP_BRIDGE_SECRET", "")
        if not self.token:
            raise RelayError(
                "Bridge token not found — start the stack once with `python bridge.py start` "
                "and pair the extension (open its popup). Token file: " + token_path)

    # ---------- low level ----------
    def _call(self, method: str, params: dict | None = None, timeout: float = 60.0) -> dict:
        payload = json.dumps({"method": method, "params": params or {}}).encode()
        req = urllib.request.Request(
            f"{self.relay}/v1/cdp", data=payload,
            headers={"Content-Type": "application/json", "X-Bridge-Token": self.token},
            method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
        if not body.get("ok"):
            raise RelayError(body.get("error", "cdp call failed"))
        return body.get("result", {})

    # ---------- high level ----------
    def open(self, url: str, wait: float = 10.0) -> None:
        """Navigate the live target. Do NOT poll readyState: evaluating on a
        navigating context returns None and can poison later evaluates."""
        self._call("Page.navigate", {"url": url})
        time.sleep(wait)

    def js(self, expr: str, await_promise: bool = False, tries: int = 5, delay: float = 2.0):
        """Evaluate with retry-on-None (a navigating context yields null)."""
        p: dict = {"expression": expr, "returnByValue": True}
        if await_promise:
            p["awaitPromise"] = True
        for _ in range(tries):
            res = self._call("Runtime.evaluate", p)
            v = res.get("result", {}).get("value")
            if v is not None:
                return v
            time.sleep(delay)
        return None

    def cookies(self, urls: list[str] | None = None) -> list[dict]:
        res = self._call("Network.getCookies", {"urls": urls} if urls else {})
        return res.get("cookies", [])

    def health(self) -> dict:
        with urllib.request.urlopen(f"{self.relay}/health", timeout=5) as r:
            return json.loads(r.read().decode())

    def close(self) -> None:
        pass  # the relay owns the connection; nothing to close


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    s = AuthenticatedSession()
    print("health:", s.health())
    s.open(url)
    print("title:", s.js("document.title"))
    status = s.js("document.body ? document.body.getAttribute('data-user-status') : null")
    print("user-status:", status)
