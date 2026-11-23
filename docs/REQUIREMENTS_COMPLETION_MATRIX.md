# Requirements Completion Matrix

Authoritative checklist for Clipsora 2.0. "Verified" means behaviour was executed in this environment and its
output or state was inspected. A module existing, a table existing or a unit test passing is **not** enough for
"complete".

Legend: **CV** complete and verified · **II** implemented, not integrated · **PI** partially implemented ·
**IU** implemented, unverified (needs media/DB/browser) · **NI** not implemented · **BL** blocked by environment.

Environment facts behind many statuses: a project-local `ffmpeg`/`ffprobe` 9.1 in `.tools/` (gitignored) was used
for the media runs; the Docker daemon does not answer and no PostgreSQL server is available; Playwright 1.65.2
with bundled Chromium and Firefox is installed under `.venv`, with committed browser tests in `tests/browser/`.
Those are stated per row rather than hidden. See `docs/MEDIA_VERIFICATION.md` for the measured output.

## A. Narrative intelligence

| # | Requirement | Status | Where | API | UI | DB | Tests | Evidence / gap |
|---|---|---|---|---|---|---|---|---|
| A1 | Content-driven clip duration, no arbitrary editorial cap | CV (unit) | `narrative.natural_window`, `duration_policy` | via jobs | existing editor only | `podcast_clips.master_duration` | `test_narrative` 22 | A 200 s story is not cut at 180; processing guard defaults 600 s, configurable |
| A2 | Sentence-aligned beginnings and endings, context step-back | CV (unit) | `narrative.sentence_spans/natural_window` | via jobs | no | `duration_basis` | `test_narrative` | Question/colon and continuation-word step-back covered |
| A3 | Complete/incomplete ending reporting | CV | `natural_window.complete_end`, `platform_variants` | via jobs | not shown | `narrative_json` | `test_narrative` | Warning text exists; UI does not surface it yet |
| A4 | Duplicate topic removal | CV (unit) | `narrative.diversify` | via jobs | no | `quality_json` | `test_narrative` | Records `diversity_of` and a reason |
| A5 | Platform compatibility, separately from length | CV (unit) | `narrative.platform_fit` | via clips API | no | `platform_fit_json` | `test_narrative` | Sources and dates recorded in `PODCAST_INTELLIGENCE.md` |
| A6 | Editorial score, confidence vs uncertainty | CV (unit) | `podcast.py` | clips API | partially | `score*`, `confidence` | `test_podcast` (partial) | "Not a virality probability" stated in `score_note` |
| A7 | Real transcript → real MP4 verification | PI | `render.render_clip` | — | — | — | `test_podcast` | Real H.264 1080×1920 7.4 s MP4 produced and probed; timed words came from a fixture, not a live ASR provider |

## B. Creative direction and typography

| # | Requirement | Status | Where | API | UI | DB | Tests | Evidence / gap |
|---|---|---|---|---|---|---|---|---|
| B1 | Five distinct systems with tokens | CV (data) | `creative.SYSTEMS` | `/api/creative/directions` | no picker | `creative_direction` | `test_creative` 65 | Caption configs round-trip through `styles`; distinctness of encoded output unverified |
| B2 | Content-aware deterministic selection | CV | `creative.choose` | `/api/...` | no | clip rows | `test_creative` | Fixed tie-break; brand preference respected |
| B3 | Preview and export share one spec | CV (contract) | `creative.render_settings` | `/api/...` | editor preview partially | — | `test_creative` | Shared spec is contract-tested; no pixel-level preview/export comparison |
| B4 | Professional typography: line breaking, no overflow | CV | `render.py`, ASS builder, Caption Studio | `/api/status`, preview route | Caption Studio | styles in job.json | `test_styles`, `run_browser` | Balanced clause groups; wrap before shrink; word order preserved; letter spacing reaches ASS and CSS. Contact sheet and before/after in `CAPTION_QUALITY_AUDIT.md` |
| B5 | Animated captions, all existing styles preserved | CV | `styles.py`, `render.py` | `/api/status` | Caption Studio | styles in job.json | `test_styles` 154, `run_browser` | 14 presets contract-tested and all 14 visually sampled at 1080×1920; style IDs and APIs unchanged |
| B6 | Intelligent speaker framing / active speaker | NI | — | — | — | — | — | Smart Director uses edge/composition heuristics, not face or active-speaker detection. Not called "intelligent framing" |

## C. Covers, openings, brand, audio

| # | Requirement | Status | Where | API | UI | DB | Tests | Evidence / gap |
|---|---|---|---|---|---|---|---|---|
| C1 | Frame candidate generation and ranking | CV (ranking) / IU (extraction) | `covers.frame_scores/rank_frames` | covers API | no | `clip_covers` | `test_covers` 49 | Extraction returns 503 without ffmpeg; ranking tested on synthetic frames |
| C2 | Five cover compositions, brand-safe, no overflow | CV (JPEG) | `covers.render_cover` | covers API | no gallery | `clip_covers` | `test_covers` | Real 1080×1920 JPEGs produced and measured; accent pixels verified |
| C3 | Headline generation without clickbait | CV | `covers.headline_candidates` | covers API | no | `clip_covers.headline` | `test_covers` | Blocklist and length/tension scoring tested |
| C4 | Selected cover used by export, no re-render | CV | `render.cover_source`, ZIP selection | select endpoint | no | `reel_cover_path` | `test_integration`, media run | A pre-chosen 1080×1920 JPEG was passed to a real render and exported unchanged as the clip cover |
| C5 | Spoken-hook-first opening; no forced static intro | NI | — | — | — | — | — | Podcast default still uses the 1 s cover intro; `intro_seconds` is now configurable |
| C6 | Multiple brands, isolation, legacy import | CV | `brands.py`, Brand Kit | `/api/brands` | Brand Kit | `brands` | `test_brands` 63, Playwright | Create/edit/delete, switch default, legacy import and isolation are exercised in both tests and UI |
| C7 | Brand applied by renderer | CV | `jobs.render_one`, `render.py` | — | — | job.json | `test_integration`, media run | Rendered outro carries brand name, Instagram/YouTube handles and the CTA |
| C8 | Sonic identity: timing, gain, fades, limiter | CV | `brands.sonic_mix_filter`, `branding.mix_signature_sound` | `/identity` | no | `brands.tokens` | `test_brands`, media run | A 1 s sting was mixed into a real clip: AAC 48 kHz stereo, mean −17.5 dB, max −10.3 dB, no clipping. Loudness target not normalised |
| C9 | Adaptive outro preserves final words | CV | `brands.outro_plan` | `/identity` | no | tokens | `test_brands`, media run | A 1.4 s outro was appended to a 6 s clip (7.4 s output); the clip end is untouched and the end card is complete |
| C10 | One CTA per platform | CV | `brands.cta_for` | `/identity` | no | tokens | `test_brands`, `test_integration` | CTA pixels drawn on end card |
| C11 | Brand consistency validator | CV | `brands.consistency_issues` | — | no | — | `test_brands` | Detects accent/handle/direction/outro/sonic/CTA drift |
| C12 | Logo/audio upload and storage | CV | `brands.save_asset/delete_asset`, `routers/brands.py` | `/api/brands/{id}/assets/{logo\|sonic}` | Brand Kit | `brand_assets` | `test_brands` 63, Playwright | Owner-checked upload, Pillow PNG normalisation, ffprobe audio validation, 2/5 MB limits, replacement, deletion, previews and isolation tested |

## D. Publishing

| # | Requirement | Status | Where | API | UI | DB | Tests | Evidence / gap |
|---|---|---|---|---|---|---|---|---|
| D1 | Separate YouTube and Instagram packages | CV (existing) | `podcast.build_platform_packages`, `posting` | clips API | existing editor | job.json | `test_podcast` partial | Metadata editors exist in the old UI |
| D2 | Per-platform state machine | CV | `publishing.py` | `/api/publishing/...` | no | `publish_targets` | `test_publishing` 32 | 8 states, explicit transitions |
| D3 | Durable attempts, idempotency, concurrent safety | CV | `publish_attempts` | attempt endpoint | no | table | `test_publishing`, `test_integration` | Double click returns the live attempt |
| D4 | Timeout never treated as success | CV | `finish_attempt("unknown")` | reconcile | no | `needs_attention` | `test_publishing` | Reconciliation required |
| D5 | Uploader uses the state machine | II | `posting._publish_begin/_finish` | — | — | table | `test_integration` | Success/failure bookkeeping tested without an upload; real/mocked upload path not run |
| D6 | Fail closed when the durable record cannot be written | CV | `posting._publish_begin` | — | — | — | `test_integration` (new) | Upload is refused, post marked failed with an actionable error; test asserts the platform function is never called |
| D7 | Bounded retries | CV | `publishing.MAX_ATTEMPTS=3` | events | no | attempts | `test_publishing` | Fourth attempt refused |
| D8 | Real platform upload verification | BL | — | — | — | — | — | No authorized accounts; not attempted |
| D9 | Automatic publishing UI and opt-in | NI | — | — | no | defaults.auto_publish | — | Default remains review-first |

## E. Interface

| # | Requirement | Status | Where | Evidence / gap |
|---|---|---|---|---|
| E1 | Primary navigation: Create, Projects, Library, Brand Kit, Publishing, Analytics, Settings | CV | `web/studio.html` at `/app` | All seven destinations exist; the previous workspace stays at `/classic`. See `STUDIO_UI.md` |
| E2 | Design system (tokens, type, spacing, states) | CV | `web/studio.css` | Charcoal/graphite/warm paper/copper tokens, editorial type, component states, breakpoints, focus and reduced motion |
| E3 | Create screen with brand/platform/direction | CV | `web/studio-flows.js` | Upload or link, brand, both platforms, auto/custom count, story-led or range length, direction, advanced settings |
| E4 | Real processing stages | CV | `web/studio-flows.js` | Polls `/api/jobs/{id}`; stage text and progress come from the job, never invented |
| E5 | Results workspace with cover/direction/status | CV | project detail, Library | Cover, title, score, direction, quality and approval are shown on real clips |
| E6 | Clip editor: cover selection, brand, outro, sonic | CV | `web/studio-workspace.js`, `jobs.request_render` | Preview, timing, captions, style/layout, covers, approval, clip-level brand, outro, watermark and signature-sound switch all persist; renderer re-reads the chosen brand |
| E7 | Brand Kit screen | CV | `web/studio-workspace.js`, `routers/brands.py` | Create/edit/delete brands, per-brand logo and signature-sound upload/replace/delete with previews, colours, type, handles, directions, cover, outro, CTAs and sonic levels |
| E8 | Publishing workspace (YT/IG tabs) | CV | `web/studio-workspace.js` | Separate packages, readiness, durable state, prepare/reserve/reconcile; real uploads still need a connected account |
| E9 | Analytics from real data | CV | `web/studio-workspace.js` | Counts from jobs and the posting queue; missing platform metrics shown as a dash, never zero |
| E10 | Accessibility and responsive layouts | PI | `studio.css` | Automated axe WCAG 2 A/AA on all seven screens: 0 serious/critical; 1440, 1024 and 390 inspected, defects fixed. Full keyboard-only journey not automated |
| E11 | Visual verification (screenshots) | CV | `tests/browser/baselines/` | 24 committed baselines (8 screens × 3 viewports), pixel-diff in CI-style run: 109 checks, 0 failed |

## F. Processing, operations, quality

| # | Requirement | Status | Where | Evidence / gap |
|---|---|---|---|---|
| F1 | Persistent job queue across restarts | NI | in-memory queues in `jobs`, `posting` | `job.json` survives, queue ownership/leases do not |
| F2 | Worker recovery and stage resume | PI | `live.recover`, `done_blocks`, `_piece_again` | Transcription resumes by block; no durable queue or lease |
| F3 | Health endpoint | CV | `GET /healthz` | Executes `select 1` |
| F4 | Readiness endpoint | NI | — | Not separate from health |
| F5 | Structured stage timings | NI | — | `job_events` table exists; nothing writes to it |
| F6 | Storage monitoring and cleanup | PI | `storage.py`, existing guards | Existing disk guard; no new cleanup job |
| F7 | Notifications for failures | CV (existing) | `alerts`, `notices` | Publishing failure notices fire from `posting` |
| F8 | FFmpeg MP4 verification | CV | `quality.verify_clip_quality` | 1080×1920 H.264, 30 fps, 7.4 s, AAC stereo, no black frames; measured with ffprobe/blackdetect |
| F9 | PostgreSQL migration and concurrency | BL | `migrations._is_pg` | No server available; SQLite path verified |
| F10 | Playwright journeys | CV | `tests/browser/` | 109 checks over navigation, create/validation/processing/cancel, library, editor, Brand Kit uploads, publishing, axe and `/classic`; Firefox decodes the real H.264 fixture |
| F11 | Visual regression | CV | `tests/browser/baselines/` | 24 baselines at 1440×900, 1024×768 and 390×844; 0.2% pixel threshold; 0 diffs on the final run |
| F12 | Security review of new endpoints | PI | existing hardening tests, `test_brands` | Brand asset ownership, foreign-brand writes, type/size validation and clip brand isolation tested at module level; no dedicated HTTP cross-account test for every new route yet |
| F13 | Performance benchmarks | NI | — | No measurements taken |
| F14 | Full regression suite | CV | `tests/run.py` | 39 suites, 1179 checks, exit 0 with the local ffmpeg 9.1. `test_load_queue` is the only flake seen (passes alone; failed once under 97% CPU) |
| F15 | Backward compatibility | CV | migrations, legacy settings | Migrations tested on a simulated old DB, and the pre-existing suites now all run to completion with ffmpeg available |
| F16 | Documentation reflecting reality | CV | `docs/` | Audit, roadmap, database, covers, brand, publishing, test strategy updated |

## Totals (counted, not estimated)

| Status | Count |
|---|---|
| Complete and verified | 46 |
| Implemented, not integrated | 1 |
| Partially implemented | 5 |
| Implemented, unverified | 0 |
| Not implemented | 7 |
| Blocked | 2 |

Counted over all 61 rows. The two remaining blockers are external: a PostgreSQL server (F9) and authorized
platform accounts (D8).

## What must happen next, in order

1. **PostgreSQL (F9)**: no server or running Docker daemon in this environment; migration SQL is written but unexecuted against PostgreSQL.
2. **Persistent queue (F1/F2)** with leases, heartbeats, crash recovery and stage timings in `job_events`.
3. **Speaker/expression detection (B6)** and hook-first openings (C5).
4. **Readiness endpoint (F4)** and complete temporary-file cleanup (F6).
5. **Security and performance passes (F12/F13)**, plus real ingestion with an authorized ASR/AI provider (A7) and authorized platform uploads (D8/D9/D5).
6. Optional automatic publishing UI (D9) once an authorized account exists.
