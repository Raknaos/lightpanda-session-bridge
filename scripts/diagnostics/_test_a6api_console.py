"""Test d'acces authentifie a la console a6api via le relais Lightpanda.
N'affiche JAMAIS de cookie, d'en-tete d'auth ou de secret : uniquement des codes
HTTP et la FORME des reponses (cles, compteurs).
"""
import json
import sys

sys.path.insert(0, r"C:\Users\bapti\Documents\Projets_Hermes\lightpanda-session-bridge")
from bridge_agent import AuthenticatedSession  # noqa: E402


def shape(obj, depth=0, maxdepth=2):
    """Decrit la forme d'une reponse sans divulguer les valeurs sensibles."""
    pad = "  " * depth
    if isinstance(obj, dict):
        lines = []
        for k, v in list(obj.items())[:14]:
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: {type(v).__name__}({len(v)})")
                if depth < maxdepth:
                    lines.append(shape(v, depth + 1, maxdepth))
            else:
                s = str(v)
                lines.append(f"{pad}{k}: {type(v).__name__} {'<vide>' if s == '' else ('<masque>' if any(t in k.lower() for t in ('key', 'token', 'secret', 'cookie', 'pass')) else s[:60])}")
        return "\n".join(x for x in lines if x)
    if isinstance(obj, list):
        if not obj:
            return f"{pad}<liste vide>"
        return f"{pad}[0] -> {type(obj[0]).__name__}" + (("\n" + shape(obj[0], depth + 1, maxdepth)) if isinstance(obj[0], (dict, list)) else "")
    return f"{pad}{obj}"


def main():
    s = AuthenticatedSession()
    print("health:", json.dumps(s.health(), default=str)[:200])

    s.open("https://a6api.com/console/log", wait=9)

    probe = r"""
    (async () => {
      const out = { url: location.href, title: document.title };
      const J = async (u, opt) => {
        try {
          const r = await fetch(u, Object.assign({credentials:'include'}, opt||{}));
          const ct = r.headers.get('content-type') || '';
          let body = null;
          if (ct.includes('json')) { try { body = await r.json(); } catch(e) { body = '<json invalide>'; } }
          else { body = (await r.text()).slice(0, 120); }
          return { status: r.status, ct: ct.slice(0, 40), body: body };
        } catch (e) { return { error: (e && e.name) + ': ' + (e && e.message) }; }
      };
      out.me      = await J('/api/user/self');
      out.log     = await J('/api/log/self/?p=1&page_size=5');
      out.notices = await J('/api/marketplace/price-notices');
      out.models  = await J('/api/models?page=1&page_size=5');
      return JSON.stringify(out);
    })()
    """
    raw = s.js(probe, await_promise=True)
    s.close()

    if not raw:
        print("aucune reponse du relais")
        return 1
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    print("\n=== page ===")
    print("url  :", data.get("url"))
    print("titre:", data.get("title"))

    for name in ("me", "log", "notices", "models"):
        sec = data.get(name) or {}
        print(f"\n=== {name} ===")
        if "error" in sec:
            print("  erreur reseau :", sec["error"])
            continue
        print("  HTTP", sec.get("status"), "|", sec.get("ct"))
        b = sec.get("body")
        if isinstance(b, str):
            print("  corps (texte):", b[:100])
        elif isinstance(b, dict):
            print("  forme:")
            print(shape(b))
        else:
            print("  corps:", b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
