const RELAY = "http://127.0.0.1:8765";
const originEl = document.querySelector('#origin');
const confirmEl = document.querySelector('#confirm');
const transferEl = document.querySelector('#transfer');
const statusEl = document.querySelector('#status');
const relayBadge = document.querySelector('#relay-badge');
const relayText = document.querySelector('#relay-text');
const glassRange = document.querySelector('#glass-range');
const glassVal = document.querySelector('#glass-val');

let currentTab = null;

// Slider d'opacité dynamique Quota Glass
if (glassRange && glassVal) {
  const saved = localStorage.getItem('quota-glass-alpha') || "0.85";
  glassRange.value = saved;
  glassVal.textContent = `${Math.round(parseFloat(saved) * 100)}%`;
  document.documentElement.style.setProperty('--glass-alpha', saved);

  glassRange.addEventListener('input', (e) => {
    const val = e.target.value;
    glassVal.textContent = `${Math.round(parseFloat(val) * 100)}%`;
    document.documentElement.style.setProperty('--glass-alpha', val);
    localStorage.setItem('quota-glass-alpha', val);
  });
}

function setStatus(text, type = 'info') {
  statusEl.textContent = text;
  if (type === 'error') {
    statusEl.style.color = 'var(--danger)';
  } else if (type === 'success') {
    statusEl.style.color = '#0d7a36';
  } else {
    statusEl.style.color = 'var(--soft)';
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
      relayBadge.className = 'badge online';
      relayText.textContent = 'Relais en ligne';
      return true;
    }
  } catch (_) {}
  relayBadge.className = 'badge offline';
  relayText.textContent = 'Relais hors-ligne';
  return false;
}

async function init() {
  const relayOk = await checkRelay();

  // Identifier le dernier onglet actif sur une page web réelle
  const tabs = await chrome.tabs.query({ currentWindow: true });
  const webTabs = tabs.filter(t => t.url && eligible(t.url));
  const activeTab = tabs.find(t => t.active);

  if (activeTab && eligible(activeTab.url)) {
    currentTab = activeTab;
  } else if (webTabs.length > 0) {
    currentTab = webTabs[0];
  } else {
    currentTab = activeTab;
  }

  const url = currentTab?.url || '';
  let origin = '';
  try {
    origin = new URL(url).origin;
  } catch (_) {}

  originEl.textContent = origin || 'Page non compatible';
  originEl.dataset.origin = origin;

  if (!eligible(url)) {
    setStatus('Ouvrez un site HTTPS public (ex: Gmail, A6API).', 'error');
  } else if (!relayOk) {
    setStatus('Le relais local (port 8765) n’est pas démarré.', 'error');
  }
}

confirmEl.addEventListener('change', () => {
  const isEligible = eligible(currentTab?.url || '');
  transferEl.disabled = !confirmEl.checked || !isEligible;
});

transferEl.addEventListener('click', async () => {
  transferEl.disabled = true;
  setStatus('Transfert et vérification en cours…');

  try {
    const url = currentTab?.url || '';
    const origin = new URL(url).origin;

    // 1. Récupération des cookies
    const cookies = await chrome.cookies.getAll({ url });
    if (!cookies || cookies.length === 0) {
      throw new Error('Aucun cookie trouvé pour cette page.');
    }

    // 2. Extraction localStorage
    let storage = null;
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: currentTab.id },
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

    // 3. Envoi au Relais
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

    setStatus(`✓ Session synchronisée (${result.cookie_count} cookies injectés).`, 'success');
  } catch (error) {
    setStatus(error.message || 'Échec du transfert.', 'error');
  } finally {
    transferEl.disabled = !confirmEl.checked;
  }
});

init();
