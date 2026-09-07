"""
A6API Session Exporter & Lightpanda Bridge
Automatise le transfert de session sans manipulations complexes d'extension si nécessaire.
"""
import json
import urllib.request
import websocket
import sys

RELAY_URL = "http://127.0.0.1:8765/v1/session/import"
CHROME_CDP = "http://127.0.0.1:9223"
LIGHTPANDA_CDP = "ws://127.0.0.1:9222/"

def _load_token() -> str:
    """Read the shared bridge token from the local secret file (~/.config/
    lightpanda-bridge/secret), same source as the relay. Returns '' if absent."""
    import os
    env = os.environ.get("LP_BRIDGE_SECRET")
    if env:
        return env
    path = os.path.join(os.path.expanduser("~"), ".config", "lightpanda-bridge", "secret")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""

def extract_and_transfer():
    try:
        tabs = json.loads(urllib.request.urlopen(f"{CHROME_CDP}/json/list").read())
    except Exception as e:
        print(f"[-] Impossible de joindre Chrome sur {CHROME_CDP}: {e}")
        return False

    a6_tab = next((t for t in tabs if "a6api.com" in t.get("url", "") and t.get("type") == "page"), None)
    if not a6_tab:
        print("[-] Aucun onglet a6api.com ouvert dans le navigateur Chrome.")
        return False

    print(f"[+] Onglet détecté: {a6_tab.get('title')} ({a6_tab.get('url')})")
    ws_url = a6_tab.get("webSocketDebuggerUrl")
    ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)

    # 1. Cookies
    ws.send(json.dumps({"id": 1, "method": "Network.getCookies", "params": {"urls": ["https://a6api.com/"]}}))
    cookies = json.loads(ws.recv())["result"]["cookies"]

    # 2. LocalStorage
    ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": "localStorage.getItem('user')", "returnByValue": True}}))
    user_val = json.loads(ws.recv())["result"]["result"]["value"]
    ws.close()

    user_dict = json.loads(user_val) if user_val else {}
    # Never print account identifiers: username, email, or numeric ID may end up
    # in agent logs / chat history. Only the cookie count is logged.
    print(f"[+] {len(cookies)} cookie(s) de session trouvés.")

    # 3. Envoyer au Relais (authentifié par le jeton partagé local)
    req = urllib.request.Request(
        RELAY_URL,
        data=json.dumps({"origin": "https://a6api.com", "cookies": cookies}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Bridge-Token": _load_token(),
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read().decode())
        print(f"[+] Transfert relais Lightpanda: {res}")
        return True

if __name__ == "__main__":
    extract_and_transfer()
