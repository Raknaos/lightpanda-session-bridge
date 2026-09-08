"""Compatibility shim — the old LightpandaClient API routed through the relay.

Lightpanda scopes its cookie jar per CDP connection: a raw socket to
ws://127.0.0.1:9222 NEVER sees the sessions synced by the extension. This
shim keeps the historical API but executes every command on the relay's
persistent connection (POST /v1/cdp), exactly like bridge_agent.AuthenticatedSession.
"""
from __future__ import annotations

from bridge_agent import AuthenticatedSession, RelayError  # noqa: F401


class LightpandaClient(AuthenticatedSession):
    """Backward-compatible client. All CDP goes through the relay proxy."""

    def connect(self):
        return self

    def check_relay(self) -> dict:
        return self.health()

    def cdp_send(self, method: str, params: dict | None = None) -> dict:
        return self._call(method, params)

    def attach_or_create(self, url: str) -> str:
        # The relay holds ONE live target; sessions are already attached.
        # Kept for API compatibility — navigation happens via Page.navigate.
        return "proxied"

    def evaluate(self, expression: str, await_promise: bool = True):
        return self.js(expression, await_promise=await_promise)

    def get_cookies(self, urls: list[str] | None = None) -> list[dict]:
        return self.cookies(urls)

    def close(self):
        pass  # the relay owns the connection


if __name__ == "__main__":
    import sys
    client = LightpandaClient()
    try:
        print(f"[+] Relais status: {client.check_relay()}")
        client.open(sys.argv[1] if len(sys.argv) > 1 else "https://example.com")
        print(f"[+] Titre page: {client.evaluate('document.title')}")
    except Exception as e:
        print(f"[-] {e}")
