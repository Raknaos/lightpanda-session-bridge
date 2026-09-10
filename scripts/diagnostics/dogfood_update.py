# -*- coding: utf-8 -*-
"""Dogfooding : installe v0.5.3 via /v1/update/apply (le chemin exact du bouton)."""
import json
import pathlib
import urllib.error
import urllib.request

CFG = pathlib.Path(r"C:\Users\bapti\.config\lightpanda-bridge")
TOKEN = (CFG / "secret").read_text().strip()
EXT_ID = (CFG / "pinned_extension_id").read_text().strip()
RELAY = "http://127.0.0.1:8765"
H = {"Content-Type": "application/json",
     "Origin": "chrome-extension://" + EXT_ID,
     "X-Bridge-Token": TOKEN}


def post(path, payload=None):
    req = urllib.request.Request(RELAY + path, data=json.dumps(payload or {}).encode(), headers=H)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


st, check = post("/v1/update/check")
print("check  : HTTP %d %s" % (st, json.dumps({k: check.get(k) for k in
      ("ok", "current", "latest", "channel", "update_available")}, ensure_ascii=False)))
st, applied = post("/v1/update/apply")
print("apply  : HTTP %d %s" % (st, json.dumps(applied, ensure_ascii=False)[:500]))

manifest = json.loads((pathlib.Path(r"C:\Users\bapti\Documents\Projets_Hermes\lightpanda-session-bridge")
                       / "extension" / "manifest.json").read_text(encoding="utf-8"))
print("\nmanifest sur disque :", manifest["version"])
info = pathlib.Path(r"C:\Users\bapti\Documents\Projets_Hermes\lightpanda-session-bridge\extension\.build-info.json")
if info.exists():
    d = json.loads(info.read_text(encoding="utf-8"))
    print("provenance          :", {k: d.get(k) for k in ("version", "tag", "installed_at", "channel")})
