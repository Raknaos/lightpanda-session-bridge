// The clear button's state belongs to the STATE OF THE LIST (measured 0.7.29).
//
// `renderSessions` fully resets the button in its "sessions exist" branch -
// `style.display`, `dataset.armed`, `title` and `clearText` - and resets only
// `style.display` in its "the list is empty" branch. So a button the user
// already ARMED for confirmation ("Confirm?") stays armed across a refresh
// that empties the list, and the next click on it wipes every synced session
// with no confirmation at all.
//
// The second half is the same absence seen from the HTML: the markup ships
// `<span id="clear-text">Clear all</span>`, an English literal that only the
// full-list branch ever replaces. A list that has just gone empty keeps it.
//
// Like 0.7.27 and 0.7.28, this needs ONE node set through TWO renders.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.argv[2] || path.join(__dirname, '..', '..');
const SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');
// `resetClearButton` is the shared owner of the button's state, so the slice
// must include it - otherwise the sandbox reproduces a missing-binding
// ReferenceError instead of the product (point 73).
const BODY = SRC.slice(
  SRC.indexOf('function resetClearButton('),
  SRC.indexOf('async function clearSessionsOnRelay(')
);

function makeNodes() {
  const nodes = {};
  for (const id of ['sessionsCount', 'sessionsList', 'sessionsClear', 'clearText']) {
    nodes[id] = {
      id, textContent: '', className: '', title: '', innerHTML: '', style: {}, dataset: {},
      setAttribute(k, v) { this[k] = v; }, removeAttribute(k) { delete this[k]; },
      appendChild() {}, addEventListener() {},
    };
  }
  return nodes;
}

function makeVm() {
  const nodes = makeNodes();
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
    sessionsCount: nodes.sessionsCount,
    sessionsList: nodes.sessionsList,
    sessionsClear: nodes.sessionsClear,
    clearText: nodes.clearText,
    t: (key, ...args) => (args.length ? key + '(' + args.join() + ')' : key),
    fmtExpiry: (x) => String(x),
    labelClear: () => 'sessionsClearShort',
    // The real click handler's second arm, so the "no confirmation" claim is
    // measured rather than asserted: an armed button wipes on the FIRST click.
    relayFetch: () => Promise.resolve({ ok: true }),
    bridgeHeaders: () => ({}),
    clearSessionsOnRelay: (o) => { ctx.__cleared = o; return Promise.resolve(true); },
    refreshSessions: () => Promise.resolve(),
    showToast: () => {},
    __cleared: 'not-called',
  };
  vm.createContext(ctx);
  vm.runInContext(BODY, ctx);
  return { ctx, nodes };
}

// Two sessions, so the button is shown and owns its state.
const TWO = { ok: true, sessions: [
  { host: 'a.example', origin: 'https://a.example', cookie_count: 3, expires: null, expired: false },
  { host: 'b.example', origin: 'https://b.example', cookie_count: 1, expires: null, expired: true },
]};
const NONE = { ok: true, sessions: [] };

let passed = 0;
let failed = 0;
function check(name, got, want) {
  const ok = got === want;
  if (ok) passed++; else failed++;
  console.log((ok ? 'ok   ' : 'FAIL ') + name +
    '  got=' + JSON.stringify(got) + ' want=' + JSON.stringify(want));
}

// --- a full list resets the button completely ---
{
  const { ctx, nodes } = makeVm();
  ctx.renderSessions(TWO);
  check('a full list shows the clear button', nodes.sessionsClear.style.display, 'inline-flex');
  check('a full list renders the count', nodes.sessionsCount.textContent, '2');
}

// --- the defect: arming survives the list going empty ---
{
  const { ctx, nodes } = makeVm();
  ctx.renderSessions(TWO);
  // The user's first click: this is the two-step confirmation's FIRST arm.
  nodes.sessionsClear.dataset.armed = '1';
  nodes.clearText.textContent = 'clearConfirmShort';
  nodes.sessionsClear.title = 'clearConfirm';
  // The list empties (another tab cleared it, or a sync removed them).
  ctx.renderSessions(NONE);
  if (nodes.sessionsClear.dataset.armed) {
    console.log('FAIL the button stays armed after the list goes empty');
    failed++;
  } else {
    console.log('ok   the button is not left armed after the list goes empty');
    passed++;
  }
  check('an empty list hides the button', nodes.sessionsClear.style.display, 'none');
}

// --- and the arming must not come back when sessions return ---
{
  const { ctx, nodes } = makeVm();
  ctx.renderSessions(TWO);
  nodes.sessionsClear.dataset.armed = '1';
  nodes.clearText.textContent = 'clearConfirmShort';
  nodes.sessionsClear.title = 'clearConfirm';
  ctx.renderSessions(NONE);
  ctx.renderSessions(TWO);
  check('sessions returning leave the button unarmed',
    nodes.sessionsClear.dataset.armed, undefined);
  check('sessions returning restore the clear wording',
    nodes.clearText.textContent, 'sessionsClearShort');
  if (nodes.sessionsClear.title) {
    console.log('FAIL sessions returning keep the confirmation tooltip');
    failed++;
  } else {
    console.log('ok   sessions returning do not keep the confirmation tooltip');
    passed++;
  }
}

// --- the English literal the markup ships, measured against the source ---
{
  const html = fs.readFileSync(path.join(ROOT, 'extension', 'popup.html'), 'utf8');
  const m = html.match(/<span id="clear-text">([^<]*)<\/span>/);
  const shipped = m ? m[1] : null;
  // The dictionary's own value is `sessionsClearShort`, which renderSessions
  // writes. So the markup's literal must be REPLACED by a render - asserted on
  // the state the user actually sees.
  const { ctx, nodes } = makeVm();
  ctx.renderSessions(TWO);
  if (shipped !== null && nodes.clearText.textContent === shipped) {
    console.log('FAIL the clear button still shows the markup literal "' + shipped + '"');
    failed++;
  } else {
    console.log('ok   the clear button does not show the markup literal "' + shipped + '"');
    passed++;
  }
}

// --- an unreadable answer is its own state, measured not guessed (point 66) ---
// That state belongs to `refreshSessions`, NOT to `renderSessions` - so measure
// it on the function that owns it. My first attempt called `renderSessions(null)`,
// which correctly renders "0 sessions" and therefore reported a defect the
// product does not have.
{
  const full = SRC.slice(SRC.indexOf('async function refreshSessions('),
                         SRC.indexOf("sessionsToggle.addEventListener"));
  const nodes = makeNodes();
  const ctx = {
    console,
    setTimeout: () => 0,
    document: { documentElement: {}, createElement: () => ({ textContent: '', className: '',
              innerHTML: '', style: {}, dataset: {}, appendChild() {}, addEventListener() {} }),
                getElementById: () => null, querySelectorAll: () => [] },
    sessionsCount: nodes.sessionsCount, sessionsList: nodes.sessionsList,
    sessionsClear: nodes.sessionsClear, clearText: nodes.clearText,
    fetchSessions: () => Promise.resolve(null),
    renderSessions: () => {},
  };
  vm.createContext(ctx);
  vm.runInContext(full, ctx);
  ctx.refreshSessions().then(() => {
    check('an unreadable list hides the button', nodes.sessionsClear.style.display, 'none');
    check('an unreadable list says so, it does not claim zero', nodes.sessionsCount.textContent, '—');
    console.log('\n' + passed + ' passed, ' + failed + ' failed');
    process.exit(failed === 0 ? 0 : 1);
  });
}
