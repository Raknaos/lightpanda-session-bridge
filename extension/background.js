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

async function refreshUpdateBadge() {
  try {
    const res = await fetch(`${RELAY}/v1/update/check`, { cache: "no-store" });
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
  } catch (_) {
    // Relay offline: keep the badge as it was, never claim "up to date".
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
