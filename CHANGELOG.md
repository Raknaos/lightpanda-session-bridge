## [0.7.6] - the document-start restore scripts stacked, and "Tout retirer" left half the session

- Every import registered a `Page.addScriptToEvaluateOnNewDocument` holding a full
  copy of the localStorage snapshot, and nothing ever called
  `Page.removeScriptToEvaluateOnNewDocument`. The scripts therefore stacked for
  the lifetime of the CDP connection - measured: 3 imports, 3 live scripts - each
  one re-writing the whole snapshot on every future page load. The relay now keeps
  the identifier of the live script and retires the previous one on each import.
- `clear_sessions` deleted the cookies by name but left the restore script
  registered, so every subsequent page load put the entire localStorage back:
  "Tout retirer" was a half-wipe, and a partial wipe is indistinguishable from a
  flaky sync. It now retires the script as well.
- `_backup()` writes `meta.json` INTO the backup directory and `rollback_update()`
  mirrors that directory into the live extension, but `_mirror` exempted only
  `.build-info.json` - so a rollback deposited a stray config file in the shipped
  tree, which the next update's prune then deleted as "not in the source tree".
  Both bookkeeping files now come from one `MIRROR_KEEP` constant, and the
  filename is no longer hard-coded at its two use sites.

The identifier assignment was initially missing its `global`, which wrote a local
and left the module-level slot empty - caught by the probe showing zero removals
after the first fix, not by the suite.

203 tests green, acceptance gate 28/28.

## [0.7.5] - the CDP proxy was handing out cookie values over HTTP

- `POST /v1/cdp {"method": "Network.getCookies"}` answered 200 with the whole
  cookie jar **including values** - measured live, 7 cookies - to anyone holding
  the token. `/v1/cdp` returned `proxy_cdp()`'s result verbatim and the blocklist
  only covered `Browser.close`, `Target.disposeBrowserContext` and
  `Network.deleteCookies`. This was the single route where a cookie value could
  reach an HTTP response. `Network.getAllCookies`, `Network.clearBrowserCookies`,
  `Storage.clearCookies`, `Storage.clearDataForOrigin` and
  `Storage.clearDataForStorageKey` are now refused too - the last two could wipe
  the storage of every synced origin while `clear_sessions` scopes the same job
  per origin. Agents that genuinely need to know whether a cookie is present get
  the new `route: "verify_cookie_names"`, which returns names only.
- `list_sessions()` iterated `_SYNCED_SESSIONS` with no lock while
  `clear_sessions` mutated it under `CDP_LOCK`: `RuntimeError: dictionary
  changed size during iteration`, 24 times in 2 seconds when measured. It now
  iterates a snapshot taken under the lock.
- `set_session` reset only two of its four per-request counters before the early
  `raise`s, so a refused import answered 400 with the PREVIOUS site's numbers:
  `storage_expected = 7` and `storage_missing = ['user','cart','tok']` for a
  payload carrying one key, rendered verbatim by the popup.
- `_authorized()` let `_load_secret()`'s PermissionError escape: the client got a
  connection reset instead of a 401, reachable unauthenticated on every guarded
  route. It now never raises, and compares bytes on both sides.
- `do_GET` had no socket timeout while `do_POST` had three, so a relay that
  accepted the socket and never answered wedged the popup on "Checking..." forever.
- `#toast` sits AFTER `<script src="popup.js">` in the document and the element
  was captured at module load, so it was null for the whole session and every
  `showToast()` was a silent no-op: "Tout retirer" cleared without confirming,
  and copy-diagnostic feedback was invisible. The lookup is now lazy.

196 tests green, acceptance gate 28/28, popup still 563 px.

## [0.7.4] - four audit findings, three of them real

- `__Host-` cookies were not forced Secure (RFC 6265bis). The branch forced
  `path=/` and dropped `domain` but left `secure` untouched, so a supplied
  `secure: false` downgraded the one prefix whose entire guarantee is
  "Secure, host-only, path=/". `__Secure-` was already forced.
- `artifacts.session_state` in the support report was permanently `unset`:
  `collect()` looked for `session_state_path` in `updater.py`, but it lives in
  `server.py` as `_session_state_path`. The report claimed the cookie file was
  absent on machines where it existed, holding the cookies.
- One torn line in `update.log` discarded the entire install history: the parser
  was a single list comprehension, so one truncated line (a power cut during an
  unsynchronised append) returned `[]`. Parsing is now per line.
- `/v1/sessions` `expires` was dead by construction: `cookie_for_cdp` pops
  `expires` (Lightpanda drops cookies set with one) and `list_sessions` read
  that same key, so expiry was always null and `expired` always false - the
  popup could never warn about a stale session. The lifetime is now preserved as
  `expires_hint`, stripped again on the way to CDP.

Rejected after verification: a nested `sub/D:evil.js` drive-relative escape
(`_safe_members` already refuses it), and cookie values reaching CDP unbounded
from the extension's own browser API (the extension is the trust boundary; a
value cap belongs at the extension, not only the relay).

Two existing tests were asserting a shape production never stores (they wrote
`expires` straight into the dict), so they stayed green while `/v1/sessions`
reported null forever. They now build cookies through `cookie_for_cdp`.

184 tests green, acceptance gate 28/28.

## [0.7.3] - the restored session can no longer be injected twice

- `_restore_persisted_session()` is reached from the CDP proxy AND from the
  session-import handler, i.e. two ThreadingHTTPServer threads. It read
  `_PERSISTED_APPLIED`, then released every lock, then made the CDP call, then
  set the flag. Both threads could pass the check in between, and both called
  `_apply_session` - and `_apply_session` SETS cookies rather than replacing
  them, so Lightpanda's jar was populated twice. The `StateLock` claim is now
  taken under the lock before the call, released on success and on failure.
- `CDP_LOCK` was never the right lock for this: it guards the socket, not the
  "has this already been done?" question.
- The `except Exception: return False` is gone. It made a structurally broken
  restore indistinguishable from "Lightpanda is down, retry later", and the
  relay went on reporting a session it had never injected. Transient failures
  still surface as the retryable types both callers already handle; the claim is
  released either way, so a later call retries.
- `_LAST_SESSION` is now snapshotted (copied) before use, so a caller cannot
  change the relay's own copy mid-apply.
- `tests/test_restore_race.py`: two threads, the first held inside the "CDP
  call". Proven red both ways - removing the claim gives `_apply_session ran 2
  times for ONE restored session`, and restoring the old `except` gives
  `ValueError not raised`.

169 tests green, acceptance gate 28/28, E2E verified after a relay restart
(import 200, `attached: true`, `cdp_attached: true`, no cookie values in the
report).

## [0.7.2] - the archive guard is now proven, not assumed

- `tests/test_archive_windows_paths.py`: the traversal tests only ever asked
  about `../../evil.txt` and `/etc/evil.txt`. The guard in `_safe_members`
  normalises backslashes, refuses drive letters and therefore also catches
  `C:/evil.txt`, `C:\evil.txt`, `C:evil.txt`, `//server/share/...` and
  `..\evil.txt` - none of it asserted. A "simplification" to a plain
  `name.startswith("/")` check would have passed all 56 updater tests and
  reopened the hole on the only platform this ships on. Proven red by making
  validation per-member instead of up-front: all four Windows shapes were then
  extracted silently.
- Also asserted: a refused archive leaves NO partially extracted tree, and a
  valid archive still lands exactly where expected (a guard that refuses
  everything is not a fix).

No product code changed. 166 tests, all green.

## [0.7.1] - the support report stopped describing a module that never ran

- `_sibling("server")` imported a SECOND copy of `relay/server.py`. In the live
  daemon `server.py` is the entry point, so its module is registered under
  `__main__` and `sys.modules` holds no `server` key at all. The report read the
  fresh copy's globals, which are always empty. Live symptom: `/health` said
  `attached: true, sessions: 1` while `/v1/diagnostics` said `cdp_attached:
  false, synced_origins: 0, cdp_transport: "NoneType"` - same process, same
  instant, opposite answers. Now `__main__` is reused when it really is the
  relay (compared by path, so a test runner as `__main__` cannot hijack it).
- `RelayServer` requests `SO_EXCLUSIVEADDRUSE`. `allow_reuse_address = False`
  only clears SO_REUSEADDR, which does NOT stop a second process binding an
  already-listening socket - two relays were live at once, each holding its own
  copy of the session state.
- `health_payload()` no longer raises on a transport object without `alive()`.
  `do_GET` has no try around it, so the AttributeError killed the HTTP thread
  instead of answering.
- The watchdog checked only that `/health` answered 200, so it called a relay
  with a dead CDP connection healthy, and it restarted the relay when only
  Lightpanda was down. It now requires `attached: true`, and a dead Lightpanda
  is logged instead of triggering a restart (the relay connects on demand).

Tests: `test_single_relay.py` (4), `test_watchdog_health.py` (8), 2 new in
`test_diagnostics.py`. 161 total, all green. Every fix proven red without it.

## [0.7.0] - the popup finally shows what /health reports

- `checkRelay()` looked only at `res.ok`, so v0.6.1's honest `attached: false`
  never reached the user: the badge still read "Relay Online" over a dead CDP
  connection. It now reads the field and shows a third state.
- New `badge.idle` style (amber). Not green - the relay is up. Not red - nothing
  is broken. The relay answers; Lightpanda is simply not attached yet.
- New `relayIdle` key in all 10 languages, kept short ("Non connecté") because
  "Relais prêt - navigateur non connecté" was clipped inside the pill.
- `preview_popup.py --state idle` renders that state, so a UI state with no
  screenshot cannot go unreviewed again.
- The acceptance gate's i18n check now also catches `t("key")` double-quoted
  calls and "two keys on one line" (an insert that ate a comma).
- `--apply-update --channel release|main|auto`: `--apply-update` silently
  followed `check_update`'s recommendation, so asking for the published release
  could install the main-channel tarball instead - whose sha256 has no sidecar,
  which it reported as `checksum_verified: false` with no way to ask otherwise.

Tests: 147 green, gate 28/28, CI green.

## [0.6.1] - /health stops lying about a dead connection

- `CdpTransport` learns when its socket died (OSError, graceful close, or a peer
  that streams events forever without answering) and reports `alive()`.
- `_ensure_connection` reopens a transport that proved it is dead. It used to
  return early on any non-`None` transport, so after a Lightpanda/WSL restart the
  relay kept a dead socket forever and only an explicit resync recovered. A
  healthy idle connection is still preserved - Lightpanda scopes its cookie jar
  per connection, so tearing that down logs the user out of every session.
- `/health` derives `attached` from the transport instead of a flag never cleared
  on death, and reports the synced-session count. It answered `200 attached=true`
  over a connection that could not carry a byte - the same class of lie as
  v0.5.7's never-ending spinner.
- `CdpTransport.request` bounds the unsolicited-event skip loop
  (`MAX_SKIPPED_EVENTS = 2000`) so a page logging hard cannot hold the serving
  thread until the socket timeout.

Tests: `tests/test_health_truth.py` (9). 147 total, all green.

# Changelog

## [0.6.0] - 2026-10-02
### Added
- **Copy diagnostic** (footer of the popup): one click puts a sanitized report
  on the clipboard - versions, counts, file fingerprints, live relay state, last
  installs. A failed sync used to end at a screenshot with nothing to act on.
  No cookie value, no token, no URL: `relay/diagnostics.py` owns that guarantee
  and both its unit tests and the acceptance gate plant credentials to prove it.
- `GET /v1/diagnostics` returns the same report as json + text.

### Fixed (v0.6.0, second pass)
- `/v1/diagnostics` answered 500 `ModuleNotFoundError` on the live relay while
  every test was green: `relay/` is not a package, so the running process
  imports its neighbours flat (`import updater`) and the dotted
  `from relay import diagnostics` did not resolve. Both spellings now work.
- Importing flat and then dotted loaded the file twice under two names, so the
  report read a second, empty copy of the relay module and answered "0 cookies"
  while the relay held 12. `_sibling()` now reuses the instance already in
  `sys.modules`. Covered by three new tests, verified red.

### Fixed
- **The release archive is now reproducible.** It was rebuilt from the same tree
  into a different sha256, because `ZipFile.write` stamped the build time and OS
  into every entry and because deflate is not reproducible across build machines
  (.venv ships zlib 1.3.1, the system python ships 1.3.1.zlib-ng - same 148 KB
  tree, 148120 vs 148524 bytes). Entries are now STORED with a fixed epoch, a
  fixed creator and no host metadata: one sha256 per tree, on every machine.
- `scripts/build_release_zip.py` died with a bare `FileNotFoundError` when
  `LOCALAPPDATA/Temp` did not exist (fresh profile, CI, non-Windows).
- Removed `relay/patch_snippet.txt`, a tracked scratch file.

## [0.5.8] - 2026-09-14
### Fixed
- `WinError 10053` shown raw in the popup ("Transfert incomplet : 0/8"): the
  storage injector caught the connection error before the 0.5.7 resync could
  see it. It now propagates - socket dies *during* injection, resync, retry.
- Page-level failures report short codes (`verify-error:Name`) translated into
  10 languages, never the OS's raw localized sentence.

## [0.5.7] - 2026-09-14
### Fixed
- **The sync could hang on "Transferring & verifying…" forever.** When WSL or Lightpanda restarted under the relay, the daemon's single CDP WebSocket died and every `/v1/session/import` failed in milliseconds (`WinError 10053` at storage-verify) - but only `proxy_cdp` had the resync-and-retry; the import path did not, so nothing revived the socket except using the agent proxy by chance. `set_session()` now resyncs and retries once on a dead connection, like the proxy always did (`tests/test_import_resync.py` proves it: red without the fix, green with). The popup additionally gets a hard 30s deadline on the import fetch (`errRelayTimeout`, all ten languages): a client waiting forever has no honest state to show, so the sync now always ends - pass, fail, or say the relay is stuck.

## [0.5.6] - 2026-09-10
### Fixed
- **Three languages rendered the string "undefined".** The Chinese, Japanese and Arabic blocks were each missing `clearConfirm` and `clearedToast`, so the tooltip on the clear button and the toast after clearing showed `undefined`. Every other language had them; nothing compared the key sets, the old test only checked a hand-picked list of *update* strings. The whole key set is now compared across all ten languages, and every `t('...')` call in `popup.js` is resolved against all ten.
### Fixed (packaging)
- **The published v0.5.6 zip carried this machine's install history.** `build_release_zip.py` walked `extension/` on disk, so the gitignored `extension/.build-info.json` - its commit, its timestamp, its previous install - went into a public download. The builder now ships what git tracks, the asset was rebuilt (14 files, `8104c4bf…f110`) and re-uploaded, and the gate compares the published archive against `HEAD` byte for byte, so a zip that is not the committed tree can no longer pass.

### Added
- **`scripts/acceptance.py`, the gate that runs before anything is committed.** 24 checks over the seams the unit tests cannot see: version agreement across manifest/pyproject/updates.xml/CHANGELOG/release notes, LF shipped tree, no scaffolding in the shipped tree, id literals that are not the pinned 32-character id, the shared secret absent from every file, i18n parity, every DOM id `popup.js` touches existing in `popup.html`, the popup's live height against Chrome's 600px cap, then the live system: relay auth (401/403/200), the release asset downloading and matching its published sha256, the main-channel tarball, the CDP proxy, a real session import round-trip, and the extension in Comet serving the repo version. `--local` runs without any service. GitHub Actions runs the local half on every push.
- The gate found and this release fixes the i18n bug above, plus a second 33-character extension id in `scripts/verify_extension.py` - the script whose `chrome-error://chromewebdata/` output had been worked around instead of fixed - and a hardcoded expected version of "0.4.3" in the same script, which reported twelve later releases as broken.
- `scripts/cdp_utils.py`: one shared resolver for the extension id (the copy-paste is what broke twice) and for the CDP plumbing, used by both scripts. `tests/test_tooling.py` guards the class: wrong-length ids refused, no id literal in a script, no expected version hardcoded, no Windows CLI read with `text=True`.
- `bridge.py` decoded Windows CLI output with `text=True` (utf-8) in two places. `wsl.exe -l -q` writes UTF-16LE and `netstat` writes cp850 on a French install: one garbled the distro list, the other killed the reader thread and returned `None`. One tolerant decoder now handles both.
- The relay reports *why* GitHub could not be reached: "GitHub API rate limit reached (anonymous is 60/hour per IP)" with `error_kind: rate_limit`, instead of "GitHub unreachable (RuntimeError)". The check cache went from 60s to 5 minutes for the same reason. `SECURITY.md` documents the optional `~/.config/lightpanda-bridge/github_token`.
- The acceptance gate runs the unit suite with the project's own interpreter: a bare `python` without `websocket-client` made two modules fail to import and the suite report 56 tests instead of 111.

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
