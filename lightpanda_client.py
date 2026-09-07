"""
Lightpanda Client SDK
Fournit une API Python simple pour manipuler Lightpanda via CDP
avec la session préalablement synchronisée par le bridge.
"""
from __future__ import annotations

import json
import urllib.request
import websocket


class LightpandaClient:
    def __init__(self, cdp_ws: str = "ws://127.0.0.1:9222/", relay_url: str = "http://127.0.0.1:8765"):
        self.cdp_ws = cdp_ws
        self.relay_url = relay_url
        self.ws = None
        self.msg_id = 0
        self.session_id = None
        self.target_id = None

    def check_relay(self) -> dict:
        """Vérifie l'état de santé du relais."""
        req = urllib.request.Request(f"{self.relay_url}/health")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())

    def connect(self):
        """Se connecte au serveur CDP de Lightpanda."""
        if not self.ws:
            self.ws = websocket.create_connection(self.cdp_ws, timeout=15, suppress_origin=True)
        return self

    def cdp_send(self, method: str, params: dict | None = None) -> dict:
        """Envoie une commande CDP avec gestion des messages asynchrones."""
        if not self.ws:
            self.connect()
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        if self.session_id:
            payload["sessionId"] = self.session_id

        self.ws.send(json.dumps(payload))
        while True:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self.msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error: {data['error']}")
                return data.get("result", {})

    def attach_or_create(self, url: str) -> str:
        """Attache ou crée une page pour l'URL cible."""
        targets = self.cdp_send("Target.getTargets").get("targetInfos", [])
        pages = [t for t in targets if t.get("type") == "page"]
        if pages:
            self.target_id = pages[0]["targetId"]
        else:
            self.target_id = self.cdp_send("Target.createTarget", {"url": url})["targetId"]

        res = self.cdp_send("Target.attachToTarget", {"targetId": self.target_id, "flatten": True})
        self.session_id = res["sessionId"]
        return self.session_id

    def evaluate(self, expression: str, await_promise: bool = True):
        """Exécute une expression JS dans le contexte de la page."""
        res = self.cdp_send("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True
        })
        return res.get("result", {}).get("value")

    def get_cookies(self, urls: list[str] | None = None) -> list[dict]:
        """Lit les cookies actuels dans Lightpanda."""
        params = {"urls": urls} if urls else {}
        res = self.cdp_send("Network.getCookies", params)
        return res.get("cookies", [])

    def close(self):
        """Ferme la connexion CDP."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None


if __name__ == "__main__":
    client = LightpandaClient()
    try:
        health = client.check_relay()
        print(f"[+] Relais status: {health}")
    except Exception as e:
        print(f"[-] Relais inaccessible: {e}")

    try:
        client.connect()
        client.attach_or_create("https://example.com")
        title = client.evaluate("document.title")
        print(f"[+] Lightpanda connecté avec succès. Titre page: {title}")
    except Exception as e:
        print(f"[-] Erreur Lightpanda: {e}")
    finally:
        client.close()
