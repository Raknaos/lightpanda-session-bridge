"""Reload the unpacked bridge extension in Comet over CDP (9223) and *verify* it.

Comet loads the extension from the repo (unpacked), so after a version bump the
running copy must be reloaded for the popup to serve the new manifest. Never
prints a cookie, a token or any page content.

Two traps this script exists to close, both hit on 2026-09-10:

1. The id was hardcoded with 33 characters. Chrome answers a wrong id with an
   error page, so the script cheerfully reported "popup ouverte: True" while
   reloading nothing. The id is now read from the pin the relay writes on first
   pairing and checked against `^[a-p]{32}$` before anything happens.
2. `chrome.runtime.reload()` evaluated inside the popup does NOT refresh the
   manifest: it restarts the extension's own workers, and a freshly opened
   popup still reports the old version. Measured here: runtime.reload() left
   the popup on 0.5.2, while `chrome.developerPrivate.reload(id)` from the
   chrome://extensions page - the "Actualiser" button, driven over CDP - moved
   it to 0.5.5 on the first try.

The version is read before and after, so a reload that did not happen fails
loudly instead of printing success.
"""
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

import websocket  # websocket-client, present in the relay venv

FALLBACK_EXT_ID = "fcigkjkchglchhohedljlenopbkgnigno"
PIN = pathlib.Path(os.path.expanduser("~"), ".config", "lightpanda-bridge",
                   "pinned_extension_id")
CDP = "http://127.0.0.1:9223"
ID_RE = re.compile(r"^[a-p]{32}$")
EXTENSIONS_PAGE = "chrome://extensions/"


def extension_id() -> str:
    try:
        pinned = PIN.read_text(encoding="utf-8").strip()
    except OSError:
        pinned = ""
    for candidate in (pinned, FALLBACK_EXT_ID):
        if ID_RE.match(candidate):
            return candidate
    sys.exit("refused: no valid 32-char extension id (pin=%r)" % pinned)


def http(path):
    return json.load(urllib.request.urlopen(CDP + path, timeout=8))


def cmd(ws, method, params=None, session=None):
    ws.seq = getattr(ws, "seq", 0) + 1
    msg = {"id": ws.seq, "method": method, "params": params or {}}
    if session:
        msg["sessionId"] = session
    ws.send(json.dumps(msg))
    while True:
        data = json.loads(ws.recv())
        if data.get("id") == ws.seq:
            return data


def open_page(ws, url):
    target = cmd(ws, "Target.createTarget", {"url": url}).get("result", {}).get("targetId")
    sid = cmd(ws, "Target.attachToTarget", {"targetId": target, "flatten": True}) \
        .get("result", {}).get("sessionId")
    return target, sid


def evaljs(ws, session, expression, await_promise=False):
    out = cmd(ws, "Runtime.evaluate",
              {"expression": expression, "returnByValue": True,
               "awaitPromise": await_promise}, session=session)
    return out.get("result", {}).get("result", {}).get("value")


def popup_version(ws, popup, tries=12):
    """Open the popup and read the manifest version it actually runs."""
    target, sid = open_page(ws, popup)
    seen = None
    for _ in range(tries):
        seen = evaljs(ws, sid, "chrome && chrome.runtime && chrome.runtime.getManifest"
                               " ? chrome.runtime.getManifest().version : null")
        if seen:
            break
        time.sleep(0.5)
    cmd(ws, "Target.closeTarget", {"targetId": target})
    return seen


def main() -> int:
    ext_id = extension_id()
    popup = "chrome-extension://%s/popup.html" % ext_id
    try:
        ver = http("/json/version")
    except (urllib.error.URLError, OSError) as err:
        print("Comet unreachable on 9223: %s" % err)
        return 2
    print("extension id: ...%s (%d car, valide)" % (ext_id[-4:], len(ext_id)))
    ws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=20,
                                     suppress_origin=True)
    try:
        before = popup_version(ws, popup)
        print("version avant reload: %s" % before)
        if not before:
            print("REFUSED: rien ne repond a cet id, donc un reload serait un no-op.")
            print("         L'extension est-elle toujours chargee ? (chrome://extensions)")
            return 2
        # The extensions page is the only surface that exposes the real reload
        # action; the popup's own chrome.runtime.reload() does not pick up a new
        # manifest.
        page, sid = open_page(ws, EXTENSIONS_PAGE)
        time.sleep(1.5)
        if not evaljs(ws, sid, "typeof chrome.developerPrivate !== 'undefined'"):
            print("FAILED: chrome.developerPrivate absent - recharge a la main.")
            return 1
        out = evaljs(ws, sid, "chrome.developerPrivate.reload('%s', {failQuietly: false})"
                              ".then(() => 'ok', (e) => 'err: ' + String(e))" % ext_id,
                     await_promise=True)
        cmd(ws, "Target.closeTarget", {"targetId": page})
        print("reload: %s" % out)
        if out != "ok":
            print("FAILED: le rechargement a ete refuse.")
            return 1
    finally:
        ws.close()

    time.sleep(3)
    ws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=20,
                                     suppress_origin=True)
    try:
        after = popup_version(ws, popup)
    finally:
        ws.close()
    print("version apres reload: %s" % after)
    if not after:
        print("FAILED: le popup n'est pas revenu - recharge l'extension a la main.")
        return 1
    if after == before:
        print("NOTE: meme version avant et apres (rien a charger, ou fichier inchange).")
    else:
        print("OK: le popup sert maintenant v%s (etait v%s)." % (after, before))
    return 0


if __name__ == "__main__":
    sys.exit(main())
