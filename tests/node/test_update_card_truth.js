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

// 5. `same` covers TWO situations that must NOT share a sentence. Measured on
//    0.7.21: adding the "deployed tree IS the tip of main" branch published
//    `shipped_tree: 'same'` too, and the popup then claimed "the branch moved
//    on" for a user who was already AT the tip - a lie in exactly the case
//    where the user is fully up to date.
const atTip = render({
  ok: true, update_available: false, shipped_tree: 'same',
  current_commit: '8e22d1ea9fe03070fb5da270f5c104be63f20c9d',
  latest_commit: '8e22d1ea9fe03070fb5da270f5c104be63f20c9d',
  current_version: '0.7.21', backup_available: true,
});
// Derive the discriminating literal from the FRENCH dictionary itself, never
// from a word I pick: ten languages spell "moved on" ten ways (avance,
// avanza, avanco, weitergezogen, advanced, moved on, ...) and a hand-written
// regex matched NONE of them - it went green even before the fix, which is the
// decorative-test trap (points 24 / 60). Read the real string, then assert on
// the part of it that is NOT the language-invariant part.
const SAME_FR = I18N.fr.updateSameBytes;
const SAME_TAIL = SAME_FR.slice(SAME_FR.indexOf('·')).trim(); // "· la branche a avancé"
ok('la phrase "identique" se termine bien par une raison variable',
  /·/.test(SAME_FR) && SAME_TAIL.length > 0, 'fr=' + SAME_FR);
ok('a la pointe de main, le popup ne rend PAS la phrase "branche avancee"',
  atTip.meta.indexOf(SAME_TAIL) === -1,
  'meta=' + JSON.stringify(atTip.meta) + ' tail=' + JSON.stringify(SAME_TAIL));
ok('a la pointe de main, il annonce la version',
  /0\.7\.21/.test(atTip.meta), 'meta=' + JSON.stringify(atTip.meta));
// The inverse: main DID move on, so that sentence is the right one - and it must
// be the EXACT string from the dictionary, not a hand-typed approximation.
const movedOn = render({
  ok: true, update_available: false, shipped_tree: 'same',
  current_commit: '34827e43c67797e41df84f11632a218727787938',
  latest_commit: 'cb4bdf51c67797e41df84f11632a218727787938',
  current_version: '0.7.20', backup_available: true,
});
ok('si la branche a avance, il rend la phrase exacte du dictionnaire',
  movedOn.meta === SAME_FR,
  JSON.stringify(movedOn.meta) + ' != ' + JSON.stringify(SAME_FR));
// The two sentences must actually differ, or the distinction is cosmetic.
ok('les deux situations ne rendent pas la meme phrase',
  atTip.meta !== movedOn.meta,
  atTip.meta + '  VS  ' + movedOn.meta);
// And the new sentence must be a real dictionary value, not an ad-hoc literal.
ok('la phrase "a jour" vient elle aussi du dictionnaire',
  atTip.meta === I18N.fr.updateUpToDate('0.7.21'),
  JSON.stringify(atTip.meta) + ' != ' + JSON.stringify(I18N.fr.updateUpToDate('0.7.21')));
// No dangling "v" when the version is missing (updateUpToDate interpolates it).
const atTipNoVersion = render({
  ok: true, update_available: false, shipped_tree: 'same',
  current_commit: '8e22d1ea9fe0', latest_commit: '8e22d1ea9fe0',
  current_version: null, backup_available: true,
});
ok('sans version, pas de "v" dangling',
  !/\sv$|\s·\s*$/.test(atTipNoVersion.meta), 'meta=' + JSON.stringify(atTipNoVersion.meta));

// 7. GitHub did not answer for the BRANCH (relay/updater.py, measured
//    0.7.22). `update_available` is still False - the release lookup succeeded -
//    but False means "we could not look", not "nothing is waiting". Before the
//    fix the popup printed reassurance it had not measured. The ordering is the
//    fix: `unreachable_branch` is read BEFORE `atTip`, because `latest_commit`
//    is absent here, so `atTip` is falsy and the chain used to fall through to
//    the versionless chip.
const branchDown = render({
  ok: true, update_available: false, shipped_tree: 'unknown',
  unreachable_branch: true,
  current_commit: '8e22d1ea9fe0', latest_commit: null,
  current_version: '0.7.22', backup_available: true,
});
const UNK_FR = I18N.fr.updateBranchUnknown;
ok('branche illisible : il ne dit PAS qu on est a jour',
  branchDown.meta !== I18N.fr.updateUpToDate('0.7.22') &&
  branchDown.meta !== I18N.fr.updateChipOk,
  'meta=' + JSON.stringify(branchDown.meta));
ok('branche illisible : il rend la phrase exacte du dictionnaire',
  branchDown.meta === UNK_FR,
  JSON.stringify(branchDown.meta) + ' != ' + JSON.stringify(UNK_FR));
// It must also not fall back to the bare-sha or baseline sentences.
ok('branche illisible : ni sha nu, ni baseline',
  !/commit [0-9a-f]/.test(branchDown.meta) &&
  branchDown.meta !== I18N.fr.updateBaseline,
  'meta=' + JSON.stringify(branchDown.meta));
// The honest state must NOT leak into the cases that can be measured: a False
// `unreachable_branch` changes nothing for the two `same` situations (point 50).
const atTipKnown = render({
  ok: true, update_available: false, shipped_tree: 'same',
  unreachable_branch: false,
  current_commit: '8e22d1ea9fe0', latest_commit: '8e22d1ea9fe0',
  current_version: '0.7.22', backup_available: true,
});
ok('branche lisible : le cas "a la pointe" est intact',
  atTipKnown.meta === I18N.fr.updateUpToDate('0.7.22'),
  'meta=' + JSON.stringify(atTipKnown.meta));
// And a key that is simply MISSING must not be read as "unreachable": an old
// relay (pre-0.7.22) never sends the field, and it must render as before.
const noKey = render({
  ok: true, update_available: false, shipped_tree: 'same',
  current_commit: '8e22d1ea9fe0', latest_commit: '8e22d1ea9fe0',
  current_version: '0.7.22', backup_available: true,
});
ok('ancien relais sans la cle : rendu inchange (pas FALLBACK)',
  noKey.meta === I18N.fr.updateUpToDate('0.7.22'),
  'meta=' + JSON.stringify(noKey.meta));

// 8. `!updateInfo.ok` covers TWO different failures. Measured 0.7.23: the relay
//    answered perfectly (/health 200) while GitHub refused, and the card still
//    said "Relay Offline" - sending the user to debug a working installation.
//    The relay publishes `error_kind`; the popup had never read it.
// A silent relay (`updateInfo === null`) must still read as offline - asserted
// through the `ok:false` + no-error row below, which is the shape the guard
// actually sees; a test whose body is `return true` cannot fail (point 24).
const ghDown = render({
  ok: false, error: 'API rate limit exceeded for 203.0.113.9',
  error_kind: 'rate_limit', update_available: false,
});
ok('GitHub en erreur : il ne dit PAS que le relais est hors ligne',
  ghDown.chip !== I18N.fr.relayOffline,
  'chip=' + JSON.stringify(ghDown.chip));
ok('GitHub en erreur : la puce est le texte GitHub du dictionnaire',
  ghDown.chip === I18N.fr.updateGitHubDown,
  JSON.stringify(ghDown.chip) + ' != ' + JSON.stringify(I18N.fr.updateGitHubDown));
ok('rate limit : il rend la phrase dediee, pas la generique',
  ghDown.meta === I18N.fr.updateRateLimited,
  JSON.stringify(ghDown.meta) + ' != ' + JSON.stringify(I18N.fr.updateRateLimited));
ok('le message brut du relais va dans l infobulle, pas dans le panneau',
  /rate limit/.test(ghDown.metaTitle) && !/rate limit/.test(ghDown.meta),
  'meta=' + JSON.stringify(ghDown.meta) + ' title=' + JSON.stringify(ghDown.metaTitle));
// The inverse: a non-rate-limit upstream failure must NOT claim a rate limit.
const ghOther = render({
  ok: false, error: 'GitHub unreachable (ConnectionError)',
  error_kind: 'unreachable', update_available: false,
});
ok('autre erreur GitHub : pas de faux "limite atteinte"',
  ghOther.meta === I18N.fr.updateGitHubDown,
  'meta=' + JSON.stringify(ghOther.meta));
// And `ok: false` with NO error at all is not upstream: it stays "relay down".
const noError = render({ ok: false, update_available: false });
ok('ok:false sans error : traite comme relais muet, pas comme GitHub',
  noError.chip === I18N.fr.relayOffline && noError.meta === '',
  'chip=' + JSON.stringify(noError.chip) + ' meta=' + JSON.stringify(noError.meta));

// 9. Every language must carry the key: a missing one renders FALLBACK.
const langs = ['en', 'fr', 'es', 'de', 'zh', 'ja', 'it', 'pt', 'ar', 'ru'];
for (const L of langs) {
  ok('cle presente en ' + L,
    I18N[L] && I18N[L].updateSameBytes && typeof I18N[L].updateSameBytes === 'string');
  ok('updateUpToDate (fonction) presente en ' + L,
    I18N[L] && typeof I18N[L].updateUpToDate === 'function',
    typeof (I18N[L] || {}).updateUpToDate);
  ok('updateBranchUnknown presente en ' + L,
    I18N[L] && typeof I18N[L].updateBranchUnknown === 'string' &&
    I18N[L].updateBranchUnknown.length > 8,
    typeof (I18N[L] || {}).updateBranchUnknown);
  ok('updateGitHubDown + updateRateLimited en ' + L,
    I18N[L] && typeof I18N[L].updateGitHubDown === 'string' &&
    I18N[L].updateGitHubDown.length > 4 &&
    typeof I18N[L].updateRateLimited === 'string' &&
    I18N[L].updateRateLimited.length > 4 &&
    I18N[L].updateRateLimited !== I18N[L].updateGitHubDown,
    L + ': ' + typeof (I18N[L] || {}).updateGitHubDown + ' / ' +
    typeof (I18N[L] || {}).updateRateLimited);
}
// And the French one must be French, not an English literal left in place.
ok('le francais est bien en francais',
  I18N.fr.updateSameBytes !== I18N.en.updateSameBytes,
  'fr=' + I18N.fr.updateSameBytes);
ok('updateUpToDate rend la version dans les 10 langues',
  langs.every(L => /0\.9\.9/.test(I18N[L].updateUpToDate('0.9.9'))),
  'en=' + I18N.en.updateUpToDate('0.9.9') + ' ja=' + I18N.ja.updateUpToDate('0.9.9'));

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);