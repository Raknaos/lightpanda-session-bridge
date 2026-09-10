# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4.0 | :x:                |

## Reporting a Vulnerability

Security is the foundational design goal of the Lightpanda Session Bridge. Since the local relay mediates session cookies, protecting against Server-Side Request Forgery (SSRF) and credential exfiltration is paramount.

If you discover a potential vulnerability:
1. **Do not open a public GitHub issue.**
2. Report the vulnerability via GitHub Private Vulnerability Reporting on this repository.
3. Include detailed steps to reproduce, affected endpoints (e.g. `/v1/session/import`, `/v1/bootstrap`), and impact analysis.

We will review reports within 48 hours and coordinate a patch and CVE disclosure if applicable.

## Threat model

The relay exists to hand a real browser session to a headless agent, so the
asset to protect is **the cookie jar and the localStorage snapshot**.

In scope:

- **Web pages** must never reach the relay: `Origin: https://…` is refused everywhere.
- **Untrusted extensions** must not read the shared secret or drive the session.
- **Blind SSRF**: the attacker-chosen `origin` must not be an internal address.

Explicitly out of scope (and why): a process already running as the same OS
user can read `~/.config/lightpanda-bridge/secret`, attach to the loopback
port and, on Windows, read any file this user can read. The bridge therefore
assumes **one user per machine** and does not pretend to isolate you from
yourself. Run it on a machine you already trust.

## Data at rest

| Path | Content | Permissions |
| ---- | ------- | ----------- |
| `~/.config/lightpanda-bridge/secret` | 32-byte shared token | `0600` + owner-only Windows ACL |
| `~/.config/lightpanda-bridge/pinned_extension_id` | pinned `chrome-extension://` id | `0600` + owner-only Windows ACL |
| `~/.config/lightpanda-bridge/session.json` | cookie values + localStorage of the last synced session | `0600` + owner-only Windows ACL |

`session.json` exists so that a relay restart, a reboot or a crashed watchdog
cannot silently drop your authentication (see 0.4.3 in the CHANGELOG). It is
written outside the repository, is never logged, and **"Clear all" in the popup
deletes it**. To remove it manually: `rm ~/.config/lightpanda-bridge/session.json`.

Never logged, never returned by an API: cookie values, localStorage values,
the shared token. `GET /v1/sessions` exposes origin, cookie count and expiry
metadata only.

## Security controls (v0.4.3)

- **Loopback only** — `HOST = 127.0.0.1:8765`, no external listener.
- **Token on every state-changing endpoint** (`/v1/session/import`, `/v1/cdp`,
  `/v1/sessions`, `/v1/sessions/clear`), compared with `hmac.compare_digest`.
- **Caller validation** — `Origin` must be the pinned `chrome-extension://` id
  (TOFU pin on the first `/v1/bootstrap` call). No `Origin` header = local CLI
  tooling; a web origin is always `403`.
- **CORS / Private Network Access headers** are reflected only to the pinned
  extension, never to a web page probing `127.0.0.1`.
- **Origin (SSRF) validation** — public `https` only, every DNS answer must be
  globally routable (rejects loopback, private, link-local, reserved, non-canonical
  numeric encodings such as `2130706433` / `0x7f000001`, IDN confusables, and
  wildcard-DNS tricks like `nip.io` / `localtest.me`). Identity-provider login
  hosts are refused so a login session can never be delegated.
- **Bounded inputs** — request bodies capped at 1 MB (`/v1/cdp`), 2 MB
  (`/import`) and 10 KB (`/clear`); socket read timeouts 10–30 s.
- **Exclusive bind** — `allow_reuse_address = False`, so two relays can never
  serve the same port (on Windows `SO_REUSEADDR` allowed a silent split-brain:
  one process holding the sessions, another answering `attached: false`).
- **No request logging** — `log_message` is disabled and the banner is neutral.

## Audit log

### 2026-09-10 — v0.4.3 (fix release)

| Ref | Finding | Severity | Status |
| --- | ------- | -------- | ------ |
| A1 | With `LP_BRIDGE_TOFU=1`, any `chrome-extension://` origin was accepted on non-bootstrap endpoints (`is_valid_extension_origin` returned `True` when nothing was pinned, even with `auto_pin=False`) | Medium | Fixed — only the bootstrap handshake may admit an unknown extension |
| A2 | Secret written with default umask then `chmod 0600` (world-readable window); files created before that fix stayed `0644` | Medium | Fixed — created via `O_CREAT, 0600`, re-hardened on load |
| A3 | CORS and `Access-Control-Allow-Private-Network: true` were advertised to callers that were not the pinned extension | Low | Fixed — headers only inside the extension-origin branch |
| A4 | `/v1/sessions/clear` read an unbounded request body | Low | Fixed — 10 KB cap |
| A5 | `Server:` banner disclosed product name and version to any local caller | Low | Fixed — neutral banner |
| A6 | On Windows `SO_REUSEADDR` let a second relay bind port 8765 already in use, producing two relays with divergent state | Medium | Fixed — `allow_reuse_address = False` + clean exit when the port is taken |
| A7 | `pinned_extension_id` was written world-readable | Low | Fixed — owner-only |
| A8 | Cookie jar only in memory: any restart silently downgraded the session to unauthenticated calls | Medium (availability/integrity) | Fixed — owner-only persisted state, replayed with retry |
| R1 | A local same-user process can spoof `Origin: chrome-extension://<pinned-id>` and read the token through `/v1/bootstrap` | Low | Accepted — documented in the threat model; the token only grants loopback access as the same user |
| R2 | TOFU pinning is first-caller-wins if `LP_BRIDGE_TOFU=1` is set on a shared machine | Low | Accepted — the official extension id is pinned by default; set `LP_BRIDGE_ALLOWED_EXTENSION_IDS` instead of enabling TOFU |

## Optional: a GitHub token for the update check

The relay asks GitHub anonymously, which allows 60 requests/hour per IP. The
badge, the popup and any tooling share that budget, and the check is cached for
5 minutes to stay inside it. If you want headroom - or if you run the acceptance
gate often - place a token where the relay can read it, and nothing else changes:

    gh auth token > ~/.config/lightpanda-bridge/github_token

The token is only ever sent to `api.github.com` (every download host is
allow-listed), it is never logged, and it is never printed by any script here.
The environment variable `LP_BRIDGE_GITHUB_TOKEN` takes precedence if you would
rather keep the credential out of the filesystem.
