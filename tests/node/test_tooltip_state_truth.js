// A tooltip is a PROPERTY of a state, so every state must own it.
//
// `renderUpdateCard` writes `updateMeta.title` in two of its three exits. The
// branch it does NOT write it in is not neutral: the node keeps whatever title
// the PREVIOUS render gave it. Measured 0.7.27 - the relay's own words stay
// hovering over an update card that is now perfectly healthy, and the tooltip
// lingers for the whole install (`runUpdate` renders with `updateBusy` true,
// which is exactly the branch that returns without touching it).
//
// The whole point needs ONE node through TWO renders, so each case below
// reuses a single node set and re-renders into it.
const fs = require('fs');
const path = require('path');

const ROOT = process.argv[2] || path.join(__dirname, '..', '..');
const SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');
const BODY = SRC.slice(
  SRC.indexOf('function renderUpdateCard()'),
  SRC.indexOf('async function refreshUpdateStatus()')
);

function makeNodes() {
  const nodes = {};
  for (const id of ['updateChip', 'updateMeta', 'updateBtn', 'rollbackBtn', 'labelUpdate', 'updateVersion']) {
    nodes[id] = {
      id, textContent: '', className: '', title: '', style: {},
      dataset: {},
      setAttribute() {}, removeAttribute() {}, appendChild() {}, addEventListener() {},
    };
  }
  return nodes;
}

function makeVm() {
  const nodes = makeNodes();
  const vm = require('vm');
  const ctx = {
    console,
    setTimeout: () => 0,
    clearTimeout: () => {},
    document: {
      documentElement: {},
      createElement: () => makeNodes().updateChip,
      getElementById: () => null,
      querySelectorAll: () => [],
    },
    chrome: { runtime: { getManifest: () => ({ version: '0.7.26' }), reload() {} } },
    updateInfo: null,
    updateBusy: false,
    labelUpdate: nodes.labelUpdate,
    updateVersion: nodes.updateVersion,
    updateChip: nodes.updateChip,
    updateMeta: nodes.updateMeta,
    updateBtn: nodes.updateBtn,
    rollbackBtn: nodes.rollbackBtn,
    t: (k) => k,
    shortCommit: (c) => String(c).slice(0, 7),
  };
  vm.createContext(ctx);
  vm.runInContext(BODY, ctx);
  return { ctx, nodes };
}

// The relay answered fine and GitHub refused: this state owns a tooltip, and it
// is the relay's own words, which is the rule point 59 established.
const UPSTREAM = { ok: false, error: 'API rate limit exceeded for 203.0.113.9', error_kind: 'rate_limit' };
const AWAITING = {
  ok: true, update_available: true, source: 'release', latest_version: '9.9.9',
  current_commit: 'aaaaaaa1111', latest_commit: 'bbbbbbb2222',
  current_version: '0.7.26', backup_available: true,
};
const UPTODATE = {
  ok: true, update_available: false, source: 'release', current_version: '0.7.26',
  current_commit: 'aaaaaaa1111', latest_commit: 'aaaaaaa1111',
  shipped_tree: 'same', backup_available: true,
};

let passed = 0;
let failed = 0;
function check(name, got, want) {
  const ok = got === want;
  if (ok) passed++; else failed++;
  console.log((ok ? 'ok   ' : 'FAIL ') + name +
    '  got=' + JSON.stringify(got) + ' want=' + JSON.stringify(want));
}

// --- the title an upstream failure owns, established on the real renderer ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = UPSTREAM;
  ctx.renderUpdateCard();
  check('upstream failure owns the relay tooltip',
    nodes.updateMeta.title, 'API rate limit exceeded for 203.0.113.9');
  check('upstream failure leaves the panel empty',
    nodes.updateMeta.textContent, 'updateRateLimited');
}

// --- the defect: a healthy state inherits the dead state's tooltip ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = UPSTREAM;
  ctx.renderUpdateCard();
  // Same nodes, next poll: the relay recovers and an update is waiting.
  ctx.updateInfo = AWAITING;
  ctx.renderUpdateCard();
  check('a waiting update does not inherit the upstream tooltip',
    nodes.updateMeta.title, '');
  // And the mirror direction: the tooltip must not come back when the state is
  // healthy. Asserting the absence, not just the empty string, so a future
  // change that writes the same value somewhere else is still caught.
  if (nodes.updateMeta.title === 'API rate limit exceeded for 203.0.113.9') {
    console.log('FAIL the upstream words are still hovering over a healthy card');
    failed++;
  } else {
    console.log('ok   the upstream words are not hovering over a healthy card');
    passed++;
  }
  check('a waiting update still offers the install button',
    nodes.updateBtn.style.display, '');
}

// --- the install itself: `runUpdate` renders with updateBusy true ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = UPSTREAM;
  ctx.renderUpdateCard();
  ctx.updateInfo = AWAITING;
  ctx.updateBusy = true;
  ctx.renderUpdateCard();
  check('an install in progress clears the tooltip',
    nodes.updateMeta.title, '');
  if (nodes.updateMeta.title === 'API rate limit exceeded for 203.0.113.9') {
    console.log('FAIL the relay tooltip survives the whole install');
    failed++;
  } else {
    console.log('ok   the relay tooltip does not survive the whole install');
    passed++;
  }
  check('an install in progress still shows the busy chip',
    nodes.updateChip.textContent, '…');
}

// --- a healthy state carries a commit tooltip, and it must not persist ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = UPTODATE;
  ctx.renderUpdateCard();
  check('an up-to-date card carries its commit tooltip',
    nodes.updateMeta.title, 'commit aaaaaaa');
  // Relay goes away entirely: the tooltip must be dropped, not kept.
  ctx.updateInfo = null;
  ctx.renderUpdateCard();
  check('a dead relay does not keep the commit tooltip',
    nodes.updateMeta.title, '');
  check('a dead relay still reports itself offline',
    nodes.updateChip.textContent, 'relayOffline');
}

// --- the case that was already correct, so a broken harness shows up here ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = UPTODATE;
  ctx.renderUpdateCard();
  check('an up-to-date card says so in the panel',
    nodes.updateMeta.textContent, 'updateUpToDate');
  check('an up-to-date card keeps undo reachable',
    nodes.rollbackBtn.style.display, '');
}

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed === 0 ? 0 : 1);
