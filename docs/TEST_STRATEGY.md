# Test Strategy

Clipsora's tests start a throwaway server on a spare port with an empty data folder (`python tests/run.py`), so
they never touch real videos, keys or the database. Each suite prints `PASS`/`FAIL` lines and exits non-zero on
failure.

## How to run

```bash
# local ffmpeg 9.1 used for verification (gitignored)
export PATH="$(pwd)/.tools/ffmpeg/ffmpeg-9.1-essentials_build/bin:$PATH"
export PYTHONIOENCODING=utf-8
.venv/Scripts/python tests/run.py             # every suite, isolated instance (needs ffmpeg on PATH)
.venv/Scripts/python tests/test_narrative.py  # one suite, no server, no ffmpeg
.venv/Scripts/python tests/test_load_queue.py "$(pwd)"   # takes the project root as an argument
```

On Windows, set `PYTHONIOENCODING=utf-8` before a suite that prints non-Latin text (`test_roman.py`); the
default cp1252 console cannot encode it and the suite exits before printing any result.

## Layers

| Layer | What it proves | Suites |
|---|---|---|
| Pure logic | boundaries, scoring, options, styles, hashtags, transliteration | `test_narrative`, `test_creative`, `test_styles`, `test_hashtags`, `test_roman`, `test_answer` |
| API contract | routes, guards, permissions, limits, approvals, ZIPs | `test_podcast`, `test_permissions`, `test_abuse`, `test_limits`, `test_delete`, `test_connect` |
| Pipeline | queue fairness, long videos, upload pieces, stuck clips, retries, storage | `test_load_queue`, `test_longvideo`, `test_upload_parts`, `test_stuck`, `test_retry`, `test_storage`, `test_jobsave` |
| Live | buffer timing, stop/start, empty URLs, failed recordings | `test_live`, `test_live_times`, `test_robustness` |
| Rendering | captions, styles, layouts, director graph, branding, outro/cover | `test_captions`, `test_bigtext`, `test_clip_edit`, `test_styles`, `test_director`, `test_podcast` |
| Security | visitor address, email normalisation, Google sign-in, prompt injection | `test_hardening`, `test_permissions` |
| AI | provider errors, rate limits, fallbacks, cheap-key mode | `test_ai`, `test_retry`, `test_local` |

## What Phase 1 and 2 added

**`tests/test_narrative.py`** — sentence grouping; mid-sentence start; question-context step-back; a 2-second
thought not stretched; a 90-second story not shortened; trim reporting `complete_end`; coherence; platform fit
for 180 s and 200 s; duplicate removal with a recorded reason; empty transcript safety.

**`tests/test_creative.py`** — five systems; deterministic selection for business/funny/emotional/declarative
content; brand preference; invalid preference fallback; every direction round-trips through
`styles.caption_config`/`layout_config`; readability bounds (≤5 words, 40–220 px); accessibility token present;
catalog completeness; job option validation; API 200/404.

**Phase 2.5–5 suites** — `test_migrations.py` (28 checks: fresh install, simulated pre-2.0 database with a live
row, idempotency, rollback refusals), `test_covers.py` (49 checks: frame ranking, headline rules, all five
compositions rendered to JPEG with measured text boxes), `test_brands.py` (40 checks: token validation, brand
isolation, adaptive outro, CTA, sonic filter, consistency), `test_publishing.py` (32 checks: transitions,
double-click dedupe, timeout honesty, reconciliation, bounded retries, package freeze), `test_integration.py`
(20 checks: the uploader reserving durable attempts, duplicate refusal, restart recognition, timeout vs
failure, fail-closed behaviour when the record cannot be written, brand option plumbing, CTA drawing, and
declining a missing signature sound). 256 checks across the seven suites passed before ffmpeg was available.

What the integration suite deliberately does **not** prove: that a platform accepted an upload. Media output and
the sonic mix were verified separately once a local ffmpeg was installed — see `docs/MEDIA_VERIFICATION.md`.

## Final media run

With ffmpeg 9.1 on `PATH`, **39 suites and 1179 checks pass (exit 0)**. The suites that were previously blocked at
their first encode now complete: `test_podcast` 78, `test_styles` 150, `test_captions` 16, `test_bigtext` 25,
`test_director` 13, `test_load_queue` 25. The full run also produced real clips and a 1080×1920 cover.

A real 6 s clip + 1.4 s outro render was then probed and inspected: 1080×1920 H.264 at 30 fps, AAC 48 kHz
stereo, max −10.3 dB, no black frames, chosen cover exported. Visual frames exposed and led to the fix of two
typography defects (hook box and caption spacing measured with the em-square instead of the pixel size).

`test_load_queue` failed once inside a full run at 97% CPU / 1.4 GB free RAM, then passed 25/25 alone. It is
recorded as an environmental flake.

**`tests/test_podcast.py`** — duration assertions updated from "30–60 s" to the content-driven contract
(8–180 s, `duration_basis` present, `platform_fit` present). No assertion was weakened or deleted; the old
boundary-snapping test with explicit `min_len=30, max_len=60` still runs unchanged.

## Rules

1. Write or update the test before the behaviour is claimed.
2. Never delete or weaken an assertion to make a build pass. When a product rule changes (as with duration),
   the assertion is rewritten to the new contract and the reason is recorded in this file.
3. Rendering claims are only made from a real file: `quality.verify_clip_quality` checks size, vertical ratio
   and duration, and tests assert the file exists and opens with Pillow/FFprobe.
4. Failures caused by the environment (no ffmpeg, cp1252 console) are reported as environment limitations, not
   as passes.

## Studio UI checks

The new studio at `/app` was exercised in a real browser with a seeded, isolated preview instance (one finished
clip with a rendered MP4, a 1080×1920 cover and word timings):

- Every screen loaded without a console error: Create, Projects, Library, clip editor, Brand Kit, Publishing,
  Analytics and Settings.
- Create was inspected at 1280 px and 390 px; the rail becomes a drawer and the form becomes one column.
- Editor tabs (Edit / Captions / Covers / Publishing) switched correctly; the real MP4 played.
- Saving the YouTube package persisted: the publishing API returned `state: ready` with the edited title, and the
  readiness checklist showed the package as prepared after reload.
- With no platform account connected, Publishing showed the blocker and never claimed a publication.

Playwright 1.65.2 now provides the regression layer:

```
python -m pip install playwright
python -m playwright install chromium firefox
python tests/browser/run_browser.py                 # compare committed baselines
python tests/browser/run_browser.py --update-baselines
python tests/browser/run_browser.py --only editor --headed
```

The runner starts an isolated server with a temporary data folder, generated H.264/JPEG media and word timings.
It covers all seven studio screens, create validation and request payloads, processing and cancellation, library
filters, editor metadata/captions/approval, clip brand + finish payloads, Brand Kit CRUD plus logo/sound uploads,
package persistence, axe on every screen, `/classic`, and Firefox H.264 playback.

Final result: **109 checks, 0 failed; 24 screenshot baselines at 1440×900, 1024×768 and 390×844 with 0 diffs;
0 serious/critical axe violations**. Playwright traces are collected on failure and screenshots/axe JSON are kept
under `tests/browser/artifacts/`. The browser suite is separate from `tests/run.py` because it needs downloaded
browser binaries; both are required before release.

## Current gaps

- PostgreSQL migrations and queries are not executed (no server).
- Browser coverage is Chromium + Firefox; WebKit is installed but not part of the required matrix.
- Keyboard-only traversal is not automated, although axe reports no serious/critical violations.
- Only `bounce` + `blur` were visually sampled; the other caption styles and layouts are contract-tested only.
- ASR was not exercised end to end: the media run used timed words from a fixture.
- Loudness normalisation (LUFS) and ducking under speech are not measured.
- No performance benchmark for the added direction/cover passes.

## Next tests to write (Phase 3+)

1. Cover ranking: given N candidate frames, the chosen cover is legible and contains the subject.
2. Opening: a podcast clip's first 0.5 s is speech when the cover intro is off.
3. Publishing: per-platform state transitions, idempotent retry, partial failure isolation.
4. Sonic identity: audio logo never exceeds 0 dBFS, ducking measured under speech.
5. Browser: create → process → review → approve → download, with a reduced-motion run.
