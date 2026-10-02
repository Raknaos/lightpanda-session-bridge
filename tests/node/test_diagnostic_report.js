// Runs the REAL report builder from extension/popup.js against a real URL parser.
//
// This test extracts the array literal copyDiagnostic actually joins, rather than
// retyping it: the previous version rebuilt the report itself, so it stayed green
// with the leaking `currentTab.url` line back in the source.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(
  path.join(__dirname, '..', '..', 'extension', 'popup.js'), 'utf8');

function grabFunction(name) {
  const start = SRC.indexOf('function ' + name + '(');
  if (start < 0) throw new Error(name + ' absent du source');
  let depth = 0, began = false;
  for (let i = SRC.indexOf('{', start); i < SRC.length; i++) {
    if (SRC[i] === '{') { depth++; began = true; }
    else if (SRC[i] === '}') { depth--; if (began && depth === 0) return SRC.slice(start, i + 1); }
  }
  throw new Error('accolades non equilibrees pour ' + name);
}

// The array literal inside copyDiagnostic, verbatim from the source.
const ARRAY_START = SRC.indexOf('const report = [');
if (ARRAY_START < 0) throw new Error('const report = [ absent');
let depth = 0, began = false, end = -1;
for (let i = SRC.indexOf('[', ARRAY_START); i < SRC.length; i++) {
  if (SRC[i] === '[') { depth++; began = true; }
  else if (SRC[i] === ']') { depth--; if (began && depth === 0) { end = i + 1; break; } }
}
const ARRAY_SRC = SRC.slice(ARRAY_START, end);

// Turn it into a real function: (data, currentTab, currentLanguage) => joined string
const body = ARRAY_SRC
  .replace('const report = [', '')
  .replace(/\]\s*$/, '')
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith('//'))
  .join('\n');

const HELPER_SRC = grabFunction('reportableOrigin');
const makeReport = vm.runInNewContext(`(function (data, currentTab, currentLanguage) {
  ${HELPER_SRC}
  return [${body}].join('\\n');
})`, {
  URL,
  // the real array reads the version out of the live DOM
  document: { getElementById: () => ({ textContent: 'v0.0.0' }) },
});

// A bare vm context has no URL global, so the helper's catch would
// return 'unknown' for everything and the test would measure the
// harness instead of the code. URL is therefore passed in.

const SECRET = 'SUPERSECRETVALUE123';
const data = { text: 'relay ok' };

const cases = [
  [{ url: 'https://x.com/home' }, 'https://x.com', 'url simple'],
  [{ url: 'https://app.io/oauth/callback?access_token=' + SECRET }, 'https://app.io', 'token en query'],
  [{ url: 'https://site.fr/p/#access_token=' + SECRET }, 'https://site.fr', 'token en fragment'],
  [{ url: 'https://bank.com/pay?session=' + SECRET + '&x=1' }, 'https://bank.com', 'session id'],
  [{ url: 'https://u:p@host.tld/a/b?q=1#frag' }, 'https://host.tld', 'userinfo + chemin'],
  [{ url: 'about:blank' }, 'null', 'page non http'],
  [{ url: '' }, 'unknown', 'url vide'],
  [null, 'unknown', 'tab absent'],
];

let failures = 0;
for (const [tab, expected, label] of cases) {
  let report;
  try {
    report = makeReport(data, tab, 'fr');
  } catch (e) {
    console.log('FAIL  ' + label + ' -> le rapport leve : ' + e.message);
    failures++;
    continue;
  }
  const leaked = report.includes(SECRET);
  const hasOrigin = report.includes(expected);
  const hasQuery = /[?#]/.test(report);
  const ok = !leaked && hasOrigin && !hasQuery;
  if (!ok) failures++;
  console.log(
    (ok ? 'ok  ' : 'FAIL') + '  ' + label.padEnd(20) +
    (leaked ? ' *** VALEUR FUITE *** ' : '') +
    (hasOrigin ? '' : ' origin absent -> ' + JSON.stringify(report) + ' ') +
    (hasQuery ? ' query/fragment present' : ''));
}

console.log(failures === 0
  ? '\nOK - le rapport ne contient ni query, ni fragment, ni valeur'
  : '\n' + failures + ' ECHEC(S)');
process.exit(failures === 0 ? 0 : 1);