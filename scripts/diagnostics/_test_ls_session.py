"""Verifie l'etat reel de la session Lightpanda (localStorage + appels authentifies).
N'imprime aucune valeur sensible : seulement presence/forme/compteurs.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\bapti\Documents\Projets_Hermes\lightpanda-session-bridge")
from bridge_agent import AuthenticatedSession  # noqa: E402


def shape(obj, depth=0, maxdepth=2):
    pad = "  " * depth
    SECRETISH = ("key", "token", "secret", "cookie", "pass", "access", "refresh")
    if isinstance(obj, dict):
        out = []
        for k, v in list(obj.items())[:16]:
            if isinstance(v, (dict, list)):
                out.append(f"{pad}{k}: {type(v).__name__}({len(v)})")
                if depth < maxdepth:
                    out.append(shape(v, depth + 1, maxdepth))
            else:
                s = str(v)
                if any(t in k.lower() for t in SECRETISH):
                    out.append(f"{pad}{k}: <masque>")
                else:
                    out.append(f"{pad}{k}: {'<vide>' if s == '' else s[:55]}")
        return "\n".join(x for x in out if x)
    if isinstance(obj, list):
        return f"{pad}<liste({len(obj)})>" if not obj else f"{pad}[0] {type(obj[0]).__name__}\n" + (shape(obj[0], depth + 1, maxdepth) if isinstance(obj[0], (dict, list)) else "")
    return f"{pad}{obj}"


s = AuthenticatedSession()
s.open("https://a6api.com/", wait=9)

probe = r"""
(async () => {
  const out = {};
  // 1. localStorage recu par Lightpanda
  try {
    const keys = Object.keys(localStorage);
    out.ls_keys = keys.slice(0, 30);
    out.ls_count = keys.length;
    const u = localStorage.getItem('user');
    out.user_present = !!u;
    if (u) { try { const p = JSON.parse(u); out.user_fields = Object.keys(p).slice(0, 20); out.user_id_type = typeof p.id; } catch (e) { out.user_parse_err = 'json'; } }
  } catch (e) { out.ls_err = '' + e.message; }

  // 2. Appel authentifie avec l'en-tete attendu par le SPA (sans jamais l'afficher)
  const hdrs = {};
  try { const u = JSON.parse(localStorage.getItem('user') || 'null'); if (u && u.id !== undefined) hdrs['New-Api-User'] = String(u.id); } catch (e) {}
  out.header_set = Object.keys(hdrs).length > 0;

  const J = async (u) => {
    try {
      const r = await fetch(u, { credentials: 'include', headers: hdrs });
      const ct = r.headers.get('content-type') || '';
      let b = null;
      if (ct.includes('json')) { try { b = await r.json(); } catch (e) { b = '<json invalide>'; } } else { b = (await r.text()).slice(0, 100); }
      return { status: r.status, body: b };
    } catch (e) { return { error: '' + (e && e.name) + ': ' + (e && e.message) }; }
  };
  if (out.header_set) {
    out.me      = await J('/api/user/self');
    out.log     = await J('/api/log/self/?p=1&page_size=5');
    out.notices = await J('/api/marketplace/price-notices');
  }
  return JSON.stringify(out);
})()
"""
raw = s.js(probe, await_promise=True)
s.close()

data = json.loads(raw) if isinstance(raw, str) else raw
print("=== localStorage cote Lightpanda ===")
print("cles :", data.get("ls_count"), "->", data.get("ls_keys"))
print("'user' present :", data.get("user_present"), "| champs :", data.get("user_fields"))
print("en-tete New-Api-User reconstruit :", data.get("header_set"))

for name in ("me", "log", "notices"):
    sec = data.get(name)
    if not sec:
        continue
    print(f"\n=== {name} ===")
    if "error" in sec:
        print("  erreur reseau :", sec["error"]); continue
    print("  HTTP", sec.get("status"))
    b = sec.get("body")
    if isinstance(b, str):
        print("  corps texte :", b[:100])
    else:
        print(shape(b))
