// Update watcher.
//
// The extension is loaded UNPACKED, so Chrome never updates it on its own and
// the popup cannot rewrite its own files. The local relay (a Python process
// with filesystem access) does the download + install; this worker only asks
// whether something newer exists on GitHub and raises the toolbar badge, so an
// available update is impossible to miss.
const RELAY = "http://127.0.0.1:8765";
const ALARM_NAME = "lpBridgeUpdateCheck";
const PERIOD_MINUTES = 180;
// Measured 0.7.38: this file was the ONLY caller of the relay with no deadline.
// popup.js routes every fetch through relayFetch (45s); here the fetch was bare,
// so a relay that accepted the socket and went silent left the service worker
// pending until Chrome killed it - the badge froze with no visible error, and
// nothing in the gate read this file to notice. The worker is short-lived, so it
// does not need the popup's 45s; it needs a bound at all.
const RELAY_TIMEOUT_MS = 10000;

async function relayFetch(path, options) {
  const opts = options || {};
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), RELAY_TIMEOUT_MS);
  try {
    return await fetch(`${RELAY}${path}`, Object.assign({}, opts, {
      signal: controller.signal
    }));
  } catch (err) {
    if (err && err.name === "AbortError") {
      const timeout = new Error("relay deadline exceeded");
      timeout.name = "RelayTimeoutError";
      throw timeout;
    }
    throw err;
  } finally {
    clearTimeout(deadline);
  }
}

async function refreshUpdateBadge() {
  try {
    const res = await relayFetch("/v1/update/check", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.ok && data.update_available) {
      const target = data.source === "release"
        ? `v${data.latest_version}`
        : (data.latest_commit_short || "main");
      await chrome.action.setBadgeBackgroundColor({ color: "#6b52ff" });
      await chrome.action.setBadgeText({ text: "\u2191" });
      await chrome.action.setTitle({
        title: `Lightpanda Bridge \u2014 update available (${target})`
      });
    } else {
      await chrome.action.setBadgeText({ text: "" });
      await chrome.action.setTitle({ title: "Transfer session to Lightpanda" });
    }
  } catch (err) {
    // Relay offline OR past the deadline: keep the badge as it was, never claim
    // "up to date". The distinction is not cosmetic - a timeout means the relay
    // accepted the request and went quiet, which is exactly the state this badge
    // must not paper over.
    void err;
  }
}

chrome.runtime.onInstalled.addListener(refreshUpdateBadge);
chrome.runtime.onStartup.addListener(refreshUpdateBadge);

// Re-arm the periodic check only when it is missing: re-creating it on every
// service-worker start would reset the timer and postpone the check forever.
chrome.alarms.get(ALARM_NAME, (alarm) => {
  if (!alarm) {
    chrome.alarms.create(ALARM_NAME, { delayInMinutes: 1, periodInMinutes: PERIOD_MINUTES });
  }
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) refreshUpdateBadge();
});

refreshUpdateBadge();
