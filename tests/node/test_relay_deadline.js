// A relay that accepts the connection and then says nothing must not be able to
// leave the popup waiting forever.
//
// This extracts the REAL `relayFetch` and the REAL `relayErrorText` out of
// popup.js and runs them in Node against a fetch that never settles, because a
// test that retypes the helper would stay green after the fix was reverted
// (skill pitfall: "a test that retypes the code under test").

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const POPUP = path.join(__dirname, '..', '..', 'extension', 'popup.js');
const SRC = fs.readFileSync(POPUP, 'utf8');

// Locate the DECLARATION of a top-level symbol. A bare indexOf(name) finds the
// first MENTION: for RelayTimeoutError that is inside RELAY_TIMEOUT_MS's
// comment block and inside `new RelayTimeoutError()`, long before the class,
// so the extracted text started mid-expression and every test died with
// "Unexpected token 'extends'". Anchor on the declaration form instead.
function findDecl(name) {
  const forms = [
    new RegExp(`^class ${name}\\b`, 'm'),
    new RegExp(`^const ${name} =`, 'm'),
    new RegExp(`^async function ${name}\\b`, 'm'),
    new RegExp(`^function ${name}\\b`, 'm'),
  ];
  for (const re of forms) {
    const m = re.exec(SRC);
    if (m) return m.index;
  }
  throw new Error(`declaration of ${name} not found in popup.js`);
}

function extract(name) {
  const start = findDecl(name);
  const decl = SRC.slice(SRC.lastIndexOf('\n', start) + 1, start);
  // A brace-less declaration (`const X = 45000;`) has no '{' of its own:
  // searching for the next one walks into whatever FOLLOWS and silently
  // returns the next symbol's body too - which then redeclares it and fails
  // every test with "Identifier already declared". Stop at ';' when the
  // statement ends before any brace.
  const semi = SRC.indexOf(';', start);
  const brace = decl.includes('class')
    ? SRC.indexOf('{', SRC.indexOf('extends', start))
    : SRC.indexOf('{', start);
  const end = (!decl.includes('class') && semi !== -1 && (brace === -1 || semi < brace))
    ? semi + 1
    : null;
  if (end !== null) {
    const chunk = SRC.slice(start, end);
    assertSingleDeclaration(chunk, name);
    return chunk;
  }
  let i = brace;
  let depth = 0;
  for (; i < SRC.length; i++) {
    if (SRC[i] === '{') depth++;
    else if (SRC[i] === '}') { depth--; if (depth === 0) { 
      const chunk = SRC.slice(start, i + 1);
      assertSingleDeclaration(chunk, name);
      return chunk;
    } }
  }
  throw new Error(`accolades non equilibrees pour ${name}`);
}

// Self-check: an extraction that swallowed the NEXT symbol looks like a
// product bug ("Identifier already declared"). Fail loudly here instead.
function assertSingleDeclaration(chunk, name) {
  const others = [...chunk.matchAll(
    /^(?:const|let|var|class|async function|function)\s+([A-Za-z_$][\w$]*)/gm)]
    .map(m => m[1])
    .filter(n => n !== name);
  if (others.length) {
    throw new Error(`extraction de ${name} a englobe ${others.join(', ')} - harnais`);
  }
}

function build(fetchImpl, clock) {
  const RELAY = 'http://127.0.0.1:8765';
  // Minimal but REAL setTimeout/clearTimeout over a controllable clock, so the
  // test advances the deadline instead of waiting 45 real seconds.
  const timers = [];
  let now = 0;
  const sandbox = {
    RELAY,
    I18N: { en: {}, fr: {} },
    currentLanguage: 'en',
    fetch: fetchImpl,
    console,
    setTimeout: (fn, ms) => { timers.push({ at: now + ms, fn }); return timers.length; },
    clearTimeout: () => {},
    AbortController: class {
      constructor() {
        this.signal = { aborted: false };
        this._listeners = [];
        const sig = this.signal;
        sig.addEventListener = (type, fn) => { if (type === 'abort') sig._fns.push(fn); };
        sig._fns = [];
      }
      abort() {
        // The REAL AbortController does NOT throw: it flips signal.aborted and
        // notifies listeners, which reject the in-flight fetch. A stub that
        // throws here made the deadline test fail on a harness fiction.
        this.signal.aborted = true;
        this.signal._fns.forEach(fn => fn());
      }
    },
  };
  sandbox.t = (key, ...args) => {
    const v = sandbox.I18N[sandbox.currentLanguage][key];
    if (v === undefined) return `MISSING:${key}`;
    return args.length ? v.replace(/\{(\d+)\}/g, (_, i) => args[i]) : v;
  };
  vm.createContext(sandbox);
  for (const name of ['RELAY_TIMEOUT_MS', 'RELAY_ERROR_KEYS', 'RelayTimeoutError',
                      'relayErrorText', 'relayFetch']) {
    vm.runInContext(extract(name), sandbox);
  }
  // Declared once, in order. No second pass: re-running `class RelayTimeoutError`
  // in the same context raises "Identifier already declared", which reads as a
  // product fault and is purely a harness bug.
  vm.runInContext(`globalThis.RELAY_TIMEOUT_MS = ${/RELAY_TIMEOUT_MS = (\d+)/.exec(SRC)[1]};
                   globalThis.relayFetch = relayFetch;
                   globalThis.relayErrorText = relayErrorText;
                   globalThis.RelayTimeoutError = RelayTimeoutError;`, sandbox);
  sandbox.I18N.en = {
    errRefused: 'Transfer refused by local relay.',
    errRelayTimeout: 'Relay did not answer.',
    errRelayUnreachable: 'Could not reach the relay.',
    errOriginRefused: 'The relay refused this site origin.',
    errUnauthorized: 'The relay rejected this extension.',
    errRouteMissing: 'The relay does not know this request.',
    errUpdateRefused: 'The relay refused the update.',
    unknownRelayError: 'Relay error: {0}',
  };
  // Controllable clock: the suite must not sleep 45 real seconds to prove the
  // deadline fires.
  sandbox.advance = (ms) => { now += ms; };
  sandbox.fire = () => { timers.splice(0).forEach(t => t.fn()); };
  return sandbox;
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test('un relais muet termine en RelayTimeoutError, pas en attente infinie', async () => {
  let seenSignal = null;
  const sb = build((url, opts) => {
    seenSignal = opts.signal;
    // Faithful to a real fetch: an aborted in-flight request REJECTS with
    // AbortError. A stub that just never settles ignores the signal entirely,
    // which is a harness fiction - the deadline could never be observed.
    return new Promise((_, reject) => {
      if (opts.signal._fns) {
        opts.signal._fns.push(() => {
          const err = new Error('The operation was aborted.');
          err.name = 'AbortError';
          reject(err);
        });
      }
    });
  });
  const pending = sb.relayFetch('/health', { method: 'GET' });
  let settled = 'pending';
  pending.then(() => { settled = 'resolved'; },
               (e) => { settled = e.name; });
  await new Promise(r => setImmediate(r));
  if (settled !== 'pending') throw new Error(`settled too early: ${settled}`);
  if (!seenSignal) throw new Error('relayFetch sent no signal: the deadline cannot fire');
  if (!Array.isArray(seenSignal._fns)) {
    // Without a cancellable signal the deadline is decorative: nothing can
    // ever reject the pending request. Say so by NAME, and do not leave the
    // await hanging (a hung test prints nothing and scores as "no failure").
    throw new Error('relayFetch used a signal the runtime cannot cancel');
  }

  // Advance past RELAY_TIMEOUT_MS and fire the timer.
  sb.advance(sb.RELAY_TIMEOUT_MS + 1);
  sb.fire();
  await pending.then(() => {}, () => {});
  if (settled !== 'RelayTimeoutError') {
    throw new Error(`expected RelayTimeoutError, got ${settled}`);
  }
});

test('le delai du popup laisse le relais repondre en premier', async () => {
  const src = Number(/RELAY_TIMEOUT_MS = (\d+)/.exec(SRC)[1]);
  // The relay cuts a body read at 10s and the class deadline is 15s. A client
  // that aborts BEFORE those gets a bare "Failed to fetch" instead of the
  // relay's own (translated) error.
  if (src <= 15000) {
    throw new Error(`RELAY_TIMEOUT_MS=${src}ms aborts before the relay's 15s deadline`);
  }
});

test('les codes du relais deviennent du texte traduit', async () => {
  const sb = build(() => Promise.resolve({}));
  const cases = [
    ['origin refused', 'The relay refused this site origin.'],
    ['unauthorized', 'The relay rejected this extension.'],
    ['not found', 'The relay does not know this request.'],
    ['update refused', 'The relay refused the update.'],
  ];
  for (const [code, want] of cases) {
    const got = sb.relayErrorText(code);
    if (got !== want) throw new Error(`${code}: got ${JSON.stringify(got)}`);
    if (/refused|unauthorized|not found/i.test(got) && got === code) {
      throw new Error(`${code} rendered verbatim (English in a translated popup)`);
    }
  }
});

test('un code inconnu reste visible mais encadre par une traduction', async () => {
  const sb = build(() => Promise.resolve({}));
  const got = sb.relayErrorText('WinError 10053 blah');
  if (!got.startsWith('Relay error:')) {
    throw new Error(`unknown code not framed: ${JSON.stringify(got)}`);
  }
  if (!got.includes('WinError 10053')) {
    throw new Error(`unknown code silently dropped: ${JSON.stringify(got)}`);
  }
});

test('aucun code du relais ne peut etre rendu verbatim', async () => {
  // Read the codes straight out of relay/server.py so a NEW relay error is
  // caught here instead of shipping into a French popup.
  const server = fs.readFileSync(
    path.join(__dirname, '..', '..', 'relay', 'server.py'), 'utf8');
  const codes = new Set([...server.matchAll(/"error":\s*"([a-z ]+)"/g)].map(m => m[1]));
  const fallbacks = new Set([...server.matchAll(/"error":\s*str\(err\)\s*or\s*"([a-z ]+)"/g)]
    .map(m => m[1]));
  const sb = build(() => Promise.resolve({}));
  for (const code of [...codes, ...fallbacks]) {
    const got = sb.relayErrorText(code);
    if (got.startsWith('Relay error:')) {
      throw new Error(`relay can emit "${code}" but it has no i18n key`);
    }
  }
});

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) {
    try {
      await fn();
      console.log(`  ok   ${name}`);
    } catch (err) {
      failed++;
      console.log(`  FAIL ${name}\n         ${err.message}`);
    }
  }
  console.log(failed ? `\n${failed} failed` : `\n${tests.length} passed`);
  process.exit(failed ? 1 : 0);
})();