// The session meta line must be translated, and must actually show the expiry.
//
// Two defects in one line: the count and the word "expired" were English literals
// in a ten-language panel, and `expires` was always null so neither the countdown
// nor the warning could ever appear.
//
// The render path is extracted from popup.js and run in Node against the real
// I18N dictionary, so the values checked here are the ones a user would read.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.argv[2];
let SRC = fs.readFileSync(path.join(ROOT, 'extension', 'popup.js'), 'utf8');
// Point at the INSTALLED popup when asked: the repo can be perfect while the
// deployed copy is stale, and this is the file a user's browser runs.
if (process.env.LP_INSTALLED === '1') {
  const inst = path.join(process.env.HOME || process.env.USERPROFILE,
    '.config', 'lightpanda-bridge', 'extension-backup', 'popup.js');
  if (fs.existsSync(inst)) SRC = fs.readFileSync(inst, 'utf8');
}

let pass = 0, fail = 0;
function ok(cond, name, detail) {
  if (cond) { console.log(`  ok   ${name}${detail ? ' - ' + detail : ''}`); pass++; }
  else { console.log(`  FAIL ${name}${detail ? ' - ' + detail : ''}`); fail++; }
}

function slice(start, end) {
  const i = SRC.indexOf(start);
  if (i < 0) throw new Error(`introuvable: ${start}`);
  const j = SRC.indexOf(end, i);
  if (j < 0) throw new Error(`introuvable la fin: ${end}`);
  return SRC.slice(i, j + end.length);
}

// ---- the real dictionary, the real t(), the real fmtExpiry -----------------
const I18N_SRC = slice('const I18N = {', '\n};');
const T_SRC = slice('function t(key, ...args) {', '\n}');
const FMT_SRC = slice('function fmtExpiry(ts) {', '\n}');

// The popup's own assignment, copied verbatim out of the source. If this slice
// ever stops matching, the tests below would be measuring a second
// implementation of the product instead of the product.
const META_START = "meta.textContent = t(s.cookie_count === 1";
function extractMetaExpr() {
  const i = SRC.indexOf(META_START);
  if (i < 0) throw new Error('la ligne de rendu des sessions a change de forme');
  let j = SRC.indexOf(';', i);
  // A FUNCTION, evaluated per call: evaluating it once at module load would
  // capture whatever `s` happened to be, which is the bug this shape invites.
  return 'var metaExpr = function (s) { return '
       + SRC.slice(i, j + 1).replace('meta.textContent =', '')
       + ' };';
}
const META_EXPR = extractMetaExpr();

function renderMeta(lang, session) {
  const sb = { console };
  sb.__lang = lang;
  vm.createContext(sb);
  vm.runInContext(I18N_SRC, sb);
  vm.runInContext(T_SRC, sb);
  vm.runInContext(FMT_SRC, sb);
  vm.runInContext('var currentLanguage = __lang;', sb);
  // The REAL render expression, sliced out of popup.js - not a transcription.
  vm.runInContext(META_EXPR, sb);
  vm.runInContext('var s = ' + JSON.stringify(session) + ';', sb);
  vm.runInContext('var out = metaExpr(s);', sb);
  return sb.out;
}

console.log('--- la ligne de session est traduite ---');

// A count of 1 in every language must not read "1 cookies" outside English.
// Only English and German have a distinct plural; fr/es/it/pt/ru/zh/ja/ar
// treat "cookie" as invariant, so "1 cookies" is correct there and asserting
// otherwise would be enforcing an English rule on ten languages.
for (const lang of ['en', 'de']) {
  const line = renderMeta(lang, { cookie_count: 1, expires: null, expired: false });
  ok(!/cookies|Cookies/i.test(line),
     `${lang}: une seule session ne dit pas "cookies"`,
     JSON.stringify(line));
  const many = renderMeta(lang, { cookie_count: 7, expires: null, expired: false });
  ok(/cookies|Cookies/i.test(many),
     `${lang}: plusieurs sessions disent "cookies"`,
     JSON.stringify(many));
}

// The exact strings a French user must read.
const frFresh = renderMeta('fr', { cookie_count: 12, expires: Date.now() / 1000 + 86400 * 3, expired: false });
const frGone = renderMeta('fr', { cookie_count: 12, expires: Date.now() / 1000 - 3600, expired: true });
ok(/^12 cookies/.test(frFresh) && !/expired/i.test(frGone),
   'fr: une session expiree se lit en francais', JSON.stringify(frGone));

const deGone = renderMeta('de', { cookie_count: 3, expires: 1, expired: true });
ok(!/[Ee]xpired/.test(deGone), 'de: aucun mot anglais pour l expiration', JSON.stringify(deGone));

const ruGone = renderMeta('ru', { cookie_count: 3, expires: 1, expired: true });
ok(!/expired/i.test(ruGone), 'ru: aucun mot anglais pour l expiration', JSON.stringify(ruGone));

// ---- and the numbers must be RIGHT, not just translated -------------------
console.log('\n--- le compte a rebours est exact ---');
const soon = Date.now() / 1000 + 86400 * 5;
const in5 = renderMeta('en', { cookie_count: 1, expires: soon, expired: false });
ok(/~5d/.test(in5), 'une session a 5 jours affiche ~5d', JSON.stringify(in5));

// A boundary EXACT value is not a usable assertion here: the test computes its
// timestamp, then the product calls Date.now() again, and the few milliseconds
// between can push a 3h00m00.00 session under the hour floor - it printed "~2h"
// and would fail intermittently. Assert values with margin, and assert the
// DIRECTION (never overstate) separately, which is stable.
const in3h = renderMeta('en', { cookie_count: 1, expires: Date.now() / 1000 + 3600 * 3.2, expired: false });
ok(/~3h/.test(in3h), 'une session a 3h12 affiche ~3h', JSON.stringify(in3h));

// An ALREADY expired session must never be offered a countdown. This is the
// inverse bug: `fmtExpiry` clamps everything under an hour to '<1h', so a
// session that died a day ago used to read "1 cookies · <1h" - a promise of an
// hour for a cookie that expired yesterday.
const longDead = renderMeta('en', { cookie_count: 1, expires: Date.now() / 1000 - 86400, expired: true });
ok(!/<1h/.test(longDead) && /expired/i.test(longDead),
   'une session morte depuis un jour ne propose pas <1h', JSON.stringify(longDead));


// ---- and the popup must actually FORWARD the lifetime ---------------------
// This closes the coverage hole the proof-red found: nothing drove the
// `chrome.cookies` -> `expires_hint` mapping, so deleting it left every suite
// green while the countdown stayed permanently dead.
console.log('\n--- la popup transmet la duree de vie du cookie ---');
function forwardExpiry() {
  // Slice the whole statement up to the semicolon that ends it. Slicing to the
  // first "}))" also matched the arrow's own closer and produced a dangling
  // brace - the harness reported a SyntaxError where it should have reported a
  // product result (skill point 24: read WHY a red run is red).
  const i = SRC.indexOf('cookies = cookies.map(');
  if (i < 0) return 'null';
  const end = SRC.indexOf(';', i);
  if (end < 0) return 'null';
  const stmt = SRC.slice(i, end);
  // "cookies = cookies.map(<arrow>)"  ->  "var fwd = <arrow>"
  return 'var fwd = ' + stmt.slice('cookies = cookies.map('.length, stmt.lastIndexOf(')')) + ';';
}

try {
  const sb = { console };
  vm.createContext(sb);
  vm.runInContext(forwardExpiry(), sb);
  const withExp = sb.fwd({ name: 'sid', value: 'v', expirationDate: 1893456000 });
  ok(withExp && withExp.expires_hint === 1893456000,
     'expirationDate devient expires_hint', JSON.stringify(withExp));
  const sessionCookie = sb.fwd({ name: 'sid', value: 'v' });
  ok(sessionCookie && sessionCookie.expires_hint === undefined,
     'un cookie de session ne recoit pas de date factice',
     JSON.stringify(sessionCookie));
} catch (err) {
  ok(false, 'la transformation des cookies est extractible', String(err).slice(0, 120));
}


// A session that has NOT yet expired but has under an hour left must say minutes,
// not "<1h": the old clamp claimed "less than an hour" for a cookie with 40
// minutes of life, which is true and useless.
const mins = renderMeta('en', { cookie_count: 1, expires: Date.now() / 1000 + 40 * 60, expired: false });
ok(/\d+m/.test(mins) && !/<1h/.test(mins),
   'une session avec 40 minutes affiche un compte en minutes', JSON.stringify(mins));


// 3h35 left: truncating says "~3h", rounding says "~4h". This is the only case
// that distinguishes the two, so without it the suite cannot see whether the
// countdown overstates the time remaining - which is the direction that
// matters, because a user deciding whether to re-sync would trust the bigger
// number.
const between = renderMeta('en', { cookie_count: 1, expires: Date.now() / 1000 + 3600 * 3.6, expired: false });
ok(/~3h/.test(between), '3h35 restantes affichent ~3h, pas ~4h', JSON.stringify(between));

// 1.4 days left: ceil says "~2d", floor says "~1d". Days round UP because
// "~1d" for a day and a third reads as if it dies sooner than it does.
const days = renderMeta('en', { cookie_count: 1, expires: Date.now() / 1000 + 86400 * 1.4, expired: false });
ok(/~2d/.test(days), '1 jour et 10 heures affichent ~2d', JSON.stringify(days));

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
