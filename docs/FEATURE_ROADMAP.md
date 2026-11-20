# Feature Roadmap — P0 to P3

Scoring: **value** to the primary segment (1–5), **complexity** (1 = a day, 5 = a multi-week programme), **risk** to the working product if done badly. Every item names its definition of done (DoD). Nothing here is built until the blueprint is approved.

---

## P0 — Foundation (must land before any redesign)

| # | Item | Value | Cplx | Risk | DoD |
|---|---|---|---|---|---|
| P0.1 | **Finish and verify hook/title variants** (written, verification interrupted) | 4 | 1 | 1 | Full suite green; one real clip switched between options; container rebuilt |
| P0.2 | **Write the missing tests for this session's work** — captions route, variant routes, re-render gate while a video runs | 3 | 1 | 1 | New cases in `tests/`, suite green, no existing assertion weakened |
| P0.3 | **Relational storage for jobs/clips/creators/accounts/posts** behind the existing API | 5 | 5 | 4 | Same endpoints, same payloads; JSON import migration for existing installs; 30-file suite green |
| P0.4 | **Migrations** (Alembic or a versioned in-house runner) | 4 | 2 | 2 | Fresh install and upgrade-from-`06bad18` both verified |
| P0.5 | **Split `server.py`** into routers by domain (`jobs`, `creators`, `accounts`, `posting`, `admin`, `pages`) with no behaviour change | 3 | 3 | 2 | 96 routes respond identically; tests unchanged |
| P0.6 | **Security fixes:** encrypt publishing tokens at rest; verify + add CSRF protection; dependency scan in CI | 5 | 2 | 2 | Tokens unreadable in `accounts` storage; CSRF tests; `pip-audit` clean or documented |
| P0.7 | **Observability:** structured logs with job id, per-stage timings, `/api/metrics` (local only) | 3 | 2 | 1 | A failed job can be explained from logs alone |
| P0.8 | **CI:** lint, type-check on new code, full suite on push | 3 | 2 | 1 | Red build blocks a merge |

## P1 — Core product (the "premium app" layer)

| # | Item | Value | Cplx | Risk | DoD |
|---|---|---|---|---|---|
| P1.1 | **Design system + shell** (tokens, components, dark/light, responsive shell) | 5 | 4 | 3 | All existing screens re-skinned from tokens; no ad-hoc CSS per screen; axe clean on shell |
| P1.2 | **Studio dashboard** (recent work, active jobs with stage + ETA, quick actions, storage) | 5 | 3 | 2 | Zero-state teaches the next action; no fake metrics |
| P1.3 | **Transcript panel + trim by text** | 5 | 3 | 2 | Delete a sentence → clip shortens; captions stay aligned; undo works |
| P1.4 | **Clip editor v2** — preview, in/out handles, layout + crop, hook & title variants, caption editor, undo/redo | 5 | 4 | 3 | Every change previewable before render; one clip re-render < 30 s |
| P1.5 | **Caption studio** — styles, fonts, weights, colours, highlight words, position, outline/box, SRT/VTT export | 5 | 4 | 2 | Live preview of every change; export matches burned-in result |
| P1.6 | **Approval inbox** before publishing, with per-clip post text | 5 | 2 | 1 | "Needs approval" queue; approve/skip; auto-post rules visible |
| P1.7 | **Library search, filter, sort** (creator, status, score, favourites) | 4 | 2 | 1 | 500 videos stays usable; server-side query, not client scan |
| P1.8 | **Cost & usage meter** — tokens per clip, per day, estimated spend per provider | 4 | 2 | 1 | Numbers reconcile with `usage` table |
| P1.9 | **Silence / filler removal** (opt-in, pre-render) | 4 | 3 | 2 | Measured duration drop; captions re-timed; reversible |

## P2 — Advanced capabilities

| # | Item | Value | Cplx | Risk |
|---|---|---|---|---|
| P2.1 | Aspect ratios 1:1 / 16:9 / 4:5 + per-platform presets | 4 | 3 | 2 |
| P2.2 | Speaker detection & speaker-based layouts | 4 | 4 | 3 |
| P2.3 | Scene/shot detection for smarter in-points | 3 | 3 | 2 |
| P2.4 | Brand kits & templates (logo, fonts, caption style, intro/outro) | 4 | 3 | 2 |
| P2.5 | Publishing calendar + bulk scheduling + per-platform export settings | 5 | 3 | 2 |
| P2.6 | Performance insights: posted-clip performance, best categories, hook-variant winners | 4 | 3 | 2 |
| P2.7 | Multi-language captions out (translate to N languages) + dubbing (TTS) | 3 | 4 | 3 |
| P2.8 | Contextual AI assistant (per clip/project actions, not a chatbot) | 3 | 3 | 2 |
| P2.9 | Thumbnail studio (frame pick + text + AI variants) | 3 | 2 | 1 |
| P2.10 | Individual-clip API tokens + webhooks | 3 | 3 | 2 |
| P2.11 | GPU / hardware encode path, per-job resource governor | 4 | 4 | 3 |

## P3 — Future / experimental

Team workspaces & roles · review links with comments · approval chains · local LLM/ASR model manager · background removal / green screen · audio enhancement · cloud storage sync (S3/Drive) · mobile capture · marketplace for caption/hook templates · plugin system.

---

## Explicitly deferred (and why)

- **Entertainment-grade motion graphics / keyframed animation** — the render engine is a caption/hook compositor; turning it into an NLE is a different product.
- **Automatic publishing to unsupported platforms** (e.g. scraped endpoints) — platform-terms violation; a supported-API-only rule applies to every integration.
- **Cloud rendering offload** — contradicts the local-first trust story.

---

## Sequencing rule

Each phase must leave `main` shippable: P0 items land behind the same API; P1 items land screen by screen; P2 items are additive. No phase may require the app to be offline, and no phase may drop a working feature to make room for a new one.
