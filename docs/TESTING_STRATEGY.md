# Testing Strategy

## 1. What exists (measured)

- 30 files in `tests/`, ~600 individual `PASS/FAIL` checks.
- `python tests/run.py` starts a throwaway server on port 8799 with an empty data folder (`CLIPSORA_FETCH_MODEL=0`, `CLIPSORA_UPDATE_CHECK=0`, accounts on, no AI key, no outbound calls), then runs every test file in a child process with a hard time budget and prints a per-suite summary. Real data is never touched.
- Coverage areas: permissions and multi-user isolation, abuse/limits, queue under load, day-long video in little memory, delete/bulk, Windows-busy saves, big text, hashtags without AI, chunked uploads, AI providers (network faked), local mode and dashboard-saved key, Roman-script captions, caption toggling, platform connect, update notice, default limits, caption overlap/sentence endings, ad breaks/static screens, odd AI answers, rate-limit waiting, game detection, facecam, live buffer timing, fresh-install tool checks, storage folder, prompt hardening, robustness, live recording stops.
- Style: plain-language check names, no mocking framework, no network. A failing check prints `got …` / `want …`.

**Honest gaps:** no frontend tests, no end-to-end browser test, no performance budget, no run inside Docker/CI, one flaky check.

**The flaky check, diagnosed (not swept away):** `test_facecam` → "a video with nothing still in it finds no webcam" fails roughly 40 % of runs, on unmodified `06bad18` as well as on current code. Pinning ffmpeg's noise seed (`all_seed`) did **not** make it deterministic (2 of 3 runs still differed), so the fixture is not the cause: the detector's confidence on pure noise is borderline, and x264's thread-count-dependent output is enough to tip it. That is a genuine (if rare) false-positive path — a game scene with heavy static could be cropped as a "webcam" corner. The fix belongs in `studio/facecam.py` (require a minimum stillness share before returning `conf: "high"`), with a fixture matrix of noise, snow and confetti, not in the test.

## 2. Target pyramid

| Layer | Tool | Scope | Gate |
|---|---|---|---|
| Unit | existing `tests/*` style | sanitisers, time maths, gating rules, caption/trim/variant logic | every push |
| Service/API | existing server harness + `TestClient` | every route: auth, ownership, validation, error codes, idempotency | every push |
| Data | ephemeral Postgres + SQLite | migrations up/down, importer idempotency, quota queries | every push (SQLite), nightly (Postgres) |
| Media | ffmpeg fixtures (2–10 s synthetic clips) | render variants, caption burn-in, SRT/VTT export, silence removal, interrupted render recovery | every push |
| Frontend unit | node test runner, no bundler | store reducers, API client error mapping, token contrast script | every push |
| E2E | Playwright against a Docker stack | the 11-step journey in §3 | nightly + release |
| Performance | scripted benchmarks | load, upload, render throughput, memory ceiling | nightly, tracked over time |

**Rule inherited from the repo:** never weaken an assertion to make a run pass. A flaky test is fixed (deterministic fixture) or quarantined with an issue link — not retried silently.

## 3. End-to-end journeys (Playwright)

1. First run → paste a fixture URL (local file served as a fake "site") → clips appear.
2. Open a clip → edit captions → save → version increments and the preview reloads.
3. Ask for three openings → choose one → hook and title change, clip re-renders.
4. Smart trim: delete a sentence → duration shrinks, captions stay aligned.
5. Captions studio: change style → preview updates → SRT export matches words.
6. Approval inbox: pending clip → approve → post row enters `scheduled`.
7. Queue: pause all → due times freeze → resume → ordering preserved.
8. Failure path: AI key invalid → banner explains, clips still made by loudness.
9. Live: start recording on a fake stream → clips cut → stop → summary correct.
10. Multi-user: two accounts, each sees only its own projects, clips, posts and settings.
11. Destructive: delete a creator → confirm dialog names what is removed → media gone, other creators untouched.

## 4. Performance budgets (enforced, not aspirational)

| Metric | Budget | Measured today |
|---|---|---|
| App first paint (local) | < 400 ms | not measured |
| `/api/sync` with no changes | < 30 ms | answers from memory (not instrumented) |
| Project list, 500 rows | < 150 ms | not possible (client-side today) |
| Re-make one cached clip | < 30 s | ~20 s on this machine |
| Memory while transcribing 1 h | < 1.5 GB | ~700 MB observed |
| Idle RSS | < 400 MB | ~300 MB observed |

## 5. CI pipeline

```
push → ruff (lint) · py_compile · unit+api+media tests (SQLite) · frontend unit · token contrast script
nightly → above + Postgres job · Playwright E2E in Docker · pip-audit · perf benchmarks → tracked results
release → full matrix (Windows path limits simulated, Linux, Docker) + changelog + tag
```

Windows is a first-class target (ffmpeg path >260 chars broke rendering once already), so the release matrix must include a Windows runner or a documented simulation.

## 6. Definition of done for any feature

1. Behaviour covered by at least one new check that fails without the change.
2. Existing suite green; no assertion edited to accommodate new behaviour.
3. If it touches the render path: one real end-to-end render with a fixture, inspected.
4. If it adds a route: authorisation test (another user gets 404/403), validation test, error-code test.
5. If it changes schema: migration test up and down.
6. Docs updated (`API_DESIGN`, `DATABASE_DESIGN`, user-facing help).
