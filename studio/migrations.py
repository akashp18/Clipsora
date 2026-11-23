"""Additive database migrations.

`meta.create_all` never changes a table that already exists, so a new column silently never reaches an
installation that was created before it. This module keeps that honest: every schema change is a numbered
step that only *adds* things (columns, tables, indexes), so an existing data folder is upgraded in place
without rewriting or dropping a single row.

Both SQLite and PostgreSQL are supported; the few places where their syntax differs (booleans, defaults)
are handled here and nowhere else. Steps are recorded in `schema_migrations`, so running the migration
twice is safe and two app processes starting together cannot apply a step twice.

Rollback: additive steps cannot lose data, but dropping a column *would* (and old SQLite builds cannot).
`rollback()` therefore only drops the tables a later step created; step 1 is deliberately irreversible.
Take a backup of the data folder before a downgrade, which is the documented procedure in
docs/MIGRATIONS.md.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

import sqlalchemy as sa

SCHEMA_TABLE = "schema_migrations"

_schema = sa.Table(
    SCHEMA_TABLE, sa.MetaData(),
    sa.Column("version", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("applied_at", sa.Float, nullable=False),
)


class Step:
    def __init__(self, version: int, name: str, run: Callable, drop_tables: Optional[List[str]] = None):
        self.version = version
        self.name = name
        self._run = run
        self.drop_tables = drop_tables or []

    def run(self, conn) -> None:
        self._run(conn)


STEPS: List[Step] = []


def step(version: int, name: str, drop_tables: Optional[List[str]] = None):
    def wrap(fn: Callable):
        STEPS.append(Step(version, name, fn, drop_tables))
        return fn
    return wrap


# ---------------------------------------------------------------- dialect helpers
def _is_pg(conn) -> bool:
    return conn.engine.dialect.name in ("postgresql", "postgres")


def _bool_type(conn, default: bool = False) -> str:
    if _is_pg(conn):
        return "BOOLEAN NOT NULL DEFAULT " + ("TRUE" if default else "FALSE")
    return "INTEGER NOT NULL DEFAULT " + ("1" if default else "0")


def _float_type(conn) -> str:
    return "DOUBLE PRECISION" if _is_pg(conn) else "REAL"


def _columns(conn, table: str) -> set:
    insp = sa.inspect(conn)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def add_column(conn, table: str, name: str, ddl: str) -> bool:
    """Add a column if it is not already there. True when it was added."""
    if name in _columns(conn, table):
        return False
    conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')
    return True


def _create_index(conn, name: str, table: str, columns: str) -> None:
    conn.exec_driver_sql(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns})')


# ---------------------------------------------------------------- 1. clip intelligence
@step(1, "podcast clip narrative and direction metadata")
def _clip_metadata(conn) -> None:
    """The fields Phases 1-2 computed but only stored in job.json."""
    text_cols = {
        "creative_direction": "VARCHAR(40) NOT NULL DEFAULT ''",
        "duration_basis": "VARCHAR(200) NOT NULL DEFAULT ''",
        "topic": "VARCHAR(160) NOT NULL DEFAULT ''",
        "narrative_summary": "TEXT NOT NULL DEFAULT ''",
        "visual_direction": "TEXT NOT NULL DEFAULT ''",
        "narrative_json": "TEXT NOT NULL DEFAULT '{}'",
        "platform_fit_json": "TEXT NOT NULL DEFAULT '{}'",
        "quality_json": "TEXT NOT NULL DEFAULT '{}'",
        "master_duration": f"{_float_type(conn)} NOT NULL DEFAULT 0",
        "direction_version": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, ddl in text_cols.items():
        add_column(conn, "podcast_clips", name, ddl)
    _create_index(conn, "podcast_clips_direction", "podcast_clips", "creative_direction")


# ---------------------------------------------------------------- 2. brands
@step(2, "brands and brand assets", drop_tables=["brand_assets", "brands"])
def _brands(conn) -> None:
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS brands (
            id VARCHAR(40) PRIMARY KEY,
            user_id VARCHAR(40) NOT NULL,
            name VARCHAR(120) NOT NULL,
            slug VARCHAR(120) NOT NULL,
            is_default {_bool_type(conn)},
            tokens TEXT NOT NULL DEFAULT '{{}}',
            created_at {_float_type(conn)} NOT NULL,
            updated_at {_float_type(conn)} NOT NULL,
            UNIQUE (user_id, slug)
        )""")
    _create_index(conn, "brands_user", "brands", "user_id")
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS brand_assets (
            id VARCHAR(40) PRIMARY KEY,
            brand_id VARCHAR(40) NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
            kind VARCHAR(20) NOT NULL,
            path VARCHAR(400) NOT NULL DEFAULT '',
            meta TEXT NOT NULL DEFAULT '{{}}',
            created_at {_float_type(conn)} NOT NULL
        )""")
    _create_index(conn, "brand_assets_brand", "brand_assets", "brand_id, kind")


# ---------------------------------------------------------------- 3. covers
@step(3, "cover candidates", drop_tables=["clip_covers"])
def _covers(conn) -> None:
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS clip_covers (
            id VARCHAR(64) PRIMARY KEY,
            clip_id VARCHAR(120) NOT NULL,
            project_id VARCHAR(64) NOT NULL DEFAULT '',
            user_id VARCHAR(40) NOT NULL,
            frame_time {_float_type(conn)} NOT NULL DEFAULT 0,
            image_path VARCHAR(400) NOT NULL DEFAULT '',
            score {_float_type(conn)} NOT NULL DEFAULT 0,
            breakdown TEXT NOT NULL DEFAULT '{{}}',
            headline VARCHAR(200) NOT NULL DEFAULT '',
            composition VARCHAR(30) NOT NULL DEFAULT '',
            selected {_bool_type(conn)},
            created_at {_float_type(conn)} NOT NULL
        )""")
    _create_index(conn, "clip_covers_clip", "clip_covers", "clip_id, score")
    _create_index(conn, "clip_covers_user", "clip_covers", "user_id")


# ---------------------------------------------------------------- 4. versions and quality
@step(4, "clip versions and quality reports", drop_tables=["quality_reports", "clip_versions"])
def _versions(conn) -> None:
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS clip_versions (
            id VARCHAR(64) PRIMARY KEY,
            clip_id VARCHAR(120) NOT NULL,
            user_id VARCHAR(40) NOT NULL,
            version INTEGER NOT NULL,
            spec TEXT NOT NULL DEFAULT '{{}}',
            created_by VARCHAR(60) NOT NULL DEFAULT 'system',
            created_at {_float_type(conn)} NOT NULL,
            UNIQUE (clip_id, version)
        )""")
    _create_index(conn, "clip_versions_clip", "clip_versions", "clip_id")
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS quality_reports (
            id VARCHAR(64) PRIMARY KEY,
            clip_id VARCHAR(120) NOT NULL,
            user_id VARCHAR(40) NOT NULL,
            checks TEXT NOT NULL DEFAULT '{{}}',
            passed {_bool_type(conn)},
            created_at {_float_type(conn)} NOT NULL
        )""")
    _create_index(conn, "quality_reports_clip", "quality_reports", "clip_id, created_at")


# ---------------------------------------------------------------- 5. publishing
@step(5, "publish targets and durable attempts", drop_tables=["publish_attempts", "publish_targets"])
def _publishing(conn) -> None:
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS publish_targets (
            id VARCHAR(64) PRIMARY KEY,
            user_id VARCHAR(40) NOT NULL,
            clip_id VARCHAR(120) NOT NULL,
            platform VARCHAR(20) NOT NULL,
            state VARCHAR(24) NOT NULL DEFAULT 'draft',
            package TEXT NOT NULL DEFAULT '{{}}',
            idempotency_key VARCHAR(80) NOT NULL DEFAULT '',
            scheduled_at {_float_type(conn)},
            approved_at {_float_type(conn)},
            published_at {_float_type(conn)},
            remote_id VARCHAR(160) NOT NULL DEFAULT '',
            remote_url VARCHAR(400) NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0,
            updated_at {_float_type(conn)} NOT NULL,
            created_at {_float_type(conn)} NOT NULL,
            UNIQUE (clip_id, platform)
        )""")
    _create_index(conn, "publish_targets_user", "publish_targets", "user_id, state")
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS publish_attempts (
            id VARCHAR(64) PRIMARY KEY,
            target_id VARCHAR(64) NOT NULL REFERENCES publish_targets(id) ON DELETE CASCADE,
            request_key VARCHAR(80) NOT NULL UNIQUE,
            started_at {_float_type(conn)} NOT NULL,
            finished_at {_float_type(conn)},
            outcome VARCHAR(20) NOT NULL DEFAULT 'running',
            http_status INTEGER,
            remote_id VARCHAR(160) NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        )""")
    _create_index(conn, "publish_attempts_target", "publish_attempts", "target_id, started_at")


# ---------------------------------------------------------------- 6. events
@step(6, "processing events", drop_tables=["job_events"])
def _events(conn) -> None:
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )""" if not _is_pg(conn) else """
        CREATE TABLE IF NOT EXISTS job_events (
            id BIGSERIAL PRIMARY KEY
        )""")
    for name, ddl in {
        "job_id": "VARCHAR(64) NOT NULL DEFAULT ''",
        "user_id": "VARCHAR(40) NOT NULL DEFAULT ''",
        "t": f"{_float_type(conn)} NOT NULL DEFAULT 0",
        "stage": "VARCHAR(40) NOT NULL DEFAULT ''",
        "level": "VARCHAR(10) NOT NULL DEFAULT 'info'",
        "detail": "TEXT NOT NULL DEFAULT ''",
    }.items():
        add_column(conn, "job_events", name, ddl)
    _create_index(conn, "job_events_job", "job_events", "job_id, t")


# ---------------------------------------------------------------- runner
def _ensure_schema_table(engine) -> None:
    _schema.create(engine, checkfirst=True)


def applied(engine) -> Dict[int, str]:
    _ensure_schema_table(engine)
    with engine.connect() as conn:
        rows = conn.execute(sa.select(_schema.c.version, _schema.c.name).order_by(_schema.c.version)).all()
    return {int(r[0]): str(r[1]) for r in rows}


def apply(engine, target: Optional[int] = None) -> List[int]:
    """Apply every pending step (up to `target`). Returns the versions applied by this call."""
    _ensure_schema_table(engine)
    done: List[int] = []
    for step_ in STEPS:
        if target is not None and step_.version > target:
            break
        with engine.begin() as conn:
            try:
                already = conn.execute(
                    sa.select(_schema.c.version).where(_schema.c.version == step_.version)).first()
            except sa.exc.ProgrammingError:      # a very old SQLite file without the table
                already = None
            if already:
                continue
            step_.run(conn)
            try:
                conn.execute(_schema.insert().values(version=step_.version, name=step_.name,
                                                     applied_at=time.time()))
            except sa.exc.IntegrityError:
                continue                          # another process won the race; its work is the same
            done.append(step_.version)
    return done


def pending(engine) -> List[int]:
    have = applied(engine)
    return [s.version for s in STEPS if s.version not in have]


def status(engine) -> Dict[str, object]:
    have = applied(engine)
    return {
        "current": max(have) if have else 0,
        "latest": STEPS[-1].version if STEPS else 0,
        "applied": [{"version": v, "name": n} for v, n in sorted(have.items())],
        "pending": pending(engine),
    }


def rollback(engine, version: int) -> List[str]:
    """Drop the tables a step created. Refuses steps that only added columns (that would lose data)."""
    by_version = {s.version: s for s in STEPS}
    if int(version) not in applied(engine):
        raise ValueError(f"Migration {version} is not applied.")
    step_ = by_version.get(int(version))
    if not step_:
        raise ValueError(f"No migration {version}.")
    if not step_.drop_tables:
        raise ValueError("This migration only added columns; rolling it back would delete data. "
                         "Restore a backup of the data folder instead (docs/MIGRATIONS.md).")
    with engine.begin() as conn:
        for table in step_.drop_tables:
            conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(sa.delete(_schema).where(_schema.c.version == step_.version))
    return list(step_.drop_tables)
