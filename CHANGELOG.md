# Changelog

All notable changes to the Lightpanda Session Bridge will be documented in this file.

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
