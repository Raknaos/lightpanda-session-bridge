# -*- coding: utf-8 -*-
"""Shared CDP helpers for the extension scripts (Comet on 9223).

The extension id used to be copy-pasted into every script, and one of those
copies carried 33 characters - Chrome answers a wrong id with an error page, so
`reload_extension.py` reloaded nothing while printing success and
`verify_extension.py` reported `chrome-error://chromewebdata/` for a day. The id
now comes from the pin the relay writes on first pairing and is validated here,
once, for every caller.

Never prints a cookie, a token or any page content: versions, urls and booleans
only.
"""
import json
import os
import pathlib
import re
import sys

try:
    import websocket  # websocket-client, present in the project venv
except ImportError:  # pragma: no cover - environment, not logic
    raise SystemExit(
        "websocket-client missing: run this with the project interpreter\n"
        "  .venv/Scripts/python.exe %s\n"
        "  (.venv/Scripts/pip install -r requirements.txt)"
        % __import__("os").path.basename(__import__("sys").argv[0]))

COMET_CDP = "http://127.0.0.1:9223"
ID_RE = re.compile(r"^[a-p]{32}$")
PIN = pathlib.Path(os.path.expanduser("~"), ".config", "lightpanda-bridge",
                   "pinned_extension_id")


UPDATES_XML = pathlib.Path(__file__).resolve().parent.parent / "updates.xml"


def declared_extension_id() -> str:
    """The id the repository declares, read from updates.xml.

    No id is ever typed into a script: a hand-copied one carried 33 characters
    and made two scripts lie. updates.xml is the single place the id belongs
    (it is Chrome's update manifest), so everything else derives from it.
    """
    try:
        xml = UPDATES_XML.read_text(encoding="utf-8")
    except OSError:
        return ""
    import re as _re
    found = _re.search(r"appid='([^']+)'", xml)
    return (found.group(1) if found else "").strip()


def extension_id(strict: bool = True) -> str:
    """The extension id: the pin the relay wrote, else what the repo declares.

    Validated either way - 32 characters, a-p only - because a wrong id opens an
    error page and Chrome says nothing about it.
    """
    try:
        pinned = PIN.read_text(encoding="utf-8").strip()
    except OSError:
        pinned = ""
    for candidate in (pinned, declared_extension_id()):
        if ID_RE.match(candidate):
            return candidate
    if strict:
        sys.exit("refused: no valid 32-char extension id (pin=%r, updates.xml=%r)"
                 % (pinned, declared_extension_id()))
    return ""


def popup_url(ext_id: str) -> str:
    return "chrome-extension://%s/popup.html" % ext_id


def http(path: str):
    import urllib.request
    return json.load(urllib.request.urlopen(COMET_CDP + path, timeout=8))


def connect(url=None):
    if url is None:
        url = http("/json/version")["webSocketDebuggerUrl"]
    return websocket.create_connection(url, timeout=20, suppress_origin=True)


def rpc(ws, method, params=None, session=None):
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
    target = rpc(ws, "Target.createTarget", {"url": url}).get("result", {}).get("targetId")
    sid = rpc(ws, "Target.attachToTarget", {"targetId": target, "flatten": True}) \
        .get("result", {}).get("sessionId")
    return target, sid


def close_page(ws, target):
    try:
        rpc(ws, "Target.closeTarget", {"targetId": target})
    except Exception:
        pass


def evaluate(ws, session, expression, await_promise=False):
    out = rpc(ws, "Runtime.evaluate",
              {"expression": expression, "returnByValue": True,
               "awaitPromise": await_promise}, session=session)
    return out.get("result", {}).get("result", {}).get("value")


def popup_version(ws=None, tries: int = 12):
    """Open the popup and read the manifest version it actually runs.

    None means the page did not answer as the extension - a wrong id, or the
    extension not loaded - which the caller must treat as a failure, never as
    "nothing to do".
    """
    ext_id = extension_id()
    own = ws is None
    ws = ws or connect()
    try:
        target, sid = open_page(ws, popup_url(ext_id))
        if not sid:
            return None
        seen = None
        import time
        for _ in range(tries):
            seen = evaluate(ws, sid, "chrome && chrome.runtime && chrome.runtime.getManifest"
                                     " ? chrome.runtime.getManifest().version : null")
            if seen:
                break
            time.sleep(0.5)
        close_page(ws, target)
        return seen
    finally:
        if own:
            ws.close()


def reload_extension(ws=None):
    """Reload through the extensions page - the popup's own chrome.runtime.reload()
    does not pick up a new manifest (measured: it stayed on the old version)."""
    own = ws is None
    ws = ws or connect()
    try:
        page, sid = open_page(ws, "chrome://extensions/")
        import time
        time.sleep(1.5)
        if not evaluate(ws, sid, "typeof chrome.developerPrivate !== 'undefined'"):
            close_page(ws, page)
            raise RuntimeError("chrome.developerPrivate unavailable")
        out = evaluate(ws, sid,
                       "chrome.developerPrivate.reload('%s', {failQuietly: false})"
                       ".then(() => 'ok', (e) => 'err: ' + String(e))" % extension_id(),
                       await_promise=True)
        close_page(ws, page)
        return out
    finally:
        if own:
            ws.close()


def repo_version() -> str:
    """The version the repository ships - the only honest reference."""
    manifest = pathlib.Path(__file__).resolve().parent.parent / "extension" / "manifest.json"
    return json.loads(manifest.read_text(encoding="utf-8"))["version"]
