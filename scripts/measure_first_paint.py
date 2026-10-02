"""Measure the popup's FIRST PAINT — the frame painted before any JS runs.

The HTML ships French literals ("Copier le diagnostic") while the default
language is English. `applyTranslations()` rewrites them a few milliseconds later,
so the interesting question is not whether the strings are eventually right: it is
whether a wrong-language frame is ever painted, and for how long.

Two passes over the real popup.html in the real Comet, via CDP:

  pass 1  JavaScript disabled  -> exactly the first frame, pre-translation
  pass 2  JavaScript enabled   -> the settled state

Any string that differs between the two passes is a flash of the wrong language.
"""
import json
import pathlib
import sys
import time
import urllib.request

import websocket

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = ROOT / "extension" / "popup.html"
CDP = "http://127.0.0.1:9223"

# Every element holding user-visible text. `diag-text` is the one suspected of
# being French-only; the others are the control group: if they match across both
# passes, the harness is measuring something real.
SELECTORS = ["#diag-text", "#relay-text", "#label-update", "#btn-text",
             "#footer-secure-tag", "#sessions-label", "#status-text"]

READ = ("JSON.stringify(Object.fromEntries("
        + json.dumps(SELECTORS)
        + ".map(s => [s, (document.querySelector(s)||{}).textContent?.trim() || ''])))")


class Cdp:
    def __init__(self, ws_url):
        # Comet rejects a websocket carrying an Origin header it did not
        # whitelist; suppress_origin sends none, which it accepts without needing
        # --remote-allow-origins and without restarting the browser.
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self.n = 0

    def send(self, method, params=None):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg

    def eval(self, expr):
        r = self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        res = (r or {}).get("result", {}).get("result", {})
        if "value" not in res:
            raise RuntimeError(json.dumps((r or {}).get("result", {}))[:300])
        return res["value"]

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def open_page():
    targets = json.loads(urllib.request.urlopen(CDP + "/json", timeout=10)
                         .read().decode("utf-8", "replace"))
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        raise RuntimeError("aucune page dans Comet")
    return pages[0]


def snapshot(cdp, url, js_enabled):
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.send("Emulation.setScriptExecutionDisabled", {"value": not js_enabled})
    cdp.send("Page.navigate", {"url": url})
    time.sleep(2.0 if js_enabled else 0.8)
    lang = cdp.eval("localStorage.getItem('lightpanda-lang') || 'en'") if js_enabled else "en"
    snap = json.loads(cdp.eval(READ) or "{}")
    cdp.send("Emulation.setScriptExecutionDisabled", {"value": False})
    return lang, snap


def main():
    try:
        page = open_page()
    except Exception as err:
        print("SKIP: Comet CDP indisponible (%s)" % err)
        return 0

    url = "file:///" + str(HTML).replace("\\", "/")
    print("popup :", url)
    cdp = Cdp(page["webSocketDebuggerUrl"])
    try:
        _, first = snapshot(cdp, url, js_enabled=False)
        lang, after = snapshot(cdp, url, js_enabled=True)
        print("langue :", lang)
        print("\n%-22s %-34s %s" % ("element", "1er rendu (sans JS)", "apres rendu (avec JS)"))
        print("-" * 96)
        flash = []
        for sel in SELECTORS:
            a, b = first.get(sel, ""), after.get(sel, "")
            mark = ""
            if a and a != b:
                mark = "  <-- FLASH"
                flash.append(sel)
            print("%-22s %-34r %r%s" % (sel, a, b, mark))
        print("\n%d flash(s) de langue au premier rendu : %s" % (len(flash), flash or "aucun"))
        return 1 if flash else 0
    finally:
        cdp.close()


if __name__ == "__main__":
    sys.exit(main())
