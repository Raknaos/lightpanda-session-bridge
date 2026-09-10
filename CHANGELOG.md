# Changelog

## [0.5.5] - 2026-09-10
### Fixed
- **"Install the latest commit" failed with `HTTP Error 415: Unsupported Media Type`.** The main channel reused the `Accept: application/octet-stream` header that was written for the CDN that serves release assets, but the archive comes from `api.github.com/repos/.../tarball/<sha>` - and the API refuses a media type it cannot produce. GitHub answered 415 before sending a single byte, so the button did nothing. Measured on the same URL: octet-stream -> **415**, `application/vnd.github+json` -> **200**, no Accept header at all -> **200**.
- The guard now lives in `_fetch` - the one place every update request goes through - so the API host always receives the GitHub media type and no caller can reintroduce the bug by asking for bytes. Download hosts keep the caller's Accept, because the CDN does serve octet-stream. The release channel worked all along; only the main channel was broken.
- 3 new tests pin it, including a behavioural one that captures the real header on a stubbed socket: **95 tests, 1 skipped**.
- **Hygiene:** `.gitattributes` pins LF for `extension/**`, so a Windows checkout, the release zip and an update install are byte-for-byte the same tree. Before this, a successful update rewrote every file (content identical, line endings not) and `git status` reported the whole extension as modified.
- **Tooling:** `scripts/reload_extension.py` now reads the extension id from the relay's pin (a hardcoded 33-char id made it reload nothing while printing success) and reloads through `chrome.developerPrivate.reload()` - `chrome.runtime.reload()` from inside the popup does not pick up a new manifest.
- **Traceability:** every install appends one JSON line to `update.log` (version, commit shas, artifact, file counts, timestamp; never a cookie, a token or a URL).

## [0.5.4] - 2026-09-10
### Fixed
- **The update card's buttons were cut off - the button existed, but it was past the fold.** Chrome caps a popup at 600px tall. The body was pinned to `max-height: 580px` with `overflow: hidden`, and the real content needed ~590px: the button row landed below the cap and was sliced in half. The body now scrolls instead of hiding, and the vertical density was trimmed so the whole popup fits in **563px** in its default state, footer included.
- **The full-width red "Clear all" bar is gone.** It sat alone on its own row at the bottom of the sessions card, where it read as a misplaced primary action. It is now a compact danger pill in the card header, next to the count badge, and it turns solid red once armed.
- **The "clear all" button lost its inner `<span>` on the first click.** The handler wrote `textContent` on the `<button>` itself, which replaced its markup and detached the label node. The label is now always written to the span; the full sentence ("click again to clear all") moves to the tooltip.
- **The commit hash was printed twice** - once in the blue chip, once in the line below. The chip now carries the STATE only (`Update` / `Up to date`) and the line below carries the target (`-> commit a478b90`), so no information repeats.
- **Two long labels no longer fight over one 430px row**: the rollback action is a 38px icon button, with the sentence as its tooltip and `aria-label`.
- The collapsible sessions card moved to the end of the popup, so opening the list only grows the tail; the list scrolls inside a capped area (132px) instead of pushing the layout.
### Added
- `scripts/diagnostics/preview_popup.py` - renders the popup in headless Chrome against a stubbed `chrome` API, prints the measured height of every block, and **exits 1** when the default state does not fit under the cap. The layout is now verifiable without a live browser.
- 6 layout regression tests pin the fix (hidden overflow behind a fixed cap, compact pill in the header, collapsible card last, no chip/meta duplication): **92 tests, 1 skipped**.

## [0.5.3] - 2026-09-10
### Fixed
- **x.com could never sync - "5/7 localStorage keys" that no re-sync could clear.** x.com keeps two of its entries under 194-character names (`rweb.sessionBinding.hashClaim:<base64>`). The snapshot filter dropped every key name longer than 128 characters **silently**, so those two were removed before the first write attempt: Lightpanda received 5 of 7, the popup honestly said so, and syncing again could never help because the missing keys never left the relay. Key names up to 1024 characters and values up to 256 KiB are now carried, with the whole snapshot bounded at 1.5 MB so it still fits the import body cap.
- **Nothing is dropped in silence any more.** A key the relay cannot carry - name or value past the bounds, or a snapshot past the total - is reported BY NAME with its size and the reason, on both the HTTP and CLI paths, instead of turning into a ratio that never reaches 100%. The incomplete-transfer message names the missing keys as well, and the popup has a translated message for a refusal.
### Added
- `storage_expected`, `storage_missing` and `storage_refused` in the import response (success *and* failure), so the popup builds a specific, translated message instead of showing the relay's raw text.
- Tests: `StoragePlanTests` plus named-refusal, named-partial and legacy-integer-verify cases - 86 tests, 1 skipped.
- Proven end to end on x.com: the live tab's session was imported through the real `/v1/session/import`, then checked **inside** Lightpanda - 7/7 keys present including the two 194-character names, zero extras, `x.com/home` loaded as the logged-in account, and the session survived two further navigations. Key names and sizes only, never a value.

## [0.5.2] - 2026-09-10
### Fixed
- **"Échec de la mise à jour : update redirect refused" — the update could never install.** GitHub answers a release-asset request with a 302 to a signed CDN URL, and it now redirects to `release-assets.githubusercontent.com`. That host was missing from the download allow-list, so the guard added in 0.5.0 rejected GitHub's own redirect and every install aborted. The current CDN host plus the two historical ones are now allow-listed; the check still runs on the **final** URL, so a redirect still cannot walk the download off GitHub, and a lookalike host (`release-assets.githubusercontent.com.evil.example`) is still refused.
### Added
- `tests/test_updater.py`: 8 tests for the download path against a fake HTTP layer — accepted CDN hosts, redirect off GitHub refused, redirect to plain http refused, lookalike host refused, non-GitHub source refused, oversized download refused by header *and* by body, and the allow-list contains no wildcard. Verified end to end against the real GitHub release: zip downloaded, `sha256` matched the published sidecar, tree installed, provenance written, rollback backup kept.

## [0.5.1] - 2026-09-10
### Changed
- When the deployed copy carries no provenance (installed by hand, or by an installer older than 0.5.0) and the release is not older, the button now installs the **tagged release artifact** — the immutable one with a published `sha256` — instead of the `main` snapshot. The `main` channel is still used when the checkout is ahead of the last release, so an update can never silently downgrade content.
### Added
- Tests: the unknown-baseline choice (release vs main), and the no-downgrade rule.

## [0.5.0] - 2026-09-10
### Added
- **An update button, and a badge that makes an update impossible to miss.** The popup compares the deployed version with GitHub and shows a *Update to vX.Y.Z* button when a release is ahead, or *Install the latest commit* when `main` has moved on. The toolbar badge appears on its own (checked every 3 h, on install and on browser start).
- **The relay installs it, because the extension cannot update itself.** `GET /v1/update/check`, `POST /v1/update/apply` and `POST /v1/update/rollback`, plus the same three operations as `python relay/server.py --check-update | --apply-update | --rollback-update`. The archive is downloaded from a compiled-in repository (never from the caller), restricted to GitHub hosts over https, size-capped, refused if it contains traversal or absolute paths, and refused unless it holds a Manifest V3 `manifest.json` whose name is this extension. A published `.zip.sha256` sidecar is verified when present, the previous tree is backed up outside the repository, and *Undo* puts it back.
- The footer version is now read from the manifest at runtime instead of being hand-edited in `popup.html` on each bump.
### Changed
- The extension requests the `alarms` permission for the periodic update check.
### Fixed
- `relay/server.py --self-test` also covers the version ordering, the archive traversal refusal and the incomplete-tree refusal.

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
