# Current State Audit — Clipsora 2.0 baseline

Written against the working tree (not the README), at the point the 2.0 programme started. Every claim below
was checked in code. "Implemented" means it runs and is wired; "partial" means the code exists but a required
behaviour is missing; "missing" means there is no implementation.

## 1. What exists and works

| Area | Where | State |
|---|---|---|
| FastAPI app, request gate, static pages, 120 routes | `studio/server.py`, `studio/routers/` | Implemented |
| URL ingestion (YouTube/Twitch/Kick allowlist, preview, cookies, YouTube block detection) | `studio/media.py`, `routers/jobs.py` | Implemented |
| Resumable chunked uploads | `routers/uploads.py` | Implemented |
| Live recording, chat spikes, AI judging, manual clip-last-30s | `studio/live.py` | Implemented |
| Local speech-to-text (Parakeet via sherpa-onnx), optional GPU worker | `studio/transcribe.py`, `asr_worker.py` | Implemented |
| AI gateway, 8 providers, retry/fallback, usage ledger | `studio/ai.py`, `usage.py` | Implemented |
| Gaming/stream clip selection, hooks, titles, caption tidying | `studio/brain.py` | Implemented |
| Podcast scoring engine, hooks, IG/YT packages, approval, ZIP | `studio/podcast.py`, `routers/podcast.py` | Implemented, duration policy replaced in 2.0 (see below) |
| Per-shot layout detection and multi-shot filtergraph | `studio/director.py`, `render._dynamic_filter` | Implemented |
| 14 caption presets, 17 layouts, 9 animations, shared preview/render config | `studio/styles.py`, `web/index.html` | Implemented |
| Reel covers, animated watermark, 1 s intro, 2 s outro, Brand Kit settings | `studio/branding.py`, `routers/settings.py` | Implemented |
| Style Learner (reference video → caption/layout profile, report, contact sheet) | `studio/style_learner.py` | Implemented (untracked in git) |
| Clip editor, triage filters, batch approve, approved ZIP | `web/index.html`, `routers/clips.py`, `routers/podcast.py` | Implemented |
| Creator workspaces, profiles, auto-record, posting rules | `studio/creators.py`, `profiles.py`, `routers/people.py` | Implemented |
| Publishing queue, YouTube/Instagram/TikTok connect, caps, retries | `studio/posting.py`, `accounts.py`, `routers/oauth.py` | Implemented |
| Accounts, Google sign-in, verification, resets, admin, quotas | `studio/auth.py`, `admin.py`, `api_common.py` | Implemented |
| SQLite by default, PostgreSQL on servers | `studio/db.py` | Implemented |
| Notifications (bell, Discord, Telegram, digest), storage manager, update check | `notices.py`, `alerts.py`, `storage.py`, `updates.py` | Implemented |
| Deployment: Docker, Compose + Postgres + Caddy, Nginx/Traefik samples | `Dockerfile`, `docker-compose.yml`, `deploy/` | Implemented |
| Test suite | `tests/` (32 suites before 2.0) | Implemented |

## 2. What was partial before 2.0, and what 2.0 changed

### 2.1 Clip duration was target-driven
`studio/podcast.py` asked the model for 30–60 s clips (35–50 preferred) and `snap_boundaries()` extended or
cut the moment to land inside those numbers. A complete 17-second statement was stretched; a 90-second story
was truncated or dropped.

**Changed (Phase 1):** `studio/narrative.py` now owns boundaries. `natural_window()` grows a hint outward to
the sentences that contain the thought, never pads a finished thought, and reports when a limit cut it short.
`discover_podcast_clips()` and `heuristic_podcast_clips()` use it; the prompt no longer names a target length.
Platform limits are checked separately (`narrative.platform_fit`).

### 2.2 Every podcast reel looked the same
Direction was a global caption style and layout chosen once per job (default `bounce` + `blur`).

**Changed (Phase 2):** `studio/creative.py` adds five versioned creative systems and a deterministic,
content-aware chooser. Jobs record `creative_direction` per clip and, when the user has not chosen their own
style/layout, apply that direction's caption and layout settings. `/api/creative/directions` exposes it.

### 2.3 Render risk hidden behind a strict dict build
`jobs._render_one` built its sidecar JSON with `clip[k]` for `title`/`description`. A clip without `title`
raised `KeyError: 'title'` *after* a successful render and was marked failed. Now `.get()`.

### 2.4 Editor style switch could be ignored
`request_render()` cleared `layout_cfg` when the layout changed, but not `caption_cfg` when the style changed,
so a fine-tuned caption config (from Style Learner or a creative direction) silently won over a new style.
Now a style change clears `caption_cfg` and sets `creative_direction = "off"`.

### 2.5 Intro cover was forced on every branded podcast clip
The 1-second static cover intro delayed the spoken hook. Defaults still allow it, but the direction system
reports `cover` as a separate asset; switching the podcast default off is a small, pending change (see roadmap).

## 3. What is missing (no implementation yet)

1. **Sonic branding** — no audio logo, ducking or loudness-matched sting. `branding.py` is visual only.
2. **Multiple brand profiles** — one Brand Kit per user (`accounts.SETTING_DEFAULTS`), no brand records, no
   per-project brand selection.
3. **Cover candidate generation and ranking** — one cover is produced deterministically; no candidates or scoring.
4. **Multi-shot speaker tracking** — `director.py` infers composition from edges and cuts, but there is no
   face tracking or active-speaker identification.
5. **Publishing state machine and idempotency keys** — `posting.py` has scheduled/posting/retry, but no
   per-platform independent status, no duplicate-post guard for retried requests, no "needs attention" state.
6. **UI redesign** — navigation is Overview / Videos & Clips / Style Learner / AI Usage / creators / Settings.
   The requested Create / Projects / Library / Brand Kit / Publishing / Analytics shell does not exist; the
   current page is a 4,600-line single file with no design-token discipline beyond `web/tokens.css`.
7. **Narrative summary / topic / visual direction in the database** — these live on the clip dict in
   `job.json`; `podcast_clips` has score columns but not these new fields.
8. **Crash recovery for the video pipeline** — `live.recover()` exists; a video interrupted mid-transcription
   restarts the block (`done_blocks`) but there is no persistent queue across restarts.
9. **Playwright / visual regression tests** — none.

## 4. Update after Phases 2.5-5 (this increment)

Implemented since the audit above:

- Additive migrations (`studio/migrations.py`) run from `db.init()`; ten clip columns and eight tables added,
  including `brands`, `clip_covers`, `publish_targets`, `publish_attempts` and `job_events`.
- Duration split into editorial, platform, processing and user policy; a master edit is no longer cut at 180 s
  because of a constant, and shorter coherent platform variants are reported rather than forced.
- Cover engine: frame scoring/ranking, headline scoring, five compositions, candidate persistence and API.
- Multi-brand Brand Kit, adaptive outros, one CTA per platform, sonic mix filter and consistency validator.
- Publishing state machine with durable attempts, idempotency, timeout honesty and reconciliation.
- New API surfaces: `/api/brands`, `/api/brands/{id}/identity`, `/api/podcast/.../covers`,
  `/api/publishing/...`.

Still missing: the UI redesign, the renderer consuming covers/brands, the upload worker using the new state
machine, Playwright/visual regression, and any real-MP4 verification on this host.

## 5. Known risks found in this audit

- `podcast_clips` uses `meta.create_all`, which does not add columns to an existing table. Any new column needs
  an additive migration runner (none exists), so 2.0 stores new clip metadata in `job.json` for now.
- `studio/style_learner.py`, `branding.py`, `podcast.py`, `director.py`, `narrative.py` and `creative.py` were/are
  outside version control at different points; `test_cover.jpg` and `test_outro.jpg` sit in the repo root.
- `CLIPSORA_BRAND_NAME`, `CLIPSORA_IG_HANDLE` and `CLIPSORA_YT_CHANNEL` are read by `config.py` but absent
  from `.env.example`.
- Rendering is CPU-heavy: a clip now runs up to four ffmpeg passes (main encode, cover frame, intro, outro).
  `RENDER_SECONDS = 600` and `CLIP_MINUTES = 15` are the only guards; there is no per-stage timing.
