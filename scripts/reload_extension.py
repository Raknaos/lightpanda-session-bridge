"""Reload the unpacked bridge extension in Comet over CDP (9223).

Comet loads the extension from the repo (unpacked), so after a version bump the
running copy must be reloaded for the popup to serve the new code. Evaluates
chrome.runtime.reload() inside the extension's own popup page - never prints a
cookie, a token or any page content.
"""
import json
import sys
import urllib.request

import websocket  # websocket-client, present in the relay venv

EXT_ID = "fcigkjkchglchhohedljlenopbkgnigno"
POPUP = f"chrome-extension://{EXT_ID}/popup.html"
CDP = "http://127.0.0.1:9223"


def http(path):
    return json.load(urllib.request.urlopen(CDP + path, timeout=8))


def main() -> int:
    ver = http("/json/version")
    ws_url = ver["webSocketDebuggerUrl"]
    # Chrome refuses a WS handshake that carries an unprefixed Origin header
    # (unless --remote-allow-origins is set); sending none is accepted.
    ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)
    seq = [0]

    def cmd(method, params=None, session=None):
        seq[0] += 1
        msg = {"id": seq[0], "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        ws.send(json.dumps(msg))
        while True:
            data = json.loads(ws.recv())
            if data.get("id") == seq[0]:
                return data

    created = cmd("Target.createTarget", {"url": POPUP})
    target_id = created.get("result", {}).get("targetId")
    print("popup ouverte:", bool(target_id))
    attached = cmd("Target.attachToTarget", {"targetId": target_id, "flatten": True})
    sid = attached.get("result", {}).get("sessionId")
    before = cmd("Runtime.evaluate",
                 {"expression": "chrome.runtime.getManifest().version", "returnByValue": True},
                 session=sid)
    print("version avant reload:", before.get("result", {}).get("result", {}).get("value"))
    cmd("Runtime.evaluate", {"expression": "chrome.runtime.reload()"}, session=sid)
    print("reload envoye")
    ws.close()

    # the reload tears the target down and brings the popup back with new code
    import time
    time.sleep(4)
    names = [t.get("url", "") for t in http("/json/list")]
    print("popup presente apres reload:", any(POPUP in n for n in names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
