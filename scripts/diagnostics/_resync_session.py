"""Rejoue le transfert de session depuis le contexte de l'extension.
Les valeurs (cookies, localStorage) ne sortent jamais du navigateur :
on n'imprime que des compteurs et des codes HTTP.
"""
import json
import time
import urllib.request

import websocket

CDP = 'http://127.0.0.1:9223'
POP = 'chrome-extension://fcigkjkchglchhohedljlenopbkgnino/popup.html'


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
(async () => {
  const out = {};
  try {
    const all = await chrome.tabs.query({});
    const tabs = all.filter(t => /a6api\.com/.test(t.url || ''));
    out.tabs = tabs.map(t => ({ id: t.id, url: t.url, active: t.active }));
    const tab = tabs.find(t => /console/.test(t.url)) || tabs[0];
    if (!tab) { out.err = 'aucun onglet a6api'; return JSON.stringify(out); }
    out.tab_url = tab.url;
    out.active = tab.active;

    const cookies = await chrome.cookies.getAll({ url: tab.url });
    out.cookie_count = cookies.length;
    out.cookie_names = cookies.map(c => c.name);

    let storage = null;
    try {
      const res = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => { const d = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); d[k] = localStorage.getItem(k); } return d; }
      });
      storage = (res && res[0] && res[0].result) || null;
      out.storage_count = storage ? Object.keys(storage).length : 0;
      out.storage_has_user = !!(storage && storage.user);
    } catch (e) { out.script_err = '' + e.message; }

    if (!storage || !out.storage_has_user) {
      out.stopped = 'storage incomplet -> import non tente';
      return JSON.stringify(out);
    }

    const tok = localStorage.getItem('lpBridgeToken') || '';
    const r = await fetch('http://127.0.0.1:8765/v1/session/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Bridge-Token': tok },
      body: JSON.stringify({ origin: new URL(tab.url).origin, cookies: cookies, storage: storage })
    });
    const j = await r.json().catch(() => ({}));
    out.import_http = r.status;
    out.import_ok = j.ok;
    out.import_cookie_count = j.cookie_count;
    out.import_storage_count = j.storage_count;
    out.import_error = j.error;
  } catch (e) { out.fatal = '' + (e && e.message); }
  return JSON.stringify(out);
})()
"""

ver = json.loads(urllib.request.urlopen(CDP + '/json/version', timeout=8).read())
ws = websocket.create_connection(ver['webSocketDebuggerUrl'], suppress_origin=True, timeout=45)
tid = rpc(ws, 1, 'Target.createTarget', {'url': POP}).get('result', {}).get('targetId')
sid = rpc(ws, 2, 'Target.attachToTarget', {'targetId': tid, 'flatten': True}).get('result', {}).get('sessionId')
time.sleep(5)
r = rpc(ws, 3, 'Runtime.evaluate', {'expression': EXPR, 'awaitPromise': True, 'returnByValue': True}, sid=sid, wait=250)
v = r.get('result', {}).get('result', {}).get('value')
print(json.dumps(json.loads(v), ensure_ascii=False, indent=1) if v else json.dumps(r, ensure_ascii=False)[:600])
rpc(ws, 4, 'Target.closeTarget', {'targetId': tid}, wait=20)
ws.close()
