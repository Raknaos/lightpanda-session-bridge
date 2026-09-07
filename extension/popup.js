const RELAY = "http://127.0.0.1:8765";
const originEl = document.querySelector('#origin');
const confirmEl = document.querySelector('#confirm');
const transferEl = document.querySelector('#transfer');
const statusEl = document.querySelector('#status');
const relayBadge = document.querySelector('#relay-badge');
let currentTab = null;

function setStatus(text, type = 'info') {
  statusEl.textContent = text;
  if (type === 'error') {
    statusEl.style.color = 'var(--red)';
  } else if (type === 'success') {
    statusEl.style.color = 'var(--green-hover)';
  } else {
    statusEl.style.color = 'var(--text-muted)';
  }
}

function eligible(url) {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && !['localhost', '127.0.0.1', '::1'].includes(u.hostname);
  } catch (_) {
    return false;
  }
}

async function checkRelay() {
  try {
    const res = await fetch(`${RELAY}/health`, { method: 'GET', cache: 'no-store' });
    if (res.ok) {
      relayBadge.textContent = 'Relais en ligne';
      relayBadge.className = 'badge online';
      return true;
    }
  } catch (_) {}
  relayBadge.textContent = 'Relais hors-ligne';
  relayBadge.className = 'badge offline';
  return false;
}

async function init() {
  const relayOk = await checkRelay();
  
  chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
    currentTab = tabs[0];
    const url = currentTab?.url || '';
    let origin = '';
    try {
      origin = new URL(url).origin;
    } catch (_) {}

    originEl.textContent = origin || 'Page non compatible';
    originEl.dataset.origin = origin;

    if (!eligible(url)) {
      setStatus('Un site HTTPS public est requis.', 'error');
    } else if (!relayOk) {
      setStatus('Le relais local (port 8765) n’est pas démarré.', 'error');
    }
  });
}

confirmEl.addEventListener('change', () => {
  const isEligible = eligible(currentTab?.url || '');
  transferEl.disabled = !confirmEl.checked || !isEligible;
});

transferEl.addEventListener('click', async () => {
  transferEl.disabled = true;
  setStatus('Transfert et vérification en cours…');

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    const url = tab?.url || '';
    const origin = new URL(url).origin;

    if (origin !== originEl.dataset.origin) {
      throw new Error('La page a changé. Veuillez réouvrir le popup.');
    }

    // Récupération des cookies
    const cookies = await chrome.cookies.getAll({ url });
    if (!cookies || cookies.length === 0) {
      throw new Error('Aucun cookie trouvé pour cette origine.');
    }

    // Extraction localStorage optionnelle
    let storage = null;
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const data = {};
          for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            data[k] = localStorage.getItem(k);
          }
          return data;
        }
      });
      if (results && results[0]?.result) {
        storage = results[0].result;
      }
    } catch (_) {}

    const payload = { origin, cookies, storage };
    const response = await fetch(`${RELAY}/v1/session/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || 'Transfert refusé par le relais.');
    }

    setStatus(`✓ Session synchronisée (${result.cookie_count} cookies).`, 'success');
  } catch (error) {
    setStatus(error.message || 'Échec du transfert.', 'error');
  } finally {
    transferEl.disabled = !confirmEl.checked;
  }
});

init();
