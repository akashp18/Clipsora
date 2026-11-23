# Implementation Roadmap

Status is what the code does today, not what is planned. "Tested" means a suite in `tests/` exercises it in
this environment; "verified" additionally means real media was produced and measured, which requires ffmpeg.

## Phase 0 — Audit and stabilisation: done

- Working tree audited (`docs/CURRENT_STATE_AUDIT.md`).
- Fixed: post-render `KeyError: 'title'`; editor style switch overridden by a saved caption config.
- ffmpeg-dependent suites remain blocked on this host (see Test Strategy).

## Phase 1 — Narrative intelligence: done (core)

- `studio/narrative.py`: sentence spans, natural windows, context step-back, coherence, diversity,
  platform fit, `processing_limit()`, `duration_policy()`, `platform_variants()`.
- `studio/podcast.py`: content-driven duration, structured narrative fields, confidence vs score, duplicate
  removal, sentence-walking heuristic fallback.
- Duration is now four separate things: editorial (content), platform reach/upload, processing safeguard
  (`CLIPSORA_MAX_CLIP_SEC`, default 600 s), and an optional user range. A 180 s platform recommendation no
  longer truncates a master edit.
- Metadata is persisted in `podcast_clips` through additive migrations.
- Tests: `test_narrative.py` (22 checks), updated `test_podcast.py`.

Remaining: opt-in silence/filler tightening with a measured duration drop.

## Phase 2 — Creative Direction Engine: done (core)

- Five versioned systems with typography, colour, caption, motion, safe area, cover, outro, CTA, audio and
  accessibility tokens; deterministic selection; render-parity settings.
- `GET /api/creative/directions` and `/{name}`.
- Per-clip direction; a user's own style/layout always wins.
- Tests: `test_creative.py` (65 checks).

Remaining: direction picker and design-token stylesheet in the UI.

## Phase 2.5 — Architecture: done (core)

- `studio/migrations.py`: numbered additive migrations, SQLite/PostgreSQL aware, idempotent, recorded in
  `schema_migrations`, called by `db.init()`.
- New tables: `brands`, `brand_assets`, `clip_covers`, `clip_versions`, `quality_reports`,
  `publish_targets`, `publish_attempts`, `job_events`; ten new clip columns.
- Historical `job.json` projects keep working; nothing renamed or dropped.
- Tests: `test_migrations.py` (28 checks), including a simulated pre-2.0 database with live rows.

## Phase 3 — Premium cover and opening system: core done

Done:
- Deterministic frame scoring (sharpness, exposure, contrast, subject, negative space, clutter) and ranking
  (`studio/covers.py`), tested on synthetic frames.
- Headline generation, cleaning and scoring with a clickbait blocklist; deterministic choice; options kept.
- Five 1080x1920 compositions (editorial, statement, documentary, minimal, kinetic) inheriting Brand Kit
  accent and direction typography; measured text boxes, computed overflow, long-word shrinking.
- Candidate persistence (`clip_covers`) and API: list / generate / select; generation reports a clear 503 when
  ffmpeg is unavailable.
- Tests: `test_covers.py` (49 checks), including a real JPEG for every composition.

Integrated:
- `render_clip` accepts a cover chosen in the review screen (`cover_source`), uses it for the intro card and
  the exported `_cover.jpg`, and skips making a second one. Selecting a cover never re-encodes the video.
- The approved-package ZIP prefers the selected cover (`reel_cover_path`), then the render-time cover.

Remaining:
- Face/expression and blink rejection; OCR check for burnt-in text.
- Opening behaviour: make the spoken hook the podcast default (cover intro opt-in).
- Visual regression screenshots of rendered covers.

## Phase 4 — Multi-brand, sonic identity and outros: core done

Done:
- `studio/brands.py` + `studio/routers/brands.py`: several brands per account, validated and clamped tokens,
  legacy settings imported as the first brand, default switching, per-account isolation.
- Adaptive outro style and duration; never starts before the final words plus 0.25 s.
- One primary CTA per platform, overridable per brand.
- Sonic identity filter: trim, fade, gain, delay, speech loudness target, hard limiter below full scale.
- Brand consistency validator.
- Tests: `test_brands.py` (40 checks).

Integrated:
- `jobs.render_one` resolves the clip's `brand_id` through the Brand Kit (scoped to the job's own user), applies
  name, handles and accent, computes the adaptive outro from `outro_plan`, and sets the single CTA.
- `render_clip` mixes the signature sound after the main encode through `branding.mix_signature_sound` and
  `brands.sonic_mix_filter`; a missing asset is a warning, not a failed render. The outro duration is the
  Brand Kit's, not a fixed two seconds.

Remaining:
- Upload UI and storage for logo/audio (`brand_assets` exists), waveform preview.
- Music bed with ducking; encoded loudness verification (needs ffmpeg).

## Phase 5 — Publishing intelligence: core done

Done:
- Eight-state per-platform machine with explicit transitions (`studio/publishing.py`).
- Durable attempts with a unique request key; double clicks and worker restarts reuse the live attempt.
- A timeout is `needs_attention`, never `published`; reconciliation records what the platform actually has.
- Bounded retries (3), package edits refused once in flight, independent platform states.
- API: states, prepare, package, events, attempt, reconcile.
- Tests: `test_publishing.py` (32 checks).

Integrated:
- Publishing fails closed: if a durable attempt cannot be reserved, the upload is refused and the post is
  marked failed with an actionable error, rather than uploading without idempotency (test asserts the platform
  function is never called).
- `posting._publish_begin` / `_publish_finish` wrap every real upload: the queue reserves a durable attempt,
  refuses a duplicate, recognises a clip already published after a restart, records a timeout as `unknown`
  (never `published`) and a failure as `failed`. Bookkeeping failure degrades to the old behaviour instead of
  blocking an upload.

Remaining:
- Remote reconciliation lookups; automatic posting stays opt-in and off by default.
- Remote reconciliation lookups (YouTube video by id, Instagram container status).
- Schedule execution reporting and credential-expiry warnings.

## Phase 6 — Premium UI/UX: complete

`/app` now serves the seven-screen studio (Create, Projects, Library, Brand Kit, Publishing, Analytics, Settings),
the clip editor, a charcoal/paper/copper design system, real processing stages, progressive disclosure, separate
publishing packages, responsive layouts and accessible states. `/classic` preserves the previous workspace.
Playwright covers all screens at 1440/1024/390, compares 24 visual baselines and reports zero serious axe issues;
see `STUDIO_UI.md` and `TEST_STRATEGY.md`.

## Phase 7 — Reliability and automation: partial

Exists: fair queue, load governor, resume-from-block, live recovery, disk guard, retries, notifications.
To build: persistent queue across restarts, per-stage timing, failure classification with one safe automatic
retry, health endpoint, actionable credential/disk notices. `job_events` is the table those logs will use.

## Phase 8 — Release readiness: media half verified, UI/ops half open

Done with a project-local ffmpeg 9.1 (`.tools/`, gitignored): full regression (39 suites, 1179 checks, exit 0),
FFprobe validation of a real 1080×1920 render (duration, ratio, audio, black frames), a measured sonic mix, a
chosen-cover export, and visual inspection of hook/caption/outro frames. That inspection found and led to the
fix of two typography defects; see `MEDIA_VERIFICATION.md`.

Playwright and automated visual regression are now in place: 109 browser checks, 24 baselines at 1440/1024/390,
zero serious axe findings. Brand Kit now has owner-checked per-brand logo and signature-sound uploads, and clips
persist a brand and sonic override through re-render.

Still open: PostgreSQL (no server; Docker daemon does not answer), durable queue leases/recovery, readiness and
stage-timing endpoints, speaker-aware framing, hook-first podcasts, real ASR/ingestion, loudness/ducking
measurement, authorized publishing, security/performance passes. These are blockers or unimplemented features,
not documentation gaps.
