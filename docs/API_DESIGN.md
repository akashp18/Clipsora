# API Design

## 1. Today

96 routes, 72 of them under `/api`. No version prefix, no OpenAPI (intentionally disabled: `docs_url=None`), errors returned as `HTTPException(detail=...)` strings aimed at humans. Authentication is a session cookie; every route derives identity from `ctx.uid()`, never from the body.

Grouped inventory:

| Prefix | Routes | Responsibility |
|---|---|---|
| `/api/auth/*` | signup, login, logout, reset, verify, google, session | identity |
| `/api/jobs*` | create, list, get, delete, clip render, clip delete, clip captions, clip variants, bulk delete, zip | projects and clips |
| `/api/creators*` | CRUD, channel lookup, live start/stop, accounts link | creator workspaces |
| `/api/accounts*`, `/oauth/*` | connect, disconnect, platform status | publishing credentials |
| `/api/posts*` | queue, post now, cancel, retry, pause | publishing |
| `/api/ai*` | settings, models, test | AI provider |
| `/api/overview`, `/api/sync`, `/api/notifications`, `/api/status`, `/api/usage` | dashboards | read models |
| `/api/admin/*` | users, quotas, feedback, logs | administration |
| `/media/*`, `/brand/*`, `/assets/*` | files | delivery |

**Weaknesses:** no versioning; several endpoints return the whole job (large) when a delta would do; `/api/sync` returns an untyped blob; error payloads carry no machine-readable code; no pagination on any list.

## 2. Target contract

- Base: `/api/v1/*`. The v0 routes stay as aliases during migration and are removed one release later, with a changelog entry.
- Content type JSON; every response is `{"data": ..., "meta": {...}}` for collections, plain object for a single resource.
- Errors: `{"error": {"code": "clip_busy", "message": "This clip is still being made.", "detail": null}}` — `message` stays human, `code` is stable for the frontend.
- Pagination: `?limit=&cursor=` keyset, `meta.next_cursor`.
- Timestamps: epoch seconds (as today) to avoid a second date dialect.
- Idempotency: `Idempotency-Key` accepted on `POST` create/queue routes.

### Resource shapes (abridged)

```jsonc
// Project
{ "id": "20261120-140347-a31795bf85", "creator_id": "cr_ab12", "kind": "video",
  "title": "CARRYMINATI PLAYS GTA VI", "status": "done", "stage": "Done", "progress": 1.0,
  "duration": 4231.2, "game": "GTA 6", "created_at": 1763633000, "finished_at": 1763633600,
  "counts": {"clips": 10, "queued": 0, "failed": 0} }

// Clip (list shape)
{ "id": "clip01", "start": 249.85, "end": 305.56, "score": 85, "category": "shock",
  "hook": "THE COUNTDOWN", "title": "GTA 6 Countdown Ends With Pure Screaming",
  "status": "done", "version": 2, "file": "clip01.mp4", "cover": "clip01.jpg",
  "variants": [{"hook": "…", "title": "…", "angle": "the fail"}], "posts": [] }
```

### Key routes (new/changed)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/projects` | link/upload/live; returns `202` + project id; `Idempotency-Key` |
| `GET` | `/api/v1/projects?status=&creator=&q=&limit=&cursor=` | server-side search replaces client filtering |
| `GET` | `/api/v1/projects/{id}` | full project + clip list |
| `GET` | `/api/v1/projects/{id}/events` | SSE: `{stage, progress, clips_changed:[ids]}` |
| `PATCH` | `/api/v1/clips/{id}` | hook, title, description, start, end, layout, style, captions — one call, one re-render |
| `GET/PUT` | `/api/v1/clips/{id}/captions` | word list with times; `PUT {words}` or `{retry:true}` (exists today) |
| `POST` | `/api/v1/clips/{id}/variants` | three openings (exists today) |
| `PUT` | `/api/v1/clips/{id}/variant` | choose one (exists today) |
| `GET` | `/api/v1/clips/{id}/download?format=mp4|srt|vtt` | SRT/VTT new |
| `POST` | `/api/v1/clips/{id}/undo` / `redo` | clip-scoped history (P1.4) |
| `GET` | `/api/v1/posts?status=needs_approval` | approval inbox |
| `PUT` | `/api/v1/posts/{id}` | `{action: "approve|skip|retry|reschedule", due_at?}` |
| `GET` | `/api/v1/insights/usage?range=14d` | tokens, cost estimate, per project |
| `GET` | `/api/v1/insights/performance?range=30d` | platform-derived metrics only, labelled by source |
| `POST` | `/api/v1/assistant` | contextual: `{clip_id, intent, text?}` — not a chat endpoint |

### Compatibility rules

1. No field removed from a response without a major version.
2. A new required field on `POST` is a breaking change → default it server-side.
3. The frontend ships in the same artefact as the backend, so a version bump is coordinated — but the alias routes keep external scripts (and users' own automations) working for one release.

## 3. Validation

Pydantic models per request body in `routers/`; the service layer re-validates anything that reaches disk or ffmpeg (as `jobs._clean_caption_words` does today) — the API is not the only caller of a service.

## 4. Rate limits and quotas

Keep the existing per-route throttle mechanism, move the counter behind a small interface so a shared store is possible. Limits documented per route in the OpenAPI schema that will be generated for v1 (doc-only, still not served publicly on a self-hosted install unless enabled).
