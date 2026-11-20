# Architecture — current, target, and the migration between them

## 1. Current (verified)

Single Python process. FastAPI serves pages, `/api`, `/media`, OAuth callbacks. Work happens on threads: a fair queue of video jobs, one "quick" worker for single-clip re-makes, one live worker, and a per-job thread pool of 2–6 renders. Identity data is in SQL; everything else is JSON files.

Strengths to keep: the queue's fairness and its independent quick/live lanes; the render engine; the media layer; the AI gateway's retry/fallback; the test harness.

## 2. Target

```
                     ┌────────────────────────── web/ (build-free SPA) ──────────────────────────┐
                     │  design tokens · components · views · api client · poll + SSE            │
                     └───────────────────────────────┬──────────────────────────────────────────┘
                                                     │ /api/v1/*
┌────────────────────────────────────────────────────▼───────────────────────────────────────────┐
│ FastAPI app                                                                                    │
│  routers/  auth · creators · projects(jobs) · clips · captions · variants · posting · insights  │
│            admin · pages · media · health                                                      │
│  services/ jobs · render · live · selection · publishing · analytics · costs                    │
│  infra/    db (SQLAlchemy) · queue · storage · ai gateway · logging · config                    │
└──────┬─────────────────────────┬───────────────────────────┬───────────────────────┬───────────┘
       │ SQL (PostgreSQL)        │ files (media, models)     │ threads/queue         │ httpx
   projects, clips, creators,    source video, clip mp4,      fair queue + quick     AI providers
   accounts, posts, usage,       words.json, covers           + live workers         (BYO key)
   notices, analytics events
```

**Decisions and why**

| Decision | Alternative rejected | Reason |
|---|---|---|
| Keep a single process with thread workers | Celery/RQ + Redis | the product is single-machine by design; a broker adds an install step and an ops burden that the primary user cannot carry. The queue interface is written so it can be swapped later. |
| Keep JSON only for large derived artefacts (`words.json`, video files) | store transcripts in SQL | transcripts are big, append-only, per-job blobs already read by path; moving them into SQL adds cost without enabling a feature |
| Move jobs/creators/accounts/posts into SQL | keep JSON + index files in memory | required for search, pagination, analytics, and for concurrent editors not corrupting each other |
| Keep vanilla JS, introduce components + tokens | React/Vite | no build step is a real self-hosting advantage; the pain today is styling sprawl and `innerHTML`, both fixable without a bundler |
| Add SSE for job progress, keep polling as fallback | WebSockets | one-way updates only; SSE survives proxies and needs no new dependency |

## 3. Module boundaries (target)

- `routers/*` — HTTP only: parse, validate (Pydantic models), call one service, return. No business rules.
- `services/*` — rules and side effects; no `Request`, no HTML.
- `infra/db` — engine, session scope, repositories per aggregate (`ProjectRepo`, `ClipRepo`…).
- `infra/queue` — the existing `_FairQueue`, with typed tasks (`JobTask`, `ClipRenderTask`) instead of `("clip", jid, cid)` tuples.
- `infra/ai` — today's `studio/ai.py` + prompt registry: every prompt gets an id and version string recorded in `usage`.
- `infra/storage` — one module that owns paths, quotas, atomic writes, cleanup. Nothing else builds a path.

## 4. Data-flow contract (unchanged where it matters)

`POST /api/v1/projects` → row + enqueue → worker stages update `projects.stage/progress` → clips rows inserted as found → render writes files, bumps `clips.version` → `ctx.bump(user)` → SSE event / poll returns the delta. The frontend contract ("poll with a version counter, redraw what changed") stays; SSE is additive.

## 5. Resource governance

- One governor decides how many renders may run: `min(JOB_WORKERS, cpus/2)` videos × `min(6, cpus/6)` clips, minus a reserve for the UI, with a memory watermark check (`load.busy()` today).
- Per-job stage budgets and the existing `CLIP_MINUTES` watchdog stay; a stuck ffmpeg still cannot hold a queue slot forever.
- Temp files live under one root with a sweeper that runs on job end and on start; the "uploads left behind" fix (commit `06bad18`) is preserved and extended to every artefact.

## 6. AI gateway evolution

Unchanged in shape (OpenAI-compatible + Gemini + Anthropic adapters). Additions only:
- prompt registry with id/version → stored per `usage` row;
- per-provider price table for the cost meter (marked "estimate");
- hard cap per user per day (opt-in) with a friendly refusal, not a crash;
- strict output validation: every AI answer passes the same `_tidy`-style sanitiser before it can reach a file or the UI.

## 7. Frontend architecture (no bundler)

```
web/
  design/tokens.css, components.css
  js/api.js        one fetch wrapper: errors, retries, CSRF header, abort
  js/store.js      single state object + subscribe()
  js/components/*.js   pure functions returning HTML strings, escaped by esc()
  js/views/*.js        one file per screen
  js/app.js        router (hash-based), keyboard map, boot
  index.html       shell only
```

Current monolithic `index.html` is split incrementally: shell + router first, then one view per PR, each shipped working.

## 8. Risks

| Risk | Mitigation |
|---|---|
| SQL migration loses a user's jobs | importer reads `job.json` files, writes rows, verifies counts, keeps files until the user confirms; a `--dry-run` mode |
| Splitting `server.py` breaks a route | routes are covered by the suite; split router by router with responses diffed before/after |
| Component rewrite stalls | shell first, then one screen at a time; old markup stays until its replacement is verified |
| Threads + SQL session misuse | one session per request/worker task via a context manager; repositories never share sessions across threads |
