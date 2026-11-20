# Security Review

Scope: the whole repository at `06bad18`, plus the local changes from this session. Method: code reading plus targeted probes against the running instance. Severity follows CVSS-style judgement (Critical / High / Medium / Low) by *impact × likelihood for a self-hosted install*.

---

## 1. Controls that already exist (verified)

| Area | Control |
|---|---|
| Sessions | Cookie holds a random token; only its SHA-256 is stored; HttpOnly, SameSite, Secure under HTTPS, `CLIPSORA_SESSION_DAYS` expiry |
| Passwords | KDF hash, never logged; Google-only accounts carry no hash |
| Identity | `ctx.uid()` from the session context var; no route reads a user id from the body |
| Multi-user isolation | Per-user data directories; every job/creator/account lookup is scoped by owner; admin routes require `is_admin` |
| SSRF | URL allow-list (`CLIPSORA_ALLOWED_SITES`), scheme checks, private-IP rejection, no redirects to internal hosts |
| Uploads | Size and part caps, content probing with ffprobe, filename sanitisation |
| Path handling | Media served by resolved path inside the job directory; no user-supplied path joins |
| Injection | ffmpeg invoked with argument arrays (no shell); SQL through SQLAlchemy parameters |
| XSS | All dynamic HTML escaped through `esc()`; CSP and security headers set |
| AI prompt injection | Video text passed through `brain._safe`, output through `brain._text` (link/handle stripping) |
| Abuse | Per-route throttles, per-user job/creator/storage quotas, disk-full guards |
| Ads/secrets | `.env` gitignored and dockerignored; keys never returned by the API (only `has_key` + last 4) |

---

## 2. Findings

### High

**S1 — Publishing OAuth tokens stored unencrypted.**
`accounts.json` holds YouTube/Instagram/TikTok access and refresh tokens in plaintext in the data folder. A backup, a copied folder, or any file-read bug leaks post-as-the-user capability.
*Fix:* `accounts` table with AES-GCM `token_enc`; key from `CLIPSORA_SECRET_KEY` or a `0600` file generated at first start; rotation documented; tokens never logged (audit `accounts.py` for accidental prints).

**S2 — CSRF relies on cookie flags and origin checks only.**
No per-request token. SameSite=Lax plus an Origin check covers modern browsers, but the check must be enforced on *every* state-changing route and proven by tests.
*Fix:* add `isSameOriginRequest` enforcement in one middleware, tests for cross-origin POST/PUT/DELETE, and a double-submit token if any route must accept cross-site form posts (none should).

### Medium

**S3 — No MFA, no API tokens, no session revocation UI.**
Sessions can be listed/revoked only by deleting the row; a stolen cookie lives until expiry. For a hosted tier this becomes High.
*Fix:* session list + revoke, optional TOTP, scoped API tokens.

**S4 — Feedback and error context can capture user content.**
`feedback.context` (up to 1000 chars) may contain paths or transcript snippets; job `error.log` may include URLs.
*Fix:* redaction pass (paths, tokens, emails) before persisting; document what is stored.

**S5 — Rate limiting is in-process and per-route.**
Restart resets counters; a long-running AI endpoint can be looped within limits.
*Fix:* shared counter interface, global per-user budget, and a hard daily AI cap option.

**S6 — Dependency supply chain.**
12 pinned packages, no vulnerability scan; `yt-dlp` and `sherpa-onnx` are high-churn.
*Fix:* `pip-audit` in CI, Dependabot/Renovate, and a documented upgrade procedure for yt-dlp (it breaks often by design).

**S7 — No audit trail for user deletions.**
Only admin actions are logged; a user deleting a creator removes media with no record.
*Fix:* `clip_events`/`audit` rows for destructive user actions (ids and counts only).

### Low

**S8** Admin dashboard exposes user emails to admins — intended, but should be documented in the privacy page and covered by a "least data" review.
**S9** `CLIPSORA_DATA` permissions depend on the host umask; Docker volume is root-owned today.
**S10** Update checker contacts GitHub on boot (documented; switchable).
**S11** Google Fonts are fetched from `fonts.googleapis.com` in the browser — reveals visitor IPs; self-host the fonts to remove the third-party call.
**S12** `CLIPSORA_YT_COOKIES` support means a user may store a Google account cookie file; must be documented as highly sensitive and excluded from backups by default.

---

## 3. Threat model (self-hosted, single user)

| Threat | Today | After P0 |
|---|---|---|
| Someone on the LAN opens the port | binds 127.0.0.1 by default; accounts optional | unchanged + first-run warning if `CLIPSORA_ACCOUNTS=0` and the bind address is not loopback |
| Malicious video URL (SSRF) | allow-list + private-IP checks | + tests for redirect chains and DNS rebinding |
| Malicious video content (ffmpeg) | argument arrays, ffprobe first | + document that ffmpeg is a large attack surface; pin and rebuild regularly |
| Stolen laptop / data folder | plaintext tokens (S1) | encrypted tokens; optional at-rest encryption of media documented as out of scope |
| Malicious prompt in a video | `_safe`/`_text` sanitisers | + a stored corpus of injection attempts in the test suite |
| Hosted multi-tenant (future) | n/a | requires S1, S2, S3, S5 closed before any multi-tenant exposure |

---

## 4. Privacy posture (product commitments)

- Raw footage, audio and transcripts never leave the machine; only prompt text is sent to the chosen AI provider, and the AI settings page says exactly what is sent.
- Deleting a creator/project deletes its media; the UI states this before the action.
- The self-hosted build has no telemetry. The update check is the only outbound call that is not user-initiated, and it is switchable.
- A privacy page already exists (`web/legal.html`); it must be updated whenever a new outbound call is added.

---

## 5. Remediation order

1. S1 tokens encrypted, S2 CSRF tests — **before** any hosted tier.
2. S3 sessions list/revoke, S4 redaction, S7 audit rows.
3. S5 budget, S6 scanning, S11 self-hosted fonts.
4. S8–S10, S12 documentation updates.
