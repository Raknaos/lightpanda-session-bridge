const RELAY = "http://127.0.0.1:8765";
const originEl = document.querySelector('#origin');
const confirmEl = document.querySelector('#confirm');
const transferEl = document.querySelector('#transfer');
const statusEl = document.querySelector('#status');
let tab;

function setStatus(text, error = false) {
  statusEl.textContent = text;
  statusEl.style.color = error ? '#b00020' : '#176b35';
}

function eligible(url) {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && !['localhost', '127.0.0.1', '::1'].includes(u.hostname);
  } catch (_) { return false; }
}

chrome.tabs.query({active: true, currentWindow: true}, async (tabs) => {
  tab = tabs[0];
  const url = tab?.url || '';
  let origin = '';
  try { origin = new URL(url).origin; } catch (_) {}
  originEl.textContent = origin || 'Page non compatible';
  originEl.dataset.origin = origin;
  if (!eligible(url)) setStatus('HTTPS public requis.', true);
});

confirmEl.addEventListener('change', () => {
  transferEl.disabled = !confirmEl.checked || !eligible(tab?.url || '');
});

transferEl.addEventListener('click', async () => {
  transferEl.disabled = true;
  try {
    const current = await chrome.tabs.query({active: true, currentWindow: true});
    const url = current[0]?.url || '';
    const origin = new URL(url).origin;
    if (origin !== originEl.dataset.origin) throw new Error('La page a changé. Ferme et rouvre le popup.');
    const cookies = await chrome.cookies.getAll({url});
    const response = await fetch(`${RELAY}/v1/session/import`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({origin, cookies})
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Relais refusé');
    setStatus(`Session transférée: ${result.cookie_count} cookie(s).`);
  } catch (error) {
    setStatus(error.message || 'Échec du transfert.', true);
  } finally {
    transferEl.disabled = false;
  }
});
