"""Additive migrations: an old database is upgraded in place, never rewritten.

The important case is the second one: a real pre-2.0 `podcast_clips` table with a row in it. The migration
must add the new columns and leave the row untouched. PostgreSQL is exercised by the same DDL branches but
needs a live server, which this suite reports instead of pretending.
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["CLIPSORA_DATA"] = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

import sqlalchemy as sa  # noqa: E402

from studio import migrations  # noqa: E402

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def main():
    tmp = Path(tempfile.mkdtemp())

    # 1. Fresh install: every step applies once, then never again.
    fresh = sa.create_engine(f"sqlite:///{tmp / 'fresh.db'}", future=True)
    dbmod = sa.MetaData()
    sa.Table("podcast_clips", dbmod, sa.Column("id", sa.String(64), primary_key=True),
             sa.Column("project_id", sa.String(64)), sa.Column("start", sa.Float), sa.Column("end", sa.Float),
             sa.Column("duration", sa.Float))
    dbmod.create_all(fresh)
    first = migrations.apply(fresh)
    check("fresh database applies every migration", first == [1, 2, 3, 4, 5, 6], str(first))
    check("a second run applies nothing", migrations.apply(fresh) == [])
    check("status reports the latest version", migrations.status(fresh)["current"] == 6)
    check("no migrations are pending", migrations.pending(fresh) == [])
    cols = {c["name"] for c in sa.inspect(fresh).get_columns("podcast_clips")}
    for name in ("creative_direction", "duration_basis", "narrative_json", "platform_fit_json",
                 "master_duration", "quality_json", "direction_version"):
        check(f"podcast_clips gained {name}", name in cols)
    tables = set(sa.inspect(fresh).get_table_names())
    for name in ("brands", "brand_assets", "clip_covers", "clip_versions", "quality_reports",
                 "publish_targets", "publish_attempts", "job_events", "schema_migrations"):
        check(f"table {name} exists", name in tables)

    # 2. An existing 2.0-era clip row survives the upgrade.
    old = tmp / "old.db"
    con = sqlite3.connect(old)
    con.execute("""CREATE TABLE podcast_clips (
        id VARCHAR(64) PRIMARY KEY, project_id VARCHAR(64), user_id VARCHAR(40), start REAL, end REAL,
        duration REAL, score INTEGER, acceptance VARCHAR(20))""")
    con.execute("INSERT INTO podcast_clips VALUES ('p1_c1','p1','u1',10.0,70.0,60.0,82,'recommended')")
    con.commit()
    con.close()
    engine = sa.create_engine(f"sqlite:///{old}", future=True)
    applied = migrations.apply(engine)
    check("legacy database receives all migrations", applied == [1, 2, 3, 4, 5, 6], str(applied))
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT id, score, acceptance, creative_direction, narrative_json "
                                   "FROM podcast_clips WHERE id='p1_c1'").first()
    check("legacy row is untouched", row is not None and row[1] == 82 and row[2] == "recommended", str(row))
    check("new columns have safe defaults", row is not None and row[3] == "" and row[4] == "{}", str(row))

    # 3. A newer app opening an older database does not re-add columns.
    check("migration is idempotent on the legacy database", migrations.apply(engine) == [])

    # 4. Rollback refuses to destroy data, but can remove a table-only step.
    try:
        migrations.rollback(engine, 1)
        refused = False
    except ValueError:
        refused = True
    check("rolling back a column migration is refused", refused)
    dropped = migrations.rollback(engine, 2)
    check("table-only rollback drops its tables", "brands" in dropped)
    check("brands table is gone after rollback", "brands" not in set(sa.inspect(engine).get_table_names()))
    try:
        migrations.rollback(engine, 2)
        gone = False
    except ValueError:
        gone = True
    check("rolling back an unapplied step is refused", gone)

    print("\nPostgreSQL: the same steps run through the postgresql branch (FLOAT/BOOLEAN/IDENTITY), "
          "but no server is available here, so that path is not executed by this suite.")

    if fails:
        print(f"\n{len(fails)} failed: " + ", ".join(fails))
        sys.exit(1)
    print("\nAll migration tests passed!")


if __name__ == "__main__":
    main()
