# Database Design

## 1. Today

Relational (8 tables, `studio/db.py`): `users`, `sessions`, `usage`, `email_ok`, `email_tokens`, `feedback`, `notices`, `admin_log`.

Files (no schema at all): `job.json` per project, `words.json` per project, `creators.json`, `accounts.json` (including OAuth tokens), `posts.json`, `ai.json`, `notices_*.json`, `storage.json`.

Consequences: no joins between "clip" and "post", no way to ask "which category performs best", whole-file rewrites on every post status change, and a hard dependency on file locking for correctness.

## 2. Target schema

ASCII ER (new tables in **bold**):

```
users 1─n sessions
users 1─n **creators** 1─n **projects** 1─n **clips** 1─n **clip_events**
users 1─n **accounts** (platform credentials, encrypted)
**clips** 1─n **posts** n─1 **accounts**
users 1─n usage (existing, + prompt_id, prompt_version, cost_micros)
users 1─n notices, feedback, email_ok, email_tokens, admin_log (unchanged)
users 1─n **settings** (key/value per user: ai, storage, tour flags)
```

### creators
`id` (str pk) · `user_id` (fk, cascade) · `name` · `channel` · **`channels` jsonb** (platform→url) · **`settings` jsonb** (all 20+ current fields, validated in code) · `created_at` · `updated_at`
*Rationale:* settings are read as a whole and change often; a JSON column keeps the current data model without 20 columns nobody queries. Fields that get queried (autopost, min_score) are promoted to columns plus a generated index.

### projects
`id` (str pk, current format kept) · `user_id` · `creator_id` (nullable) · `kind` (`video|live`) · `title` · `uploader` · `source` jsonb · `status` · `stage` · `progress` · `duration` · `width` · `height` · `lang` · `game` · `ai` jsonb · `error` · `created_at` · `finished_at`
Indexes: `(user_id, created_at desc)`, `(user_id, status)`, `(creator_id, created_at desc)`.

### clips
`id` · `project_id` (fk cascade) · `idx` · `start` · `end` · `score` · `category` · `hook` · `title` · `description` · `hashtags` jsonb · `highlight_words` jsonb · `reason` · `status` · `version` · `file` · `cover` · `layout` · `style` · `captions` bool · `words` jsonb (edited words) · `variants` jsonb · `fixed_words` jsonb · `facecam` jsonb · `created_at` · `made_at`
Indexes: `(project_id, idx)`, `(status)`, `(score desc)` per creator via join.

### accounts (credentials)
`id` · `user_id` · `platform` · `name` · `label` · `external_id` · **`token_enc` bytea** · `token_meta` jsonb (expiry, scopes) · `created_at` · `revoked_at`
Encryption: AES-GCM with a key from `CLIPSORA_SECRET_KEY` (new) or a generated file with `0600`; never logged, never returned by the API (only `has_token: true`).

### posts
`id` · `clip_id` · `account_id` · `user_id` · `platform` · `status` (`needs_approval|scheduled|posting|posted|failed|cancelled`) · `due_at` · `posted_at` · `remote_id` · `url` · `tries` · `error` · `views` · `views_at` · `title` · `description`
Indexes: `(account_id, status, due_at)`, `(user_id, status)`, unique `(clip_id, account_id)`.

### clip_events (new, small, high value)
`id` · `clip_id` · `user_id` · `kind` (`selected|edited|variant_chosen|caption_edited|posted|deleted`) · `value` jsonb · `t` — the raw material for "which openings work", without touching user media.

### usage (extend, not replace)
Add `prompt_id` · `prompt_version` · `model` · `cost_micros` · `project_id` (nullable). Existing rows stay valid (all new columns nullable).

## 3. Migration strategy

1. **Add** new tables next to the existing ones; nothing dropped.
2. **Importer** (`studio/migrate.py`): walks `CLIPSORA_DATA`, inserts creators/projects/clips/posts/settings/accounts, verifies row counts against file counts, writes `migration-report.json`. `--dry-run` prints the plan. Files are **not** deleted; a documented flag does that after the user confirms in the UI.
3. **Dual-read window:** the repositories read SQL when the migration marker exists, else fall back to files, so an interrupted upgrade still boots.
4. **Migrations** runner: versioned SQL files applied in order, recorded in `schema_version`. Alembic is acceptable but not required; a 60-line runner keeps the install dependency-free.

## 4. Retention and deletion

- Deleting a creator → cascade projects → cascade clips → cascade posts; media files deleted last, after rows (so a crash leaves an orphan file, never a broken row).
- Clip/project deletion removes `clip_events` for them (event log is not a compliance artefact).
- `usage` and `clip_events` are retained 400 days, then rolled up into `usage_daily`.
- Account deletion: tokens deleted first, then rows, then the user's data folder.

## 5. Performance notes

- Project list at 500 rows: cover via `(user_id, created_at desc)` limit 50 + keyset pagination (`created_at, id`).
- "Best categories": `clip_events` joined to `clips` grouped by category, ≤ 1 index scan over a narrow table.
- Avoid `SELECT *` on `clips` (words/variants jsonb can be large): list queries select explicit columns; the editor fetches the full row.
- JSON columns are for settings/words/variants only — anything filtered or sorted becomes a column.

## 6. What is deliberately not modelled

- Render job internals (ffmpeg logs, temp paths) — they belong to a job run, not to the user's data; they stay in a per-run log file.
- AI conversation history for the assistant (P2.8) — session-scoped, capped, stored per project, never used for training.
