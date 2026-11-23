# Clipsora Studio UI

The signed-in product now opens on the new studio at `/app`. The previous workspace stays at `/classic`
(live recording, creator profiles, Style Learner, posting queue and storage tools).

## Architecture

No framework and no build step. Four modules are served by the existing `/assets/{name}` route:

| File | Responsibility |
|---|---|
| `web/studio.html` | Shell: charcoal rail, breadcrumb topbar, view container, modal and toast roots |
| `web/studio.css` | Design system: colour, type, spacing, components, breakpoints, focus and reduced motion |
| `web/studio-core.js` | API client, shared state and cache, router, formatters, nav, dialogs, status loading |
| `web/studio-flows.js` | Create, processing, projects, project detail, library |
| `web/studio-workspace.js` | Clip editor, Brand Kit, Publishing, Analytics, Settings |
| `web/studio.js` | Route table and first paint |

Routes are hash-based (`#/create`, `#/projects/:jid`, `#/library/:jid/:cid`,
`#/brands/:bid`, `#/publishing/:jid/:cid`, `#/analytics`, `#/settings`), so one page carries every screen
and navigation never reloads the shell.

## Design system

- Charcoal `#17191C` rail, graphite surfaces, warm paper `#F5F2EA`, warm-white cards, copper `#C58A4C`.
- Editorial serif for display type (Iowan Old Style / Palatino / Georgia), system sans for UI, mono for times.
- 4–64 px spacing scale, 4–14 px radii, hairline borders instead of shadows.
- One accent used for active navigation, focus, primary emphasis. No purple, no gradients, no glassmorphism.
- Visible `:focus-visible` rings, labelled controls, skip link, `aria-current`, live regions, and
  `prefers-reduced-motion` support.
- Breakpoints: 1180 px, 960 px (rail becomes a drawer), 620 px (single column, two-up clip grid).

## Screens and their APIs

| Screen | Real calls |
|---|---|
| Create | `POST /api/upload/start`, `PUT /api/upload/{id}/{n}`, `POST /api/upload/{id}/finish`; `POST /api/jobs`; `GET /api/brands`, `GET /api/creative/directions`, `GET /api/status` |
| Processing | `GET /api/jobs/{id}` every 1.8 s; `DELETE /api/jobs/{id}`; stage and percentage come from the job itself |
| Projects | `GET /api/podcast/projects`, `GET /api/jobs`, `GET /api/podcast/projects/{id}`, `/clips`, `download-approved` |
| Library | `GET /api/jobs`; `POST /api/podcast/projects/{id}/batch-approve`; per-project ZIP download |
| Clip editor | `GET /api/jobs/{id}`, `GET .../captions`, `PUT .../captions`, `PATCH .../metadata`, `PATCH .../timestamps`, `POST /api/jobs/{id}/clips/{cid}/render` (brand, sonic switch/gain, finish), `GET/POST .../covers`, `POST .../covers/select`, `PUT .../status`, `DELETE` clip |
| Brand Kit | `GET/POST /api/brands`, `GET/PUT/DELETE /api/brands/{id}`, `GET/POST/DELETE /api/brands/{id}/assets/{logo\|sonic}`, `POST/DELETE /api/brand/logo`, `GET /api/brand/logo` |
| Publishing | `GET /api/publishing/projects/{id}/clips/{cid}`, `POST .../prepare`, `PUT .../{platform}/package`, `POST .../{platform}/events`, `POST .../attempt`, `POST .../reconcile` |
| Analytics | `GET /api/jobs`, `GET /api/overview`, `GET /api/accounts` |
| Settings | `GET/PUT /api/settings`, `GET/PUT /api/ai`, `POST /api/ai/test`, `GET /api/storage`, `GET /api/accounts`, `DELETE /api/accounts/{id}`, `POST /api/alerts/test` |

Two small read routes were added because a browser cannot read server paths: a cover image endpoint
(`.../covers/{cover_id}/image`, owner-checked) and `GET /api/brand/logo`.

## What was verified in the browser

Screens inspected at 1280 px and 390 px with the local server and real data:

- Create: upload/link tabs, drag-and-drop target, brand/platform/count/length/direction controls,
  advanced settings, full-width generate bar.
- Projects: search, status filter, sort, real empty state.
- Library: real 9:16 cover, approval badge, selection controls, filters.
- Clip editor: real MP4 playback, title/hook/description, timing, style/layout, brand and finish,
  caption words, covers, publishing readiness; tabs switch without errors.
- Brand Kit: brand list, identity preview, full token form, per-brand logo and signature sound
  (upload, preview, replace, remove), account logo, save/delete/create.
- Publishing: clip picker, YouTube/Instagram package tabs, readiness checklist, platform state,
  prepare/reserve/reconcile actions.
- Analytics: real counts, missing platform data shown as a dash with an explanation, empty-history state.
- Settings: defaults, AI provider/key status, notifications, storage, connections, advanced tools.
- Console: no JavaScript errors on any inspected screen.

Screenshots are in `screenshots/` (`create-1280.png`, `brands-1280.png`, `analytics-1280.png`,
`settings-1280.png`, `library-1280.png`, `editor-1280.png`, `editor-captions-1280.png`,
`publishing-1280.png`, `create-390.png`).

## Caption Studio

The Captions tab is a dedicated editing surface over the clean cut (`GET /api/jobs/{jid}/clips/{cid}/preview`),
not a second application. It contains:

- a 9:16 video frame with a live caption overlay, safe guides and no native-control overlap;
- a style gallery built from the actual preset type, colour, stroke and panel, not icons;
- essential type controls (family, size, letter spacing, line height, group size, casing, position);
- advanced type and colour (stroke, shadow, panel opacity/colour, text/spoken/emphasis/stroke colours);
- motion (animation family, duration, intensity) and manual emphasis;
- the existing word transcript/timing editor;
- Save & render, Undo, Redo, Reset style and a safe-guides toggle.

The preview uses the same bundled fonts and preset data as the renderer. `Save & render captions` sends the full
`caption_cfg` plus `highlight_words`; the Edit-tab style select stays as a quick preset choice. See
`CAPTION_QUALITY_AUDIT.md` for the pre-change comparison and `CAPTION_DESIGN_SYSTEM.md` for the specification.

## Clip-level brand and sound

A clip stores `brand_id` and a `sonic` switch; `sonic_gain_db` is an optional explicit gain override. Everything
else stays owned by the Brand Kit, so identity has one source of truth. On re-render the server re-reads the brand
as the job's owner, never by a client-supplied path. A deleted or foreign brand never falls through to another
account: the clip keeps its current branding and receives a visible quality warning.

Brand assets are stored under `users/<user>/brands/<brand>/logo.png` and `sonic.<ext>`. The logo is decoded and
re-encoded with Pillow (under 2 MB); the sound is probed by ffprobe, must contain an audio stream, and is limited
to 10 seconds and 5 MB. Both read routes check brand ownership.

## Automated verification

`python tests/browser/run_browser.py` starts an isolated server with generated media and runs Chromium across
1440×900, 1024×768 and 390×844 plus Firefox for H.264 playback. It covers all seven screens, create validation
and payloads, processing/cancellation, library filters, editor metadata/captions/approval/brand finish, Brand Kit
CRUD and both asset uploads, YouTube/Instagram package persistence, readiness, axe WCAG 2 A/AA and `/classic`.

Final run: **109 checks, 0 failed, 0 serious/critical axe violations, 24 visual baselines with 0 pixel diffs**.
Artifacts and baselines are in `tests/browser/`; no baseline is rewritten unless `--update-baselines` is passed.

## Remaining limitations

- A full keyboard-only journey is not automated; axe and visible focus states pass.
- Real uploads to YouTube or Instagram were not attempted; no account is connected.
- Automatic publishing remains in the Classic workspace and fails closed.
- The browser fixture's H.264 clip verifies playback and editor state, not a new 1080×1920 product render;
  product render measurements remain in `MEDIA_VERIFICATION.md`.
