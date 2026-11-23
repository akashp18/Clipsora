"""The database: accounts, sign-in sessions, notifications and the record of AI use.

PostgreSQL on a server (DATABASE_URL=postgresql+psycopg://...). With no DATABASE_URL it uses a SQLite file,
which is fine for one machine."""
import time

import sqlalchemy as sa

from . import config

_SQLITE = config.DATABASE_URL.startswith("sqlite")
_SQLITE_MEM = _SQLITE and (":memory:" in config.DATABASE_URL or config.DATABASE_URL.rstrip("/") == "sqlite://")
_pool_kw = {} if _SQLITE_MEM else {"pool_size": 20, "max_overflow": 40}
engine = sa.create_engine(config.DATABASE_URL, pool_pre_ping=not _SQLITE, future=True, **_pool_kw,
                          **({"connect_args": {"timeout": 30}} if _SQLITE else {}))

if _SQLITE:
    @sa.event.listens_for(engine, "connect")
    def _fast_sqlite(conn, _record):
        # WAL: people reading are never held up by someone writing. NORMAL: safe against crashes of the app,
        # without waiting for the disk on every single write.
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
meta = sa.MetaData()

users = sa.Table(
    "users", meta,
    sa.Column("id", sa.String(40), primary_key=True),
    sa.Column("email", sa.String(254), nullable=False, unique=True),          # always lower case
    sa.Column("name", sa.String(120), nullable=False, server_default=""),
    sa.Column("password_hash", sa.String(300)),                               # empty for Google-only accounts
    sa.Column("google_sub", sa.String(64), unique=True),
    sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("disabled", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("last_seen", sa.Float),
)
sessions = sa.Table(
    "sessions", meta,
    sa.Column("token_hash", sa.String(64), primary_key=True),                 # sha256 of the cookie; the cookie itself is never stored
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("expires_at", sa.Float, nullable=False),
    sa.Column("ip", sa.String(64)),
    sa.Column("agent", sa.String(300)),
)
usage = sa.Table(                                                             # one row per AI call
    "usage", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("t", sa.Float, nullable=False),
    sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),   # text sent to the AI
    sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),  # text it wrote back
    sa.Column("purpose", sa.String(60), nullable=False),
    sa.Column("creator", sa.String(80)),
    sa.Column("place", sa.String(200)),
    sa.Index("usage_user_t", "user_id", "t"),
)


email_ok = sa.Table(                                                          # addresses proven to belong to the account
    "email_ok", meta,
    sa.Column("user_id", sa.String(40), primary_key=True),                    # "_existing" marks that older accounts were counted
    sa.Column("verified_at", sa.Float, nullable=False),
)
email_tokens = sa.Table(                                                      # one-time links: verify an email, reset a password
    "email_tokens", meta,
    sa.Column("token_hash", sa.String(64), primary_key=True),                 # sha256 of the link token; the token itself is never stored
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("purpose", sa.String(10), nullable=False),                      # verify | reset
    sa.Column("expires_at", sa.Float, nullable=False),
    sa.Column("used_at", sa.Float),
)


feedback = sa.Table(                                                          # bug reports and ideas, read by admins
    "feedback", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="SET NULL")),
    sa.Column("t", sa.Float, nullable=False, index=True),
    sa.Column("kind", sa.String(10), nullable=False),                         # bug | idea | other
    sa.Column("message", sa.Text, nullable=False),
    sa.Column("page", sa.String(200), nullable=False, server_default=""),     # where in the app they were
    sa.Column("context", sa.String(1000), nullable=False, server_default=""), # e.g. the error they were looking at
    sa.Column("status", sa.String(10), nullable=False, server_default="new", index=True),  # new | seen | done
    sa.Column("updated_at", sa.Float, nullable=False),
)
notices = sa.Table(                                                           # the bell: things worth telling someone about
    "notices", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("t", sa.Float, nullable=False),
    sa.Column("kind", sa.String(20), nullable=False),                         # live | clips | post | account | feedback
    sa.Column("title", sa.String(160), nullable=False),
    sa.Column("body", sa.String(400), nullable=False, server_default=""),
    sa.Column("link", sa.String(200), nullable=False, server_default=""),
    sa.Column("ref", sa.String(80)),                                          # set when it must only be sent once
    sa.Column("read_at", sa.Float),
    sa.Index("notices_user_t", "user_id", "t"),
)


admin_log = sa.Table(                                                         # what admins did, never edited
    "admin_log", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("t", sa.Float, nullable=False, index=True),
    sa.Column("admin_id", sa.String(40), nullable=False),
    sa.Column("action", sa.String(30), nullable=False),                       # disable | enable | delete | role:admin | role:user
    sa.Column("target_id", sa.String(40)),
    sa.Column("detail", sa.String(300), nullable=False, server_default=""),
)

podcast_projects = sa.Table(                                                  # AI podcast-to-shorts analysis jobs
    "podcast_projects", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("title", sa.String(300), nullable=False, server_default=""),
    sa.Column("source_url", sa.String(500), nullable=False, server_default=""),
    sa.Column("source_type", sa.String(30), nullable=False, server_default="url"),
    sa.Column("status", sa.String(30), nullable=False, server_default="queued", index=True),
    sa.Column("duration", sa.Float, nullable=False, server_default="0"),
    sa.Column("speakers", sa.Text, nullable=False, server_default="[]"),
    sa.Column("topics", sa.Text, nullable=False, server_default="[]"),
    sa.Column("source_attribution", sa.String(300), nullable=False, server_default=""),
    sa.Column("permission_status", sa.String(50), nullable=False, server_default="user_verified"),
    sa.Column("error", sa.Text, nullable=False, server_default=""),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("updated_at", sa.Float, nullable=False),
)

podcast_clips = sa.Table(                                                     # Discovered podcast highlights & scoring
    "podcast_clips", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("project_id", sa.String(64), sa.ForeignKey("podcast_projects.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("start", sa.Float, nullable=False),
    sa.Column("end", sa.Float, nullable=False),
    sa.Column("duration", sa.Float, nullable=False),
    sa.Column("score", sa.Integer, nullable=False, server_default="0", index=True),
    sa.Column("score_hook", sa.Integer, nullable=False, server_default="0"),
    sa.Column("score_emotion", sa.Integer, nullable=False, server_default="0"),
    sa.Column("score_context", sa.Integer, nullable=False, server_default="0"),
    sa.Column("score_value", sa.Integer, nullable=False, server_default="0"),
    sa.Column("score_retention", sa.Integer, nullable=False, server_default="0"),
    sa.Column("score_ending", sa.Integer, nullable=False, server_default="0"),
    sa.Column("categories", sa.Text, nullable=False, server_default="[]"),
    sa.Column("hook_curiosity", sa.String(300), nullable=False, server_default=""),
    sa.Column("hook_bold", sa.String(300), nullable=False, server_default=""),
    sa.Column("hook_emotional", sa.String(300), nullable=False, server_default=""),
    sa.Column("selected_hook", sa.String(300), nullable=False, server_default=""),
    sa.Column("titles", sa.Text, nullable=False, server_default="[]"),
    sa.Column("selected_title", sa.String(300), nullable=False, server_default=""),
    sa.Column("description", sa.Text, nullable=False, server_default=""),
    sa.Column("caption", sa.Text, nullable=False, server_default=""),
    sa.Column("hashtags", sa.Text, nullable=False, server_default="[]"),
    sa.Column("pinned_comment", sa.Text, nullable=False, server_default=""),
    sa.Column("call_to_action", sa.String(300), nullable=False, server_default=""),
    sa.Column("thumbnail_text", sa.String(100), nullable=False, server_default=""),
    sa.Column("explanation", sa.Text, nullable=False, server_default=""),
    sa.Column("transcript_evidence", sa.Text, nullable=False, server_default=""),
    sa.Column("transcript", sa.Text, nullable=False, server_default=""),
    sa.Column("confidence", sa.Float, nullable=False, server_default="0.85"),
    sa.Column("suggested_improvements", sa.Text, nullable=False, server_default=""),
    sa.Column("approval_status", sa.String(20), nullable=False, server_default="recommended", index=True),
    sa.Column("render_status", sa.String(20), nullable=False, server_default="pending", index=True),
    sa.Column("rendered_file", sa.String(300), nullable=False, server_default=""),
    sa.Column("rendered_cover", sa.String(300), nullable=False, server_default=""),
    sa.Column("creative_direction", sa.String(40), nullable=False, server_default=""),
    sa.Column("direction_version", sa.Integer, nullable=False, server_default="0"),
    sa.Column("duration_basis", sa.String(200), nullable=False, server_default=""),
    sa.Column("master_duration", sa.Float, nullable=False, server_default="0"),
    sa.Column("topic", sa.String(160), nullable=False, server_default=""),
    sa.Column("narrative_summary", sa.Text, nullable=False, server_default=""),
    sa.Column("visual_direction", sa.Text, nullable=False, server_default=""),
    sa.Column("narrative_json", sa.Text, nullable=False, server_default="{}"),
    sa.Column("platform_fit_json", sa.Text, nullable=False, server_default="{}"),
    sa.Column("quality_json", sa.Text, nullable=False, server_default="{}"),
    sa.Column("error", sa.Text, nullable=False, server_default=""),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("updated_at", sa.Float, nullable=False),
)


brands = sa.Table(                                                            # several identities per account
    "brands", meta,
    sa.Column("id", sa.String(40), primary_key=True),
    sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("slug", sa.String(120), nullable=False),
    sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("tokens", sa.Text, nullable=False, server_default="{}"),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("updated_at", sa.Float, nullable=False),
    sa.UniqueConstraint("user_id", "slug", name="uq_brand_user_slug"),
)
brand_assets = sa.Table(
    "brand_assets", meta,
    sa.Column("id", sa.String(40), primary_key=True),
    sa.Column("brand_id", sa.String(40), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("kind", sa.String(20), nullable=False),                      # logo | audio | cover
    sa.Column("path", sa.String(400), nullable=False, server_default=""),
    sa.Column("meta", sa.Text, nullable=False, server_default="{}"),
    sa.Column("created_at", sa.Float, nullable=False),
)
clip_covers = sa.Table(
    "clip_covers", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("clip_id", sa.String(120), nullable=False, index=True),
    sa.Column("project_id", sa.String(64), nullable=False, server_default=""),
    sa.Column("user_id", sa.String(40), nullable=False, index=True),
    sa.Column("frame_time", sa.Float, nullable=False, server_default="0"),
    sa.Column("image_path", sa.String(400), nullable=False, server_default=""),
    sa.Column("score", sa.Float, nullable=False, server_default="0"),
    sa.Column("breakdown", sa.Text, nullable=False, server_default="{}"),
    sa.Column("headline", sa.String(200), nullable=False, server_default=""),
    sa.Column("composition", sa.String(30), nullable=False, server_default=""),
    sa.Column("selected", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.Float, nullable=False),
)
clip_versions = sa.Table(
    "clip_versions", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("clip_id", sa.String(120), nullable=False, index=True),
    sa.Column("user_id", sa.String(40), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("spec", sa.Text, nullable=False, server_default="{}"),
    sa.Column("created_by", sa.String(60), nullable=False, server_default="system"),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.UniqueConstraint("clip_id", "version", name="uq_clip_version"),
)
quality_reports = sa.Table(
    "quality_reports", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("clip_id", sa.String(120), nullable=False, index=True),
    sa.Column("user_id", sa.String(40), nullable=False),
    sa.Column("checks", sa.Text, nullable=False, server_default="{}"),
    sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.Float, nullable=False),
)
publish_targets = sa.Table(
    "publish_targets", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("user_id", sa.String(40), nullable=False, index=True),
    sa.Column("clip_id", sa.String(120), nullable=False),
    sa.Column("platform", sa.String(20), nullable=False),
    sa.Column("state", sa.String(24), nullable=False, server_default="draft", index=True),
    sa.Column("package", sa.Text, nullable=False, server_default="{}"),
    sa.Column("idempotency_key", sa.String(80), nullable=False, server_default=""),
    sa.Column("scheduled_at", sa.Float),
    sa.Column("approved_at", sa.Float),
    sa.Column("published_at", sa.Float),
    sa.Column("remote_id", sa.String(160), nullable=False, server_default=""),
    sa.Column("remote_url", sa.String(400), nullable=False, server_default=""),
    sa.Column("last_error", sa.Text, nullable=False, server_default=""),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("updated_at", sa.Float, nullable=False),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.UniqueConstraint("clip_id", "platform", name="uq_publish_clip_platform"),
)
publish_attempts = sa.Table(
    "publish_attempts", meta,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("target_id", sa.String(64), sa.ForeignKey("publish_targets.id", ondelete="CASCADE"),
              nullable=False, index=True),
    sa.Column("request_key", sa.String(80), nullable=False, unique=True),
    sa.Column("started_at", sa.Float, nullable=False),
    sa.Column("finished_at", sa.Float),
    sa.Column("outcome", sa.String(20), nullable=False, server_default="running"),
    sa.Column("http_status", sa.Integer),
    sa.Column("remote_id", sa.String(160), nullable=False, server_default=""),
    sa.Column("error", sa.Text, nullable=False, server_default=""),
)
job_events = sa.Table(
    "job_events", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("job_id", sa.String(64), nullable=False, server_default="", index=True),
    sa.Column("user_id", sa.String(40), nullable=False, server_default=""),
    sa.Column("t", sa.Float, nullable=False),
    sa.Column("stage", sa.String(40), nullable=False, server_default=""),
    sa.Column("level", sa.String(10), nullable=False, server_default="info"),
    sa.Column("detail", sa.Text, nullable=False, server_default=""),
)


def init():
    meta.create_all(engine)
    from . import migrations
    migrations.apply(engine)
    from . import migrations
    migrations.apply(engine)


def now() -> float:
    return time.time()
