// What a failed update says.
//
// Measured 0.7.25: `runUpdate` was correct up to the point where it threw, and
// then its catch replaced the message UNCONDITIONALLY with "Relay Offline (is it
// running?)". So a refused checksum, a refused origin, an unauthenticated
// extension, a rate limit, a dead relay and a timeout were six different
// situations wearing one sentence - and the user was told to debug a healthy
// installation. `relayErrorText()` had existed all along and was never called
// from here; that was the second unread function after `error_kind` (0.7.24).
//
// The second fault was in `unknownRelayError`, written as "Relay error: {0}"
// in all ten languages while `t()` only substituted arguments into FUNCTION
// values. The literal `{0}` reached the screen and the relay's code never did.
// Fixed together: `t()` now formats a string placeholder too.
//
// Harness rules learned on this file, each one a wasted run:
//   - `relayFetch` is DEFINED at line 985, BELOW `runUpdate`. A stub placed on
//     the context object is beaten by the hoisted sandbox declaration, so the
//     real one runs and calls `fetch()`. Both must be declared INSIDE.
//   - `bridgeHeaders()` reads `bridgeToken`; if that binding is missing the
//     ReferenceError is caught by the very catch under test and reads as
//     "relay offline". The sandbox must carry `bridgeToken: null`.
//   - The real `t()` is used, not a stub: a stub cannot show a `{0}` that was
//     never substituted, which is the bug.
//
// Run: node tests/node/test_update_failure_text.js <repo-root>

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.argv[2] || path.join(__dirname, '..', '..');
const SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');

function matchingBrace(text, from) {
  let depth = 0;
  for (let k = from; k < text.length; k++) {
    if (text[k] === '{') depth++;
    else if (text[k] === '}') { depth--; if (depth === 0) return k + 1; }
  }
  return -1;
}

function cut(sig) {
  const i = SRC.indexOf(sig);
  if (i < 0) { console.error('absent du popup.js: ' + sig); process.exit(2); }
  const end = matchingBrace(SRC, SRC.indexOf('{', i));
  if (end < 0) { console.error('fin introuvable pour: ' + sig); process.exit(2); }
  return SRC.slice(i, end);
}

let passed = 0;
const failures = [];
function ok(name, cond, detail) {
  if (cond) { passed++; console.log('  ok   ' + name); }
  else { failures.push(name); console.log('  FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

(async () => {
  const i18nSrc = cut('const I18N = {');
  const I18N = vm.runInNewContext('(' + i18nSrc.slice(i18nSrc.indexOf('{')) + ')');

  const ctx = {
    I18N,
    currentLanguage: 'fr',
    setStatus: (msg, kind) => { ctx.__last = String(msg) + ' [' + kind + ']'; },
    renderUpdateCard: () => {},
    refreshUpdateStatus: () => {},
    updateBusy: false,
    updateBtn: {},
    rollbackBtn: {},
    bridgeToken: null,
    chrome: { runtime: { reload() {} } },
    // If the real fetch ever runs, say so instead of letting it look like a
    // product failure (this exact confusion cost several runs).
    fetch: () => { throw new Error('HARNESS: le fetch reel a ete appele'); }
  };
  vm.createContext(ctx);
  vm.runInContext([
    cut('function t(key, ...args) {'),
    cut('const RELAY_ERROR_KEYS = {'),
    cut('function relayErrorText('),
    cut('function bridgeHeaders('),
    cut('async function runUpdate('),
    'relayFetch = globalThis.__impl;'
  ].join('\n'), ctx);

  const setFetch = (impl) =>
    vm.runInContext('relayFetch = globalThis.__impl', Object.assign(ctx, { __impl: impl }));

  // The relay answered 4xx/5xx with `{"ok": false, "error": "<code>"}`.
  const REFUSALS = [
    ['checksum refuse', 400, 'checksum mismatch: artifact refused', 'errChecksumMismatch'],
    ['rien a installer', 400, 'nothing to install: already up to date', 'errNothingToInstall'],
    ['archive invalide', 400, 'archive refused: path traversal', 'errArchiveRefused'],
    ['ext dir absente', 400, 'extension directory not found', 'errExtDirMissing'],
    ['ext dir lecture seule', 400, 'extension directory is not writable', 'errExtDirReadonly'],
    ['pas de backup', 400, 'no backup to restore', 'errNoBackup'],
    ['origin refuse', 403, 'origin refused', 'errOriginRefused'],
    ['non appairee', 401, 'unauthorized', 'errUnauthorized']
  ];

  const offline = I18N.fr.errRelayUnreachable;
  const timeout = I18N.fr.errRelayTimeout;

  for (const [label, status, code, key] of REFUSALS) {
    await setFetch(() => Promise.resolve({
      ok: false, status, json: () => Promise.resolve({ ok: false, error: code })
    }));
    ctx.__last = null;
    await vm.runInContext("runUpdate('/v1/update/apply','x','y')", ctx);
    const said = ctx.__last || '';
    const expected = typeof I18N.fr[key] === 'function' ? I18N.fr[key]() : I18N.fr[key];
    ok(label + ' : nomme la cause', said.includes(expected),
       JSON.stringify(said) + ' sans ' + JSON.stringify(expected));
    ok(label + ' : ne dit pas "relais hors ligne"', said !== offline && !said.includes(offline),
       JSON.stringify(said));
  }

  // A dead relay and a timeout are the ONLY two cases allowed to say unreachable.
  await setFetch(() => Promise.reject(Object.assign(new Error('failed to fetch'), { name: 'TypeError' })));
  ctx.__last = null;
  await vm.runInContext("runUpdate('/v1/update/apply','x','y')", ctx);
  ok('relais muet : injoignable', ctx.__last.includes(offline), JSON.stringify(ctx.__last));

  await setFetch(() => Promise.reject(Object.assign(new Error('aborted'), { name: 'RelayTimeoutError' })));
  ctx.__last = null;
  await vm.runInContext("runUpdate('/v1/update/apply','x','y')", ctx);
  ok('delai depasse : distingue de la panne', ctx.__last.includes(timeout) && ctx.__last !== offline,
     JSON.stringify(ctx.__last));

  // An unmapped code must be SHOWN, not swallowed and not templated.
  await setFetch(() => Promise.resolve({
    ok: false, status: 500, json: () => Promise.resolve({ ok: false, error: 'nobody mapped this' })
  }));
  ctx.__last = null;
  await vm.runInContext("runUpdate('/v1/update/apply','x','y')", ctx);
  ok('code inconnu : montre le code', (ctx.__last || '').includes('nobody mapped this'), JSON.stringify(ctx.__last));
  ok('code inconnu : aucun {0} residue', !(ctx.__last || '').includes('{0}'), JSON.stringify(ctx.__last));

  // Every refusal must be DISTINGUISHABLE. One shared sentence is the bug.
  const rendered = [];
  for (const [, status, code] of REFUSALS) {
    await setFetch(() => Promise.resolve({
      ok: false, status, json: () => Promise.resolve({ ok: false, error: code })
    }));
    ctx.__last = null;
    await vm.runInContext("runUpdate('/v1/update/apply','x','y')", ctx);
    rendered.push(ctx.__last);
  }
  ok('les 8 refus sont distinguables', new Set(rendered).size === rendered.length,
     new Set(rendered).size + ' distincts pour ' + rendered.length);

  // t() substitutes {0} in a plain string, in every language that has one.
  const langs = Object.keys(I18N).filter((l) => typeof I18N[l].unknownRelayError === 'string');
  ok('unknownRelayError est un template dans 10 langues', langs.length === 10, JSON.stringify(langs));
  for (const lang of langs) {
    vm.runInContext('currentLanguage = ' + JSON.stringify(lang), ctx);
    const got = vm.runInContext("t('unknownRelayError','CODE-X')", ctx);
    ok('langue ' + lang + ' : substitue {0}', got.includes('CODE-X') && !got.includes('{0}'), JSON.stringify(got));
  }
  vm.runInContext("currentLanguage = 'fr'", ctx);

  console.log('\n' + passed + ' passed, ' + failures.length + ' failed');
  if (failures.length) {
    for (const f of failures) console.log('  - ' + f);
    process.exit(1);
  }
})().catch((e) => { console.error('HARNESS', e.message); process.exit(2); });