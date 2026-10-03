// When the relay measures "the published bytes are identical", the popup must
// SAY SO. Otherwise the chip reads "Up to date" plus a bare commit sha, and a
// user cannot tell "nothing new" from "a code change is waiting" - the whole
// point of the shipped_tree flag is that it was measured, not guessed.
//
// Measured on 0.7.19: main had moved on (cb4bdf51) while the deployed tree was
// byte-identical to the last shipped commit. The popup showed "À jour" and
// "commit 34827e4", which is true and completely unhelpful.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.argv[2];
let SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');

let passed = 0;
let failed = 0;
function ok(name, cond, extra) {
  if (cond) { passed++; console.log('ok   ' + name); }
  else { failed++; console.log('FAIL ' + name + (extra ? ' -> ' + extra : '')); }
}

// ---- Extract renderUpdateCard and run it against a stub DOM -----------------
// Cut at the block's OWN closing brace. `indexOf('\nfunction ')` overruns into
// the next block and evaluates the click wiring too, which needs a real DOM
// element - the harness then dies on addEventListener and reads as a product
// fault. (Harness lesson, twice on this file: the first cut took the NEXT
// function, and a `let depth` was declared twice.)
function matchingBrace(text, from) {
  let depth = 0;
  for (let k = from; k < text.length; k++) {
    if (text[k] === '{') depth++;
    else if (text[k] === '}') { depth--; if (depth === 0) return k + 1; }
  }
  return -1;
}

const start = SRC.indexOf('function renderUpdateCard(');
if (start < 0) { console.error('renderUpdateCard introuvable'); process.exit(2); }
const fnEnd = matchingBrace(SRC, SRC.indexOf('{', start));
if (fnEnd < 0) { console.error('fin de renderUpdateCard introuvable'); process.exit(2); }
const body = SRC.slice(start, fnEnd);

// The stub records what the card was told, and `t()` resolves against the REAL
// dictionary so a missing key or a broken escape shows up as French/FALLBACK.
function render(info) {
  // Plain data objects, and READ THEM BACK after the render. Accessors declared
  // inside the sandbox literal are dropped by the proxy (measured: the
  // descriptor came back with no get/set), and re-defining them afterwards did
  // not help because the proxy had already snapshotted the data property. So:
  // let the code write plain fields, then inspect what it wrote.
  const ctx = {
    updateInfo: info,
    updateBusy: false,
    updateChip: { className: '', textContent: '', setAttribute() {} },
    labelUpdate: { textContent: '' },
    updateVersion: { textContent: '' },
    updateMeta: { textContent: '', title: '' },
    updateBtn: { textContent: '', style: {}, setAttribute() {} },
    rollbackBtn: { textContent: '', style: {}, setAttribute() {}, title: '' },
    shortCommit: (s) => (s ? String(s).slice(0, 7) : ''),
    chrome: { runtime: { getManifest: () => ({ version: '0.7.19' }) } },
    t: (key, arg) => {
      const val = I18N.fr[key];
      if (typeof val === 'function') return val(arg);
      return val === undefined ? 'FALLBACK:' + key : val;
    },
  };
  vm.createContext(ctx);
  // Declare it AND call it: `runInContext` with the function source only
  // DEFINES the symbol, so the card stayed blank and every assertion below
  // read the initial ''. Four rounds of harness debugging on one blank field.
  vm.runInContext(body + '\nrenderUpdateCard();', ctx);
  return {
    chip: ctx.updateChip.textContent,
    meta: ctx.updateMeta.textContent,
    metaTitle: ctx.updateMeta.title,
  };
}

// ---- Load the real dictionary out of popup.js --------------------------------
const dictStart = SRC.indexOf('const I18N = {');
if (dictStart < 0) { console.error('I18N introuvable'); process.exit(2); }
// Evaluate only the dictionary literal, by cutting at its matching brace.
const dictEnd = matchingBrace(SRC, SRC.indexOf('{', dictStart));
const literal = SRC.slice(SRC.indexOf('{', dictStart), dictEnd);
const I18N = vm.runInNewContext('(' + literal + ')');

// ---------------------------------------------------------------------------
// 1. The measured state must be announced, in French, from a real key.
const same = render({
  ok: true, update_available: false, shipped_tree: 'same',
  current_commit: '34827e43c67797e41df84f11632a218727787938',
  backup_available: true,
});
ok('la puce dit qu il n y a rien a installer', same.chip === 'À jour', same.chip);
ok('la ligne dit POURQUOI (identique, pas juste un sha)',
   /Identique/.test(same.meta), 'meta=' + JSON.stringify(same.meta));
ok('la ligne ne montre pas seulement un commit nu',
   !/^commit [0-9a-f]{7}$/.test(same.meta), 'meta=' + JSON.stringify(same.meta));
ok('le commit reste disponible (infobulle)',
   /34827e4/.test(same.metaTitle), 'title=' + JSON.stringify(same.metaTitle));

// 2. Same version, bytes DIFFERENT -> that is an update, not this branch.
//    (The relay reports update_available true there, so the chip is 'new'.)
const differs = render({
  ok: true, update_available: true, source: 'release', shipped_tree: 'differs',
  latest_version: '0.7.20', current_commit: '34827e43c677', backup_available: true,
});
ok('des octets differents donnent bien une MAJ',
   differs.chip === 'Mise à jour', differs.chip);

// 3. Unknown state must NOT claim the bytes are identical.
const unknown = render({
  ok: true, update_available: false, shipped_tree: null,
  current_commit: '34827e43c677', backup_available: true,
});
ok('un arbre inconnu n announce pas une identite mesuree',
   !/Identique/.test(unknown.meta), 'meta=' + JSON.stringify(unknown.meta));

// 4. No provenance: the baseline message, not the identity claim.
const noCommit = render({
  ok: true, update_available: false, shipped_tree: 'same',
  current_commit: null, backup_available: true,
});
ok('sans commit installe, pas de sha a afficher',
   !/commit [0-9a-f]/.test(noCommit.meta), 'meta=' + JSON.stringify(noCommit.meta));

// 5. Every language must carry the key: a missing one renders FALLBACK.
const langs = ['en', 'fr', 'es', 'de', 'zh', 'ja', 'it', 'pt', 'ar', 'ru'];
for (const L of langs) {
  ok('cle presente en ' + L,
     I18N[L] && I18N[L].updateSameBytes && typeof I18N[L].updateSameBytes === 'string');
}
// And the French one must be French, not an English literal left in place.
ok('le francais est bien en francais',
   I18N.fr.updateSameBytes !== I18N.en.updateSameBytes,
   'fr=' + I18N.fr.updateSameBytes);

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);