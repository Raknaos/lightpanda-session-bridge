"""Screencast the REAL popup, in the REAL extension, in the REAL Comet.

Everything so far loaded `extension/popup.html` over `file://`, which is NOT the
product: the shipped popup runs on `chrome-extension://<id>`, where a different
localStorage lives and where the running extension can rewrite the language
underneath the measurement. That is why the `file://` runs disagreed with each
other - they were not measuring the product.

This drives the installed extension's popup document and records the frames the
compositor actually presented, then reads the language the popup itself resolved,
so the report cannot claim a language it did not measure.
"""
import base64
import json
import pathlib
import sys
import time
import urllib.request

import websocket
from PIL import Image
from io import BytesIO

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / "scripts" / "artifacts"
CDP = "http://127.0.0.1:9223"
EXT_ID = None
PIN = pathlib.Path.home() / ".config" / "lightpanda-bridge" / "pinned_extension_id"


def ext_id():
    if PIN.is_file():
        v = PIN.read_text(encoding="utf-8").strip()
        if v:
            return v
    raise RuntimeError("aucun extension id epingle")


class Sc:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
        self.n = 0
        self.frames = []

    def cmd(self, method, params=None):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        self.ws.settimeout(15)
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("method") == "Page.screencastFrame":
                p = msg["params"]
                self.frames.append(p["data"])
                self.ws.send(json.dumps({"id": self.n + 1, "method": "Page.screencastFrameAck",
                                         "params": {"sessionId": p["sessionId"]}}))
                self.n += 1
            elif msg.get("id") == mid:
                return msg

    def pump(self, seconds):
        end = time.time() + seconds
        self.ws.settimeout(0.4)
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Page.screencastFrame":
                p = msg["params"]
                self.frames.append(p["data"])
                try:
                    self.ws.send(json.dumps({"id": self.n + 1, "method": "Page.screencastFrameAck",
                                             "params": {"sessionId": p["sessionId"]}}))
                    self.n += 1
                except Exception:
                    pass

    def evaluate(self, expr, need=True):
        r = self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        res = (r or {}).get("result", {}).get("result", {})
        if "value" not in res:
            if need:
                raise RuntimeError(json.dumps((r or {}).get("result", {}))[:300])
            return None
        return res["value"]

    def close(self):
        try:
            self.cmd("Page.stopScreencast")
            self.ws.close()
        except Exception:
            pass


def fp(b64):
    img = Image.open(BytesIO(base64.b64decode(b64))).convert("L")
    w, h = img.size
    px = img.load()
    return tuple(sum(1 for x in range(0, w, 3) if px[x, y] < 140) for y in range(0, h, 2)), img.size


def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else "fr"
    try:
        eid = ext_id()
    except Exception as err:
        print("SKIP: %s" % err)
        return 0
    url = "chrome-extension://%s/popup.html" % eid
    try:
        targets = json.loads(urllib.request.urlopen(CDP + "/json", timeout=10)
                             .read().decode("utf-8", "replace"))
    except Exception as err:
        print("SKIP: Comet CDP indisponible (%s)" % err)
        return 0
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        print("SKIP: aucune page")
        return 0

    ART.mkdir(exist_ok=True)
    sc = Sc(pages[0]["webSocketDebuggerUrl"])
    try:
        sc.cmd("Page.enable")
        sc.cmd("Runtime.enable")
        sc.cmd("Emulation.setDeviceMetricsOverride",
               {"width": 380, "height": 620, "deviceScaleFactor": 1, "mobile": False})
        sc.cmd("Page.navigate", {"url": url})
        sc.pump(1.5)
        sc.evaluate("localStorage.setItem('lightpanda-lang', %s)" % json.dumps(lang), need=False)
        stored = sc.evaluate("localStorage.getItem('lightpanda-lang')")

        sc.cmd("Page.startScreencast", {"format": "png", "quality": 100,
                                        "maxWidth": 380, "maxHeight": 620, "everyNthFrame": 1})
        time.sleep(0.3)
        sc.frames.clear()

        sc.cmd("Page.navigate", {"url": url})
        sc.pump(3.0)

        # The session row ships COLLAPSED, so the expiry meta line - the thing
        # v0.7.18 rewrote - is never painted. Expand it through the real control
        # (a click, not a style override) so what the screencast records is a
        # state the user can actually reach.
        expanded = sc.evaluate(
            "(function(){var els=document.querySelectorAll('[aria-expanded],"
            ".session-toggle,#sessions-toggle,.card-head,.collapse-head');"
            "for (var i=0;i<els.length;i++){"
            " if (els[i].getAttribute('aria-expanded')==='false'){"
            "   els[i].click(); return 'clicked '+i;} }"
            "return 'aucun controle replie trouve';})()", need=False)

        sc.pump(1.2)
        sc.cmd("Page.stopScreencast")

        # What the INSTALLED popup itself says it resolved - not what storage holds.
        resolved = sc.evaluate(
            "JSON.stringify({stored: localStorage.getItem('lightpanda-lang'),"
            " diag: (document.querySelector('#diag-text')||{}).textContent,"
            " lang: (document.querySelector('.lang-value')||document.querySelector('.lang-current')||{}).textContent})")
        print("popup INSTALLE : %s" % url)
        print("langue demandee : %s | localStorage lu : %s" % (lang, stored))
        print("ligne sessions deploiee : %s" % expanded)
        print("ce que le popup a resolu : %s" % resolved)

        frames = list(sc.frames)
        print("\nframes COMPOSITEES : %d" % len(frames))
        if not frames:
            print("SKIP: aucune frame compositee - la mesure serait decorative")
            return 0

        seen = []
        for data in frames:
            f, size = fp(data)
            if f not in [s[0] for s in seen]:
                seen.append((f, data, size))
        print("frames visuellement distinctes : %d" % len(seen))
        for i, (f, data, size) in enumerate(seen):
            p = ART / ("real_screencast_%s_f%d.png" % (lang, i))
            Image.open(BytesIO(base64.b64decode(data))).save(p)
            print("  frame %d %dx%d -> %s" % (i, size[0], size[1], p.name))
        print("\nRESULTAT: %d etat(s) peint(s) sur l'extension reelle" % len(seen))
        return 0
    finally:
        sc.close()


if __name__ == "__main__":
    sys.exit(main())
