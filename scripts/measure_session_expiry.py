"""Does the popup's session expiry tell the truth as time passes?

`list_sessions()` computes `expired` once, per request, from the server's clock.
The popup renders that boolean and then stops: between two 30s ticks a session
can cross its expiry and the panel keeps claiming it is valid. This measures the
product's real behaviour by POSTING a session whose cookies expire in seconds,
then polling `/v1/sessions` and rendering the popup's own line.

The cookie VALUES are never printed - only names and expiry metadata, as the
product's own confidentiality rule requires.
"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RELAY = "http://127.0.0.1:8765"
SECRET = pathlib.Path.home() / ".config" / "lightpanda-bridge" / "secret"


def call(path, payload=None, timeout=20):
    token = SECRET.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(RELAY + path,
                                 method="POST" if payload is not None else "GET")
    req.add_header("X-Bridge-Token", token)
    req.add_header("Origin", "chrome-extension://fcigkjkchglchhohedljlenopbkgnino")
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8", "replace"))


def popup_line(session):
    """Render the popup's meta line with the popup's OWN JavaScript.

    `fmtExpiry` and the concatenation are extracted from popup.js and run in
    Node - not reimplemented in Python. A Python transcription would be a second
    implementation that can drift from the product, which is exactly the kind of
    harness that proves whatever it was written to prove.
    """
    src = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
    fs = src.index("function fmtExpiry(ts)")
    fe = src.index("\n}", fs)
    js = src[fs:fe + 2] + """
const s = %s;
const out = `${s.cookie_count} cookies`
  + (s.expires && !s.expired ? ` · ${fmtExpiry(s.expires)}` : '')
  + (s.expired ? ' · expired' : '');
console.log(JSON.stringify({line: out,
  expires: s.expires || null, expired: s.expired, cookie_count: s.cookie_count}));
""" % json.dumps(session)
    start = src.index("meta.textContent = `${s.cookie_count} cookies`")
    expr = src[start:src.index(";", start)]
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError("node a echoue: %s" % (r.stderr or "")[:200])
    return json.loads(r.stdout.strip())["line"], expr


def main():
    origin = "https://example.com"
    status, _ = call("/v1/sessions/clear", {"origin": origin})  # best effort

    # expires_hint is seconds-since-epoch. 6s from now: inside a single 30s tick.
    soon = time.time() + 6
    payload = {"origin": origin,
               "cookies": [{"name": "lp_expiry_probe", "value": "probe", "domain": "example.com",
                            "path": "/", "secure": True, "httpOnly": False,
                            "expires_hint": soon}]}
    # The import route is /v1/session/import - /v1/sessions is GET-only and
    # answers 404 for POST, which is what the first run of this probe reported.
    status, resp = call("/v1/session/import", {"origin": origin, "cookies": payload["cookies"]})
    print("POST /v1/session/import -> %s %s" % (status, json.dumps(resp)[:160]))
    if status != 200:
        print("ECHEC: la session de sonde n'a pas ete importee, la mesure serait vide")
        return 1

    print("\n%-9s %-10s %-9s %-28s" % ("t+", "expires?", "expired?", "ligne rendue par le popup"))
    print("-" * 62)
    line_expr = ""
    crossings = []
    prev_expired = None
    for step in range(9):
        now = time.time()
        _, data = call("/v1/sessions")
        sess = next((s for s in data.get("sessions", []) if s["host"] == "example.com"), None)
        if sess is None:
            print("%-9s %s" % ("%.1fs" % (now - (soon - 6)), "absent"))
        else:
            line, line_expr = popup_line(sess)
            print("%-9s %-10s %-9s %s"
                  % ("%.1fs" % (now - (soon - 6)),
                     "%.0f" % sess["expires"] if sess.get("expires") else "-",
                     sess["expired"], line))
            if prev_expired is not None and sess["expired"] != prev_expired:
                crossings.append(("%.1fs" % (now - (soon - 6)), prev_expired, sess["expired"]))
            prev_expired = sess["expired"]
        time.sleep(3)

    print("\nexpression rendue (copiee du popup) :")
    print("  " + line_expr.replace("\n", "\n  "))
    print("\nbasculements de `expired` vus par le popup : %s" % (crossings or "aucun"))
    st, cl = call("/v1/sessions/clear", {"origin": origin})
    print("\nnettoyage: POST /v1/sessions/clear -> %s %s" % (st, json.dumps(cl)[:80]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
