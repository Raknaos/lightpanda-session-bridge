const RELAY = "http://127.0.0.1:8765";

// Multilingual Dictionary (Default English + French, Spanish, German, Chinese, Japanese, Italian, Portuguese, Arabic, Russian)
const I18N = {
  en: {
    code: "EN",
    relayChecking: "Checking…",
    relayOnline: "Relay Online",
    relayOffline: "Relay Offline",
    targetOrigin: "Target Origin",
    readingTab: "Reading tab…",
    incompatiblePage: "Incompatible page",
    desc: "Seamlessly transfers cookies and local session state to your isolated background Lightpanda runtime.",
    consent: "I authorize the explicit transfer of this tab's authenticated session to Lightpanda.",
    btnSync: "Sync to Lightpanda",
    syncing: "Transferring & verifying session…",
    success: (count) => `✓ Session synchronized (${count} cookies injected).`,
    errNeedHttps: "Please open a public HTTPS website (e.g. Gmail, A6API).",
    errNoRelay: "Local relay (port 8765) is not running.",
    errNoCookies: "No cookies found for this page.",
    errRefused: "Transfer refused by local relay.",
    footerTag: "Isolated Profile · Localhost CDP",
    sessionsLabel: "Active sessions in Lightpanda",
    sessionsEmpty: "No sessions synced into Lightpanda.",
    sessionsClear: (n) => `Clear all (${n})`,
    sessionRemove: "Remove this session"
  },
  fr: {
    code: "FR",
    relayChecking: "Vérification…",
    relayOnline: "Relais en ligne",
    relayOffline: "Relais hors-ligne",
    targetOrigin: "Origine Cible",
    readingTab: "Lecture de la page…",
    incompatiblePage: "Page non compatible",
    desc: "Synchronisation directe et sécurisée des cookies de session et du stockage local vers le moteur autonome Lightpanda.",
    consent: "J'autorise le transfert explicite de la session de cet onglet vers Lightpanda.",
    btnSync: "Synchroniser vers Lightpanda",
    syncing: "Transfert et vérification en cours…",
    success: (count) => `✓ Session synchronisée (${count} cookies injectés).`,
    errNeedHttps: "Ouvrez un site HTTPS public (ex: Gmail, A6API).",
    errNoRelay: "Le relais local (port 8765) n’est pas démarré.",
    errNoCookies: "Aucun cookie trouvé pour cette page.",
    errRefused: "Transfert refusé par le relais local.",
    footerTag: "Profil isolé · Localhost CDP",
    sessionsLabel: "Sessions actives dans Lightpanda",
    sessionsEmpty: "Aucune session synchronisée dans Lightpanda.",
    sessionsClear: (n) => `Tout retirer (${n})`,
    sessionRemove: "Retirer cette session"
  },
  es: {
    code: "ES",
    relayChecking: "Comprobando…",
    relayOnline: "Relé en línea",
    relayOffline: "Relé desconectado",
    targetOrigin: "Origen de destino",
    readingTab: "Leyendo pestaña…",
    incompatiblePage: "Página no compatible",
    desc: "Transfiere de forma segura las cookies y el estado de la sesión al entorno aislado de Lightpanda.",
    consent: "Autorizo la transferencia explícita de la sesión autenticada a Lightpanda.",
    btnSync: "Sincronizar con Lightpanda",
    syncing: "Transfiriendo y verificando sesión…",
    success: (count) => `✓ Sesión sincronizada (${count} cookies inyectadas).`,
    errNeedHttps: "Abre un sitio web HTTPS público (ej. Gmail, A6API).",
    errNoRelay: "El relé local (puerto 8765) no está en ejecución.",
    errNoCookies: "No se encontraron cookies para esta página.",
    errRefused: "Transferencia rechazada por el relé local.",
    footerTag: "Perfil aislado · Localhost CDP",
    sessionsLabel: "Sesiones activas en Lightpanda",
    sessionsEmpty: "No hay sesiones sincronizadas en Lightpanda.",
    sessionsClear: (n) => `Borrar todas (${n})`,
    sessionRemove: "Eliminar esta sesión"
  },
  de: {
    code: "DE",
    relayChecking: "Prüfe…",
    relayOnline: "Relais online",
    relayOffline: "Relais offline",
    targetOrigin: "Zielursprung",
    readingTab: "Tab wird gelesen…",
    incompatiblePage: "Nicht kompatible Seite",
    desc: "Überträgt Cookies und Sitzungsstatus nahtlos an die isolierte Lightpanda-Runtime.",
    consent: "Ich autorisiere die Übertragung der authentifizierten Sitzung an Lightpanda.",
    btnSync: "Mit Lightpanda synchronisieren",
    syncing: "Sitzung wird übertragen & geprüft…",
    success: (count) => `✓ Sitzung synchronisiert (${count} Cookies injiziert).`,
    errNeedHttps: "Bitte öffnen Sie eine öffentliche HTTPS-Website.",
    errNoRelay: "Lokales Relais (Port 8765) läuft nicht.",
    errNoCookies: "Keine Cookies für diese Seite gefunden.",
    errRefused: "Übertragung vom lokalen Relais abgelehnt.",
    footerTag: "Isoliertes Profil · Localhost CDP",
    sessionsLabel: "Aktive Sitzungen in Lightpanda",
    sessionsEmpty: "Keine Sitzungen in Lightpanda synchronisiert.",
    sessionsClear: (n) => `Alle löschen (${n})`,
    sessionRemove: "Diese Sitzung entfernen"
  },
  zh: {
    code: "ZH",
    relayChecking: "检查中…",
    relayOnline: "中继在线",
    relayOffline: "中继离线",
    targetOrigin: "目标源",
    readingTab: "读取标签页…",
    incompatiblePage: "页面不兼容",
    desc: "将 Cookie 和会话状态无缝传输到隔离的后台 Lightpanda 运行时。",
    consent: "我授权将此标签页的认证会话显式传输至 Lightpanda。",
    btnSync: "同步至 Lightpanda",
    syncing: "正在传输并验证会话…",
    success: (count) => `✓ 会话已同步（注入 ${count} 个 Cookie）。`,
    errNeedHttps: "请打开公开的 HTTPS 网站（例如 Gmail、A6API）。",
    errNoRelay: "本地中继（端口 8765）未启动。",
    errNoCookies: "未找到此页面的 Cookie。",
    errRefused: "本地中继拒绝了传输。",
    footerTag: "隔离配置文件 · 本地 CDP",
    sessionsLabel: "Lightpanda 中的活动会话",
    sessionsEmpty: "Lightpanda 中没有已同步的会话。",
    sessionsClear: (n) => `清除全部（${n}）`,
    sessionRemove: "移除此会话"
  },
  ja: {
    code: "JA",
    relayChecking: "確認中…",
    relayOnline: "リレー オンライン",
    relayOffline: "リレー オフライン",
    targetOrigin: "ターゲット オリジン",
    readingTab: "タブを読み取り中…",
    incompatiblePage: "非対応のページ",
    desc: "Cookieとセッション状態を隔離されたLightpandaランタイムに安全に転送します。",
    consent: "このタブの認証済みセッションをLightpandaに転送することを承認します。",
    btnSync: "Lightpandaに同期",
    syncing: "セッションの転送と検証中…",
    success: (count) => `✓ セッションが同期されました（${count}個のCookieを挿入）。`,
    errNeedHttps: "公開HTTPSサイト（Gmail、A6APIなど）を開いてください。",
    errNoRelay: "ローカルリレー（ポート8765）が起動していません。",
    errNoCookies: "このページのCookieが見つかりません。",
    errRefused: "ローカルリレーによって転送が拒否されました。",
    footerTag: "分離プロファイル · Localhost CDP",
    sessionsLabel: "Lightpanda内のアクティブなセッション",
    sessionsEmpty: "Lightpandaに同期されたセッションはありません。",
    sessionsClear: (n) => `すべて削除（${n}）`,
    sessionRemove: "このセッションを削除"
  },
  it: {
    code: "IT",
    relayChecking: "Verifica…",
    relayOnline: "Relè Online",
    relayOffline: "Relè Offline",
    targetOrigin: "Origine Destinazione",
    readingTab: "Lettura scheda…",
    incompatiblePage: "Pagina non compatibile",
    desc: "Trasferisce cookie e sessione al runtime isolato di Lightpanda in background.",
    consent: "Autorizzo il trasferimento esplicito della sessione a Lightpanda.",
    btnSync: "Sincronizza con Lightpanda",
    syncing: "Trasferimento e verifica in corso…",
    success: (count) => `✓ Sessione sincronizzata (${count} cookie inseriti).`,
    errNeedHttps: "Apri un sito HTTPS pubblico (es. Gmail, A6API).",
    errNoRelay: "Il relè locale (porta 8765) non è attivo.",
    errNoCookies: "Nessun cookie trovato per questa pagina.",
    errRefused: "Trasferimento rifiutato dal relè locale.",
    footerTag: "Profilo isolato · Localhost CDP",
    sessionsLabel: "Sessioni attive in Lightpanda",
    sessionsEmpty: "Nessuna sessione sincronizzata in Lightpanda.",
    sessionsClear: (n) => `Rimuovi tutte (${n})`,
    sessionRemove: "Rimuovi questa sessione"
  },
  pt: {
    code: "PT",
    relayChecking: "Verificando…",
    relayOnline: "Relé Online",
    relayOffline: "Relé Offline",
    targetOrigin: "Origem de Destino",
    readingTab: "Lendo guia…",
    incompatiblePage: "Página incompatível",
    desc: "Transfere cookies e estado de sessão para o runtime isolado do Lightpanda.",
    consent: "Autorizo a transferência explícita da sessão autenticada para o Lightpanda.",
    btnSync: "Sincronizar para Lightpanda",
    syncing: "Transferindo e verificando sessão…",
    success: (count) => `✓ Sessão sincronizada (${count} cookies injetados).`,
    errNeedHttps: "Abra um site HTTPS público (ex: Gmail, A6API).",
    errNoRelay: "O relé local (porta 8765) não está em execução.",
    errNoCookies: "Nenhum cookie encontrado para esta página.",
    errRefused: "Transferência recusada pelo relé local.",
    footerTag: "Perfil isolado · Localhost CDP",
    sessionsLabel: "Sessões ativas no Lightpanda",
    sessionsEmpty: "Nenhuma sessão sincronizada no Lightpanda.",
    sessionsClear: (n) => `Limpar todas (${n})`,
    sessionRemove: "Remover esta sessão"
  },
  ar: {
    code: "AR",
    relayChecking: "جاري الفحص…",
    relayOnline: "المرحل متصل",
    relayOffline: "المرحل غير متصل",
    targetOrigin: "المصدر المستهدف",
    readingTab: "قراءة الصفحة…",
    incompatiblePage: "صفحة غير متوافقة",
    desc: "نقل ملفات تعريف الارتباط وحالة الجلسة بأمان إلى بيئة Lightpanda المعزولة.",
    consent: "أوافق على نقل جلسة المصادقة صراحةً إلى Lightpanda.",
    btnSync: "مزامنة إلى Lightpanda",
    syncing: "جاري النقل والتحقق…",
    success: (count) => `✓ تمت مزامنة الجلسة (تم حقن ${count} ملف تعريف).`,
    errNeedHttps: "يرجى فتح موقع HTTPS عام.",
    errNoRelay: "المرحل المحلي (المنفذ 8765) لا يعمل.",
    errNoCookies: "لم يتم العثور على ملفات تعريف الارتباط.",
    errRefused: "تم رفض النقل بواسطة المرحل المحلي.",
    footerTag: "ملف تعريف معزول · Localhost CDP",
    sessionsLabel: "الجلسات النشطة في Lightpanda",
    sessionsEmpty: "لا توجد جلسات متزامنة في Lightpanda.",
    sessionsClear: (n) => `إزالة الكل (${n})`,
    sessionRemove: "إزالة هذه الجلسة"
  },
  ru: {
    code: "RU",
    relayChecking: "Проверка…",
    relayOnline: "Реле онлайн",
    relayOffline: "Реле офлайн",
    targetOrigin: "Целевой источник",
    readingTab: "Чтение вкладки…",
    incompatiblePage: "Несовместимая страница",
    desc: "Безопасный перенос файлов cookie и сеанса в изолированную среду Lightpanda.",
    consent: "Я разрешаю явную передачу аутентифицированного сеанса в Lightpanda.",
    btnSync: "Синхронизировать с Lightpanda",
    syncing: "Перенос и проверка сеанса…",
    success: (count) => `✓ Сеанс синхронизирован (внедрено ${count} cookie).`,
    errNeedHttps: "Откройте общедоступный сайт HTTPS (например, Gmail, A6API).",
    errNoRelay: "Локальное реле (порт 8765) не запущено.",
    errNoCookies: "Файлы cookie для этой страницы не найдены.",
    errRefused: "Перенос отклонен локальным реле.",
    footerTag: "Изолированный профиль · Localhost CDP",
    sessionsLabel: "Активные сеансы в Lightpanda",
    sessionsEmpty: "Нет сеансов, синхронизированных с Lightpanda.",
    sessionsClear: (n) => `Удалить все (${n})`,
    sessionRemove: "Удалить этот сеанс"
  }
};

// UI Elements
const originEl = document.querySelector('#origin');
const confirmEl = document.querySelector('#confirm');
const transferEl = document.querySelector('#transfer');
const statusEl = document.querySelector('#status');
const relayBadge = document.querySelector('#relay-badge');
const relayText = document.querySelector('#relay-text');
const langBtn = document.querySelector('#lang-btn');
const langDropdown = document.querySelector('#lang-dropdown');
const currentLangCode = document.querySelector('#current-lang-code');

const labelTargetOrigin = document.querySelector('#label-target-origin');
const descText = document.querySelector('#desc-text');
const consentText = document.querySelector('#consent-text');
const btnText = document.querySelector('#btn-text');
const footerSecureTag = document.querySelector('#footer-secure-tag');

// Active sessions UI
const sessionsCard = document.querySelector('#sessions-card');
const sessionsToggle = document.querySelector('#sessions-toggle');
const sessionsCount = document.querySelector('#sessions-count');
const sessionsList = document.querySelector('#sessions-list');
const sessionsClear = document.querySelector('#sessions-clear');
const labelSessions = document.querySelector('#label-sessions');
const clearText = document.querySelector('#clear-text');

let currentTab = null;
let currentLanguage = localStorage.getItem('lightpanda-lang') || 'en'; // Default English
let bridgeToken = ''; // loaded before any transfer

// Shared-secret token: stored in the extension's OWN localStorage (origin
// chrome-extension://<id>, isolated from web pages, no extra permission).
// Same value as the relay's ~/.config/lightpanda-bridge/secret (see server.py).
const TOKEN_KEY = 'lpBridgeToken';

async function loadBridgeToken() {
  try {
    bridgeToken = localStorage.getItem(TOKEN_KEY) || '';
    if (!bridgeToken) {
      // Fallback: chrome.storage.local (set by background/bootstrap tooling)
      const stored = await chrome.storage.local.get(TOKEN_KEY);
      bridgeToken = stored[TOKEN_KEY] || '';
    }
  } catch (_) {
    bridgeToken = bridgeToken || '';
  }
}

async function bootstrapToken() {
  // One-time pairing with the local relay: fetch the shared secret from
  // /v1/bootstrap (restricted to chrome-extension:// callers) and persist it.
  try {
    const res = await fetch(`${RELAY}/v1/bootstrap`, { method: 'GET', cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      if (data && data.token) {
        bridgeToken = data.token;
        try {
          localStorage.setItem(TOKEN_KEY, bridgeToken);
        } catch (_) { /* extension storage may be unavailable in some contexts */ }
        return true;
      }
    }
  } catch (_) { /* relay offline */ }
  return false;
}

function bridgeHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (bridgeToken) headers['X-Bridge-Token'] = bridgeToken;
  return headers;
}

function t(key, ...args) {
  const dict = I18N[currentLanguage] || I18N.en;
  const val = dict[key] || I18N.en[key] || "";
  return typeof val === 'function' ? val(...args) : val;
}

function applyTranslations() {
  const dict = I18N[currentLanguage] || I18N.en;
  currentLangCode.textContent = dict.code;
  document.documentElement.lang = currentLanguage;

  labelTargetOrigin.textContent = t('targetOrigin');
  descText.textContent = t('desc');
  consentText.textContent = t('consent');
  btnText.textContent = t('btnSync');
  footerSecureTag.textContent = t('footerTag');
  labelSessions.textContent = t('sessionsLabel');

  // Update dropdown active item
  document.querySelectorAll('.lang-item').forEach(item => {
    item.classList.toggle('active', item.dataset.lang === currentLanguage);
  });

  // Re-check status messages
  if (relayBadge.classList.contains('online')) {
    relayText.textContent = t('relayOnline');
  } else if (relayBadge.classList.contains('offline')) {
    relayText.textContent = t('relayOffline');
  } else {
    relayText.textContent = t('relayChecking');
  }
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
      relayText.textContent = t('relayOnline');
      return true;
    }
  } catch (_) {}
  relayBadge.className = 'badge offline';
  relayText.textContent = t('relayOffline');
  return false;
}

// ---------- Active sessions (what's synced inside Lightpanda) ----------

async function fetchSessions() {
  try {
    const res = await fetch(`${RELAY}/v1/sessions`, {
      method: 'GET', cache: 'no-store', headers: bridgeHeaders()
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.ok ? data : null;
  } catch (_) { return null; }
}

function fmtExpiry(ts) {
  const d = new Date(ts * 1000);
  const days = Math.floor((ts * 1000 - Date.now()) / 86400000);
  if (days > 0) return `~${days}d`;
  const hours = Math.floor((ts * 1000 - Date.now()) / 3600000);
  if (hours > 0) return `~${hours}h`;
  return '<1h';
}

function renderSessions(data) {
  const sessions = (data && data.sessions) || [];
  sessionsCount.textContent = String(sessions.length);
  sessionsList.innerHTML = '';

  if (!sessions.length) {
    const empty = document.createElement('div');
    empty.className = 'sessions-empty';
    empty.textContent = t('sessionsEmpty');
    sessionsList.appendChild(empty);
    sessionsClear.style.display = 'none';
    return;
  }

  sessions.forEach(s => {
    const row = document.createElement('div');
    row.className = 'session-row';

    const info = document.createElement('div');
    const host = document.createElement('div');
    host.className = 'session-host';
    host.textContent = s.host;
    const meta = document.createElement('div');
    meta.className = 'session-meta';
    meta.textContent = `${s.cookie_count} cookies` +
      (s.expires && !s.expired ? ` · ${fmtExpiry(s.expires)}` : '') +
      (s.expired ? ' · expired' : '');
    info.appendChild(host);
    info.appendChild(meta);

    const rm = document.createElement('button');
    rm.className = 'session-remove';
    rm.type = 'button';
    rm.innerHTML = '✕';
    rm.title = t('sessionRemove');
    rm.addEventListener('click', async () => {
      rm.disabled = true;
      await clearSessionsOnRelay(s.origin);
      await refreshSessions();
    });

    row.appendChild(info);
    row.appendChild(rm);
    sessionsList.appendChild(row);
  });

  sessionsClear.style.display = 'block';
  clearText.textContent = t('sessionsClear', sessions.length);
}

async function clearSessionsOnRelay(origin = null) {
  try {
    const body = origin ? { origin } : {};
    const res = await fetch(`${RELAY}/v1/sessions/clear`, {
      method: 'POST', headers: bridgeHeaders(), body: JSON.stringify(body)
    });
    return res.ok;
  } catch (_) { return false; }
}

async function refreshSessions() {
  const data = await fetchSessions();
  if (data === null) {
    sessionsCount.textContent = '—';
    sessionsList.innerHTML = '';
    sessionsClear.style.display = 'none';
    return;
  }
  renderSessions(data);
}

sessionsToggle.addEventListener('click', () => {
  sessionsCard.classList.toggle('open');
  if (sessionsCard.classList.contains('open')) refreshSessions();
});

sessionsClear.addEventListener('click', async () => {
  sessionsClear.disabled = true;
  await clearSessionsOnRelay(null);
  await refreshSessions();
  sessionsClear.disabled = false;
});

async function init() {
  applyTranslations();
  await loadBridgeToken();
  if (!bridgeToken) {
    // First run: auto-pair with the local relay (fetch shared secret).
    await bootstrapToken();
  }
  const relayOk = await checkRelay();
  if (relayOk) refreshSessions();  // populate the sessions counter badge

  // Find target tab
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

  originEl.textContent = origin || t('incompatiblePage');
  originEl.dataset.origin = origin;

  if (!eligible(url)) {
    setStatus(t('errNeedHttps'), 'error');
  } else if (!relayOk) {
    setStatus(t('errNoRelay'), 'error');
  }
}

// Language Picker events
langBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  langDropdown.classList.toggle('open');
});

document.addEventListener('click', () => {
  langDropdown.classList.remove('open');
});

document.querySelectorAll('.lang-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.stopPropagation();
    currentLanguage = item.dataset.lang;
    localStorage.setItem('lightpanda-lang', currentLanguage);
    langDropdown.classList.remove('open');
    applyTranslations();
  });
});

confirmEl.addEventListener('change', () => {
  const isEligible = eligible(currentTab?.url || '');
  transferEl.disabled = !confirmEl.checked || !isEligible;
});

transferEl.addEventListener('click', async () => {
  transferEl.disabled = true;
  setStatus(t('syncing'));

  try {
    const url = currentTab?.url || '';
    const origin = new URL(url).origin;

    // 1. Fetch Cookies
    const cookies = await chrome.cookies.getAll({ url });
    if (!cookies || cookies.length === 0) {
      throw new Error(t('errNoCookies'));
    }

    // 2. Extract localStorage
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

    // 3. Send payload to Relay (authenticated with shared token)
    const payload = { origin, cookies, storage };
    const response = await fetch(`${RELAY}/v1/session/import`, {
      method: 'POST',
      headers: bridgeHeaders(),
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || t('errRefused'));
    }

    setStatus(t('success', result.cookie_count), 'success');
  } catch (error) {
    setStatus(error.message || t('errRefused'), 'error');
  } finally {
    transferEl.disabled = !confirmEl.checked;
  }
});

init();
