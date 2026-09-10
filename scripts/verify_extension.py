"""Verify the running Comet extension serves the released code (version + new strings).

Comet keeps a stale error page around after runtime.reload(), so any existing
popup target is closed first and a fresh one is polled until chrome.runtime is
alive. Prints only the extension version and booleans about the served file -
never a cookie, a token or any page content.
"""
import json
import sys
import time
import urllib.request

import websocket

EXT_ID = "fcigkjkchglchhohedljlenopbkgnigno"
POPUP = f"chrome-extension://{EXT_ID}/popup.html"
CDP = "http://127.0.0.1:9223"


def http(path):
    return json.load(urllib.request.urlopen(CDP + path, timeout=8))


def connect(url):
    return websocket.create_connection(url, timeout=15, suppress_origin=True)


def rpc(ws, seq, method, params=None, session=None):
    seq[0] += 1
    msg = {"id": seq[0], "method": method, "params": params or {}}
    if session:
        msg["sessionId"] = session
    ws.send(json.dumps(msg))
    while True:
        data = json.loads(ws.recv())
        if data.get("id") == seq[0]:
            return data


def main() -> int:
    browser = connect(http("/json/version")["webSocketDebuggerUrl"])
    bseq = [0]
    # drop every stale popup page (they survive runtime.reload as error pages)
    for t in http("/json/list"):
        if t.get("url", "").startswith(POPUP):
            rpc(browser, bseq, "Target.closeTarget", {"targetId": t["id"]})
    time.sleep(1)
    created = rpc(browser, bseq, "Target.createTarget", {"url": POPUP})
    target_id = created.get("result", {}).get("targetId")
    time.sleep(3)
    attached = rpc(browser, bseq, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
    sid = attached.get("result", {}).get("sessionId")
    browser.close()

    ws = None
    for t in http("/json/list"):
        if t.get("id") == target_id:
            ws = connect(t["webSocketDebuggerUrl"])
            break
    if ws is None:
        print("cible popup introuvable")
        return 1
    seq = [0]
    rpc(ws, seq, "Runtime.enable")

    def evaluate(expr, await_promise=False):
        r = rpc(ws, seq, "Runtime.evaluate",
                {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
        return r.get("result", {}).get("result", {}).get("value")

    href, version = None, None
    for _ in range(12):
        href = evaluate("location.href")
        if href and href.startswith("chrome-extension://"):
            version = evaluate("(typeof chrome !== 'undefined' && chrome.runtime && "
                               "chrome.runtime.getManifest) ? chrome.runtime.getManifest().version : null")
            if version:
                break
        time.sleep(1)
    print("url:", href)
    print("extension version:", version)
    if version:
        served = evaluate(
            "fetch(chrome.runtime.getURL('popup.js')).then(r => r.text())"
            ".then(t => ['errPartialStorage','errStorageExtract','success: (count, keys)',"
            "'result.storage_count < storageKeys'].map(k => k + '=' + t.includes(k)).join(' '))",
            await_promise=True)
        print("code servi:", served)
    ws.close()
    return 0 if version == "0.4.3" else 2


if __name__ == "__main__":
    sys.exit(main())
