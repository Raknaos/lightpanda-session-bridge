// The relay badge must be RE-EVALUATED, not sampled once.
//
// It used to be checked exactly once, in init(), while the 30s interval refreshed
// only the session counter. So a relay that died after the popup opened kept
// showing "Relay Online" for as long as the panel stayed open - and the third
// state added in v0.6.1 (relay alive, CDP dead) was unreachable except in the
// few hundred milliseconds after opening.
//
// Extracts the REAL setInterval callback and the REAL visibilitychange listener
// out of popup.js and drives them in Node, because a test that retypes the
// scheduling stays green after the fix is reverted.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const POPUP = path.join(__dirname, '..', '..', 'extension', 'popup.js');
const SRC = fs.readFileSync(POPUP, 'utf8');

// Locate a top-level statement by its exact opening text.
function sliceFrom(marker, stopAt) {
  const i = SRC.indexOf(marker);
  if (i < 0) throw new Error(`${marker} absent de popup.js`);
  const j = SRC.indexOf(stopAt, i);
  if (j < 0) throw new Error(`fin de ${marker} introuvable`);
  return SRC.slice(i, j + stopAt.length);
}

function build({ relayOk = true } = {}) {
  const calls = { health: 0, sessions: 0, listeners: {} };
  const timers = [];
  const doc = {
    visibilityState: 'visible',
    addEventListener: (type, fn) => { calls.listeners[type] = fn; },
  };
  const sb = {
    document: doc,
    console,
    Date: class extends Date { static now() { return Date.now(); } },
    setInterval: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    setTimeout: () => 1,
    clearTimeout: () => {},
    refreshSessions: () => { calls.sessions++; },
    checkRelay: async () => { calls.health++; return relayOk; },
    RELAY_MIN_CHECK_GAP_MS: Number(/RELAY_MIN_CHECK_GAP_MS = (\d+)/.exec(SRC)[1]),
    bridgeToken: 'x',
  };
  sb.Date.now = () => sb._now;
  sb._now = 100000;
  vm.createContext(sb);
  vm.runInContext(sliceFrom('setInterval(() => {', '}, 30000);'), sb);
  // `let lastRelayCheck` is declared immediately ABOVE the listener and is read
  // inside it; extracting only the listener raised "lastRelayCheck is not
  // defined" - a harness gap that looks like a product bug.
  vm.runInContext(sliceFrom('let lastRelayCheck = 0;', 'lastRelayCheck = 0;'), sb);
  const vis = sliceFrom("document.addEventListener('visibilitychange'", '});');
  vm.runInContext(vis, sb);
  return { sb, calls, timers, doc };
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test('le badge est reevalue par le tick periodique', async () => {
  const { calls, timers } = build();
  if (timers.length !== 1) throw new Error(`${timers.length} setInterval enregistre(s)`);
  if (timers[0].ms !== 30000) throw new Error(`cadence ${timers[0].ms}ms, pas 30s`);
  if (calls.health !== 0) throw new Error('un /health a ete envoye avant le tick');
  timers[0].fn();
  await new Promise(r => setImmediate(r));
  if (calls.health < 1) {
    throw new Error('le tick ne reevalue PAS le relais: le badge reste fige');
  }
  if (calls.sessions < 1) throw new Error('le tick ne rafraichit pas les sessions');
});

test('un popup masque ne depense rien sur le relais', async () => {
  const { calls, timers, doc } = build();
  doc.visibilityState = 'hidden';
  timers[0].fn();
  await new Promise(r => setImmediate(r));
  if (calls.health !== 0 || calls.sessions !== 0) {
    throw new Error(`popup masque: ${calls.health} /health et ${calls.sessions} sessions`);
  }
});

test('sans jeton appaire, aucun appel', async () => {
  const { sb, calls, timers } = build();
  sb.bridgeToken = '';
  timers[0].fn();
  await new Promise(r => setImmediate(r));
  if (calls.health !== 0) throw new Error('appel sans jeton: /health lance quand meme');
});

test('revenir au premier plan reevalue immediatement', async () => {
  const { sb, calls, doc } = build();
  const onVis = calls.listeners.visibilitychange;
  if (!onVis) throw new Error('aucun listener visibilitychange enregistre');
  // The popup was opened a while ago: init() checked, enough time has passed.
  sb._now += 60000;
  doc.visibilityState = 'visible';
  await onVis();
  if (calls.health < 1) {
    throw new Error('revenir au premier plan ne reevalue pas le relais');
  }
});

test('les rafales de visibilitychange sont coalescees', async () => {
  const { sb, calls, doc } = build();
  const onVis = calls.listeners.visibilitychange;
  sb._now += 60000;
  for (let i = 0; i < 20; i++) {
    doc.visibilityState = 'hidden';
    await onVis();
    doc.visibilityState = 'visible';
    await onVis();
  }
  if (calls.health > 1) {
    throw new Error(`rafale: ${calls.health} /health, le coalescement ne marche pas`);
  }
});

test('passer en arriere-plan ne lance rien', async () => {
  const { calls, doc } = build();
  const onVis = calls.listeners.visibilitychange;
  doc.visibilityState = 'hidden';
  await onVis();
  if (calls.health !== 0) throw new Error(`arriere-plan: ${calls.health} /health`);
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
