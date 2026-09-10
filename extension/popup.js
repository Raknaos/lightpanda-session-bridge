const RELAY = "http://127.0.0.1:8765";

// Multilingual Dictionary (Default English + French, Spanish, German, Chinese, Japanese, Italian, Portuguese, Arabic, Russian)
const I18N = {
  en: {
    clearConfirm: "Click again to clear all",
    clearedToast: "All sessions cleared",
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
    success: (count, keys) => `✓ Session synchronized (${count} cookies, ${keys} localStorage keys).`,
    errStorageExtract: 'Could not read localStorage on this page (missing permission, or the page is not injectable). Reload the tab and try again.',
    errPartialStorage: (got, want, names) => `Incomplete transfer: ${got}/${want} localStorage keys reached Lightpanda${names}. Sync again.`,
    missingKeys: (list) => ` (missing: ${list})`,
    errStorageRefused: (detail) => `Some localStorage keys could not be transferred: ${detail}`,
    errNeedHttps: "Please open a public HTTPS website (e.g. Gmail, A6API).",
    errNoRelay: "Local relay (port 8765) is not running.",
    errNoCookies: "No cookies found for this page.",
    errCookiesOutOfScope: "These cookies are outside the extension's permission scope. Reload the extension (chrome://extensions) and try again.",
    errRefused: "Transfer refused by local relay.",
    updateLabel: "Bridge update",
    updateChecking: "Checking for updates…",
    updateUpToDate: (x) => `Up to date · v${x}`,
    updateAvailable: (x) => `Update available: v${x}`,
    updateMainAvailable: (x) => `New commit on ${x}`,
    updateBtn: (x) => `Update to v${x}`,
    updateBtnMain: "Install the latest commit",
    updateApplying: "Downloading and installing from GitHub…",
    updateApplied: (x) => `Installed v${x} — reloading…`,
    updateFailed: (x) => `Update failed: ${x}`,
    updateRollback: "Undo the last update",
    updateRolledBack: (x) => `Restored v${x} — reloading…`,
    updateBaseline: "Exact commit tracking is off: install once so the deployed commit is recorded.",
    footerTag: "Isolated Profile · Localhost CDP",
    sessionsLabel: "Active sessions in Lightpanda",
    sessionsEmpty: "No sessions synced into Lightpanda.",
    sessionsClear: (n) => `Clear all (${n})`,
    sessionRemove: "Remove this session"
  },
  fr: {
    clearConfirm: "Cliquez encore pour tout effacer",
    clearedToast: "Toutes les sessions effacées",
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
    success: (count, keys) => `✓ Session synchronisée (${count} cookies, ${keys} clés localStorage).`,
    errStorageExtract: 'Lecture du localStorage impossible sur cette page (permission manquante ou page non injectable). Rechargez l\'onglet et réessayez.',
    errPartialStorage: (got, want, names) => `Transfert incomplet : ${got}/${want} clés localStorage reçues par Lightpanda${names}. Resynchronisez.`,
    missingKeys: (list) => ` (manquantes: ${list})`,
    errStorageRefused: (detail) => `Certaines clés localStorage n'ont pas pu être transférées : ${detail}`,
    errNeedHttps: "Ouvrez un site HTTPS public (ex: Gmail, A6API).",
    errNoRelay: "Le relais local (port 8765) n’est pas démarré.",
    errNoCookies: "Aucun cookie trouvé pour cette page.",
    errCookiesOutOfScope: "Ces cookies sont hors du périmètre d'autorisation de l'extension. Rechargez l'extension (chrome://extensions) puis réessayez.",
    errRefused: "Transfert refusé par le relais local.",
    updateLabel: "Mise à jour du Bridge",
    updateChecking: "Recherche de mise à jour…",
    updateUpToDate: (x) => `À jour · v${x}`,
    updateAvailable: (x) => `Mise à jour disponible : v${x}`,
    updateMainAvailable: (x) => `Nouveau commit ${x}`,
    updateBtn: (x) => `Mettre à jour vers v${x}`,
    updateBtnMain: "Installer le dernier commit",
    updateApplying: "Téléchargement et installation depuis GitHub…",
    updateApplied: (x) => `v${x} installée — rechargement…`,
    updateFailed: (x) => `Échec de la mise à jour : ${x}`,
    updateRollback: "Annuler la dernière mise à jour",
    updateRolledBack: (x) => `v${x} restaurée — rechargement…`,
    updateBaseline: "Suivi exact désactivé : lancez une installation pour enregistrer le commit déployé.",
    footerTag: "Profil isolé · Localhost CDP",
    sessionsLabel: "Sessions actives dans Lightpanda",
    sessionsEmpty: "Aucune session synchronisée dans Lightpanda.",
    sessionsClear: (n) => `Tout retirer (${n})`,
    sessionRemove: "Retirer cette session"
  },
  es: {
    clearConfirm: "Pulsa de nuevo para borrar todo",
    clearedToast: "Todas las sesiones borradas",
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
    success: (count, keys) => `✓ Sesión sincronizada (${count} cookies, ${keys} claves de localStorage).`,
    errStorageExtract: 'No se pudo leer localStorage en esta página (falta permiso o la página no es inyectable). Recarga la pestaña y reintenta.',
    errPartialStorage: (got, want, names) => `Transferencia incompleta: ${got}/${want} claves de localStorage llegaron a Lightpanda${names}. Sincroniza de nuevo.`,
    missingKeys: (list) => ` (faltan: ${list})`,
    errStorageRefused: (detail) => `No se pudieron transferir algunas claves de localStorage: ${detail}`,
    errNeedHttps: "Abre un sitio web HTTPS público (ej. Gmail, A6API).",
    errNoRelay: "El relé local (puerto 8765) no está en ejecución.",
    errNoCookies: "No se encontraron cookies para esta página.",
    errCookiesOutOfScope: "Estas cookies están fuera de los permisos de la extensión. Recarga la extensión (chrome://extensions) e inténtalo de nuevo.",
    errRefused: "Transferencia rechazada por el relé local.",
    updateLabel: "Actualización del Bridge",
    updateChecking: "Buscando actualizaciones…",
    updateUpToDate: (x) => `Al día · v${x}`,
    updateAvailable: (x) => `Actualización disponible: v${x}`,
    updateMainAvailable: (x) => `Nuevo commit ${x}`,
    updateBtn: (x) => `Actualizar a v${x}`,
    updateBtnMain: "Instalar el último commit",
    updateApplying: "Descargando e instalando desde GitHub…",
    updateApplied: (x) => `v${x} instalada — recargando…`,
    updateFailed: (x) => `Error de actualización: ${x}`,
    updateRollback: "Deshacer la última actualización",
    updateRolledBack: (x) => `v${x} restaurada — recargando…`,
    updateBaseline: "El seguimiento exacto está desactivado: instala una vez para registrar el commit desplegado.",
    footerTag: "Perfil aislado · Localhost CDP",
    sessionsLabel: "Sesiones activas en Lightpanda",
    sessionsEmpty: "No hay sesiones sincronizadas en Lightpanda.",
    sessionsClear: (n) => `Borrar todas (${n})`,
    sessionRemove: "Eliminar esta sesión"
  },
  de: {
    clearConfirm: "Erneut klicken, um alles zu löschen",
    clearedToast: "Alle Sitzungen gelöscht",
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
    success: (count, keys) => `✓ Sitzung synchronisiert (${count} Cookies, ${keys} localStorage-Schlüssel).`,
    errStorageExtract: 'localStorage konnte auf dieser Seite nicht gelesen werden (fehlende Berechtigung oder Seite nicht injizierbar). Tab neu laden und erneut versuchen.',
    errPartialStorage: (got, want, names) => `Unvollständige Übertragung: ${got}/${want} localStorage-Schlüssel sind bei Lightpanda angekommen${names}. Erneut synchronisieren.`,
    missingKeys: (list) => ` (fehlen: ${list})`,
    errStorageRefused: (detail) => `Einige localStorage-Schlüssel konnten nicht übertragen werden: ${detail}`,
    errNeedHttps: "Bitte öffnen Sie eine öffentliche HTTPS-Website.",
    errNoRelay: "Lokales Relais (Port 8765) läuft nicht.",
    errNoCookies: "Keine Cookies für diese Seite gefunden.",
    errCookiesOutOfScope: "Diese Cookies liegen außerhalb der Berechtigungen der Erweiterung. Lade die Erweiterung neu (chrome://extensions) und versuche es erneut.",
    errRefused: "Übertragung vom lokalen Relais abgelehnt.",
    updateLabel: "Bridge-Aktualisierung",
    updateChecking: "Suche nach Updates…",
    updateUpToDate: (x) => `Aktuell · v${x}`,
    updateAvailable: (x) => `Update verfügbar: v${x}`,
    updateMainAvailable: (x) => `Neuer Commit ${x}`,
    updateBtn: (x) => `Auf v${x} aktualisieren`,
    updateBtnMain: "Neuesten Commit installieren",
    updateApplying: "Wird von GitHub geladen und installiert…",
    updateApplied: (x) => `v${x} installiert — Neuladen…`,
    updateFailed: (x) => `Update fehlgeschlagen: ${x}`,
    updateRollback: "Letztes Update rückgängig machen",
    updateRolledBack: (x) => `v${x} wiederhergestellt — Neuladen…`,
    updateBaseline: "Genaue Commit-Verfolgung ist aus: einmal installieren, um den Commit zu erfassen.",
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
    success: (count, keys) => `✓ 会话已同步（${count} 个 Cookie，${keys} 个 localStorage 键）。`,
    errStorageExtract: '无法在此页面读取 localStorage（缺少权限或页面不可注入）。请重新加载标签页后重试。',
    errPartialStorage: (got, want, names) => `传输不完整：${got}/${want} 个 localStorage 键到达 Lightpanda${names}。请重新同步。`,
    missingKeys: (list) => ` (缺失: ${list})`,
    errStorageRefused: (detail) => `部分 localStorage 键无法传输：${detail}`,
    errNeedHttps: "请打开公开的 HTTPS 网站（例如 Gmail、A6API）。",
    errNoRelay: "本地中继（端口 8765）未启动。",
    errNoCookies: "未找到此页面的 Cookie。",
    errCookiesOutOfScope: "这些 Cookie 超出扩展程序的权限范围。请重新加载扩展程序（chrome://extensions）后重试。",
    errRefused: "本地中继拒绝了传输。",
    updateLabel: "Bridge 更新",
    updateChecking: "正在检查更新…",
    updateUpToDate: (x) => `已是最新 · v${x}`,
    updateAvailable: (x) => `有可用更新：v${x}`,
    updateMainAvailable: (x) => `新提交 ${x}`,
    updateBtn: (x) => `更新到 v${x}`,
    updateBtnMain: "安装最新提交",
    updateApplying: "正在从 GitHub 下载并安装…",
    updateApplied: (x) => `已安装 v${x} — 正在重新加载…`,
    updateFailed: (x) => `更新失败：${x}`,
    updateRollback: "撤销上次更新",
    updateRolledBack: (x) => `已恢复 v${x} — 正在重新加载…`,
    updateBaseline: "提交跟踪未启用：安装一次即可记录当前提交。",
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
    success: (count, keys) => `✓ セッションを同期しました（Cookie ${count} 個、localStorage ${keys} 件）。`,
    errStorageExtract: 'このページで localStorage を読み取れません（権限不足、または注入できないページ）。タブを再読み込みして再試行してください。',
    errPartialStorage: (got, want, names) => `転送が不完全です：localStorage ${got}/${want} 件のみ Lightpanda に到達しました${names}。再同期してください。`,
    missingKeys: (list) => ` (欠落: ${list})`,
    errStorageRefused: (detail) => `一部の localStorage キーを転送できませんでした：${detail}`,
    errNeedHttps: "公開HTTPSサイト（Gmail、A6APIなど）を開いてください。",
    errNoRelay: "ローカルリレー（ポート8765）が起動していません。",
    errNoCookies: "このページのCookieが見つかりません。",
    errCookiesOutOfScope: "これらのCookieは拡張機能の権限範囲外です。拡張機能を再読み込み（chrome://extensions）して再試行してください。",
    errRefused: "ローカルリレーによって転送が拒否されました。",
    updateLabel: "Bridge の更新",
    updateChecking: "更新を確認中…",
    updateUpToDate: (x) => `最新です · v${x}`,
    updateAvailable: (x) => `更新があります: v${x}`,
    updateMainAvailable: (x) => `新しいコミット ${x}`,
    updateBtn: (x) => `v${x} に更新`,
    updateBtnMain: "最新コミットをインストール",
    updateApplying: "GitHub からダウンロードしてインストール中…",
    updateApplied: (x) => `v${x} をインストールしました — 再読み込み中…`,
    updateFailed: (x) => `更新に失敗しました: ${x}`,
    updateRollback: "最後の更新を元に戻す",
    updateRolledBack: (x) => `v${x} を復元しました — 再読み込み中…`,
    updateBaseline: "コミット追跡は未設定です: 一度インストールすると記録されます。",
    footerTag: "分離プロファイル · Localhost CDP",
    sessionsLabel: "Lightpanda内のアクティブなセッション",
    sessionsEmpty: "Lightpandaに同期されたセッションはありません。",
    sessionsClear: (n) => `すべて削除（${n}）`,
    sessionRemove: "このセッションを削除"
  },
  it: {
    clearConfirm: "Clicca di nuovo per cancellare tutto",
    clearedToast: "Tutte le sessioni cancellate",
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
    success: (count, keys) => `✓ Sessione sincronizzata (${count} cookie, ${keys} chiavi localStorage).`,
    errStorageExtract: 'Impossibile leggere localStorage su questa pagina (permesso mancante o pagina non iniettabile). Ricarica la scheda e riprova.',
    errPartialStorage: (got, want, names) => `Trasferimento incompleto: ${got}/${want} chiavi localStorage arrivate a Lightpanda${names}. Sincronizza di nuovo.`,
    missingKeys: (list) => ` (mancanti: ${list})`,
    errStorageRefused: (detail) => `Alcune chiavi localStorage non sono state trasferite: ${detail}`,
    errNeedHttps: "Apri un sito HTTPS pubblico (es. Gmail, A6API).",
    errNoRelay: "Il relè locale (porta 8765) non è attivo.",
    errNoCookies: "Nessun cookie trovato per questa pagina.",
    errCookiesOutOfScope: "Questi cookie sono fuori dai permessi dell'estensione. Ricarica l'estensione (chrome://extensions) e riprova.",
    errRefused: "Trasferimento rifiutato dal relè locale.",
    updateLabel: "Aggiornamento Bridge",
    updateChecking: "Ricerca aggiornamenti…",
    updateUpToDate: (x) => `Aggiornato · v${x}`,
    updateAvailable: (x) => `Aggiornamento disponibile: v${x}`,
    updateMainAvailable: (x) => `Nuovo commit ${x}`,
    updateBtn: (x) => `Aggiorna a v${x}`,
    updateBtnMain: "Installa l'ultimo commit",
    updateApplying: "Download e installazione da GitHub…",
    updateApplied: (x) => `v${x} installata — ricarica…`,
    updateFailed: (x) => `Aggiornamento non riuscito: ${x}`,
    updateRollback: "Annulla l'ultimo aggiornamento",
    updateRolledBack: (x) => `v${x} ripristinata — ricarica…`,
    updateBaseline: "Tracciamento esatto disattivato: installa una volta per registrare il commit.",
    footerTag: "Profilo isolato · Localhost CDP",
    sessionsLabel: "Sessioni attive in Lightpanda",
    sessionsEmpty: "Nessuna sessione sincronizzata in Lightpanda.",
    sessionsClear: (n) => `Rimuovi tutte (${n})`,
    sessionRemove: "Rimuovi questa sessione"
  },
  pt: {
    clearConfirm: "Clique novamente para limpar tudo",
    clearedToast: "Todas as sessões apagadas",
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
    success: (count, keys) => `✓ Sessão sincronizada (${count} cookies, ${keys} chaves de localStorage).`,
    errStorageExtract: 'Não foi possível ler o localStorage nesta página (permissão ausente ou página não injetável). Recarregue a aba e tente novamente.',
    errPartialStorage: (got, want, names) => `Transferência incompleta: ${got}/${want} chaves de localStorage chegaram ao Lightpanda${names}. Sincronize novamente.`,
    missingKeys: (list) => ` (faltando: ${list})`,
    errStorageRefused: (detail) => `Algumas chaves de localStorage não puderam ser transferidas: ${detail}`,
    errNeedHttps: "Abra um site HTTPS público (ex: Gmail, A6API).",
    errNoRelay: "O relé local (porta 8765) não está em execução.",
    errNoCookies: "Nenhum cookie encontrado para esta página.",
    errCookiesOutOfScope: "Estes cookies estão fora das permissões da extensão. Recarregue a extensão (chrome://extensions) e tente novamente.",
    errRefused: "Transferência recusada pelo relé local.",
    updateLabel: "Atualização do Bridge",
    updateChecking: "Verificando atualizações…",
    updateUpToDate: (x) => `Atualizado · v${x}`,
    updateAvailable: (x) => `Atualização disponível: v${x}`,
    updateMainAvailable: (x) => `Novo commit ${x}`,
    updateBtn: (x) => `Atualizar para v${x}`,
    updateBtnMain: "Instalar o último commit",
    updateApplying: "Baixando e instalando do GitHub…",
    updateApplied: (x) => `v${x} instalada — recarregando…`,
    updateFailed: (x) => `Falha na atualização: ${x}`,
    updateRollback: "Desfazer a última atualização",
    updateRolledBack: (x) => `v${x} restaurada — recarregando…`,
    updateBaseline: "Rastreamento exato desativado: instale uma vez para registrar o commit.",
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
    success: (count, keys) => `✓ تمت مزامنة الجلسة (${count} ملف تعريف، ${keys} مفتاح localStorage).`,
    errStorageExtract: 'تعذر قراءة localStorage في هذه الصفحة (صلاحية ناقصة أو صفحة غير قابلة للحقن). أعد تحميل التبويب وحاول مرة أخرى.',
    errPartialStorage: (got, want, names) => `النقل غير مكتمل: ${got}/${want} مفتاح localStorage وصل إلى Lightpanda${names}. أعد المزامنة.`,
    missingKeys: (list) => ` (المفقودة: ${list})`,
    errStorageRefused: (detail) => `تعذّر نقل بعض مفاتيح localStorage: ${detail}`,
    errNeedHttps: "يرجى فتح موقع HTTPS عام.",
    errNoRelay: "المرحل المحلي (المنفذ 8765) لا يعمل.",
    errNoCookies: "لم يتم العثور على ملفات تعريف الارتباط.",
    errCookiesOutOfScope: "ملفات تعريف الارتباط هذه خارج نطاق أذونات الإضافة. أعد تحميل الإضافة (chrome://extensions) ثم أعد المحاولة.",
    errRefused: "تم رفض النقل بواسطة المرحل المحلي.",
    updateLabel: "تحديث Bridge",
    updateChecking: "جارٍ التحقق من التحديثات…",
    updateUpToDate: (x) => `محدَّث · v${x}`,
    updateAvailable: (x) => `يتوفر تحديث: v${x}`,
    updateMainAvailable: (x) => `التزام جديد ${x}`,
    updateBtn: (x) => `التحديث إلى v${x}`,
    updateBtnMain: "تثبيت أحدث التزام",
    updateApplying: "جارٍ التنزيل والتثبيت من GitHub…",
    updateApplied: (x) => `تم تثبيت v${x} — جارٍ إعادة التحميل…`,
    updateFailed: (x) => `فشل التحديث: ${x}`,
    updateRollback: "تراجع عن آخر تحديث",
    updateRolledBack: (x) => `تمت استعادة v${x} — جارٍ إعادة التحميل…`,
    updateBaseline: "تتبّع الالتزام غير مفعّل: ثبّت مرة واحدة لتسجيل الالتزام المنشور.",
    footerTag: "ملف تعريف معزول · Localhost CDP",
    sessionsLabel: "الجلسات النشطة في Lightpanda",
    sessionsEmpty: "لا توجد جلسات متزامنة في Lightpanda.",
    sessionsClear: (n) => `إزالة الكل (${n})`,
    sessionRemove: "إزالة هذه الجلسة"
  },
  ru: {
    clearConfirm: "Нажмите ещё раз, чтобы очистить всё",
    clearedToast: "Все сессии удалены",
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
    success: (count, keys) => `✓ Сеанс синхронизирован (${count} cookie, ${keys} ключей localStorage).`,
    errStorageExtract: 'Не удалось прочитать localStorage на этой странице (нет разрешения или страница не поддерживает внедрение). Перезагрузите вкладку и повторите.',
    errPartialStorage: (got, want, names) => `Перенос неполный: ${got}/${want} ключей localStorage достигли Lightpanda${names}. Синхронизируйте снова.`,
    missingKeys: (list) => ` (отсутствуют: ${list})`,
    errStorageRefused: (detail) => `Некоторые ключи localStorage не удалось перенести: ${detail}`,
    errNeedHttps: "Откройте общедоступный сайт HTTPS (например, Gmail, A6API).",
    errNoRelay: "Локальное реле (порт 8765) не запущено.",
    errNoCookies: "Файлы cookie для этой страницы не найдены.",
    errCookiesOutOfScope: "Эти файлы cookie вне разрешений расширения. Перезагрузите расширение (chrome://extensions) и повторите попытку.",
    errRefused: "Перенос отклонен локальным реле.",
    updateLabel: "Обновление Bridge",
    updateChecking: "Проверка обновлений…",
    updateUpToDate: (x) => `Актуально · v${x}`,
    updateAvailable: (x) => `Доступно обновление: v${x}`,
    updateMainAvailable: (x) => `Новый коммит ${x}`,
    updateBtn: (x) => `Обновить до v${x}`,
    updateBtnMain: "Установить последний коммит",
    updateApplying: "Загрузка и установка с GitHub…",
    updateApplied: (x) => `v${x} установлена — перезагрузка…`,
    updateFailed: (x) => `Ошибка обновления: ${x}`,
    updateRollback: "Отменить последнее обновление",
    updateRolledBack: (x) => `v${x} восстановлена — перезагрузка…`,
    updateBaseline: "Точное отслеживание коммита выключено: установите один раз, чтобы записать коммит.",
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
const clearTextBase = clearText ? clearText.textContent : '';
// Bridge update UI (the relay does the download; this is only the button)
const updateChip = document.querySelector('#update-chip');
const updateVersion = document.querySelector('#update-version');
const updateMeta = document.querySelector('#update-meta');
const updateBtn = document.querySelector('#update-btn');
const rollbackBtn = document.querySelector('#rollback-btn');
const labelUpdate = document.querySelector('#label-update');
const appVersion = document.querySelector('#app-version');

const toastEl = document.querySelector('#toast');

let toastTimer = null;
function showToast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2600);
}

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
  if (labelUpdate) labelUpdate.textContent = t('updateLabel');

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

  renderUpdateCard();
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
  // Two-step confirmation so a mis-click never wipes every synced session.
  if (!sessionsClear.dataset.armed) {
    sessionsClear.dataset.armed = '1';
    sessionsClear.textContent = t('clearConfirm');
    setTimeout(() => {
      if (sessionsClear.dataset.armed) {
        delete sessionsClear.dataset.armed;
        sessionsClear.textContent = clearTextBase;
      }
    }, 3500);
    return;
  }
  delete sessionsClear.dataset.armed;
  sessionsClear.textContent = clearTextBase;
  sessionsClear.disabled = true;
  await clearSessionsOnRelay(null);
  await refreshSessions();
  showToast(t('clearedToast'));
  sessionsClear.disabled = false;
});

// Keep the counter honest while the popup stays open (30s cadence, only when
// the tab is still visible to avoid pointless relay hits).
setInterval(() => {
  if (document.visibilityState === 'visible' && bridgeToken) {
    refreshSessions();
  }
}, 30000);

// ---- Bridge update (GitHub) ------------------------------------------------
// The extension is loaded unpacked: it can never rewrite its own files, and
// Chrome never auto-updates it. The local relay does the download and the
// install; the popup only reports the state and presses the button.
let updateInfo = null;
let updateBusy = false;

function shortCommit(sha) {
  return sha ? String(sha).slice(0, 7) : '';
}

function renderUpdateCard() {
  if (!updateChip) return;
  labelUpdate.textContent = t('updateLabel');
  const deployed = chrome.runtime.getManifest().version;
  updateVersion.textContent = 'v' + deployed;

  if (updateBusy) {
    updateChip.className = 'update-chip';
    updateChip.textContent = t('updateApplying');
    updateMeta.textContent = '';
    return;
  }

  // No answer from the relay: never claim "up to date" on a guess.
  if (!updateInfo || !updateInfo.ok) {
    updateChip.className = 'update-chip off';
    updateChip.textContent = t('relayOffline');
    updateMeta.textContent = '';
    updateBtn.style.display = 'none';
    rollbackBtn.style.display = 'none';
    return;
  }

  rollbackBtn.textContent = t('updateRollback');
  rollbackBtn.style.display = updateInfo.backup_available ? '' : 'none';

  if (updateInfo.update_available) {
    const fromRelease = updateInfo.source === 'release';
    updateChip.className = 'update-chip new';
    updateChip.textContent = fromRelease
      ? 'v' + updateInfo.latest_version
      : shortCommit(updateInfo.latest_commit);
    updateMeta.textContent = fromRelease
      ? t('updateAvailable', updateInfo.latest_version)
      : t('updateMainAvailable', shortCommit(updateInfo.latest_commit));
    updateBtn.textContent = fromRelease
      ? t('updateBtn', updateInfo.latest_version)
      : t('updateBtnMain');
    updateBtn.style.display = '';
  } else {
    updateChip.className = 'update-chip ok';
    updateChip.textContent = t('updateUpToDate', deployed);
    updateMeta.textContent = updateInfo.current_commit
      ? shortCommit(updateInfo.current_commit)
      : t('updateBaseline');
    updateBtn.style.display = 'none';
  }
}

async function refreshUpdateStatus() {
  try {
    const res = await fetch(`${RELAY}/v1/update/check`, { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    updateInfo = await res.json();
  } catch (_) {
    updateInfo = null;
  }
  renderUpdateCard();
}

async function runUpdate(path, label, doneKey) {
  if (updateBusy) return;
  updateBusy = true;
  setStatus(label, 'info');
  updateBtn.disabled = true;
  rollbackBtn.disabled = true;
  renderUpdateCard();
  try {
    const res = await fetch(`${RELAY}${path}`, {
      method: 'POST',
      headers: bridgeHeaders(),
      body: JSON.stringify({ source: 'auto' })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || t('errRefused'));
    updateBusy = false;
    setStatus(t(doneKey, data.version || ''), 'success');
    // The new files are on disk; reload so Comet serves them. The popup goes
    // away with the reload - the status line above is the last thing seen.
    setTimeout(() => { try { chrome.runtime.reload(); } catch (_) {} }, 1400);
  } catch (error) {
    updateBusy = false;
    updateBtn.disabled = false;
    rollbackBtn.disabled = false;
    setStatus(t('updateFailed', error.message || ''), 'error');
    refreshUpdateStatus();
  }
}

if (updateBtn) {
  updateBtn.addEventListener('click', () => runUpdate('/v1/update/apply', t('updateApplying'), 'updateApplied'));
}
if (rollbackBtn) {
  rollbackBtn.addEventListener('click', () => runUpdate('/v1/update/rollback', t('updateApplying'), 'updateRolledBack'));
}

async function init() {
  applyTranslations();
  // The footer version is read from the manifest: no hand-edit on each bump.
  if (appVersion) appVersion.textContent = 'v' + chrome.runtime.getManifest().version;
  await loadBridgeToken();
  if (!bridgeToken) {
    // First run: auto-pair with the local relay (fetch shared secret).
    await bootstrapToken();
  }
  const relayOk = await checkRelay();
  if (relayOk) refreshSessions();  // populate the sessions counter badge
  // Is GitHub ahead of the version Comet is running? The relay answers; the
  // toolbar badge (background.js) says the same thing without opening this.
  refreshUpdateStatus();

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

    // 1. Fetch Cookies.
    // chrome.cookies.getAll({url}) silently hides cookies whose `secure` flag
    // does not match the URL scheme, and returns nothing at all when the
    // extension holds no host permission for that scheme. Falling back to a
    // domain query - and telling a scope problem apart from a genuinely empty
    // jar - is what stops a live session from being reported as "no cookies".
    let cookies = await chrome.cookies.getAll({ url });
    if (!cookies || cookies.length === 0) {
      const host = new URL(url).hostname;
      const byDomain = await chrome.cookies.getAll({ domain: host });
      if (byDomain && byDomain.length) {
        cookies = byDomain;
      } else {
        let inScope = true;
        try {
          inScope = await chrome.permissions.contains({
            origins: [`https://${host}/*`, `http://${host}/*`]
          });
        } catch (_) {}
        throw new Error(t(inScope ? 'errNoCookies' : 'errCookiesOutOfScope'));
      }
    }

    // 2. Extract localStorage.
    //    Retried once, and its failure is REPORTED instead of swallowed: a
    //    snapshot that silently comes back empty (or half-built while the SPA
    //    is still booting) is what makes the next authenticated call fail with
    //    a 401/407 - a6api builds its New-Api-User header from
    //    localStorage["user"], so one missing key breaks the whole session.
    let storage = null;
    let storageError = null;
    for (let attempt = 0; attempt < 2; attempt++) {
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
        const got = results && results[0] ? results[0].result : null;
        if (got && typeof got === 'object') {
          storage = got;
          storageError = null;
          if (Object.keys(got).length) break;
        }
      } catch (err) {
        storageError = err;
      }
      await new Promise((r) => setTimeout(r, 250));
    }
    if (storageError && !storage) {
      throw new Error(t('errStorageExtract'));
    }
    const storageKeys = storage ? Object.keys(storage).length : 0;

    // 3. Send payload to Relay (authenticated with shared token)
    const payload = { origin, cookies, storage };
    const response = await fetch(`${RELAY}/v1/session/import`, {
      method: 'POST',
      headers: bridgeHeaders(),
      body: JSON.stringify(payload)
    });

    const result = await response.json();

    // The relay verifies EVERY key it was sent, so a short count means a
    // partial snapshot reached Lightpanda. It must never read as success here
    // either: that is a session that looks synced and answers 401/407. Since
    // v0.5.3 the relay also names the keys it could not carry, so the message
    // says WHAT is missing - a bare ratio is what made "sync again" useless.
    const expectedKeys = (typeof result.storage_expected === 'number' && result.storage_expected)
      ? result.storage_expected : storageKeys;
    if (typeof result.storage_count === 'number' && expectedKeys &&
        result.storage_count < expectedKeys) {
      const missing = Array.isArray(result.storage_missing) ? result.storage_missing : [];
      const names = missing.length ? t('missingKeys', missing.join(', ')) : '';
      throw new Error(t('errPartialStorage', result.storage_count, expectedKeys, names));
    }

    // Keys the relay refuses to carry (name or value past its size bounds) are
    // reported BY NAME, never silently dropped.
    if (Array.isArray(result.storage_refused) && result.storage_refused.length) {
      throw new Error(t('errStorageRefused', result.storage_refused.join('; ')));
    }

    if (!response.ok || !result.ok) {
      throw new Error(result.error || t('errRefused'));
    }

    setStatus(t('success', result.cookie_count, result.storage_count ?? storageKeys), 'success');
    // Refresh the sessions panel immediately so the counter and the list
    // reflect the sync that just happened (no extra click needed).
    sessionsCard.classList.add('open');
    await refreshSessions();
  } catch (error) {
    setStatus(error.message || t('errRefused'), 'error');
  } finally {
    transferEl.disabled = !confirmEl.checked;
  }
});

init();
