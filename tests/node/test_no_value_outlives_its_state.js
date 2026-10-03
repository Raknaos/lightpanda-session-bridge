// A node's value must be a function of the CURRENT state and nothing else.
//
// This is the machine form of the family measured in 0.7.26-0.7.30: a property
// written on one path and not another, so the node keeps whatever the previous
// render left. 0.7.27 title, 0.7.28 button wording, 0.7.29 the armed
// confirmation, 0.7.30 the version that had to wait for the network.
//
// The invariant needs no control-flow analysis and no vocabulary of mine:
//   render(A) then render(B) into ONE node set  ==  render(B) into a FRESH one.
// Any difference is a value that survived a state change. That comparison is
// exhaustive over pairs, catches an absence (which a duplicate-write detector
// cannot see), and cannot be fooled by `if/else` arms that are mutually
// exclusive.
//
// States are declared per function, and every state drives the REAL renderer.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.argv[2] || path.join(__dirname, '..', '..');
const SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');

// Slice by BRACE COUNT - `indexOf('\n}\n')` truncates at the first line starting
// with a closing brace, which inside nested blocks is an inner one.
function sliceFunction(src, header) {
  const at = src.indexOf(header);
  if (at < 0) throw new Error('not found: ' + header);
  let d = 0, started = false;
  for (let k = src.indexOf('{', at); k < src.length; k++) {
    if (src[k] === '{') { d++; started = true; }
    else if (src[k] === '}') { d--; if (started && d === 0) return src.slice(at, k + 1); }
  }
  throw new Error('unbalanced: ' + header);
}

// The JS-name -> HTML-id mapping is read out of the PRODUCT, never re-typed.
const ID_OF = {};
for (const m of SRC.matchAll(
  /(?:const|let|var)\s+(\w+)\s*=\s*document\.(?:querySelector|getElementById)\('#([\w-]+)'\)/g)) {
  ID_OF[m[1]] = m[2];
}

// MEASURED, not assumed: the surviving value depends on the state that came
// BEFORE (`rollbackBtn.display` is '' after `a jour`, 'none' after `relay muet`),
// so no single hand-written set is right for all pairs. The declaration below
// names NODES, and the audit verifies per pair that the named node really does
// survive - an escape hatch that grows without evidence is point 72's trap.

const NODES = [
  'updateChip', 'updateMeta', 'updateBtn', 'rollbackBtn', 'labelUpdate',
  'updateVersion', 'appVersion', 'relayText', 'relayBadge', 'statusEl',
  'sessionsCount', 'sessionsList', 'sessionsClear', 'clearText', 'toastEl',
];

// The list above is a HARNESS CONSTANT, and a harness constant that parses to
// three fused entries is how 0.7.31 shipped an audit that could not see a single
// node: `nodesTouched` matched nothing, so its "every compared node has a state"
// check had verified nothing and reported green. So the list is parsed and
// ASSERTED here, once, before any state runs - a malformed constant is a
// harness FAILURE (exit 1), never a silently narrower audit.
if (NODES.length !== 15 || new Set(NODES).size !== NODES.length
    || NODES.some((n) => !/^[A-Za-z][\w]*$/.test(n))) {
  console.error('HARNESS FAIL: NODES parsed as ' + JSON.stringify(NODES));
  process.exit(1);
}

// Every node starts from the MARKUP's own initial content, not from blank:
// `popup.html` ships `<span id="update-version">v0.5.0</span>`, and a harness that
// starts blank is structurally blind to the whole 0.7.30 class - the value a user
// really sees on the first frame comes from the file, not from a `undefined` I
// invented. Reading it here also means a change to the markup can turn this suite
// red on its own (the sentinel below is the tell).
let HTML_SRC = '';
function seedFromHtml(jsName) {
  const id = ID_OF[jsName] || jsName.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
  const m = new RegExp('<[^>]*id="' + id + '"[^>]*>([\\s\\S]*?)<').exec(HTML_SRC);
  return m ? m[1].trim() : undefined;
}
function makeNodes() {
  const nodes = {};
  for (const id of NODES) {
    nodes[id] = {
      id,
      textContent: seedFromHtml(id),
      className: undefined,
      title: seedFromHtml(id + '-title'),
      innerHTML: undefined,
      style: {}, dataset: {},
      setAttribute(k, v) { this[k] = v; },
      removeAttribute(k) { delete this[k]; },
      appendChild() {}, addEventListener() {},
    };
  }
  return nodes;
}

// Which product helpers each sliced function needs. The KEY is the exact slice,
// so a helper is only present for the function that calls it.
const HELPERS_FOR = {
  [sliceFunction(SRC, 'function renderSessions(')]: { resetClearButton: sliceFunction(SRC, 'function resetClearButton(') },
};

// The markup is read ONCE, at load: it is the source of the values a user sees
// before any script runs, so it is part of the product under test.
const HTML_PATH = path.join(ROOT, 'extension', 'popup.html');
if (fs.existsSync(HTML_PATH)) {
  HTML_SRC = fs.readFileSync(HTML_PATH, 'utf8');
  // The id the product queries must exist in the markup - otherwise the seeding
  // above silently measures an invented blank.
  const absent = Object.entries(ID_OF).filter(([, htmlId]) =>
    !HTML_SRC.includes('id="' + htmlId + '"')).map(([js, htmlId]) => js + ' -> #' + htmlId);
  if (absent.length) {
    console.error('HARNESS FAIL: queried but absent from popup.html: ' + absent.join(', '));
    process.exit(1);
  }
}

function vmFor(nodes, body) {
  const ctx = {
    console,
    setTimeout: () => 0,
    clearTimeout: () => {},
    document: {
      documentElement: {},
      createElement: () => ({ textContent: '', className: '', innerHTML: '', title: '',
                              style: {}, dataset: {}, appendChild() {}, addEventListener() {} }),
      getElementById: () => null,
      querySelectorAll: () => [],
    },
    chrome: { runtime: { getManifest: () => ({ version: '0.7.30' }), reload() {} } },
    updateInfo: null,
    updateBusy: false,
    bridgeToken: 'tok',
    t: (key, ...args) => (args.length ? key + '(' + args.join() + ')' : key),
    shortCommit: (c) => String(c).slice(0, 7),
    labelClear: () => 'sessionsClearShort',
    fmtExpiry: (x) => String(x),
    showToast: () => {},
    eligible: () => true,
  };
  for (const id of NODES) ctx[id] = nodes[id];
  vm.createContext(ctx);
  // Helpers the code under test CALLS are taken from the product itself, not
  // retyped here: a stub that pins a defect the product does not have is the
  // harness failing at its own job (point 85). `resetClearButton` is a separate
  // top-level function, so it is compiled alongside rather than concatenated -
  // two functions joined put a `return` at top level.
  for (const [name, src] of Object.entries(HELPERS_FOR[body] || {})) {
    vm.runInContext(src, ctx);
    if (name) ctx[name] = ctx[name];
  }
  vm.runInContext(body, ctx);
  return ctx;
}


// What the comparison actually reads. `style.display` is compared as a scalar
// rather than by object identity, and `dataset` is flattened, because the
// product mutates both in place.
function snapshot(nodes) {
  const out = {};
  for (const id of NODES) {
    const n = nodes[id];
    out[id] = {
      textContent: n.textContent,
      className: n.className,
      title: n.title,
      innerHTML: n.innerHTML,
      display: n.style.display,
      armed: n.dataset.armed,
      label: n.getAttribute ? n.getAttribute('aria-label') : undefined,
    };
  }
  return out;
}

let passed = 0;
let failed = 0;
function ok(name, extra) {
  passed++;
  console.log('ok   ' + name + (extra ? '  ' + extra : ''));
}
function bad(name, detail) {
  failed++;
  console.log('FAIL ' + name + '  ' + detail);
}

// Every node the function under test touches must be in NODES, or the
// comparison is blind to it (point 73: the harness declares what it reads).
function nodesTouched(body) {
  const t = new Set();
  for (const m of body.matchAll(/(\w+)\.(\w+)\s*=(?!=)/g)) {
    if (NODES.includes(m[1])) t.add(m[1]);
  }
  return [...t];
}

// The whole check: for each declared function, for each ordered PAIR of states,
// render the pair into one node set and render B alone into a fresh one, then
// compare. Any difference is a value that outlived the state that set it.
function audit(label, body, states) {
  const touched = nodesTouched(body);
  for (const a of touched) {
    if (!states.some((s) => s.__sets.includes(a))) {
      bad(label + ': every compared node has a state', a + ' is written but no state sets it');
    }
  }
  for (let i = 0; i < states.length; i++) {
    for (let j = 0; j < states.length; j++) {
      if (i === j) continue;
      const A = states[i], B = states[j];

      const shared = makeNodes();
      const ctxShared = vmFor(shared, body);
      A.drive(ctxShared, shared);
      B.drive(ctxShared, shared);

      const fresh = makeNodes();
      const ctxFresh = vmFor(fresh, body);
      B.drive(ctxFresh, fresh);

      const sShared = snapshot(shared), sFresh = snapshot(fresh);
      const leaks = [];
      for (const id of NODES) {
        for (const prop of Object.keys(sFresh[id])) {
          const a = sShared[id][prop], b = sFresh[id][prop];
          if (JSON.stringify(a) !== JSON.stringify(b)) {
            leaks.push(id + '.' + prop + ' = ' + JSON.stringify(a) +
                       ' (state alone renders ' + JSON.stringify(b) + ')');
          }
        }
      }
      const pair = label + '  [' + A.name + ' -> ' + B.name + ']';
      const excused = DELIBERATE[B.name];
      const kept = new Set(leaks.map((l) => l.split('.')[0]));
      const real = excused ? leaks.filter((l) => !excused.has(l.split('.')[0])) : leaks;
      const overreach = excused ? [...kept].filter((n) => !excused.has(n)) : [];
      for (const l of real) bad(pair, l);
      for (const n of overreach) bad(pair, 'DELIBERATE names a node that did not survive here: ' + n);
      if (!real.length && !overreach.length) {
        ok(pair + (kept.size ? '  (' + [...kept].join(', ') + ' conserve(s) a dessein)' : ''));
      }
    }
  }
}

// ---------------------------------------------------------------- declared survive
// A state may keep a value ON PURPOSE, and no comparison can tell that from the
// defect family. Measured 0.7.31 on every pair of `renderUpdateCard`, the only
// two such cases, each verified by DOM, not assumed:
//
//   - `updateBusy` keeps `updateBtn` and `rollbackBtn` untouched. `runUpdate`
//     sets `disabled = true` on BOTH (popup.js:1449-1450) before it renders, so
//     neither can be clicked or hovered. The busy card says "installing" and the
//     status line names the operation; re-deriving the buttons' geometry here
//     would only flash a target that is already dead.
//   - `relay muet` and `upstream refuse` keep `rollbackBtn.title`, because they
//     `return` at line 52, before the tooltip is written at line 56 - and they
//     also set `rollbackBtn.style.display = 'none'` on the line above. A node
//     with `display:none` has NO hover, so the stale tooltip cannot reach the
//     user; measured, not inferred.
//
// The rule is therefore "a state either writes the value, or has DECLARED that
// keeping it is the point - and the declaration is checked per pair, never
// trusted." A declared node that does NOT survive here is a FAIL, so the escape
// hatch cannot grow without evidence (point 72: a guard that only ever widens is
// a guard that has stopped guarding).
const DELIBERATE = {
  'installation en cours': new Set(['updateBtn', 'rollbackBtn']),
  'relay muet': new Set(['rollbackBtn']),
  'upstream refuse': new Set(['rollbackBtn']),
};
// ---------------------------------------------------------------- renderUpdateCard
const UPDATE_BODY = sliceFunction(SRC, 'function renderUpdateCard()');
// Every state sets BOTH module globals explicitly. `updateBusy` is sticky: a
// state that only sets `updateInfo` leaves the previous state's busy flag in
// place, so every pair AFTER a busy state re-renders busy and the comparison
// reports the busy values as "surviving" - a defect in the harness attributed
// to the product. Declare the whole input, never part of it.
const st = (name, info, busy) => ({
  name,
  busy: !!busy,
  __sets: ['updateVersion', 'labelUpdate', 'updateChip', 'updateMeta', 'updateBtn', 'rollbackBtn'],
  drive(ctx) { ctx.updateInfo = info; ctx.updateBusy = !!busy; ctx.renderUpdateCard(); },
});
const UPSTREAM = { ok: false, error: 'API rate limit exceeded for 203.0.113.9', error_kind: 'rate_limit' };
const AWAIT_V = { ok: true, update_available: true, source: 'release', latest_version: '0.7.31',
                 current_commit: 'aaaaaaa1111', latest_commit: 'bbbbbbb2222',
                 current_version: '0.7.30', backup_available: true };
const AWAIT_MAIN = { ok: true, update_available: true, source: 'main', latest_version: '0.7.30',
                     current_commit: 'aaaaaaa1111', latest_commit: 'bbbbbbb2222',
                     current_version: '0.7.30', backup_available: true };
const UPTODATE = { ok: true, update_available: false, source: 'release', current_version: '0.7.30',
                  current_commit: 'aaaaaaa1111', latest_commit: 'aaaaaaa1111',
                  shipped_tree: 'same', backup_available: true };
const BASELINE = { ok: true, update_available: false, current_version: '0.7.30',
                   backup_available: false };
audit('renderUpdateCard', UPDATE_BODY, [
  st('relay muet', null),
  st('upstream refuse', UPSTREAM),
  st('release en attente', AWAIT_V),
  st('branche en attente', AWAIT_MAIN),
  st('a jour', UPTODATE),
  st('ligne de base', BASELINE),
  st('installation en cours', AWAIT_V, true),
]);

// ---------------------------------------------------------------- renderSessions
// `resetClearButton` is declared in the SANDBOX, not pasted next to
// `renderSessions`: two functions concatenated put a `return` at top level
// (Illegal return statement). Point 73 says declare what the code under test
// touches; the real implementation is preferred over a copy of it.
const SESS_BODY = sliceFunction(SRC, 'function renderSessions(');
const sess = (name, data, arm) => ({
  name,
  __sets: ['sessionsCount', 'sessionsList', 'sessionsClear', 'clearText'],
  drive(ctx, nodes) {
    if (arm) {
      nodes.sessionsClear.dataset.armed = '1';
      nodes.clearText.textContent = 'clearConfirmShort';
      nodes.sessionsClear.setAttribute('title', 'clearConfirm');
    }
    ctx.renderSessions(data);
  },
});
const TWO = { ok: true, sessions: [
  { host: 'a.example', origin: 'https://a.example', cookie_count: 3, expires: null, expired: false },
  { host: 'b.example', origin: 'https://b.example', cookie_count: 1, expires: null, expired: true },
]};
const NONE = { ok: true, sessions: [] };
audit('renderSessions', SESS_BODY, [
  sess('liste vide', NONE),
  sess('deux sessions', TWO),
  sess('deux sessions, bouton arme', TWO, true),
  sess('liste vide depuis un bouton arme', NONE, true),
]);

// ---------------------------------------------------------------- checkRelay
const RELAY_BODY = sliceFunction(SRC, 'async function checkRelay()');
const relay = (name, attached) => ({
  name,
  __sets: ['relayBadge', 'relayText'],
  async drive(ctx) {
    ctx.relayFetch = () => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ ok: true, attached }),
    });
    await ctx.checkRelay();
  },
});
// The relay body is async, so it needs its own comparison: same rule, awaited.
async function auditRelay() {
  const states = [relay('attache', true), relay('detache', false), relay('injoignable', true, false)];
  for (const A of states) {
    for (const B of states) {
      if (A === B) continue;
      const shared = makeNodes(), ctxS = vmFor(shared, RELAY_BODY);
      if (A.name === 'injoignable') ctxS.relayFetch = () => Promise.reject(new Error('x'));
      await A.drive(ctxS);
      if (B.name === 'injoignable') ctxS.relayFetch = () => Promise.reject(new Error('x'));
      await B.drive(ctxS);
      const fresh = makeNodes(), ctxF = vmFor(fresh, RELAY_BODY);
      if (B.name === 'injoignable') ctxF.relayFetch = () => Promise.reject(new Error('x'));
      await B.drive(ctxF);
      const s1 = snapshot(shared), s2 = snapshot(fresh);
      const leaks = [];
      for (const id of NODES) {
        for (const p of Object.keys(s2[id])) {
          if (JSON.stringify(s1[id][p]) !== JSON.stringify(s2[id][p])) {
            leaks.push(id + '.' + p + ' = ' + JSON.stringify(s1[id][p]) +
                       ' (state alone renders ' + JSON.stringify(s2[id][p]) + ')');
          }
        }
      }
      const pair = 'checkRelay  [' + A.name + ' -> ' + B.name + ']';
      if (!leaks.length) ok(pair);
      else for (const l of leaks) bad(pair, l);
    }
  }
}

// ---------------------------------------------------------------- copyDiagnostic
const DIAG_BODY = sliceFunction(SRC, 'async function copyDiagnostic()');
function auditDiag() {
  const states = [
    { name: 'succes', result: true },
    { name: 'echec', result: false },
  ];
  for (const A of states) {
    for (const B of states) {
      if (A === B) continue;
      const shared = makeNodes(), ctxS = vmFor(shared, DIAG_BODY);
      ctxS.navigator = { clipboard: { writeText: () => Promise.resolve(A.result) } };
      ctxS.copyDiagnostic();
      ctxS.navigator = { clipboard: { writeText: () => Promise.resolve(B.result) } };
      ctxS.copyDiagnostic();
      const fresh = makeNodes(), ctxF = vmFor(fresh, DIAG_BODY);
      ctxF.navigator = { clipboard: { writeText: () => Promise.resolve(B.result) } };
      ctxF.copyDiagnostic();
      const s1 = snapshot(shared), s2 = snapshot(fresh);
      const leaks = [];
      for (const id of NODES) {
        for (const p of Object.keys(s2[id])) {
          if (JSON.stringify(s1[id][p]) !== JSON.stringify(s2[id][p])) {
            leaks.push(id + '.' + p + ' = ' + JSON.stringify(s1[id][p]) +
                       ' (state alone renders ' + JSON.stringify(s2[id][p]) + ')');
          }
        }
      }
      const pair = 'copyDiagnostic  [' + A.name + ' -> ' + B.name + ']';
      // copyDiagnostic is async and its label resets on a timer this harness
      // freezes, so only the IMMEDIATE difference is in scope - and that is the
      // window a user clicks inside.
      if (!leaks.length) ok(pair);
      else for (const l of leaks) bad(pair, l);
    }
  }
}

auditRelay().then(() => {
  auditDiag();
  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed === 0 ? 0 : 1);
});
