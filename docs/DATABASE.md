# Database Schema and Migrations

SQLite by default (one file in the data folder), PostgreSQL when `DATABASE_URL` is set. The same code creates
both, with the few dialect differences isolated in `studio/migrations.py`.

## What changed in 2.0

`meta.create_all()` only creates missing tables; it never adds a column to an existing one. 2.0 therefore adds
a numbered, additive migration runner and calls it from `db.init()`:

```python
def init():
    meta.create_all(engine)
    from . import migrations
    migrations.apply(engine)
```

Every step is recorded in `schema_migrations`, so a second start applies nothing and two processes starting
together cannot apply a step twice.

| # | Step | Adds |
|---|---|---|
| 1 | clip intelligence | columns on `podcast_clips`: `creative_direction`, `direction_version`, `duration_basis`, `master_duration`, `topic`, `narrative_summary`, `visual_direction`, `narrative_json`, `platform_fit_json`, `quality_json` + index |
| 2 | brands | `brands`, `brand_assets` |
| 3 | covers | `clip_covers` |
| 4 | versions & quality | `clip_versions`, `quality_reports` |
| 5 | publishing | `publish_targets`, `publish_attempts` |
| 6 | events | `job_events` |

## Where each kind of data lives

| Data | Home | Why |
|---|---|---|
| A clip's editable shape (times, hook, title, direction, packages) | `job.json` | the pipeline and the editor read one document; rewriting it is atomic |
| The same clip, queryable and scored | `podcast_clips` | search, sorting, joins, history |
| Narrative/fit/quality detail | JSON columns on `podcast_clips` | shape still evolving; no migrations for every field |
| Cover candidates and the selected one | `clip_covers` | many rows per clip, selected flag in one place |
| Brand identity and sound settings | `brands.tokens` (JSON) | validated at the boundary by `brands.normalize_tokens` |
| Logo and audio files | `brand_assets.path` + `users/<user>/brands/<brand>/` | binaries never belong in the database; the path is unique per brand and kind |
| Publishing state and history | `publish_targets`, `publish_attempts` | needs constraints, uniqueness and durable attempts |
| Processing log | `job_events` | cheap append-only diagnostics, not user data |

`job.json` stays authoritative for the live editor; `podcast_clips` is the durable mirror. Existing projects
remain readable because nothing was renamed or removed, and the new columns have safe defaults.

## Constraints and indexes

- `brands`: unique `(user_id, slug)`, index on `user_id`.
- `publish_targets`: unique `(clip_id, platform)` — one target per destination; index `(user_id, state)`.
- `publish_attempts`: unique `request_key` — the idempotency guarantee; index `(target_id, started_at)`.
- `clip_covers`: index `(clip_id, score)`, `(user_id)`.
- `clip_versions`: unique `(clip_id, version)`.
- `podcast_clips`: existing indexes plus `creative_direction`.

## Upgrade and rollback

Upgrade: start the app (or call `db.init()`); pending steps apply in order. A backup of the data folder is
recommended before a release upgrade, and is required before a downgrade.

Rollback is deliberately limited:

- `migrations.rollback(engine, n)` refuses step 1, because dropping a column would delete data and older
  SQLite builds cannot do it safely.
- Table-only steps can be dropped (`2`–`6`), removing their rows with them.
- Downgrading the code without downgrading the schema is safe: old code ignores new columns and tables.

## Verified here

`tests/test_migrations.py` (28 checks) builds a fresh database and a simulated pre-2.0 `podcast_clips` table
with a row, applies every step, and proves the row survives with defaults in the new columns. It also proves
idempotency and the rollback refusals. PostgreSQL's DDL branch is implemented but **not executed here** — no
PostgreSQL server is available in this environment.
