// Every label on the update card belongs to a STATE (measured 0.7.27 for
// `updateMeta.title`; this file covers the sibling defect on the same node set).
//
// `renderUpdateCard` writes `updateBtn.textContent` ONLY in the
// `update_available` branch. The other three exits - relay down, upstream
// refused, and "nothing to install" - leave it holding the previous render's
// wording, which names a version: "Installer v0.7.28". The button is hidden in
// every one of those states, so the stale wording is invisible while hidden -
// and reappears the moment the same button is shown again for a DIFFERENT
// version, or re-shown by the busy branch.
//
// The whole point needs ONE node through TWO renders, so every case below
// re-renders into the same node set (a fresh DOM per case measures nothing).
const fs = require('fs');
const path = require('path');
const vm = require('vm');

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
      id, textContent: '', className: '', title: '', style: {}, dataset: {},
      setAttribute() {}, removeAttribute() {}, appendChild() {}, addEventListener() {},
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
      createElement: () => makeNodes().updateChip,
      getElementById: () => null,
      querySelectorAll: () => [],
    },
    chrome: { runtime: { getManifest: () => ({ version: '0.7.27' }), reload() {} } },
    updateInfo: null,
    updateBusy: false,
    labelUpdate: nodes.labelUpdate,
    updateVersion: nodes.updateVersion,
    updateChip: nodes.updateChip,
    updateMeta: nodes.updateMeta,
    updateBtn: nodes.updateBtn,
    rollbackBtn: nodes.rollbackBtn,
    // The real `t()` contract, both shapes (fixed in 0.7.25): a FUNCTION value
    // is CALLED with the args, a string is only formatted when it carries a
    // `{0}` placeholder. My first stub concatenated unconditionally, which
    // rendered `updateBtn\0v0.7.28` - a harness fault that would have pinned a
    // defect the product does not have (point 65: a hand-built literal in an
    // assertion matches nothing and reports green).
    t: (key, ...args) => {
      if (args.length && key.indexOf('{0}') !== -1) return key.replace('{0}', args[0]);
      return args.length ? key + '(' + args.join() + ')' : key;
    },
    shortCommit: (c) => String(c).slice(0, 7),
  };
  vm.createContext(ctx);
  vm.runInContext(BODY, ctx);
  return { ctx, nodes };
}

const AWAITING_V28 = {
  ok: true, update_available: true, source: 'release', latest_version: '0.7.28',
  current_commit: 'aaaaaaa1111', latest_commit: 'bbbbbbb2222',
  current_version: '0.7.27', backup_available: true,
};
const AWAITING_MAIN = {
  ok: true, update_available: true, source: 'main', latest_version: '0.7.27',
  current_commit: 'aaaaaaa1111', latest_commit: 'bbbbbbb2222',
  current_version: '0.7.27', backup_available: true,
};
const UPTODATE = {
  ok: true, update_available: false, source: 'release', current_version: '0.7.27',
  current_commit: 'aaaaaaa1111', latest_commit: 'aaaaaaa1111',
  shipped_tree: 'same', backup_available: true,
};
const RELAY_DOWN = null;

let passed = 0;
let failed = 0;
function check(name, got, want) {
  const ok = got === want;
  if (ok) passed++; else failed++;
  console.log((ok ? 'ok   ' : 'FAIL ') + name +
    '  got=' + JSON.stringify(got) + ' want=' + JSON.stringify(want));
}

// --- the wording that belongs to the waiting state ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = AWAITING_V28;
  ctx.renderUpdateCard();
  check('a waiting release names its version on the button',
    nodes.updateBtn.textContent, 'updateBtn(0.7.28)');
  check('a waiting release shows the button', nodes.updateBtn.style.display, '');
}

// --- the defect: the other exits never own the wording ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = AWAITING_V28;
  ctx.renderUpdateCard();
  // Relay goes away: the button is hidden, but the wording must still be reset.
  ctx.updateInfo = RELAY_DOWN;
  ctx.renderUpdateCard();
  if (String(nodes.updateBtn.textContent).indexOf('0.7.28') !== -1) {
    console.log('FAIL a dead relay keeps the version the button used to offer');
    failed++;
  } else {
    console.log('ok   a dead relay does not keep the version the button used to offer');
    passed++;
  }
  check('a dead relay hides the button', nodes.updateBtn.style.display, 'none');
}

// --- the mirror, and the one that is actually VISIBLE: main offers a branch ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = AWAITING_V28;
  ctx.renderUpdateCard();
  // Same button, different source: a branch update has its OWN wording, so the
  // version must not survive into it.
  ctx.updateInfo = AWAITING_MAIN;
  ctx.renderUpdateCard();
  check('a branch update does not inherit the release wording',
    nodes.updateBtn.textContent, 'updateBtnMain');
  if (String(nodes.updateBtn.textContent).indexOf('0.7.28') !== -1) {
    console.log('FAIL the button still offers a version that is not the one on offer');
    failed++;
  } else {
    console.log('ok   the button does not offer a version that is not the one on offer');
    passed++;
  }
}

// --- up to date, then waiting again: the common cycle ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = AWAITING_V28;
  ctx.renderUpdateCard();
  ctx.updateInfo = UPTODATE;
  ctx.renderUpdateCard();
  check('an up-to-date card hides the button', nodes.updateBtn.style.display, 'none');
  ctx.updateInfo = AWAITING_MAIN;
  ctx.renderUpdateCard();
  check('a branch update after an up-to-date state names no version',
    nodes.updateBtn.textContent, 'updateBtnMain');
}

// --- an install in progress: runUpdate renders with updateBusy true ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = AWAITING_V28;
  ctx.renderUpdateCard();
  ctx.updateBusy = true;
  ctx.renderUpdateCard();
  if (String(nodes.updateBtn.textContent).indexOf('0.7.28') !== -1) {
    console.log('FAIL the offered version stays on the button through the install');
    failed++;
  } else {
    console.log('ok   the offered version does not stay on the button through the install');
    passed++;
  }
}

// --- the case that was already correct, so a broken harness shows up here ---
{
  const { ctx, nodes } = makeVm();
  ctx.updateInfo = AWAITING_MAIN;
  ctx.renderUpdateCard();
  check('a branch update shows the button', nodes.updateBtn.style.display, '');
  check('a branch update names the branch in the panel',
    nodes.updateMeta.textContent, '→ commit bbbbbbb');
  check('a branch update is a "new" chip', nodes.updateChip.className, 'update-chip new');
}

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed === 0 ? 0 : 1);
