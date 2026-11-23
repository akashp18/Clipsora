# Working on Clipsora

A short map for contributors and AI coding assistants.

## Installing or updating Clipsora for someone

**Before installing, ask the person where to put it**, and suggest a short, permanent folder: `C:\clipsora` on
Windows, `~/clipsora` on a Mac or Linux. Do not just clone into the folder you happen to be running in: AI assistants
often run in a temporary, scratch or session workspace, which gets deleted, and whose path is long enough that
Windows cannot load the speech library (Windows can't open files whose full path is over 260 characters; the error
is "DLL load failed ... The filename or extension is too long"). Tell the person where you put it.

**When updating**, look at where Clipsora is first. If its folder path is long (roughly over 100 characters) or inside
a temporary or assistant workspace, ask the person whether to move it to `C:\clipsora` (or `~/clipsora`) as part of the
update. Moving is safe when done like this: clone the latest version into the new folder, copy over `.env`,
`storage.json` and the `data` folder if there is one (the videos and clips; `storage.json` may point to a data folder
elsewhere, which then stays where it is), install the requirements, start it from the new folder, check the clips
are there, and only then offer to delete the old folder. Never delete anything without asking.

## Run and test

- Run: `python -m studio.server` (settings from `.env`; see `.env.example`). Needs Python 3.10+ and `ffmpeg`.
- The speech model (about 480 MB) downloads by itself on first start; `python -m studio.fetch_model` gets it ahead of time.
- Tests: `python tests/run.py`. It starts a throwaway copy on a spare port with an empty data folder. Run it
  before and after any change to `studio/`. No keys needed.
- Browser tests: `python tests/browser/run_browser.py` (after `python -m playwright install chromium firefox`).
  It starts an isolated server with generated media and compares 24 committed visual baselines at desktop,
  tablet and mobile. `--update-baselines` rewrites them; `--only <screen> --headed` debugs one screen.
- To try a risky change by hand without touching real data:
  `CLIPSORA_DATA=<temp folder> CLIPSORA_PORT=8766 python -m studio.server`.

## Where things are

| File | What it does |
|---|---|
| `studio/server.py` | The app, startup, and the gate that runs before each request (who is asking, limits, headers) |
| `studio/routers/` | Every web route, one file per area: `pages`, `auth`, `dashboard`, `jobs`, `uploads`, `clips`, `projects`, `media`, `people`, `ai`, `settings`, `oauth`, `storage`, `postqueue`, `admin`, `notices` |
| `studio/identity.py` | Who is asking (`_me`, `_admin`, `_need_verified`) and the visitor-address checks the gate uses |
| `studio/api_common.py` | The guards and limits the routers share: free slots, disk quota, throttling, sync tokens, and the shared `BOOT`/`WEB`/`VIDEO_TYPES` |
| `studio/config.py` | Every setting, read from environment variables |
| `studio/ai.py` | The only code that talks to an AI service, and the AI settings saved from the dashboard (`ai.json` in the data folder) |
| `studio/narrative.py` | Where a story starts and ends: sentence boundaries, content-driven clip length, platform limits, duplicate removal |
| `studio/creative.py` | The five creative directions: typography, colour, motion, CTAs, and the exact render settings each one resolves to |
| `studio/covers.py` | Cover frames, headlines and the five 1080x1920 compositions, with measured text boxes |
| `studio/brands.py` | Several brands per account, their tokens, adaptive outros, CTAs and the sonic mix filter |
| `studio/publishing.py` | Per-platform publishing states, durable attempts, idempotency and reconciliation |
| `studio/migrations.py` | Numbered additive schema migrations for SQLite and PostgreSQL; `db.init()` runs them |
| `studio/brain.py` | The prompts: finding clips, live judging, hooks and titles, caption fixes |
| `studio/usage.py` | The record of AI calls and tokens shown on the AI usage page |
| `studio/jobs.py` | The video pipeline and the fair queue |
| `studio/live.py` | Live recording and clipping |
| `studio/transcribe.py`, `studio/asr_worker.py` | Speech to text, here or on a second machine |
| `studio/render.py` | Cutting, layouts and captions (ffmpeg and Pillow) |
| `studio/media.py` | Downloading (yt-dlp), probing, audio |
| `studio/auth.py`, `studio/account.py`, `studio/admin.py` | Sign-in, deleting things, the admin dashboard |
| `studio/db.py` | Database tables (SQLAlchemy core; SQLite or PostgreSQL) |
| `web/index.html` | The Classic signed-in app, one file, no build step (served at `/classic`) |
| `web/studio*.html/css/js` | The studio at `/app`: shell, design system, flows, editor, Brand Kit, publishing |
| `tests/browser/` | Playwright journeys, axe checks, visual baselines and the isolated server fixture |
| `studio/routers/brands.py` | Brand CRUD plus owner-checked logo/signature-sound upload, read and delete |
| `studio/styles.py` | The versioned caption and layout presets shared by preview and renderer |
| `studio/render.py` | ASS construction, font metrics, line breaking, animation and ffmpeg composition |
| `docs/CAPTION_QUALITY_AUDIT.md` | Classic vs Studio evidence, defects and corrections |
| `docs/CAPTION_DESIGN_SYSTEM.md` | Typography, grouping, motion, safe areas and parity rules |

## Rules worth knowing

- **Sign-in is off by default** (`config.ACCOUNTS`): every request then belongs to one built-in owner
  (`auth.local_user()`). With `CLIPSORA_ACCOUNTS=1` it is a normal multi-user site. Both paths are tested.
- **Who is asking** always comes from the session (`ctx.uid()`), never from the request body. Background threads
  set it themselves with `ctx.as_user(...)`.
- **Anything that changes what a user sees must call `ctx.bump()`**. The page polls `/api/sync`, which answers
  from memory when that user's counter has not moved.
- **Text from videos is untrusted**: it goes into prompts through `brain._safe` and out through `brain._text`.
- **Adding an AI provider**: add a row to `PROVIDERS` in `studio/ai.py`. If it speaks the OpenAI chat format that
  is all; otherwise add one function that returns `(parsed JSON, tokens in, tokens out)`.
- **Clips are rendered in a short temporary folder** and moved into place (`render.render_clip`): ffmpeg's caption
  step cannot open paths longer than 260 characters on Windows.
- **Publishing goes through `publishing.py`.** `posting._post` reserves a durable attempt before uploading and
  records the platform's answer after; never set a post to posted without the platform's id. A timeout is
  `needs_attention`, not success.
- **The story decides a clip's length.** `narrative.natural_window` grows a moment out to the sentences that
  contain it; never add a target duration or stretch a finished thought to reach a minimum. Platform limits are
  checked separately (`narrative.platform_fit`).
- **Secrets** are read from the environment or from files named by `*_FILE` settings. Never write a key, a real
  address or a personal path into a tracked file.
- **Pages** are plain HTML, CSS and JavaScript. Keep the existing palette, no shadows, and hover states that
  change colour only.
- Comments and messages are written in plain language for people who do not program. Keep that tone.
