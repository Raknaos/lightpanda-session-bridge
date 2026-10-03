const RELAY = "http://127.0.0.1:8765";

// Multilingual Dictionary (Default English + French, Spanish, German, Chinese, Japanese, Italian, Portuguese, Arabic, Russian)
const I18N = {
  en: {
    clearConfirm: "Click again to clear all",
    clearedToast: "All sessions cleared",
    sessionCookieUnit: (n) => `${n} cookies`,
    sessionCookieOne: (n) => `${n} cookie`,
    sessionExpired: "expired",
    code: "EN",
    relayChecking: "Checking…",
    relayOnline: "Relay Online",
    relayOffline: "Relay Offline",
    relayOffline: "Relay Offline",
    relayIdle: "Not connected",
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
    diagBtn: "Copy diagnostic",
    diagCopied: "Diagnostic copied",
    diagFailed: "Copy failed",
    errRelayTimeout: 'Relay did not answer (Lightpanda restarting?). Try again.',
    errRelayUnreachable: "Could not reach the relay (is it running?).",
    errOriginRefused: "The relay refused this site's origin.",
    errUnauthorized: "The relay rejected this extension (not paired).",
    errRouteMissing: "The relay does not know this request.",
    errUpdateRefused: "The relay refused the update operation.",
    unknownRelayError: "Relay error: {0}",
    missingKeys: (list) => ` (missing: ${list})`,
    errStorageRefused: (detail) => `Some localStorage keys could not be transferred: ${detail}`,
    errNeedHttps: "Please open a public HTTPS website (e.g. Gmail, A6API).",
    errNoRelay: "Local relay (port 8765) is not running.",
    errNoCookies: "No cookies found for this page.",
    errCookiesOutOfScope: "These cookies are outside the extension's permission scope. Reload the extension (chrome://extensions) and try again.",
    errRefused: "Transfer refused by local relay.",
    updateLabel: "Bridge update",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Update",
    updateChipOk: "Up to date",
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
    errExtDirMissing: 'Extension folder not found',
    errExtDirReadonly: 'Extension folder is read-only',
    errNothingToInstall: 'Nothing to install: already up to date',
    errChecksumMismatch: 'Checksum mismatch: the download was refused',
    errArtifactTooLarge: 'The downloaded artifact is too large',
    errRedirectRefused: 'The update server refused the redirect',
    errUpdateSourceRefused: 'Unknown update source',
    errReleaseNotFound: 'No published release found',
    errMainNotFound: 'No main branch found',
    errNoBackup: 'No backup to restore',
    errArchiveRefused: 'The downloaded archive is not a valid extension',
    updateGitHubDown: 'GitHub did not answer',
    updateRateLimited: 'GitHub rate limit reached · try again later',
    updateBranchUnknown: 'Branch state unreadable · only the release was compared',
    updateSameBytes: "Identical to the published release \u00b7 main moved on",
    footerTag: "Isolated Profile · Localhost CDP",
    sessionsLabel: "Active sessions in Lightpanda",
    sessionsEmpty: "No sessions synced into Lightpanda.",
    sessionsClear: (n) => `Clear all (${n})`,
    sessionsClearShort: "Clear all",
    clearConfirmShort: "Confirm?",
    sessionRemove: "Remove this session"
  },
  fr: {
    clearConfirm: "Cliquez encore pour tout effacer",
    clearedToast: "Toutes les sessions effacées",
    sessionCookieUnit: (n) => `${n} cookies`,
    sessionCookieOne: (n) => `${n} cookie`,
    sessionExpired: "expirée",
    code: "FR",
    relayChecking: "Vérification…",
    relayOnline: "Relais en ligne",
    relayOffline: "Relais hors-ligne",
    relayOffline: "Relais hors-ligne",
    relayIdle: "Non connecté",
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
    diagBtn: "Copier le diagnostic",
    diagCopied: "Diagnostic copié",
    diagFailed: "Échec de la copie",
    errRelayTimeout: 'Le relais n\'a pas répondu (Lightpanda en redémarrage ?). Réessayez.',
    errRelayUnreachable: "Impossible de joindre le relais (est-il démarré ?).",
    errOriginRefused: "Le relais a refusé l'origine de ce site.",
    errUnauthorized: "Le relais a rejeté cette extension (non appairée).",
    errRouteMissing: "Le relais ne connaît pas cette requête.",
    errUpdateRefused: "Le relais a refusé l'opération de mise à jour.",
    unknownRelayError: "Erreur du relais : {0}",
    missingKeys: (list) => ` (manquantes: ${list})`,
    errStorageRefused: (detail) => `Certaines clés localStorage n'ont pas pu être transférées : ${detail}`,
    errNeedHttps: "Ouvrez un site HTTPS public (ex: Gmail, A6API).",
    errNoRelay: "Le relais local (port 8765) n’est pas démarré.",
    errNoCookies: "Aucun cookie trouvé pour cette page.",
    errCookiesOutOfScope: "Ces cookies sont hors du périmètre d'autorisation de l'extension. Rechargez l'extension (chrome://extensions) puis réessayez.",
    errRefused: "Transfert refusé par le relais local.",
    updateLabel: "Mise à jour du Bridge",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Mise à jour",
    updateChipOk: "À jour",
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
    errExtDirMissing: 'Dossier d\'extension introuvable',
    errExtDirReadonly: 'Le dossier d\'extension est en lecture seule',
    errNothingToInstall: 'Rien à installer : déjà à jour',
    errChecksumMismatch: 'Somme de contrôle incorrecte : le téléchargement a été refusé',
    errArtifactTooLarge: 'L\'artefact téléchargé est trop volumineux',
    errRedirectRefused: 'Le serveur de MAJ a refusé la redirection',
    errUpdateSourceRefused: 'Source de mise à jour inconnue',
    errReleaseNotFound: 'Aucune release publiée trouvée',
    errMainNotFound: 'Branche main introuvable',
    errNoBackup: 'Aucune sauvegarde à restaurer',
    errArchiveRefused: 'L\'archive téléchargée n\'est pas une extension valide',
    updateGitHubDown: 'GitHub n\'a pas répondu',
    updateRateLimited: 'Limite GitHub atteinte · réessaie plus tard',
    updateBranchUnknown: 'État de la branche illisible · seule la release a été comparée',
    updateSameBytes: "Identique \u00e0 la release publi\u00e9e \u00b7 la branche a avanc\u00e9",
    footerTag: "Profil isolé · Localhost CDP",
    sessionsLabel: "Sessions actives dans Lightpanda",
    sessionsEmpty: "Aucune session synchronisée dans Lightpanda.",
    sessionsClear: (n) => `Tout retirer (${n})`,
    sessionsClearShort: "Tout retirer",
    clearConfirmShort: "Confirmer ?",
    sessionRemove: "Retirer cette session"
  },
  es: {
    clearConfirm: "Pulsa de nuevo para borrar todo",
    clearedToast: "Todas las sesiones borradas",
    sessionCookieUnit: (n) => `${n} cookies`,
    sessionCookieOne: (n) => `${n} cookie`,
    sessionExpired: "caducada",
    code: "ES",
    relayChecking: "Comprobando…",
    relayOnline: "Relé en línea",
    relayOffline: "Relé desconectado",
    relayOffline: "Relé desconectado",
    relayIdle: "Sin conexión",
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
    diagBtn: "Copiar diagnóstico",
    diagCopied: "Diagnóstico copiado",
    diagFailed: "Error al copiar",
    errRelayTimeout: 'El relay no respondió (¿Lightpanda reiniciándose?). Inténtelo de nuevo.',
    errRelayUnreachable: "No se pudo contactar con el relay (¿está en marcha?).",
    errOriginRefused: "El relay rechazó el origen de este sitio.",
    errUnauthorized: "El relay rechazó esta extensión (sin emparejar).",
    errRouteMissing: "El relay no conoce esta solicitud.",
    errUpdateRefused: "El relay rechazó la operación de actualización.",
    unknownRelayError: "Error del relay: {0}",
    missingKeys: (list) => ` (faltan: ${list})`,
    errStorageRefused: (detail) => `No se pudieron transferir algunas claves de localStorage: ${detail}`,
    errNeedHttps: "Abre un sitio web HTTPS público (ej. Gmail, A6API).",
    errNoRelay: "El relé local (puerto 8765) no está en ejecución.",
    errNoCookies: "No se encontraron cookies para esta página.",
    errCookiesOutOfScope: "Estas cookies están fuera de los permisos de la extensión. Recarga la extensión (chrome://extensions) e inténtalo de nuevo.",
    errRefused: "Transferencia rechazada por el relé local.",
    updateLabel: "Actualización del Bridge",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Actualización",
    updateChipOk: "Al día",
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
    errExtDirMissing: 'No se encontró la carpeta de la extensión',
    errExtDirReadonly: 'La carpeta de la extensión es de solo lectura',
    errNothingToInstall: 'Nada que instalar: ya está actualizado',
    errChecksumMismatch: 'Suma de control incorrecta: se rechazó la descarga',
    errArtifactTooLarge: 'El artefacto descargado es demasiado grande',
    errRedirectRefused: 'El servidor de actualización rechazó la redirección',
    errUpdateSourceRefused: 'Fuente de actualización desconocida',
    errReleaseNotFound: 'No se encontró ninguna release publicada',
    errMainNotFound: 'No se encontró la rama main',
    errNoBackup: 'No hay copia de seguridad que restaurar',
    errArchiveRefused: 'El archivo descargado no es una extensión válida',
    updateGitHubDown: 'GitHub no respondió',
    updateRateLimited: 'Límite de GitHub alcanzada · inténtalo más tarde',
    updateBranchUnknown: 'Estado de la rama ilegible · sólo se comparó la release',
    updateSameBytes: "Id\u00e9ntico a la release publicada \u00b7 main avanz\u00f3",
    footerTag: "Perfil aislado · Localhost CDP",
    sessionsLabel: "Sesiones activas en Lightpanda",
    sessionsEmpty: "No hay sesiones sincronizadas en Lightpanda.",
    sessionsClear: (n) => `Borrar todas (${n})`,
    sessionsClearShort: "Borrar todo",
    clearConfirmShort: "¿Confirmar?",
    sessionRemove: "Eliminar esta sesión"
  },
  de: {
    clearConfirm: "Erneut klicken, um alles zu löschen",
    clearedToast: "Alle Sitzungen gelöscht",
    sessionCookieUnit: (n) => `${n} Cookies`,
    sessionCookieOne: (n) => `${n} Cookie`,
    sessionExpired: "abgelaufen",
    code: "DE",
    relayChecking: "Prüfe…",
    relayOnline: "Relais online",
    relayOffline: "Relais offline",
    relayOffline: "Relais offline",
    relayIdle: "Nicht verbunden",
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
    diagBtn: "Diagnose kopieren",
    diagCopied: "Diagnose kopiert",
    diagFailed: "Kopieren fehlgeschlagen",
    errRelayTimeout: 'Relay hat nicht geantwortet (Lightpanda startet neu?). Erneut versuchen.',
    errRelayUnreachable: "Der Relay war nicht erreichbar (läuft er?).",
    errOriginRefused: "Der Relay hat den Ursprung dieser Seite abgelehnt.",
    errUnauthorized: "Der Relay hat diese Erweiterung abgelehnt (nicht gekoppelt).",
    errRouteMissing: "Der Relay kennt diese Anfrage nicht.",
    errUpdateRefused: "Der Relay hat den Vorgang abgelehnt.",
    unknownRelayError: "Relay-Fehler: {0}",
    missingKeys: (list) => ` (fehlen: ${list})`,
    errStorageRefused: (detail) => `Einige localStorage-Schlüssel konnten nicht übertragen werden: ${detail}`,
    errNeedHttps: "Bitte öffnen Sie eine öffentliche HTTPS-Website.",
    errNoRelay: "Lokales Relais (Port 8765) läuft nicht.",
    errNoCookies: "Keine Cookies für diese Seite gefunden.",
    errCookiesOutOfScope: "Diese Cookies liegen außerhalb der Berechtigungen der Erweiterung. Lade die Erweiterung neu (chrome://extensions) und versuche es erneut.",
    errRefused: "Übertragung vom lokalen Relais abgelehnt.",
    updateLabel: "Bridge-Aktualisierung",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Aktualisierung",
    updateChipOk: "Aktuell",
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
    errExtDirMissing: 'Erweiterungsordner nicht gefunden',
    errExtDirReadonly: 'Erweiterungsordner ist schreibgeschützt',
    errNothingToInstall: 'Nichts zu installieren: bereits aktuell',
    errChecksumMismatch: 'Prüfsumme falsch: Download wurde abgelehnt',
    errArtifactTooLarge: 'Das heruntergeladene Artefakt ist zu groß',
    errRedirectRefused: 'Der Update-Server hat die Weiterleitung abgelehnt',
    errUpdateSourceRefused: 'Unbekannte Update-Quelle',
    errReleaseNotFound: 'Keine veröffentlichte Release gefunden',
    errMainNotFound: 'Main-Branch nicht gefunden',
    errNoBackup: 'Keine Sicherung zum Wiederherstellen',
    errArchiveRefused: 'Das heruntergeladene Archiv ist keine gültige Erweiterung',
    updateGitHubDown: 'GitHub hat nicht geantwortet',
    updateRateLimited: 'GitHub-Limit erreicht · später erneut versuchen',
    updateBranchUnknown: 'Zweigzustand nicht lesbar · nur die Release wurde verglichen',
    updateSameBytes: "Identisch mit dem ver\u00f6ffentlichten Release \u00b7 main ist weitergezogen",
    footerTag: "Isoliertes Profil · Localhost CDP",
    sessionsLabel: "Aktive Sitzungen in Lightpanda",
    sessionsEmpty: "Keine Sitzungen in Lightpanda synchronisiert.",
    sessionsClear: (n) => `Alle löschen (${n})`,
    sessionsClearShort: "Alle entfernen",
    clearConfirmShort: "Bestätigen?",
    sessionRemove: "Diese Sitzung entfernen"
  },
  zh: {
    sessionCookieUnit: (n) => `${n} 个 Cookie`,
    sessionCookieOne: (n) => `${n} 个 Cookie`,
    sessionExpired: "已过期",
    code: "ZH",
    relayChecking: "检查中…",
    relayOnline: "中继在线",
    relayOffline: "中继离线",
    relayOffline: "中继离线",
    relayIdle: "未连接",
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
    diagBtn: "复制诊断信息",
    diagCopied: "诊断信息已复制",
    diagFailed: "复制失败",
    errRelayTimeout: '中继未响应（Lightpanda 正在重启？）。请重试。',
    errRelayUnreachable: "无法连接中继（它是否在运行？）。",
    errOriginRefused: "中继拒绝了该站点的来源。",
    errUnauthorized: "中继拒绝了此扩展（未配对）。",
    errRouteMissing: "中继不认识此请求。",
    errUpdateRefused: "中继拒绝了更新操作。",
    unknownRelayError: "中继错误：{0}",
    missingKeys: (list) => ` (缺失: ${list})`,
    errStorageRefused: (detail) => `部分 localStorage 键无法传输：${detail}`,
    errNeedHttps: "请打开公开的 HTTPS 网站（例如 Gmail、A6API）。",
    errNoRelay: "本地中继（端口 8765）未启动。",
    errNoCookies: "未找到此页面的 Cookie。",
    errCookiesOutOfScope: "这些 Cookie 超出扩展程序的权限范围。请重新加载扩展程序（chrome://extensions）后重试。",
    errRefused: "本地中继拒绝了传输。",
    updateLabel: "Bridge 更新",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "有更新",
    updateChipOk: "已是最新",
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
    errExtDirMissing: '未找到扩展文件夹',
    errExtDirReadonly: '扩展文件夹为只读',
    errNothingToInstall: '无需安装：已是最新',
    errChecksumMismatch: '校验和不匹配：下载已被拒绝',
    errArtifactTooLarge: '下载的构件过大',
    errRedirectRefused: '更新服务器拒绝了重定向',
    errUpdateSourceRefused: '未知的更新来源',
    errReleaseNotFound: '未找到已发布版本',
    errMainNotFound: '未找到 main 分支',
    errNoBackup: '没有可恢复的备份',
    errArchiveRefused: '下载的压缩包不是有效的扩展',
    updateGitHubDown: 'GitHub 未响应',
    updateRateLimited: '已达 GitHub 限额 · 请稍后再试',
    updateBranchUnknown: '无法读取分支状态 · 仅比较了已发布版本',
    updateSameBytes: "\u4e0e\u5df2\u53d1\u5e03\u7248\u672c\u5b8c\u5168\u4e00\u81f4 \u00b7 main \u5df2\u524d\u8fdb",
    footerTag: "隔离配置文件 · 本地 CDP",
    sessionsLabel: "Lightpanda 中的活动会话",
    sessionsEmpty: "Lightpanda 中没有已同步的会话。",
    sessionsClear: (n) => `清除全部（${n}）`,
    sessionsClearShort: "全部清除",
    clearConfirm: "再次点击以清除全部",
    clearedToast: "所有会话已清除",
    clearConfirmShort: "确认？",
    sessionRemove: "移除此会话"
  },
  ja: {
    sessionCookieUnit: (n) => `${n} Cookie`,
    sessionCookieOne: (n) => `${n} Cookie`,
    sessionExpired: "期限切れ",
    code: "JA",
    relayChecking: "確認中…",
    relayOnline: "リレー オンライン",
    relayOffline: "リレー オフライン",
    relayOffline: "リレー オフライン",
    relayIdle: "未接続",
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
    diagBtn: "診断情報をコピー",
    diagCopied: "診断情報をコピーしました",
    diagFailed: "コピーに失敗しました",
    errRelayTimeout: 'リレーが応答しませんでした（Lightpanda再起動中？）。もう一度お試しください。',
    errRelayUnreachable: "リレーに接続できません（起動していますか？）。",
    errOriginRefused: "リレーがこのサイトのオリジンを拒否しました。",
    errUnauthorized: "リレーがこの拡張機能を拒否しました（未ペアリング）。",
    errRouteMissing: "リレーはこのリクエスト知りません。",
    errUpdateRefused: "リレーが更新操作を拒否しました。",
    unknownRelayError: "リレーエラー：{0}",
    missingKeys: (list) => ` (欠落: ${list})`,
    errStorageRefused: (detail) => `一部の localStorage キーを転送できませんでした：${detail}`,
    errNeedHttps: "公開HTTPSサイト（Gmail、A6APIなど）を開いてください。",
    errNoRelay: "ローカルリレー（ポート8765）が起動していません。",
    errNoCookies: "このページのCookieが見つかりません。",
    errCookiesOutOfScope: "これらのCookieは拡張機能の権限範囲外です。拡張機能を再読み込み（chrome://extensions）して再試行してください。",
    errRefused: "ローカルリレーによって転送が拒否されました。",
    updateLabel: "Bridge の更新",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "更新あり",
    updateChipOk: "最新",
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
    errExtDirMissing: '拡張機能フォルダが見つかりません',
    errExtDirReadonly: '拡張機能フォルダは読み取り専用です',
    errNothingToInstall: 'インストールするものがありません：すでに最新です',
    errChecksumMismatch: 'チェックサムの不一致：ダウンロードは拒否されました',
    errArtifactTooLarge: 'ダウンロードしたアーティファクトが大きすぎます',
    errRedirectRefused: '更新サーバーがリダイレクトを拒否しました',
    errUpdateSourceRefused: '不明な更新ソース',
    errReleaseNotFound: '公開されたリリースが見つかりません',
    errMainNotFound: 'main ブランチが見つかりません',
    errNoBackup: '復元するバックアップがありません',
    errArchiveRefused: 'ダウンロードしたアーカイブは有効な拡張機能ではありません',
    updateGitHubDown: 'GitHub が応答しませんでした',
    updateRateLimited: 'GitHub の上限に達しました · 後で再試行',
    updateBranchUnknown: 'ブランチの状態が読めません · リリースのみ比較しました',
    updateSameBytes: "\u516c\u958b\u30ea\u30ea\u30fc\u30b9\u3068\u540c\u3058 \u00b7 main \u306f\u9032\u6358\u3057\u307e\u3057\u305f",
    footerTag: "分離プロファイル · Localhost CDP",
    sessionsLabel: "Lightpanda内のアクティブなセッション",
    sessionsEmpty: "Lightpandaに同期されたセッションはありません。",
    sessionsClear: (n) => `すべて削除（${n}）`,
    sessionsClearShort: "すべて削除",
    clearConfirm: "もう一度クリックで全て削除",
    clearedToast: "すべてのセッションを削除しました",
    clearConfirmShort: "確認？",
    sessionRemove: "このセッションを削除"
  },
  it: {
    clearConfirm: "Clicca di nuovo per cancellare tutto",
    clearedToast: "Tutte le sessioni cancellate",
    sessionCookieUnit: (n) => `${n} cookie`,
    sessionCookieOne: (n) => `${n} cookie`,
    sessionExpired: "scaduta",
    code: "IT",
    relayChecking: "Verifica…",
    relayOnline: "Relè Online",
    relayOffline: "Relè Offline",
    relayOffline: "Relè Offline",
    relayIdle: "Non connesso",
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
    diagBtn: "Copia diagnostica",
    diagCopied: "Diagnostica copiata",
    diagFailed: "Copia non riuscita",
    errRelayTimeout: 'Il relay non ha risposto (Lightpanda in riavvio?). Riprova.',
    errRelayUnreachable: "Impossibile raggiungere il relay (è in esecuzione?).",
    errOriginRefused: "Il relay ha rifiutato l'origine di questo sito.",
    errUnauthorized: "Il relay ha rifiutato questa estensione (non associata).",
    errRouteMissing: "Il relay non riconosce questa richiesta.",
    errUpdateRefused: "Il relay ha rifiutato l'operazione di aggiornamento.",
    unknownRelayError: "Errore del relay: {0}",
    missingKeys: (list) => ` (mancanti: ${list})`,
    errStorageRefused: (detail) => `Alcune chiavi localStorage non sono state trasferite: ${detail}`,
    errNeedHttps: "Apri un sito HTTPS pubblico (es. Gmail, A6API).",
    errNoRelay: "Il relè locale (porta 8765) non è attivo.",
    errNoCookies: "Nessun cookie trovato per questa pagina.",
    errCookiesOutOfScope: "Questi cookie sono fuori dai permessi dell'estensione. Ricarica l'estensione (chrome://extensions) e riprova.",
    errRefused: "Trasferimento rifiutato dal relè locale.",
    updateLabel: "Aggiornamento Bridge",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Aggiornamento",
    updateChipOk: "Aggiornato",
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
    errExtDirMissing: 'Cartella dell\'estensione non trovata',
    errExtDirReadonly: 'La cartella dell\'estensione è in sola lettura',
    errNothingToInstall: 'Niente da installare: già aggiornato',
    errChecksumMismatch: 'Checksum non corrispondente: download rifiutato',
    errArtifactTooLarge: 'L\'artefatto scaricato è troppo grande',
    errRedirectRefused: 'Il server di aggiornamento ha rifiutato il reindirizzamento',
    errUpdateSourceRefused: 'Sorgente di aggiornamento sconosciuta',
    errReleaseNotFound: 'Nessuna release pubblicata trovata',
    errMainNotFound: 'Ramo main non trovato',
    errNoBackup: 'Nessun backup da ripristinare',
    errArchiveRefused: 'L\'archivio scaricato non è un\'estensione valida',
    updateGitHubDown: 'GitHub non ha risposto',
    updateRateLimited: 'Limite GitHub raggiunto · riprova più tardi',
    updateBranchUnknown: 'Stato del ramo illeggibile · solo la release è stata confrontata',
    updateSameBytes: "Identico alla release pubblicata \u00b7 main \u00e8 avanzato",
    footerTag: "Profilo isolato · Localhost CDP",
    sessionsLabel: "Sessioni attive in Lightpanda",
    sessionsEmpty: "Nessuna sessione sincronizzata in Lightpanda.",
    sessionsClear: (n) => `Rimuovi tutte (${n})`,
    sessionsClearShort: "Rimuovi tutto",
    clearConfirmShort: "Confermare?",
    sessionRemove: "Rimuovi questa sessione"
  },
  pt: {
    clearConfirm: "Clique novamente para limpar tudo",
    clearedToast: "Todas as sessões apagadas",
    sessionCookieUnit: (n) => `${n} cookies`,
    sessionCookieOne: (n) => `${n} cookie`,
    sessionExpired: "expirada",
    code: "PT",
    relayChecking: "Verificando…",
    relayOnline: "Relé Online",
    relayOffline: "Relé Offline",
    relayOffline: "Relé Offline",
    relayIdle: "Não conectado",
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
    diagBtn: "Copiar diagnóstico",
    diagCopied: "Diagnóstico copiado",
    diagFailed: "Falha ao copiar",
    errRelayTimeout: 'O relay não respondeu (Lightpanda reiniciando?). Tente novamente.',
    errRelayUnreachable: "Não foi possível contatar o relay (ele está rodando?).",
    errOriginRefused: "O relay recusou a origem deste site.",
    errUnauthorized: "O relay rejeitou esta extensão (não pareada).",
    errRouteMissing: "O relay não conhece este pedido.",
    errUpdateRefused: "O relay recusou a operação de atualização.",
    unknownRelayError: "Erro do relay: {0}",
    missingKeys: (list) => ` (faltando: ${list})`,
    errStorageRefused: (detail) => `Algumas chaves de localStorage não puderam ser transferidas: ${detail}`,
    errNeedHttps: "Abra um site HTTPS público (ex: Gmail, A6API).",
    errNoRelay: "O relé local (porta 8765) não está em execução.",
    errNoCookies: "Nenhum cookie encontrado para esta página.",
    errCookiesOutOfScope: "Estes cookies estão fora das permissões da extensão. Recarregue a extensão (chrome://extensions) e tente novamente.",
    errRefused: "Transferência recusada pelo relé local.",
    updateLabel: "Atualização do Bridge",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Atualização",
    updateChipOk: "Atualizado",
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
    errExtDirMissing: 'Pasta da extensão não encontrada',
    errExtDirReadonly: 'A pasta da extensão é somente leitura',
    errNothingToInstall: 'Nada para instalar: já está atualizado',
    errChecksumMismatch: 'Soma de verificação incompatível: download recusado',
    errArtifactTooLarge: 'O artefato baixado é muito grande',
    errRedirectRefused: 'O servidor de atualização recusou o redirecionamento',
    errUpdateSourceRefused: 'Fonte de atualização desconhecida',
    errReleaseNotFound: 'Nenhuma release publicada encontrada',
    errMainNotFound: 'Ramo main não encontrado',
    errNoBackup: 'Nenhum backup para restaurar',
    errArchiveRefused: 'O arquivo baixado não é uma extensão válida',
    updateGitHubDown: 'O GitHub não respondeu',
    updateRateLimited: 'Limite do GitHub atingido · tente mais tarde',
    updateBranchUnknown: 'Estado da branch ilegível · apenas a release foi comparada',
    updateSameBytes: "Id\u00e9ntico \u00e0 release publicada \u00b7 o main avan\u00e7ou",
    footerTag: "Perfil isolado · Localhost CDP",
    sessionsLabel: "Sessões ativas no Lightpanda",
    sessionsEmpty: "Nenhuma sessão sincronizada no Lightpanda.",
    sessionsClear: (n) => `Limpar todas (${n})`,
    sessionsClearShort: "Remover tudo",
    clearConfirmShort: "Confirmar?",
    sessionRemove: "Remover esta sessão"
  },
  ar: {
    sessionCookieUnit: (n) => `${n} ملف تعريف ارتباط`,
    sessionCookieOne: (n) => `${n} ملف تعريف ارتباط`,
    sessionExpired: "منتهية",
    code: "AR",
    relayChecking: "جاري الفحص…",
    relayOnline: "المرحل متصل",
    relayOffline: "المرحل غير متصل",
    relayOffline: "المرحل غير متصل",
    relayIdle: "غير متصل",
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
    diagBtn: "نسخ التشخيص",
    diagCopied: "تم نسخ التشخيص",
    diagFailed: "فشل النسخ",
    errRelayTimeout: 'لم يستجب المرجع (هل يعيد Lightpanda التشغيل؟). حاول مرة أخرى.',
    errRelayUnreachable: "تعذر الوصول إلى الوسيط (هل يعمل؟).",
    errOriginRefused: "رفض الوسيط أصل هذا الموقع.",
    errUnauthorized: "رفض الوسيط هذا الامتداد (غير مقترن).",
    errRouteMissing: "لا يعرف الوسيط هذا الطلب.",
    errUpdateRefused: "رفض الوسيط عملية التحديث.",
    unknownRelayError: "خطأ الوسيط: {0}",
    missingKeys: (list) => ` (المفقودة: ${list})`,
    errStorageRefused: (detail) => `تعذّر نقل بعض مفاتيح localStorage: ${detail}`,
    errNeedHttps: "يرجى فتح موقع HTTPS عام.",
    errNoRelay: "المرحل المحلي (المنفذ 8765) لا يعمل.",
    errNoCookies: "لم يتم العثور على ملفات تعريف الارتباط.",
    errCookiesOutOfScope: "ملفات تعريف الارتباط هذه خارج نطاق أذونات الإضافة. أعد تحميل الإضافة (chrome://extensions) ثم أعد المحاولة.",
    errRefused: "تم رفض النقل بواسطة المرحل المحلي.",
    updateLabel: "تحديث Bridge",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "تحديث",
    updateChipOk: "محدّث",
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
    errExtDirMissing: 'مجلد الامتداد غير موجود',
    errExtDirReadonly: 'مجلد الامتداد للقراءة فقط',
    errNothingToInstall: 'لا شيء لتثبيته: محدث بالفعل',
    errChecksumMismatch: 'عدم تطابق المجموع الاختباري: تم رفض التنزيل',
    errArtifactTooLarge: 'حجم الملف الذي نُزّل كبير جدًا',
    errRedirectRefused: 'رفض خادم التحديث إعادة التوجيه',
    errUpdateSourceRefused: 'مصدر تحديث غير معروف',
    errReleaseNotFound: 'لم يُعثر على إصدار منشور',
    errMainNotFound: 'لم يُعثر على فرع main',
    errNoBackup: 'لا يوجد نسخة احتياطية للاستعادة',
    errArchiveRefused: 'الأرشيف المنزّل ليس امتدادًا صالحًا',
    updateGitHubDown: 'لم يستجب GitHub',
    updateRateLimited: 'تم بلوغ حد GitHub · أعد المحاولة لاحقاً',
    updateBranchUnknown: 'حالة الفرع غير قابلة للقراءة · تمت مقارنة الإصدار المنشور فقط',
    updateSameBytes: "\u0645\u0637\u0627\u0628\u0642 \u0644\u0644\u0625\u0637\u0644\u0627\u0642 \u0627\u0644\u0645\u0646\u0634\u0648\u0631 \u00b7 main \u062a\u0642\u062f\u0645",
    footerTag: "ملف تعريف معزول · Localhost CDP",
    sessionsLabel: "الجلسات النشطة في Lightpanda",
    sessionsEmpty: "لا توجد جلسات متزامنة في Lightpanda.",
    sessionsClear: (n) => `إزالة الكل (${n})`,
    sessionsClearShort: "إزالة الكل",
    clearConfirm: "انقر مرة أخرى لمسح الكل",
    clearedToast: "تم مسح جميع الجلسات",
    clearConfirmShort: "تأكيد؟",
    sessionRemove: "إزالة هذه الجلسة"
  },
  ru: {
    clearConfirm: "Нажмите ещё раз, чтобы очистить всё",
    clearedToast: "Все сессии удалены",
    sessionCookieUnit: (n) => `${n} cookie`,
    sessionCookieOne: (n) => `${n} cookie`,
    sessionExpired: "истекла",
    code: "RU",
    relayChecking: "Проверка…",
    relayOnline: "Реле онлайн",
    relayOffline: "Реле офлайн",
    relayOffline: "Реле офлайн",
    relayIdle: "Не подключено",
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
    diagBtn: "Скопировать диагностику",
    diagCopied: "Диагностика скопирована",
    diagFailed: "Не удалось скопировать",
    errRelayTimeout: 'Реле не ответило (Lightpanda перезапускается?). Повторите попытку.',
    errRelayUnreachable: "Не удалось связаться с реле (оно запущено?).",
    errOriginRefused: "Реле отклонило источник этого сайта.",
    errUnauthorized: "Реле отклонило это расширение (не сопряжено).",
    errRouteMissing: "Реле не знает этот запрос.",
    errUpdateRefused: "Реле отклонило операцию обновления.",
    unknownRelayError: "Ошибка реле: {0}",
    missingKeys: (list) => ` (отсутствуют: ${list})`,
    errStorageRefused: (detail) => `Некоторые ключи localStorage не удалось перенести: ${detail}`,
    errNeedHttps: "Откройте общедоступный сайт HTTPS (например, Gmail, A6API).",
    errNoRelay: "Локальное реле (порт 8765) не запущено.",
    errNoCookies: "Файлы cookie для этой страницы не найдены.",
    errCookiesOutOfScope: "Эти файлы cookie вне разрешений расширения. Перезагрузите расширение (chrome://extensions) и повторите попытку.",
    errRefused: "Перенос отклонен локальным реле.",
    updateLabel: "Обновление Bridge",
    // Puce = etat court. La version/le hash vit sur la ligne du dessous :
    // afficher les deux repetait la meme info dans une carte etroite.
    updateChipNew: "Обновление",
    updateChipOk: "Актуально",
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
    errExtDirMissing: 'Папка расширения не найдена',
    errExtDirReadonly: 'Папка расширения доступна только для чтения',
    errNothingToInstall: 'Нечего устанавливать: уже обновлено',
    errChecksumMismatch: 'Несовпадение контрольной суммы: загрузка отклонена',
    errArtifactTooLarge: 'Загруженный файл слишком велик',
    errRedirectRefused: 'Сервер обновлений отклонил перенаправление',
    errUpdateSourceRefused: 'Неизвестный источник обновления',
    errReleaseNotFound: 'Опубликованный релиз не найден',
    errMainNotFound: 'Ветка main не найдена',
    errNoBackup: 'Нет резервной копии для восстановления',
    errArchiveRefused: 'Загруженный архив не является корректным расширением',
    updateGitHubDown: 'GitHub не ответил',
    updateRateLimited: 'Лимит GitHub исчерпан · попробуйте позже',
    updateBranchUnknown: 'Состояние ветки не прочитано · сравнен только релиз',
    updateSameBytes: "\u0418\u0434\u0435\u043d\u0442\u0438\u0447\u043d\u043e \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d\u043d\u043e\u0439 \u0432\u0435\u0440\u0441\u0438\u0438 \u00b7 main \u0440\u0430\u0441\u0448\u0438\u0440\u0438\u043b\u0441\u044f",
    footerTag: "Изолированный профиль · Localhost CDP",
    sessionsLabel: "Активные сеансы в Lightpanda",
    sessionsEmpty: "Нет сеансов, синхронизированных с Lightpanda.",
    sessionsClear: (n) => `Удалить все (${n})`,
    sessionsClearShort: "Удалить все",
    clearConfirmShort: "Подтвердить?",
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
const diagText = document.querySelector('#diag-text');
const diagBtn = document.querySelector('#diag-btn');
// Le libelle est TOUJOURS ecrit dans le <span> interne : ecrire sur le bouton
// lui-meme remplacait son contenu et detachait le span au premier clic.
const labelClear = () => t('sessionsClearShort');
// Bridge update UI (the relay does the download; this is only the button)
const updateChip = document.querySelector('#update-chip');
const updateVersion = document.querySelector('#update-version');
const updateMeta = document.querySelector('#update-meta');
const updateBtn = document.querySelector('#update-btn');
const rollbackBtn = document.querySelector('#rollback-btn');
const labelUpdate = document.querySelector('#label-update');
const appVersion = document.querySelector('#app-version');

// Resolved LAZILY: the <script> tag sits BEFORE <div id="toast"> in the
// document, and it is a classic script (no defer, not a module), so at module
// evaluation time the element does not exist yet. Capturing it once at load gave
// null FOREVER, `showToast` returned early on every call, and all three callers
// ("Tout retirer" confirmation, copy-diagnostic success and failure) wrote to a
// dead element: the action happened, with no feedback at all.
let toastEl = null;
let toastTimer = null;
function showToast(msg) {
  if (!toastEl) toastEl = document.querySelector('#toast');
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl && toastEl.classList.remove('show'), 2600);
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
    const res = await relayFetch('/v1/bootstrap', { method: 'GET', cache: 'no-store' });
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

// Every relay call must END, one way or another.
//
// Seven of the eight fetches in this popup had no deadline at all. A relay that
// accepts the TCP connection and then says nothing - which is exactly what a
// wedged or restarting daemon does - left the popup on a hardcoded "Checking..."
// with an undifferentiated badge, forever, with /health never even attempted.
// A spinner is not a status (skill pitfall 10).
//
// The deadline is deliberately LONGER than the relay's own (10s body reads,
// 15s class deadline): the relay should get to answer with a real, translated
// error first. It exists only for the case where the relay dies mid-request,
// where the alternative is a popup that can never recover. Aborting earlier
// than the relay turns a specific message into a bare "Failed to fetch".
const RELAY_TIMEOUT_MS = 45000;

// Shortest gap between two badge refreshes. The popup can be closed and reopened
// faster than the 30s cadence, and a burst of visibilitychange events would
// otherwise fire one /health request each.
const RELAY_MIN_CHECK_GAP_MS = 2000;

// Name of the abort we raise, so callers can tell "the relay went silent" from
// "the network refused". A bare TypeError('Failed to fetch') is not actionable
// and is not translated.
class RelayTimeoutError extends Error {
  constructor() {
    super('relay-timeout');
    this.name = 'RelayTimeoutError';
  }
}

// The relay answers in short English codes. Rendering them verbatim put an
// English sentence inside a translated popup, which is a defect in a product
// shipped in 10 languages. Map the codes the relay can actually emit (read off
// relay/server.py, not guessed) to translated keys; an unknown code still
// surfaces, but inside a translated frame rather than as raw relay prose.
//
// `str(err)` from Python is free text and CANNOT be mapped - it may be a
// localized OS sentence. So it is never rendered raw: it lands in a translated
// frame that names the operation instead of quoting untranslatable prose.
const RELAY_ERROR_KEYS = {
  'origin refused': 'errOriginRefused',
  'unauthorized': 'errUnauthorized',
  'not found': 'errRouteMissing',
  'session import refused': 'errRefused',
  'clear refused': 'errRefused',
  'cdp call refused': 'errRefused',
  'update refused': 'errUpdateRefused',
  'update check failed': 'errUpdateRefused',
  'rollback refused': 'errUpdateRefused',
  // The update path's own codes, read out of relay/updater.py. Measured
  // 0.7.25: nineteen of them were unmapped, and `relayErrorText` was never
  // called from `runUpdate` anyway - so a refused checksum, a refused origin
  // and a dead relay all rendered "Relay Offline (is it running?)". Mapped by
  // CAUSE, not one key per string: eight archive refusals are one problem
  // (the artifact is not a valid MV3 extension), and telling a user their
  // download "was not a Manifest V3 extension" teaches them nothing.
  'extension directory not found': 'errExtDirMissing',
  'extension directory is not writable': 'errExtDirReadonly',
  'nothing to install: already up to date': 'errNothingToInstall',
  'checksum mismatch: artifact refused': 'errChecksumMismatch',
  'update artifact too large': 'errArtifactTooLarge',
  'update redirect refused': 'errRedirectRefused',
  'update source refused': 'errUpdateSourceRefused',
  'release not found': 'errReleaseNotFound',
  'main branch not found': 'errMainNotFound',
  'no backup to restore': 'errNoBackup',
  'archive refused: absolute path': 'errArchiveRefused',
  'archive refused: incomplete tree': 'errArchiveRefused',
  'archive refused: no extension/manifest.json inside': 'errArchiveRefused',
  'archive refused: not a Manifest V3 extension': 'errArchiveRefused',
  'archive refused: path traversal': 'errArchiveRefused',
  'archive refused: unexpected extension name': 'errArchiveRefused',
  'archive refused: unparsable version': 'errArchiveRefused',
  'archive refused: unreadable manifest.json': 'errArchiveRefused',
  'refused: write outside the extension directory': 'errArchiveRefused'
};

function relayErrorText(code) {
  if (!code) return t('errRefused');
  const key = RELAY_ERROR_KEYS[String(code).trim().toLowerCase()];
  if (key) return t(key);
  // Unknown code: keep it visible but translated-framed. `unknownRelayError`
  // takes the code as a parameter so nothing is silently dropped.
  return t('unknownRelayError', code);
}

async function relayFetch(path, options) {
  const opts = options || {};
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), RELAY_TIMEOUT_MS);
  try {
    return await fetch(`${RELAY}${path}`, Object.assign({}, opts, {
      signal: controller.signal
    }));
  } catch (err) {
    if (err && (err.name === 'AbortError' || err.name === 'RelayTimeoutError')) {
      throw new RelayTimeoutError();
    }
    throw err;
  } finally {
    clearTimeout(deadline);
  }
}

function t(key, ...args) {
  const dict = I18N[currentLanguage] || I18N.en;
  const val = dict[key] || I18N.en[key] || "";
  // Measured 0.7.25: only FUNCTION values got their arguments substituted, so a
  // string written as "Relay error: {0}" reached the screen with the literal
  // {0} still in it - the code was NEVER shown. `unknownRelayError` was the
  // only key in that shape, so this is its second fault, not a first.
  // Both shapes work from here on: a function is called, a string is formatted.
  // `{0}` is the only placeholder - no key needs more than one.
  if (typeof val === 'function') return val(...args);
  if (args.length && typeof val === 'string' && val.includes('{0}')) {
    return val.replace('{0}', args[0]);
  }
  return val;
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
  // Libelles poses par le rendu (pas par le HTML) : sans ca, un changement
  // de langue les laissait dans l'ancienne langue.
  if (clearText && !sessionsClear.dataset.armed) clearText.textContent = labelClear();
  // Diagnostic button: same trap as the labels above - the HTML ships one
  // language, so without this it stayed French in the other nine.
  if (diagText) diagText.textContent = t('diagBtn');
  renderUpdateCard();

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
    const res = await relayFetch('/health', { method: 'GET', cache: 'no-store' });
    if (res.ok) {
      // Three states, not two. The relay can be perfectly reachable while its
      // CDP connection to Lightpanda is dead - and then every sync fails while
      // the badge said "online". v0.6.1 made the relay honest about that; the
      // popup has to pass the truth on instead of only looking at res.ok.
      let attached = true;
      try {
        const data = await res.json();
        if (typeof data.attached === 'boolean') attached = data.attached;
      } catch (_) { /* old relay without the field: keep the old behaviour */ }
      if (!attached) {
        // 'idle', not 'offline': the relay process is alive and answering. The
        // amber badge is the honest third state - red here would report an
        // outage that is not happening, green would promise a sync that cannot
        // succeed yet.
        relayBadge.className = 'badge idle';
        relayText.textContent = t('relayIdle');
        return true;
      }
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
    const res = await relayFetch('/v1/sessions', {
      method: 'GET', cache: 'no-store', headers: bridgeHeaders()
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.ok ? data : null;
  } catch (_) { return null; }
}

function fmtExpiry(ts) {
  // Read the clock ONCE: `Date.now()` called twice in one expression can straddle
  // a tick and print an hour less than the truth (measured "~3h" for a 3h session).
  const left = ts * 1000 - Date.now();
  // Days ROUND UP - a session with 1.5 days left is more usefully "2d" than "1d",
  // because "1d" reads as if it dies sooner than it does.
  if (left >= 86400000) return `~${Math.ceil(left / 86400000)}d`;
  // Hours TRUNCATE - rounding a countdown up promises time that is not there:
  // 40 minutes left read "~1h". Truncating is the honest direction for a clock
  // that is running down.
  if (left >= 3600000) return `~${Math.floor(left / 3600000)}h`;
  // Under an hour, minutes are the useful unit. The old code clamped everything
  // below an hour to "<1h", which is true of 40 minutes and useless.
  return `~${Math.max(1, Math.floor(left / 60000))}m`;
}


// Every property the clear button owns, in one place. Measured 0.7.29: the
// empty-list branch reset `style.display` alone while this one reset four
// properties, so an ARMED button ("Confirm?") survived a refresh that emptied
// the list and the next click wiped every synced session with no confirmation.
// The two-step confirmation is a SAFETY property, so its state must be owned by
// the list's state and never inherited - and with one function, a future branch
// cannot forget the third property either.
function resetClearButton(display = 'none') {
  delete sessionsClear.dataset.armed;
  sessionsClear.removeAttribute('title');
  clearText.textContent = labelClear();
  sessionsClear.style.display = display;
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
    // This branch owns the WHOLE button state, not just its visibility.
    // Measured 0.7.29: it reset `style.display` alone, so a button the user had
    // already ARMED for confirmation kept `dataset.armed`, its `title` and its
    // "Confirm?" wording across a refresh that emptied the list - and the next
    // click then wiped every synced session with no confirmation at all. The
    // full-list branch below resets all four; this one must too. Same rule as
    // 0.7.27 (title) and 0.7.28 (button wording): a value belongs to a state,
    // and every branch must own it or deliberately leave it alone.
    resetClearButton();
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
    // Both words are translated keys: "cookies" and "expired" were English
    // literals in a ten-language panel, so a French user read
    // "1 cookies · expired" - the one line that tells them whether the session
    // they are relying on is still alive.
    meta.textContent = t(s.cookie_count === 1 ? 'sessionCookieOne' : 'sessionCookieUnit', s.cookie_count) +
      (s.expires && !s.expired ? ` · ${fmtExpiry(s.expires)}` : '') +
      (s.expired ? ` · ${t('sessionExpired')}` : '');
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

  resetClearButton('inline-flex');
}

async function clearSessionsOnRelay(origin = null) {
  try {
    const body = origin ? { origin } : {};
    const res = await relayFetch('/v1/sessions/clear', {
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
  const open = sessionsCard.classList.toggle('open');
  sessionsToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open) refreshSessions();
});

sessionsClear.addEventListener('click', async () => {
  // Two-step confirmation so a mis-click never wipes every synced session.
  if (!sessionsClear.dataset.armed) {
    sessionsClear.dataset.armed = '1';
    clearText.textContent = t('clearConfirmShort');
    sessionsClear.title = t('clearConfirm');
    setTimeout(() => {
      if (sessionsClear.dataset.armed) {
        delete sessionsClear.dataset.armed;
        clearText.textContent = labelClear();
        sessionsClear.removeAttribute('title');
      }
    }, 3500);
    return;
  }
  delete sessionsClear.dataset.armed;
  clearText.textContent = labelClear();
  sessionsClear.removeAttribute('title');
  sessionsClear.disabled = true;
  await clearSessionsOnRelay(null);
  await refreshSessions();
  showToast(t('clearedToast'));
  sessionsClear.disabled = false;
});

// Keep BOTH panels honest while the popup stays open.
//
// The badge used to be sampled once, in init(), and never again: a relay that
// died (or a Lightpanda that restarted) after the popup opened left "Relay
// Online" on screen for as long as the panel stayed open - so the one check the
// user reads first was the one thing that went stale. The third state from
// v0.6.1 ('idle': relay alive, CDP dead) was therefore unreachable except in the
// few hundred milliseconds after opening.
//
// One cadence, both refreshes, and only while visible: a hidden popup must not
// spend the relay's budget on nothing.
setInterval(() => {
  if (document.visibilityState !== 'visible' || !bridgeToken) return;
  refreshSessions();
  checkRelay();
}, 30000);

// Re-check on the way back in. Opening the popup is the moment a user most often
// reacts to something having just broken (Lightpanda restarted, relay relaunched
// after an update), and a stale badge is worse than no badge. Coalesced onto the
// same tick as the interval so a fast close/reopen cannot pile up requests.
let lastRelayCheck = 0;
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible' || !bridgeToken) return;
  const since = Date.now() - lastRelayCheck;
  if (since < RELAY_MIN_CHECK_GAP_MS) return;
  lastRelayCheck = Date.now();
  checkRelay();
  refreshSessions();
});

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
  // A tooltip belongs to a STATE, so every state owns it. Measured 0.7.27: only
  // two of the three exits below wrote `updateMeta.title`, and the node kept
  // whatever the previous render gave it. The relay's own words ("API rate limit
  // exceeded for 203.0.113.9") therefore kept hovering over a card that had
  // become perfectly healthy - and survived the whole install, because
  // `runUpdate` renders with `updateBusy` true, which is the branch that
  // returned without touching it. Seed the empty title HERE, so a branch can
  // only ever refuse it deliberately: the same rule as seeding `shipped_tree` in
  // the relay's result dict (points 64/66), applied to the DOM.
  updateMeta.title = '';
  // Same rule for the button's own wording, measured 0.7.28: it was written ONLY
  // in the `update_available` branch, so the three other exits left it holding
  // the version a previous render offered - "Installer v0.7.28" - on a button
  // they hide. A branch update has its OWN wording (`updateBtnMain`, which names
  // no version at all), and it inherits the release wording when it arrives
  // second. Seed it here so the wording is owned by the state, never inherited.
  updateBtn.textContent = '';
  const deployed = chrome.runtime.getManifest().version;
  updateVersion.textContent = 'v' + deployed;

  if (updateBusy) {
    updateChip.className = 'update-chip';
    updateChip.textContent = '…';
    updateMeta.textContent = '';
    return;
  }

  // Two DIFFERENT failures arrive as `!updateInfo.ok` (measured 0.7.24), and
  // they are not the same thing. `updateInfo === null` means the relay did not
  // answer (it is down, or not started); `updateInfo.ok === false` with an
  // `error` means the relay answered FINE and the failure is upstream - GitHub
  // refused, rate limit reached. Both used to render "Relay Offline", which
  // sends the user to debug their own installation while /health returns 200.
  // `error_kind` is published by the relay and was never read here.
  if (!updateInfo || !updateInfo.ok) {
    const upstream = !!(updateInfo && !updateInfo.ok && updateInfo.error);
    const kind = (updateInfo && updateInfo.error_kind) || '';
    updateChip.className = 'update-chip' + (upstream ? '' : ' off');
    updateChip.textContent = upstream ? t('updateGitHubDown') : t('relayOffline');
    // The relay's own message names the rate limit and the caller's identity;
    // it is a log line, so it belongs in the tooltip, not in the panel - the
    // same rule as the update note (point 59).
    updateMeta.textContent = upstream
      ? t(kind === 'rate_limit' ? 'updateRateLimited' : 'updateGitHubDown')
      : '';
    updateMeta.title = upstream ? String(updateInfo.error || '') : '';
    updateBtn.style.display = 'none';
    rollbackBtn.style.display = 'none';
    return;
  }

  // Icone seule : le libelle complet passe en infobulle.
  rollbackBtn.title = t('updateRollback');
  rollbackBtn.setAttribute('aria-label', t('updateRollback'));
  rollbackBtn.style.display = (updateInfo.backup_available && !updateInfo.update_available) ? '' : 'none';

  // La puce dit l'ETAT ; la ligne du dessous dit CE QU'ON GAGNE.
  // Avant, la puce ET la meta affichaient le meme hash : du bruit dans 430px.
  if (updateInfo.update_available) {
    const fromRelease = updateInfo.source === 'release';
    updateChip.className = 'update-chip new';
    updateChip.textContent = t('updateChipNew');
    updateMeta.textContent = fromRelease
      ? '\u2192 v' + updateInfo.latest_version
      : '\u2192 commit ' + shortCommit(updateInfo.latest_commit);
    updateBtn.textContent = fromRelease
      ? t('updateBtn', updateInfo.latest_version)
      : t('updateBtnMain');
    updateBtn.style.display = '';
    rollbackBtn.style.display = updateInfo.backup_available ? '' : 'none';
  } else {
    updateChip.className = 'update-chip ok';
    updateChip.textContent = t('updateChipOk');
    // Say WHY there is nothing to install. Measured by the relay, never guessed.
    // `shipped_tree: 'same'` covers TWO materially different situations that must
    // not share a sentence:
    //   - main moved on, but only on commits outside extension/ (0.7.19) - "the
    //     branch has moved on" is true and useful;
    //   - the deployed tree IS the tip of main (measured 0.7.21) - nothing moved,
    //     and claiming it did is a lie in the one case where the user is fully
    //     up to date. Same state, different sentence: the relay publishes the same
    //     `same`, and the popup separates them on the two commits it already has.
    // A user reading a bare commit sha cannot tell either apart from "a code
    // change is waiting". The commit stays in the tooltip.
    const atTip = updateInfo.current_commit && updateInfo.latest_commit
      && updateInfo.current_commit === updateInfo.latest_commit;
    // GitHub did not answer for the branch (relay/updater.py, measured
    // 0.7.23). The release lookup DID succeed, so `update_available` is False -
    // but False here means "we could not look", not "nothing is waiting". This
    // must be read BEFORE `atTip`: with `latest_commit` absent, `atTip` is
    // falsy, so the chain below would have fallen through to the versionless
    // chip and printed reassurance we did not measure.
    if (updateInfo.unreachable_branch) {
      updateMeta.textContent = t('updateBranchUnknown');
    } else if (atTip) {
      // `updateUpToDate` interpolates the version; a missing one would render
      // "Up to date · v" with nothing after the v, so fall back to the versionless
      // chip rather than showing a dangling unit.
      updateMeta.textContent = updateInfo.current_version
        ? t('updateUpToDate', updateInfo.current_version)
        : t('updateChipOk');
    } else if (updateInfo.shipped_tree === 'same') {
      updateMeta.textContent = t('updateSameBytes');
    } else if (updateInfo.current_commit) {
      updateMeta.textContent = 'commit ' + shortCommit(updateInfo.current_commit);
    } else {
      updateMeta.textContent = t('updateBaseline');
    }
    updateMeta.title = updateInfo.current_commit
      ? 'commit ' + shortCommit(updateInfo.current_commit)
      : '';
    updateBtn.style.display = 'none';
    // Measured 0.7.26: `rollbackBtn.style.display` was already computed correctly
    // 58 lines above - `(backup_available && !update_available) ? '' : 'none'` -
    // which is EXACTLY the state this branch is in. This line overwrote it with
    // 'none', so undo was reachable only while an update was WAITING and never
    // in the one moment it is useful: right after installing one. The relay
    // measured `backup_available: true` and the popup read the field - then threw
    // the reading away. `updateBtn` legitimately has no button to hide here;
    // `rollbackBtn` does, and hiding it is the defect.
  }
}

async function refreshUpdateStatus() {
  try {
    const res = await relayFetch('/v1/update/check', { cache: 'no-store' });
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
    const res = await relayFetch(path, {
      method: 'POST',
      headers: bridgeHeaders(),
      body: JSON.stringify({ source: 'auto' })
    });
    const data = await res.json();
    // Keep the relay's CODE on the Error so the catch below can translate it.
    // Measured 0.7.25: `new Error(data.error || ...)` was correct here, but the
    // catch replaced the message with "relay unreachable" unconditionally - so a
    // refused checksum, a refused origin, a rate limit and a dead relay all
    // rendered the SAME sentence, and `relayErrorText()` existed but was never
    // called from here (second unread function after `error_kind`).
    if (!res.ok || !data.ok) {
      const err = new Error(data.error || t('errRefused'));
      err.relayCode = data.error || '';
      throw err;
    }
    updateBusy = false;
    setStatus(t(doneKey, data.version || ''), 'success');
    // The new files are on disk; reload so Comet serves them. The popup goes
    // away with the reload - the status line above is the last thing seen.
    setTimeout(() => { try { chrome.runtime.reload(); } catch (_) {} }, 1400);
  } catch (error) {
    updateBusy = false;
    updateBtn.disabled = false;
    rollbackBtn.disabled = false;
    // Three distinct failures, one shape of catch:
    //   - the relay never answered        -> errRelayUnreachable / timeout
    //   - the relay answered and refused  -> translate ITS code
    //   - the relay answered, code unknown -> framed, never silently dropped
    let reason;
    if (error && error.name === 'RelayTimeoutError') {
      reason = t('errRelayTimeout');
    } else if (error && error.relayCode) {
      reason = relayErrorText(error.relayCode);
    } else {
      reason = t('errRelayUnreachable');
    }
    setStatus(t('updateFailed', reason), 'error');
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
  // Measured 0.7.30: the update card's own identity is LOCAL knowledge, but
  // `renderUpdateCard` only ran after `await loadBridgeToken()`, the bootstrap
  // and the relay probe - and `/v1/update/check` answers in 864 ms on the
  // running relay. For that whole window the card showed `v0.5.0`, the literal
  // in `popup.html`, on an extension installed at 0.7.29: twenty-nine versions
  // stale, on the panel whose whole purpose is to say which version you are on.
  // Render it now, with `updateInfo` still null, so the version is right on the
  // first frame; the relay-dependent part arrives when it arrives. The chip is
  // honest meanwhile - "Relay Offline" means "I have not been told yet", the
  // same rule as points 64/67 on the relay side.
  renderUpdateCard();
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

    // Forward each cookie's lifetime to the relay. `chrome.cookies` calls the
    // field `expirationDate`; the relay reads `expires_hint`. Without this
    // rename the number never left the popup, `/v1/sessions` reported
    // `expires: null` for every session (measured over 26s of polling), and the
    // countdown and the expiry warning were unreachable no matter what the
    // relay did. Only the rename: no cookie VALUE is added or moved.
    cookies = cookies.map(c => ({
      ...c,
      expires_hint: typeof c.expirationDate === 'number' ? c.expirationDate : undefined
    }));

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

    // 3. Send payload to Relay (authenticated with shared token).
    //    relayFetch carries the deadline: without one, a relay that never
    //    answers (or an extension reload mid-fetch) left the status line on
    //    "Transferring & verifying…" forever - the popup has no way to say
    //    "still working" honestly, so the sync must end, pass or fail.
    //    This route gets the LONGER budget: it is the only one that makes the
    //    relay talk to Lightpanda (navigate + settle + four injection rounds),
    //    so 10s is its own body deadline and 45s the client-side backstop.
    const payload = { origin, cookies, storage };
    let response, result;
    try {
      response = await relayFetch('/v1/session/import', {
        method: 'POST',
        headers: bridgeHeaders(),
        body: JSON.stringify(payload)
      });
      result = await response.json();
    } catch (fetchErr) {
      // RelayTimeoutError is what relayFetch raises on the deadline; the raw
      // AbortError is kept in the check too in case relayFetch is bypassed.
      if (fetchErr && (fetchErr.name === 'RelayTimeoutError'
                       || fetchErr.name === 'AbortError')) {
        throw new Error(t('errRelayTimeout'));
      }
      throw fetchErr;
    }

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
      // The relay speaks in short English codes ('origin refused',
      // 'unauthorized', 'session import refused', ...). Rendering them
      // verbatim put an English sentence in a French popup. Map the known
      // codes to translated keys and keep the fallback translated too; an
      // unknown code still surfaces, but in a translated frame rather than as
      // raw relay prose.
      throw new Error(relayErrorText(result.error));
    }

    setStatus(t('success', result.cookie_count, result.storage_count ?? storageKeys), 'success');
    // Refresh the sessions panel immediately so the counter and the list
    // reflect the sync that just happened (no extra click needed).
    sessionsCard.classList.add('open');
    await refreshSessions();
  } catch (error) {
    // `error.message` is always truthy, so the i18n fallback beside it could
    // never run - the popup rendered either raw relay prose or Chrome's
    // 'Failed to fetch'. Only messages we raised ourselves are safe to
    // show; anything else is a browser/network string we cannot translate.
    const shown = (error && error.name === 'Error' && !error.relayCode)
      ? error.message
      : (error && error.name === 'RelayTimeoutError'
          ? t('errRelayTimeout')
          : t('errRelayUnreachable'));
    setStatus(shown, 'error');
  } finally {
    transferEl.disabled = !confirmEl.checked;
  }
});

// ---------------------------------------------------------------------------
// Never copy more than the origin out of the tab. A full URL routinely carries
// ?token=, #access_token= or a session id, and the clipboard is paste-anywhere.
function reportableOrigin(url) {
  try {
    return new URL(url).origin;
  } catch (_) {
    return 'unknown';
  }
}

// Copy diagnostic (v0.6.0)
// A failed sync used to end at a screenshot with nothing to act on. This pulls
// the relay's sanitized report (versions, counts, live state - no cookie, no
// token, no URL) and puts it on the clipboard so a bug report carries evidence.
// ---------------------------------------------------------------------------
async function copyDiagnostic() {
  if (!diagBtn) return;
  const label = diagText;
  const original = label ? label.textContent : '';
  try {
    const res = await relayFetch('/v1/diagnostics', {
      method: 'GET', cache: 'no-store', headers: bridgeHeaders()
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.code || data.error || 'diagnostics failed');
    const report = [
      data.text,
      '',
      '--- extension side ---',
      'popup: ' + (document.getElementById('app-version') || {}).textContent,
      // ORIGIN only. This used to copy `currentTab.url` whole, which routinely
      // carries `?token=`, `#access_token=` or a session id in the query or
      // fragment - so a "no URL, no token" diagnostic exported the credential
      // into a paste-anywhere clipboard. The sync path already narrows to the
      // origin; the report does the same now.
      'site: ' + reportableOrigin(currentTab ? currentTab.url : ''),
      'language: ' + currentLanguage
    ].join('\n');
    await navigator.clipboard.writeText(report);
    if (label) label.textContent = t('diagCopied');
    showToast(t('diagCopied'));
  } catch (err) {
    if (label) label.textContent = t('diagFailed');
    showToast(t('diagFailed') + ' — ' + ((err && err.name === 'RelayTimeoutError') ? t('errRelayTimeout') : t('errRelayUnreachable')));
  } finally {
    setTimeout(() => { if (label) label.textContent = original; }, 2500);
  }
}

if (diagBtn) diagBtn.addEventListener('click', copyDiagnostic);

init();
