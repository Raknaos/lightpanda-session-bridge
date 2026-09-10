"""Compare l'etat a6api dans Comet (source) et dans Lightpanda (cible).
N'affiche QUE des noms de cles et des booleens : aucune valeur, aucun secret.
"""
import json
import urllib.request

import websocket

CDP = 'http://127.0.0.1:9223'
SECRETISH = ('key', 'token', 'secret', 'cookie', 'pass', 'access', 'refresh', 'auth')


def rpc(ws, i, method, params=None, sid=None, wait=120):
    d = {'id': i, 'method': method, 'params': params or {}}
    if sid:
        d['sessionId'] = sid
    ws.send(json.dumps(d))
    n = 0
    while n < wait:
        r = json.loads(ws.recv())
        n += 1
        if r.get('id') == i:
            return r
    return {}


EXPR = r"""
(() => {
  const out = { url: location.href };
  try {
    const keys = Object.keys(localStorage);
    out.ls_count = keys.length;
    out.ls_keys = keys.slice(0, 40);
    out.has_user = keys.includes('user');
    const u = localStorage.getItem('user');
    out.user_len = u ? String(u).length : 0;
    if (u) {
      try { const p = JSON.parse(u); out.user_fields = Object.keys(p); out.user_id_type = typeof p.id; out.user_id_len = String(p.id ?? '').length; } catch (e) { out.user_fields = '<json invalide>'; }
    }
    out.ss_keys = Object.keys(sessionStorage).slice(0, 20);
  } catch (e) { out.err = '' + e.message; }
  return JSON.stringify(out);
})()
"""

ver = json.loads(urllib.request.urlopen(CDP + '/json/version', timeout=8).read())
ws = websocket.create_connection(ver['webSocketDebuggerUrl'], suppress_origin=True, timeout=40)
tabs = json.loads(urllib.request.urlopen(CDP + '/json/list', timeout=8).read())
targets = [t for t in tabs if t.get('type') == 'page' and 'a6api.com' in (t.get('url') or '')]
print('onglets a6api dans Comet :', len(targets))
for t in targets:
    sid = rpc(ws, 1, 'Target.attachToTarget', {'targetId': t['id'], 'flatten': True}).get('result', {}).get('sessionId')
    if not sid:
        print('  attache impossible')
        continue
    r = rpc(ws, 2, 'Runtime.evaluate', {'expression': EXPR, 'returnByValue': True}, sid=sid)
    v = r.get('result', {}).get('result', {}).get('value')
    if not v:
        print('  eval KO:', json.dumps(r)[:160]); continue
    d = json.loads(v)
    print('\n--- onglet', t.get('url'))
    print('  URL            :', d.get('url'))
    print('  localStorage   :', d.get('ls_count'), 'cles')
    print('  \'user\' present :', d.get('has_user'), '| longueur:', d.get('user_len'), '| champs:', d.get('user_fields'))
    print('  cles           :', d.get('ls_keys'))
    print('  sessionStorage :', d.get('ss_keys'))
ws.close()
