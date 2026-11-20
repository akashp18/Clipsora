# Implementation Plan

Read with `FEATURE_ROADMAP.md` (what) — this is **in what order, with what risk**.

---

## 1. Ground rules

1. `main` stays shippable every day. No branch lives longer than a week.
2. Every change to `studio/` runs the suite before and after (repo rule).
3. No feature ships without a failing-then-passing check.
4. No phase removes a working capability to make room for a new one.
5. Secrets never enter the repo; `.env` stays gitignored.
6. Every schema change has a migration and an importer dry-run.
7. Docs are updated in the same PR when an API or schema changes.

## 2. Sequence and dependencies

```
P0.1 variants verify ─┐
P0.2 new tests ───────┼─► P0.5 router split ─┬─► P0.3 SQL storage ─► P0.4 migrations ─► P1.7 search
P0.7 logging ─────────┘                      │
P0.6 security ───────────────────────────────┴─► P1.6 approval inbox
P1.1 design system + shell ─► P1.2 dashboard ─┬─► P1.4 clip editor v2 ─► P1.5 caption studio
P1.3 transcript trim ─────────────────────────┘
P1.8 cost meter (needs P0.3 usage rollups)
P2.x only after P1 acceptance criteria are met
```

Hard dependencies worth calling out:

- **P1.4 depends on P1.1** — rebuilding the editor before tokens/components exist would create a second styling system.
- **P1.7 depends on P0.3** — client-side search over `job.json` files cannot hold 500 projects.
- **P1.5 (export) depends on nothing** but is the natural pair with P1.4.
- **P2.6 (insights) depends on `clip_events`**, which only exists after P0.3.

## 3. Complexity estimates (relative, not calendar promises)

| Item | Days (1 dev, familiar with the code) | Uncertainty |
|---|---|---|
| P0.1 + P0.2 | 1–2 | low |
| P0.5 router split | 3–4 | low |
| P0.3 SQL + importer | 8–12 | high (data migration) |
| P0.4 migrations | 2–3 | low |
| P0.6 security | 3–5 | medium |
| P0.7 logging/metrics | 2 | low |
| P1.1 design system + shell | 6–8 | medium |
| P1.2 dashboard | 3–4 | low |
| P1.3 transcript trim | 4–6 | medium (caption re-timing) |
| P1.4 clip editor v2 | 8–10 | medium |
| P1.5 caption studio + SRT/VTT | 6–8 | medium |
| P1.6 approval inbox | 2–3 | low |
| P1.7 search/filters | 2–3 | low |
| P1.8 cost meter | 2 | low |
| P2.1 aspect ratios | 3–4 | medium |
| P2.5 calendar + bulk schedule | 5–7 | medium |

## 4. Risk register

| # | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R1 | Data migration loses or duplicates jobs | high | medium | importer with dry-run, count verification, files retained, dual-read fallback |
| R2 | Router split subtly changes a response | medium | medium | response diffing per route before/after; suite as the oracle |
| R3 | Editor rewrite stalls behind component work | medium | high | ship screens one at a time; keep old markup until replaced and verified |
| R4 | ffmpeg/yt-dlp breakage breaks the demo | high | medium | pinned versions, upgrade runbook, friendly failure + fallback path |
| R5 | AI provider limits make clips look bad | high | high | local-model path documented, loud banner, no silent quality drop |
| R6 | Windows path length (>260 chars) returns | medium | medium | temp-dir render already; add a CI simulation + docs |
| R7 | Security regression during large refactor | high | low | S1/S2 land early; auth tests are part of the suite |
| R8 | Scope creep from the feature list | high | high | roadmap is the contract; new ideas go to P3 with a note |

## 5. Proposed folder structure (target)

```
studio/
  server.py              # app factory, middleware, mounts only
  routers/               # auth.py creators.py projects.py clips.py captions.py variants.py
                         # posting.py insights.py admin.py pages.py media.py health.py
  services/              # jobs.py render.py live.py selection.py publishing.py analytics.py costs.py
  infra/                 # db.py queue.py storage.py ai/ (gateway, prompts/) logging.py config.py
  migrations/            # 0001_init.sql ...
  migrate.py             # JSON → SQL importer (dry-run)
web/
  index.html             # shell
  design/                # tokens.css components.css
  js/                    # api.js store.js components/ views/ app.js
  brand/                 # logo, favicon, social cards
tests/                   # unchanged layout + e2e/ (Playwright) + fixtures/
docs/                    # this blueprint + user-facing docs
```

Existing module names are kept where they still make sense (`brain.py`, `media.py`, `transcribe.py`) — renaming files costs review time and breaks deep links in docs.

## 6. Existing vs proposed, at a glance

| Area | Existing | Proposed |
|---|---|---|
| Storage | JSON files + 8 SQL tables | SQL for all domain objects; files only for media/transcripts |
| API | 72 unversioned routes | `/api/v1` with typed errors, pagination, SSE |
| Frontend | one 2.5k-line file | shell + views + components + tokens, still build-free |
| Editor | dialog with fields | preview-first editor with trim, variants, captions, undo |
| Captions | styles + word fix | full studio + SRT/VTT + translated output |
| Publishing | queue with rules | + approval inbox, calendar, per-platform settings |
| Insights | views count | usage/cost + platform metrics + clip_events analysis |
| Deploy | compose (app+db) | unchanged + migrations on start + healthcheck |

## 7. Definition of done (project level)

A phase is done when: suite + new checks green; the feature works on a clean install and on an upgraded install; docs updated; no known security regression; measured numbers recorded in the PR; and one real user (or the owner) has done the journey end to end without a workaround.

## 8. Decisions needed before coding starts

1. **Repository destination** — exact GitHub owner/repo for the new history (the directive says "a repository that I will specify"; it has not been given yet).
2. **Brand** — Clipsora, recorded in `BRANDING.md`; domain and trademark checks are the owner's before any public use.
3. **Licence intent** — keep MIT for the whole product (recommended), or split a paid hosted tier into a separate repo.
4. **Scope for the first implementation block** — recommended: P0.1–P0.2 + P0.5 + P1.1 shell, so the app immediately looks different *and* the unverified work is closed.
