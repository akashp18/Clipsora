# Clipsora — Product & Technical Audit

**Audited commit:** `06bad18` (plus local, uncommitted work listed in §12)
**Method:** every module under `studio/`, `web/`, `tests/`, Docker and config files read directly; the running stack exercised end to end; numbers below counted from the code, not estimated from marketing.
**Audience:** whoever approves the transformation blueprint. Nothing in this document is aspirational — it describes what is there today.

---

## 1. What the product is today

A self-hostable, single-tenant-by-default AI clipping tool for streamers and gaming channels:

1. Paste a video URL or upload a file (or attach a creator's Twitch/Kick/YouTube channel and let it record live).
2. `yt-dlp` fetches the media; `ffmpeg` extracts audio.
3. Speech is transcribed locally by `sherpa-onnx` (≈480 MB model, downloaded on first use) or by a second machine running `asr_worker`. YouTube's own transcript is borrowed when it covers the part being clipped.
4. An LLM reads the timestamped transcript (plus loudness marks and live-chat spikes) and returns clips as JSON: start, end, score, category, hook, title, description, hashtags, highlight words, reason.
5. Each clip is rendered by ffmpeg into a 1080×1920 vertical video with word-by-word captions and a hook box, then optionally queued for posting to YouTube / Instagram / TikTok.
6. Posting is governed by per-creator rules (score threshold, gap between posts, daily cap, privacy) with a fair queue and view tracking.

It is genuinely more than a demo: the live path records with a rolling buffer, two independent AI judges gate live clips, renders recover from interrupted jobs, and there is a real test suite.

### Measured size

| Area | Count |
|---|---|
| Backend modules (`studio/`) | 34 files, ~10.6k lines |
| Largest modules | `server.py` 1,684 · `live.py` 1,042 · `jobs.py` ~940 · `brain.py` 690 · `accounts.py` 579 |
| HTTP routes | 96 total — 72 under `/api`, plus pages, `/media`, `/oauth`, `/healthz` |
| Database tables | 8: `users`, `sessions`, `usage`, `email_ok`, `email_tokens`, `feedback`, `notices`, `admin_log` |
| Frontend | `web/index.html` 2,543 lines of vanilla JS + HTML + CSS, no build step; 7 other static pages |
| Tests | 30 files, ~600 individual checks, run by `tests/run.py` |
| Dependencies | 12 pinned Python packages; ffmpeg, Deno, ffprobe at runtime |
| Deployment | Docker Compose: `app` + `db`, optional Caddy profile for HTTPS |

---

## 2. Architecture as built

```
Browser (single-page index.html, poll-driven)
   │  fetch /api/*  (session cookie)
   ▼
FastAPI (one process, one event loop)  ── middleware: identity, limits, headers, CSRF-ish checks
   ├── auth / accounts / admin      → SQLAlchemy → PostgreSQL | SQLite
   ├── jobs  ── _FairQueue ─────────┬── N workers (JOB_WORKERS) : one video each
   │                               ├── 1 "quick" worker        : re-make one clip
   │                               └── 1 live worker           : live clips never wait
   ├── live  ── rolling recorder (yt-dlp → ffmpeg segments)
   ├── transcribe ── sherpa-onnx local  |  remote asr_worker over HTTP
   ├── brain  ── prompts + JSON schema  ──► ai.py ──► 8 providers / custom OpenAI-compatible
   ├── media  ── yt-dlp, ffmpeg, probe, loudness
   ├── render ── ffmpeg filters, ASS captions, hook overlay, facecam crop
   └── posting ── platform APIs, due times, daily caps
```

**Durable state is split in two kinds of storage:**

| Stored where | What | Why it matters |
|---|---|---|
| PostgreSQL / SQLite | users, sessions, AI usage rows, email tokens, feedback, notices, admin log | relational, indexed, transactional |
| JSON files under `CLIPSORA_DATA` | jobs (`job.json`, `words.json`), creators, connected accounts & their tokens, AI settings (`ai.json`), post queue (`posts.json`), notices-per-user, storage location, `storage.json` | no indexes, whole-file rewrites, per-file locking |

This split is the single most consequential architectural fact in the audit. It is not wrong for a one-machine tool — it is why the product installs in one command — but it is the ceiling on multi-user hosting, analytics and collaboration.

---

## 3. Capability inventory (verified in code)

### Ingestion
- URL import via yt-dlp (YouTube, Twitch VODs and clips, Kick and other supported sites), local upload, batch links, drag-and-drop, chunked uploads (`CLIPSORA_UPLOAD_PART_MB`).
- Channel lookups with live/preview metadata; per-creator multi-channel mapping (YouTube, Twitch, Kick, Instagram, TikTok profiles).
- Time-range import (`range_start`/`range_end`), max video hours cap, disk quota per user.

### Transcription
- Local sherpa-onnx model, remote ASR worker, YouTube transcript borrowing with a coverage check, per-clip re-transcription for exact word timing, Hinglish (Devanagari/Urdu → Roman) normalisation, English translation of non-English captions, caption wording repair by AI with per-word validation.

### Clip selection
- Windowed transcript analysis (15 min windows, 60 s overlap), game-awareness (extra rules + tags for known games), loudness z-score marks, live chat bursts, static/ad-break rejection, overlap suppression, loudness-only fallback when the AI is unavailable, configurable length/clips-per-video.

### Live
- Two independent judges (words-only, signals-only), must-pick mode, trigger words ("clip that"), per-hour caps, minimum gaps, rolling buffer in minutes, recording resume, storage guardrails, live worker isolated from video jobs.

### Rendering
- 1080×1920 only; layouts `blur`, `fill`, `split`, `gameplay` (auto facecam detection with a measured box, AI assist optional); 5+ caption styles; hook box with two-line balancing and auto-shrink; highlight-word colouring; optional captions; cover image; per-clip download and zip of many.

### Editing (what exists today)
- Per clip: hook text, title, description, caption style, layout, start/end seconds, captions on/off, **word-level caption correction (new, this session)**, **three hook/title options (new, unverified — see §12)**, re-make one clip.
- Per creator: 20+ settings covering AI thresholds, clip length/count, captions, big text, description, posting rules, privacy, rate per 1k views, credit line.

### Publishing
- OAuth connect for YouTube, Instagram, TikTok; queue with due times, per-account gap and daily cap, pause-all, retry, cancel, post-now, auto-post threshold, view polling, per-clip post badges.

### Accounts & operations
- Local single-user mode (`CLIPSORA_ACCOUNTS=0`) or full multi-user (email+password, Google sign-in, email verification, password reset, admin dashboard, per-user quotas), notifications bell, in-app feedback, legal pages, update checker, health endpoint, Docker healthcheck.

---

## 4. User journeys, traced end to end

### A. "Paste a link, get shorts"
`POST /api/jobs` → `jobs.create` writes `job.json`, enqueues into `_FairQueue` → worker `_run_job`: yt-dlp metadata → audio extract → loudness → optional YouTube transcript → blocks of 10 min transcribed → `brain.find_clips` per block → clips appended with `status:"queued"` → up to 6 parallel `render_one` calls → ffmpeg → `clips/*.mp4` + `.json` → `job.status="done"` → notice + creator log.
Frontend polls `/api/sync?v=<counter>`; `ctx.bump()` on any change makes the poll return fresh state; the dashboard redraws from that snapshot.

### B. "Fix a caption and keep the clip"
Clip editor → `PUT /api/jobs/{j}/clips/{c}/captions` → `jobs.set_caption_words` validates and stores `edited_words` on the clip → status `queued` → quick worker → `_caption_words` prefers the edited words → ffmpeg re-render → `version` +1 → the `<video>` element is re-fetched with `?v=<version>`.

### C. "Record a streamer while they're live"
Creator → `POST` start → `live.SESSIONS` starts an ffmpeg ring buffer with per-segment timestamps → every N minutes each judge reads its own slice → agreed moment → clip cut from the buffer → `jobs.submit_live` renders on the live worker → queue → post. Interruptions are recorded and the stream is resumed when it returns.

---

## 5. UI / UX problems (observed in the running app)

| # | Problem | Evidence |
|---|---|---|
| U1 | One 2.5k-line file with `innerHTML` re-renders; no components, no routing, no state store | `render()`/`drawShell()` rebuild whole regions; view state lives in a global `S` |
| U2 | Dashboard leads with four zero-value stat cards and an empty 14-day chart before any action | live screenshot of Home |
| U3 | Marketing chrome ("Star on GitHub", "Follow me", update banner) sits above the primary composer | same |
| U4 | No search, filter or sort anywhere in the library; 10 videos already scroll | no search input exists in `index.html` |
| U5 | Long labels truncate ("Custom (Open…") with no tooltip fallback | sidebar AI card |
| U6 | Editing a clip silently discards nothing but *gives no preview of the change* until re-render finishes | clip dialog |
| U7 | 20+ creator settings in one long form, no presets, no copy-from-another-creator | creator Setup tab |
| U8 | Light theme only; no dark mode | single palette in CSS variables |
| U9 | Accessibility is partial: ARIA on tabs/dialogs, but no focus trap in dialogs, no skip link, contrast untested | markup |
| U10 | Mobile layout collapses to a hamburger but the clip editor works poorly under ~420 px | CSS breakpoints |
| U11 | Errors surface as toasts that vanish; failures inside a job are only visible in a text log | creator Log tab |
| U12 | No onboarding beyond a "Next steps" card; nothing explains what a creator is or why to connect an account | `nextSteps()` |

---

## 6. Backend limitations

| # | Limitation | Consequence |
|---|---|---|
| B1 | Domain objects (jobs, creators, accounts, posts) live in JSON files guarded by an `RLock` and retried file replaces | no querying, no pagination, no foreign keys; whole-file writes grow with history; concurrent renders rely on luck and locks |
| B2 | `server.py` is 1,684 lines holding routes, validation, throttling and HTML serving | hard to test in isolation, easy to regress |
| B3 | No schema migrations — `meta.create_all()` only | any column change needs hand-written migration code |
| B4 | One in-process queue per machine, no durable queue | a crash mid-render is recovered by re-queuing from `job.json`, not by a broker; no horizontal scaling |
| B5 | Rendering is CPU-bound in threads; 2–6 concurrent ffmpeg processes per video, ×JOB_WORKERS | a big machine can be oversubscribed; no GPU path, no hardware encoder selection |
| B6 | Every AI call is a direct `httpx` request inside the request or job thread; no prompt versioning, no per-provider cost model | slow providers block a worker thread; cost is tokens only |
| B7 | Polling (`/api/sync` every 2–4 s) instead of server push | O(clients) polling load; no live progress events |
| B8 | No structured logging, metrics or tracing; errors go to `error.log` per job and stdout | no way to answer "why was this slow" in production |
| B9 | Rate limiting is per-process, in-memory | resets on restart; meaningless across replicas |

---

## 7. Database design problems

- Only identity/telemetry data is relational. There are **no `jobs`, `clips`, `creators`, `accounts` or `posts` tables**, so analytics ("best performers", "clips by category") can only be computed by scanning every `job.json` on disk.
- `usage` is per-call rows with `(user_id, t)` index — good — but there is no rollup, so the 14-day chart recomputes from files.
- No retention policy for `usage`, `notices`, `feedback` (they grow forever).
- `sessions.expires_at` has no index; expiry cleanup is a scan on each login.
- Publishing credentials (OAuth tokens) are stored in `accounts.json` in the data folder, not encrypted, protected only by file permissions.
- No audit trail for user-initiated destructive actions (only admin actions are logged).

---

## 8. Performance observations

Measured on this machine (Docker Desktop, 16.5 GB RAM), not a benchmark rig:

- Re-making one 55-second clip: ~20 s end to end (transcript cached, one ffmpeg pass).
- Full video, 10 clips: minutes, dominated by ASR (local, CPU) and one ffmpeg per clip.
- `/api/sync` with no changes answers from memory (counter compare) — cheap; with changes it serialises every job of that user.
- Idle memory ~250–400 MB; model load adds ~500 MB when transcribing.
- Bottlenecks in order: ASR on CPU → ffmpeg encodes → `yt-dlp` downloads → AI latency.

---

## 9. Security posture

**Present and good:** session tokens stored only as SHA-256 hashes; password hashing via a KDF; optional Google OIDC; per-user data isolation enforced through `ctx.uid()` (never from the request body); SSRF allowlist (`CLIPSORA_ALLOWED_SITES`) and URL validation; upload part/size caps; path traversal guards on media serving; per-route throttles; security headers and a CSP; `no-store` on personalised responses; local mode binds 127.0.0.1; HTML escaping throughout the single-page app; injection-resistant prompt handling (`brain._safe` / `_text`).

**Gaps to fix in P0:** publishing tokens unencrypted at rest; no CSRF token (mitigated by SameSite cookies + origin checks — needs verification and tests); no MFA; no per-user API tokens; feedback/log context can capture user text; no dependency vulnerability scanning in CI; admin actions logged but not user deletions.

---

## 10. Feature gaps against the market (detail in `MARKET_RESEARCH.md`)

Table stakes missing: transcript-based trimming, silence/filler removal, SRT/VTT export, aspect ratios beyond 9:16, brand kits/presets, bulk scheduling calendar, retention analytics.
Differentiators this codebase already earns and should protect: local ASR with no per-minute cost, BYO AI key, explainable clip selection (reason per clip), live clipping with two judges, self-hosting, real per-creator posting rules.

---

## 11. Preserve / redesign / remove

| Decision | Items |
|---|---|
| **Preserve as-is** | fair queue and worker model; live recorder and dual judges; ASR pipeline (local + remote); render/caption/hook engine; yt-dlp media layer; auth and admin; SSRF and throttle guards; the 30-file test suite |
| **Redesign** | the single-page frontend → component architecture with design tokens, routing, dark mode; job/creator/account/post storage → relational schema behind the same API surface; dashboard IA; clip editor layout; caption editing UX |
| **Replace** | polling-only sync → polling + SSE for job progress; ad-hoc HTML in `server.py` → template/route split; per-provider cost accounting → unified AI gateway with prompt versions; JSON `posts.json` queue → table with retry state machine |
| **Remove** | nothing user-facing. Internally: duplicate HTML page logic, dead fallbacks, the ad-hoc `_q.put(("clip", …))` string protocol (replace with typed tasks) |

---

## 12. Work already in flight (uncommitted, on this machine)

| Change | State |
|---|---|
| Hook-first / searchable-title rules in the clip-selection prompt (`brain.RULES`) | implemented, full suite passed, running in the container |
| Word-level caption editor + "Fix with AI" + re-render of one clip (`jobs.caption_words`, `jobs.set_caption_words`, `GET/PUT .../captions`, clip-dialog UI) | implemented, end-to-end verified on a real clip (version 1 → 2, 14 MB output, no errors) |
| Re-make a clip while its video is still running (removed the blanket `job.status in ("queued","running")` refusal) | implemented, gate behaviour verified by direct route calls |
| Three hook/title options per clip (`brain.variants`, `POST .../variants`, `PUT .../variant`, UI cards) | **code written, verification interrupted** — syntax compiles, but the behavioural check and suite run after these edits did not complete, and the container has not been rebuilt with them |

Recommendation: finish validating the variants work (one suite run + one real clip) before any larger refactor, so the blueprint is not built on an unverified baseline.

---

## 13. Audit conclusion

The engineering underneath is better than the interface on top of it. Clip selection, live recording, rendering and posting rules are real and tested; the gap to a premium product is **surface (UI/UX), structure (relational data, migrations, observability) and editing depth (transcript trim, captions, exports)** — in that order of user-visible payoff, and the reverse order of implementation risk.

The roadmap in `FEATURE_ROADMAP.md` is built on exactly that ordering, and `IMPLEMENTATION_PLAN.md` sequences it so the working product never stops working.
