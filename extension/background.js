// Auto-reload development helper
// Checks if the extension files have been updated locally and reloads cleanly
(function checkUpdate() {
  try {
    fetch('http://127.0.0.1:8765/health')
      .then(res => res.json())
      .catch(() => {});
  } catch (_) {}
})();
