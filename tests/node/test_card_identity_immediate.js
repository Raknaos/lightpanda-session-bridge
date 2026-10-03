// The popup shows its OWN version before it has spoken to the relay (0.7.30).
//
// `init()` writes the footer version (`appVersion`) synchronously, then awaits
// the token load, the token bootstrap and the relay probe - and only THEN calls
// `refreshUpdateStatus()` -> `renderUpdateCard()`, which is the single place
// that writes `updateVersion`. Measured 0.7.30: `/v1/update/check` alone answers
// in 864 ms on the running relay.
//
// For that whole window the update card reads `v0.5.0` - the literal shipped in
// `popup.html` - on a popup installed at 0.7.29. Twenty-nine versions stale, on
// the card whose entire purpose is to say which version you are on.
//
// The version is local knowledge: it comes from `chrome.runtime.getManifest()`
// and needs no network at all. So the fix is to render the card's own identity
// immediately, and let only the RELAY-dependent part arrive later.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.argv[2] || path.join(__dirname, '..', '..');
const SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');
const HTML = fs.readFileSync(path.join(ROOT, 'extension', 'popup.html'), 'utf8');
const markupPlaceholder = (HTML.match(/id="update-version"[^>]*>([^<]*)</) || [, ''])[1].trim();

const CARD = SRC.slice(
  SRC.indexOf('function renderUpdateCard()'),
  SRC.indexOf('async function refreshUpdateStatus()')
);
// Slice by BRACE COUNT: `indexOf('\n}\n')` finds the first line that starts
// with a closing brace, which inside a function with nested blocks is an inner
// one - the result is a truncated function and a bare SyntaxError (point 73).
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
const INIT = sliceFunction(SRC, 'async function init()');

function makeNodes() {
  const nodes = {};
  for (const id of ['updateChip', 'updateMeta', 'updateBtn', 'rollbackBtn', 'labelUpdate',
                    'updateVersion', 'appVersion', 'relayText', 'relayBadge',
                    'sessionsCount', 'sessionsList', 'sessionsClear', 'clearText',
                    'currentLangCode', 'originEl', 'statusEl', 'toastEl']) {
    nodes[id] = {
      id, textContent: '', className: '', title: '', innerHTML: '', style: {}, dataset: {},
      setAttribute(k, v) { this[k] = v; },
      removeAttribute(k) { delete this[k]; },
      appendChild() {}, addEventListener() {},
    };
  }
  return nodes;
}

// The markup's own initial content, so the harness starts from what a user sees
// the instant the popup opens - not from an empty node.
// The JS-name -> HTML-id mapping is read out of the PRODUCT, never re-typed
// here: a hand-written table is a second source of truth that silently rots
// when a node is renamed (skill 13).
const ID_OF = (() => {
  const map = {};
  for (const m of SRC.matchAll(
    /(?:const|let|var)\s+(\w+)\s*=\s*document\.(?:querySelector|getElementById)\('#([\w-]+)'\)/g)) {
    map[m[1]] = m[2];
  }
  return map;
})();

function seedFromHtml(nodes) {
  for (const id of Object.keys(nodes)) {
    // Anchor on the id, then find the TAG CLOSE - the markup puts `class`
    // BEFORE `id`, so requiring `id="..."` to be immediately followed by `>`
    // silently matched nothing (point 60: a pattern that matches nothing reads
    // as "the thing is absent", which is the OPPOSITE of what I was measuring).
    const htmlId = ID_OF[id];
    if (!htmlId) continue;
    const at = HTML.indexOf('id="' + htmlId + '"');
    if (at < 0) continue;
    const gt = HTML.indexOf('>', at);
    const lt = HTML.indexOf('<', gt);
    if (gt > 0 && lt > gt) nodes[id].textContent = HTML.slice(gt + 1, lt).trim();
  }
  return nodes;
}

let passed = 0;
let failed = 0;
function check(name, got, want) {
  const ok = got === want;
  if (ok) passed++; else failed++;
  console.log((ok ? 'ok   ' : 'FAIL ') + name +
    '  got=' + JSON.stringify(got) + ' want=' + JSON.stringify(want));
}

function vmFor(nodes) {
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
    updateInfo: null, updateBusy: false,
    labelUpdate: nodes.labelUpdate, updateVersion: nodes.updateVersion,
    updateChip: nodes.updateChip, updateMeta: nodes.updateMeta,
    updateBtn: nodes.updateBtn, rollbackBtn: nodes.rollbackBtn,
    appVersion: nodes.appVersion, relayText: nodes.relayText, relayBadge: nodes.relayBadge,
    sessionsCount: nodes.sessionsCount, sessionsList: nodes.sessionsList,
    sessionsClear: nodes.sessionsClear, clearText: nodes.clearText,
    currentLangCode: nodes.currentLangCode, originEl: nodes.originEl,
    statusEl: nodes.statusEl, toastEl: nodes.toastEl,
    t: (key, ...args) => (args.length ? key + '(' + args.join() + ')' : key),
    shortCommit: (c) => String(c).slice(0, 7),
    labelClear: () => 'sessionsClearShort',
    fmtExpiry: (x) => String(x),
    bridgeToken: 'tok',
    // Counters: the harness must be able to SEE whether a dependency was
    // awaited before the card rendered (point 73 - zero calls is a different
    // diagnosis from a wrong mapping).
    loadBridgeToken: () => Promise.resolve(),
    bootstrapToken: () => Promise.resolve(),
    checkRelay: () => Promise.resolve(true),
    refreshUpdateStatus: () => {},
    refreshSessions: () => {},
    applyTranslations: () => {},
    showToast: () => {},
    eligible: () => true,
    chrome: { runtime: { getManifest: () => ({ version: '0.7.30' }), reload() {} },
             tabs: { query: () => Promise.resolve([]) } },
    __relayCalls: 0,
    __renderCalls: 0,
  };
  vm.createContext(ctx);
  vm.runInContext(CARD, ctx);
  vm.runInContext(INIT, ctx);
  // Wrap renderUpdateCard so we can count the invocations.
  const real = ctx.renderUpdateCard;
  ctx.renderUpdateCard = function () { ctx.__renderCalls++; return real.apply(this, arguments); };
  return ctx;
}

// --- the fact that matters: what the card shows before any await resolves ---
{
  const nodes = seedFromHtml(makeNodes());
  const ctx = vmFor(nodes);
  const installed = 'v' + ctx.chrome.runtime.getManifest().version;
  check('the markup ships a stale version placeholder', markupPlaceholder, 'v0.5.0');

  // The user's popup has just opened. `init()` runs synchronously up to its
  // first `await`, and that prefix is the FIRST PAINT - it lasts for the whole
  // chain of network calls behind it. So run the real `init()` and read the card
  // before any promise resolves: calling `renderUpdateCard()` directly would
  // have measured a state no user ever sees (points 37 / 73: test the path, not
  // the helper).
  ctx.applyTranslations = () => {};
  ctx.loadBridgeToken = () => new Promise(() => {}); // never resolves: the
  // window we are measuring is the one BEFORE the relay is asked anything.
  ctx.init();

  check('on the first frame the card already names the installed version',
    nodes.updateVersion.textContent, installed);
  if (nodes.updateVersion.textContent !== installed) {
    console.log('FAIL the first frame shows ' + nodes.updateVersion.textContent +
      ' instead of the installed ' + installed);
    failed++;
  } else {
    console.log('ok   the first frame names the installed version, not ' + markupPlaceholder);
    passed++;
  }
}

// --- what the card must show as soon as it can, with no network at all ---
{
  const nodes = seedFromHtml(makeNodes());
  const ctx = vmFor(nodes);
  // `updateInfo === null` is the honest state before the first answer: the relay
  // has not spoken yet, which is NOT the same as "the relay is down".
  ctx.updateInfo = null;
  ctx.renderUpdateCard();
  check('a silent relay is not claimed to be a dead relay',
    nodes.updateChip.textContent, 'relayOffline');
  check('but the installed version is shown immediately',
    nodes.updateVersion.textContent, 'v0.7.30');
}

// --- the case that was already correct: the footer version ---
{
  const nodes = seedFromHtml(makeNodes());
  const ctx = vmFor(nodes);
  ctx.appVersion.textContent = 'v' + ctx.chrome.runtime.getManifest().version;
  check('the footer reports the installed version',
    nodes.appVersion.textContent, 'v0.7.30');
}

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed === 0 ? 0 : 1);
