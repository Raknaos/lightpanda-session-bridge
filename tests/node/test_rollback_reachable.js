// When the undo button is reachable.
//
// Measured 0.7.26, driving the real `renderUpdateCard`: `rollbackBtn.style.display`
// is computed CORRECTLY near the top of the function -
// `(backup_available && !update_available) ? '' : 'none'` - and then the
// "nothing to install" branch overwrote it with `'none'` on its last line. So the
// undo button was reachable ONLY while an update was WAITING, and never in the
// one state where it is useful: the user just installed an update and wants to
// go back. The relay measured `backup_available: true`, the popup READ the field,
// and then threw the reading away.
//
// The relay did its job, the consumer used the value, and the value was
// discarded one screen later. Both directions are asserted: showing undo with no
// backup behind it is as wrong as hiding it when one exists.
//
// Run: node tests/node/test_rollback_reachable.js <repo-root>

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
  if (end < 0) { console.error('fin introuvable: ' + sig); process.exit(2); }
  return SRC.slice(i, end);
}

let passed = 0;
const failures = [];
function ok(name, cond, detail) {
  if (cond) { passed++; console.log('  ok   ' + name); }
  else { failures.push(name); console.log('  FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

(async () => {
  const i18 = cut('const I18N = {');
  const I18N = vm.runInNewContext('(' + i18.slice(i18.indexOf('{')) + ')');

  const ctx = {
    I18N, currentLanguage: 'fr',
    t: (k, a) => {
      const v = I18N.fr[k];
      return typeof v === 'function' ? v(a) : (v === undefined ? 'FALLBACK:' + k : v);
    },
    shortCommit: (s) => (s ? s.slice(0, 7) : ''),
    updateInfo: null,
    updateChip: { className: '', textContent: '', title: '' },
    updateMeta: { textContent: '', title: '' },
    updateBtn: { textContent: '', style: {}, setAttribute() {} },
    rollbackBtn: { textContent: '', title: '', style: {}, setAttribute() {} },
    labelUpdate: { textContent: '' },
    updateVersion: { textContent: '' },
    labelSessions: { textContent: '' },
    updateRow: {}, statusEl: { textContent: '', className: '' },
    updateBusy: false,
    bridgeToken: null,
    RELAY: 'http://127.0.0.1:8765', RELAY_TIMEOUT_MS: 45000,
    showToast: () => {},
    chrome: {
      runtime: { reload() {}, lastError: null, getManifest: () => ({ version: '0.7.25' }) },
      storage: { local: { get() {}, set() {} } }
    }
  };
  vm.createContext(ctx);
  vm.runInContext([
    cut('function t(key, ...args) {'),
    cut('function shortCommit('),
    cut('function renderUpdateCard(')
  ].join('\n'), ctx);

  const SHA_A = 'a'.repeat(40), SHA_B = 'b'.repeat(40);
  const CASES = [
    ['rien a installer, backup dispo', { ok: true, update_available: false, backup_available: true, shipped_tree: 'same', current_commit: SHA_A, latest_commit: SHA_A, current_version: '0.7.25' }],
    ['rien a installer, AUCUN backup', { ok: true, update_available: false, backup_available: false, shipped_tree: 'same', current_commit: SHA_A, latest_commit: SHA_A, current_version: '0.7.25' }],
    ['branche avancee, backup dispo', { ok: true, update_available: false, backup_available: true, shipped_tree: 'same', current_commit: SHA_A, latest_commit: SHA_B, current_version: '0.7.25' }],
    ['mise a jour disponible, backup dispo', { ok: true, update_available: true, backup_available: true, source: 'release', latest_version: '0.7.26' }],
    ['mise a jour disponible, AUCUN backup', { ok: true, update_available: true, backup_available: false, source: 'release', latest_version: '0.7.26' }]
  ];

  const shown = [];
  for (const [label, info] of CASES) {
    vm.runInContext('updateInfo = ' + JSON.stringify(info), ctx);
    vm.runInContext('renderUpdateCard()', ctx);
    const rollback = vm.runInContext("rollbackBtn.style.display", ctx);
    const install = vm.runInContext("updateBtn.style.display", ctx);
    shown.push(rollback);
    console.log('    [' + label + '] rollback=' + JSON.stringify(rollback) + ' install=' + JSON.stringify(install));
  }

  // The defect itself: undo must be reachable when a backup exists and nothing is
  // waiting. This is the case the overwriting line used to kill.
  ok('undo joignable apres une installation (backup present)',
     shown[0] === '', 'affiche ' + JSON.stringify(shown[0]));
  ok('undo masque quand aucun backup n existe',
     shown[1] === 'none', 'affiche ' + JSON.stringify(shown[1]));
  ok('undo joignable apres une branche avancee (backup present)',
     shown[2] === '', 'affiche ' + JSON.stringify(shown[2]));
  ok('undo joignable quand une mise a jour attend (backup present)',
     shown[3] === '', 'affiche ' + JSON.stringify(shown[3]));
  ok('undo masque quand une mise a jour attend sans backup',
     shown[4] === 'none', 'affiche ' + JSON.stringify(shown[4]));

  // The install button must NOT appear when there is nothing to install, and the
  // fix must not have made it visible by accident.
  vm.runInContext('updateInfo = ' + JSON.stringify(CASES[0][1]), ctx);
  vm.runInContext('renderUpdateCard()', ctx);
  ok('pas de bouton installer quand rien a installer',
     vm.runInContext("updateBtn.style.display", ctx) === 'none');

  // A relay that never answered keeps both hidden: there is no measured backup.
  vm.runInContext('updateInfo = null', ctx);
  vm.runInContext('renderUpdateCard()', ctx);
  ok('relais muet : aucun bouton', vm.runInContext("rollbackBtn.style.display", ctx) === 'none');

  console.log('\n' + passed + ' passed, ' + failures.length + ' failed');
  if (failures.length) {
    for (const f of failures) console.log('  - ' + f);
    process.exit(1);
  }
})().catch((e) => { console.error('HARNESS', e.message); process.exit(2); });