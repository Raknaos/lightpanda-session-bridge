# Changelog

All notable changes to the Lightpanda Session Bridge will be documented in this file.

## [0.4.3] - 2026-09-10
### Fixed
- **A partial `localStorage` snapshot is no longer reported as a success.** The import was satisfied with "some keys landed": a real `a6api.com` sync moved **17 of 29 keys**, `user` was among the dropped ones, every authenticated call then answered **407 `New-Api-User`**, and the popup still said "synchronized" — the reason a session seemingly only worked *after a second sync*. Keys are now verified **one by one** (4 attempts, with a page reload in between so the durable restore replays the snapshot), and an incomplete transfer fails loudly with the ratio: `localStorage transfer incomplete: 17/29 keys verified`.
- **The popup no longer swallows a `localStorage` extraction failure.** `chrome.scripting.executeScript` errors were caught and ignored, so a sync could silently leave with cookies only; extraction is retried, a failure is now an explicit translated error (`errStorageExtract`), and a short `storage_count` returned by the relay is refused client-side as well (`errPartialStorage`).
- **Session survives a relay restart / reboot / watchdog restart.** The synced session lived only in memory, so a restart emptied the jar while `/health` still answered `{"ok": true}` and agents silently ran unauthenticated. The session is now persisted to `~/.config/lightpanda-bridge/session.json` (owner-only, cookie values never logged) and re-applied at startup, with a retry on every call until Lightpanda answers.
- **`localStorage` now survives any later navigation.** Injecting after a navigation was still lost by the *next* one (Lightpanda keeps it in the page context); a document-start restore is registered once, so the snapshot is re-applied on every new document.
- **Cookies whose `secure` flag does not match the URL scheme are found again** — the `session` cookie of a6api is `secure: false`, and Chrome only exposes a cookie to `chrome.cookies` when a host permission covers its origin scheme: `host_permissions` now includes `http://*/*`, the popup falls back to a domain query, and an empty jar is told apart from an out-of-scope one (`errCookiesOutOfScope`).
- **Relay startup could fail silently**: `UnicodeEncodeError` (cp1252 console encoding of `✓`) killed `bridge.py start` before the launch step, and a stray interpreter without `websocket-client` failed instantly. Both streams are reconfigured to UTF-8 and the launcher picks an interpreter that can actually import the relay's dependencies.
- Only one relay can bind the port now (`allow_reuse_address` disabled): on Windows `SO_REUSEADDR` let a second, session-less relay answer `attached: false` alongside the real one.
- `clear_sessions` counted the wrong entries and now also erases the persisted state on disk.
### Added
- The success message reports both halves of the transfer: `✓ Session synchronized (N cookies, M localStorage keys)` — translated in all 10 popup languages, alongside the two new error strings.
- `scripts/verify_live.sh`: one-shot live check of the relay (health, unauthenticated `401`, foreign-origin `403`, banner) that never prints a secret.
- `scripts/diagnostics/`: the read-only scripts that pinned the a6api chain down (key names and HTTP codes only, never a cookie value or a token).
### Security
- Extension-origin check hardened (pinned extension ID + allow-list), the relay no longer advertises itself in a `Server:` banner, `/clear` bodies are size-bounded, and `SECURITY.md` documents the applied hardening and the two accepted risks model ("one user per machine", TOFU).

## [0.4.2] - 2026-09-08
### Fixed
- Sessions panel now refreshes **immediately after a successful sync** (counter and list update without any click) and auto-expands to show the newly synced site.
- Counter refreshes on every popup open even while the panel is collapsed.
## [0.4.1] - 2026-09-08
### Added
- **Session manager in the popup**: see which sites have active sessions inside Lightpanda (origin, cookie count, nearest expiry — never cookie values), remove a single site's session, or clear everything at once.
- Relay endpoints: `GET /v1/sessions` (sanitized list, token-required) and `POST /v1/sessions/clear` (per-origin or all, token-required). Cookies are deleted from Lightpanda's jar over CDP.
- i18n: session manager translated in all 10 popup languages.
## [0.4.0] - 2026-09-08
### The zero-configuration release
- **Relay owns the only CDP connection.** Lightpanda scopes its cookie jar **per CDP connection** — an agent opening its own socket never saw synced sessions (the failure hit in practice on dev.to). The relay now keeps its connection for good and exposes `POST /v1/cdp` so every agent executes commands on the connection that holds the sessions. If Lightpanda restarts, the last session is replayed from memory automatically.
- **`bridge.py` one-command lifecycle**: `setup` (installs WSL2/Lightpanda/deps), `start` (idempotent), `status`, `doctor`, `install-browser-ext`.
- **`bridge_agent.py` SDK**: authenticated automation in 3 lines from any synced site; evaluation hardened with retry-on-None.
- **Import navigates the live target to the synced origin immediately** — the authenticated page is ready the moment the sync ends.
- `lightpanda_client.py` kept as a compatibility shim routed through the same proxy.

## [0.3.5] - 2026-09-08
### Fixed
- Relay: drop the `expires` attribute when injecting cookies — Lightpanda silently discards cookies carrying `expires`, which broke every transferred session (verified server-side: `logged-in` confirmed on dev.to after the fix).
- Cookie injection shape: explicit `Domain` + `httpOnly` + `Secure`, path `/`.
### Added
- `lightpanda_agent_session.py`: single-connection authenticated agent SDK. Lightpanda scopes its cookie jar per CDP connection, so the pulling/injecting/acting connection must be one and the same — this module encapsulates the working pattern (pull cookies from the desktop browser over loopback CDP, inject, navigate, evaluate with retry-on-None).

## [0.3.4] - 2026-09-08
### Added
- Automated token pairing via `/v1/bootstrap` restricted to `chrome-extension://` origins.
- `llms.txt` and `llms-full.txt` standard files for LLM documentation indexing.
- Continuous Integration workflow via GitHub Actions (`.github/workflows/ci.yml`).
- `pyproject.toml` standard packaging metadata.
- Citation support via `CITATION.cff`.
- Security policy (`SECURITY.md`) and Contribution guidelines (`CONTRIBUTING.md`).

### Fixed
- Enforce strict origin checking on secret-delivering bootstrap endpoints to block local CLI or malicious web script exfiltration.
- PascalCase normalization for CDP cookie `sameSite` parameters to eliminate `-31998 InvalidEnumTag` crashes.
- Bundled local fonts (`Space Grotesk`, `DM Sans`) to prevent third-party IP leakage.

## [0.3.3] - 2026-09-07
### Security
- DNS resolution validation before CDP WebSocket attachments with 60-second DNS caching (anti-SSRF / anti-TOCTOU).
- Elimination of `/v1/session/inspect` debugging leaks.
- Loopback-only socket binding (`127.0.0.1`).
