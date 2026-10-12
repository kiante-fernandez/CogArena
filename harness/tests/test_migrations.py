"""The migration path, tested against a PRE-migration schema.

The rest of the suite cannot cover this: ``test_api.py``'s ``reset_db`` fixture
builds every table from the current model, so it never sees a database that is
missing a column. But that is exactly the state of the deployed database at the
moment a new column ships, and getting it wrong is a site outage rather than a
degraded page — every Score read goes through the ORM, which names its columns
explicitly, so one missing column breaks the leaderboard, the scorecard, the
admin list and /api/evaluate at once.

So these tests hand-write the old CREATE TABLE and migrate forward.
"""
import sqlite3

import pytest
from sqlalchemy import create_engine, select, text

# LEGACY_VERSION comes from scoring.version, the module every READER uses.
# Importing the migration's own copy would let the writer and readers drift
# apart while this test still passed.
from harness.db.migrations import migrate
from scoring.version import LEGACY_VERSION
from harness.db.models import Score

# The scores table as it existed before scorer_version/spec_digest.
_PRE_MIGRATION_DDL = """
CREATE TABLE scores (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR NOT NULL,
    task_id VARCHAR NOT NULL,
    l1_completion FLOAT NOT NULL,
    l2_accuracy FLOAT NOT NULL,
    l3_behavioral FLOAT NOT NULL,
    composite FLOAT NOT NULL,
    details TEXT,
    scored_at DATETIME
)
"""


@pytest.fixture
def legacy_db(tmp_path):
    """A database at the pre-migration schema, holding three real rows."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(_PRE_MIGRATION_DDL)
    for i, task in enumerate(["stroop", "n_back", "marbles_risk"]):
        conn.execute(
            "INSERT INTO scores (session_id, task_id, l1_completion, l2_accuracy,"
            " l3_behavioral, composite, details, scored_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (f"sess-{i}", task, 1.0, 0.5, 0.25, 50.0, "{}", "2026-05-06 02:49:12"),
        )
    conn.commit()
    conn.close()
    return path


def _engine(path):
    return create_engine(f"sqlite:///{path}")


def test_migrate_adds_columns_and_labels_existing_rows(legacy_db):
    """Pre-existing rows survive and are labelled, not dropped."""
    engine = _engine(legacy_db)
    with engine.begin() as conn:
        summary = migrate(conn)

    assert summary["columns_added"] == 2
    assert summary["rows_backfilled"] == 3

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT task_id, scorer_version, spec_digest FROM scores ORDER BY task_id"
        )).all()
    assert len(rows) == 3, "migration must not delete rows"
    assert {r[1] for r in rows} == {LEGACY_VERSION}
    assert {r[2] for r in rows} == {None}


def test_orm_reads_and_writes_after_migration(legacy_db):
    """The ORM's explicit column list is what breaks pre-migration."""
    engine = _engine(legacy_db)
    with engine.begin() as conn:
        migrate(conn)

    from sqlalchemy.orm import Session as OrmSession
    with OrmSession(engine) as db:
        existing = db.execute(select(Score)).scalars().all()
        assert len(existing) == 3
        assert all(s.scorer_version == LEGACY_VERSION for s in existing)

        db.add(Score(session_id="new", task_id="stroop", l1_completion=1.0,
                     l2_accuracy=0.5, l3_behavioral=0.5, composite=60.0,
                     details="{}", scorer_version="1.2-abcdef123456",
                     spec_digest="abcdef123456"))
        db.commit()
        assert len(db.execute(select(Score)).scalars().all()) == 4


def test_migrate_is_idempotent(legacy_db):
    """Serverless cold starts race each other into _ensure_db."""
    engine = _engine(legacy_db)
    with engine.begin() as conn:
        migrate(conn)
    with engine.begin() as conn:
        second = migrate(conn)

    assert second["columns_added"] == 0, "an up-to-date schema needs no ALTER"
    assert second["rows_backfilled"] == 0, "must not relabel rows that have a version"

    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM scores")).scalar() == 3


def test_migrate_does_not_relabel_a_real_version(legacy_db):
    """A row with a genuine version must never be downgraded to legacy."""
    engine = _engine(legacy_db)
    with engine.begin() as conn:
        migrate(conn)
        conn.execute(text("UPDATE scores SET scorer_version = '1.2-real' WHERE task_id = 'stroop'"))
    with engine.begin() as conn:
        migrate(conn)
        got = conn.execute(text(
            "SELECT scorer_version FROM scores WHERE task_id = 'stroop'")).scalar()
    assert got == "1.2-real"


def test_migrate_on_a_fresh_schema_is_a_noop_plus_indexes(tmp_path):
    """create_all already made the columns; migrate must not blow up."""
    from harness.db.models import Base
    engine = _engine(tmp_path / "fresh.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        summary = migrate(conn)
    assert summary["columns_added"] == 0
    assert summary["rows_backfilled"] == 0

    names = sqlite3.connect(tmp_path / "fresh.db").execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='scores'"
    ).fetchall()
    assert any("session_task_version" in n[0] for n in names)


def test_a_new_mapped_column_migrates_without_editing_this_module(legacy_db):
    """The column set is derived from the models, not hand-listed.

    A hardcoded list reproduces the dd338b0 failure one step later: forgetting to
    append to it is invisible to the suite, because every other test builds its
    schema from the models and so never sees a database missing a column.
    """
    from sqlalchemy import Column, String
    from harness.db.models import Base, Score

    engine = _engine(legacy_db)
    with engine.begin() as conn:
        migrate(conn)

    extra = Column("simplify_probe", String, nullable=True)
    Score.__table__.append_column(extra)
    try:
        with engine.begin() as conn:
            summary = migrate(conn)
        assert summary["columns_added"] == 1, "a new mapped column must migrate itself"
        with engine.begin() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(scores)")).all()}
        assert "simplify_probe" in cols
    finally:
        Score.__table__._columns.remove(extra)


def test_ensure_db_sequence_on_a_partially_migrated_database(legacy_db):
    """create_all THEN migrate, which is what _ensure_db does on both paths.

    This is the production scenario and the one the rest of the suite cannot
    reach: `scores` already exists, so `create_all(checkfirst=True)` skips it
    entirely and leaves it short two columns. Everything after that depends on
    `migrate` noticing. The libsql/Turso branch runs exactly this against a sync
    engine, so a sync engine is what this uses.
    """
    from sqlalchemy.orm import Session as OrmSession
    from harness.db.models import Base

    engine = _engine(legacy_db)
    Base.metadata.create_all(engine)          # no-op on the existing scores table
    with engine.begin() as conn:
        summary = migrate(conn)

    assert summary["columns_added"] == 2, "create_all cannot add columns; migrate must"
    assert summary["rows_backfilled"] == 3

    # The ORM emits an explicit column list, which is what breaks pre-migration.
    with OrmSession(engine) as db:
        rows = db.execute(select(Score)).scalars().all()
        assert len(rows) == 3
        assert all(r.scorer_version == LEGACY_VERSION for r in rows)

    # And a second cold start costs nothing: no ALTER, no backfill, no index.
    with engine.begin() as conn:
        assert migrate(conn) == {"columns_added": 0, "rows_backfilled": 0,
                                 "indexes_created": 0, "tables_rebuilt": 0}


def test_model_declared_indexes_are_created_on_an_existing_table(legacy_db):
    """Indexes are derived from the models, not hand-listed.

    This is not hypothetical: the first v1.2.1 deploy created only the composite
    index, because `ix_scores_scorer_version` comes from `Column(index=True)` and
    was absent from the hardcoded list — leaving production with a different
    schema from any fresh clone, which is the drift the derived column set was
    written to prevent.
    """
    from harness.db.models import Base

    engine = _engine(legacy_db)
    Base.metadata.create_all(engine)   # skips the existing scores table
    with engine.begin() as conn:
        migrate(conn)

    declared = {i.name for i in Base.metadata.tables["scores"].indexes}
    live = {r[1] for r in sqlite3.connect(legacy_db).execute(
        "SELECT type, name FROM sqlite_master WHERE type='index' AND tbl_name='scores'")}
    assert declared <= live, f"missing from the live schema: {declared - live}"


# The scores table as v1.2.1 deployed it: versioned, but l2_accuracy NOT NULL.
# Copied from a live database rather than written from the model, because the
# point is the state the model no longer describes.
_V121_DDL = [
    """CREATE TABLE sessions (
        id VARCHAR NOT NULL, agent_name VARCHAR NOT NULL, scaffold VARCHAR,
        model_name VARCHAR, observation_mode VARCHAR, status VARCHAR NOT NULL,
        approved BOOLEAN, reviewed_by VARCHAR, review_notes TEXT,
        reviewed_at DATETIME, created_at DATETIME, updated_at DATETIME,
        PRIMARY KEY (id))""",
    """CREATE TABLE scores (
        id INTEGER NOT NULL,
        session_id VARCHAR NOT NULL,
        task_id VARCHAR NOT NULL,
        l1_completion FLOAT NOT NULL,
        l2_accuracy FLOAT NOT NULL,
        l3_behavioral FLOAT NOT NULL,
        composite FLOAT NOT NULL,
        details TEXT,
        scored_at DATETIME, scorer_version VARCHAR, spec_digest VARCHAR,
        PRIMARY KEY (id),
        FOREIGN KEY(session_id) REFERENCES sessions (id))""",
    "CREATE INDEX ix_scores_session_task_version ON scores (session_id, task_id, scorer_version)",
    "CREATE INDEX ix_scores_scorer_version ON scores (scorer_version)",
]


def test_migrate_relaxes_l2_not_null_and_keeps_every_row(tmp_path):
    """A task with no Level 2 metrics writes NULL; v1.2.1 databases refuse it."""
    from sqlalchemy.orm import Session as OrmSession

    path = tmp_path / "v121.db"
    raw = sqlite3.connect(path)
    for ddl in _V121_DDL:
        raw.execute(ddl)
    raw.executemany(
        "INSERT INTO scores (id, session_id, task_id, l1_completion, l2_accuracy,"
        " l3_behavioral, composite, details, scorer_version) VALUES (?,?,?,?,?,?,?,?,?)",
        [(7, "s", "stroop", 1.0, 0.25, 0.5, 50.0, "{}", "1.2.1-aaaaaaaaaaaa"),
         (9, "s", "moral_machine", 1.0, 0.75, 1.0, 90.0, None, "1.2.1-aaaaaaaaaaaa")])
    raw.commit()
    raw.close()

    engine = _engine(path)
    with engine.begin() as conn:
        summary = migrate(conn)
    assert summary["tables_rebuilt"] == 1
    assert summary["columns_added"] == 0

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, task_id, l2_accuracy, composite, scorer_version FROM scores ORDER BY id")).all()
        notnull = {r[1]: r[3] for r in conn.execute(text("PRAGMA table_info(scores)")).all()}
        indexes = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='scores'")).all()}
    assert [tuple(r) for r in rows] == [(7, "stroop", 0.25, 50.0, "1.2.1-aaaaaaaaaaaa"),
                                        (9, "moral_machine", 0.75, 90.0, "1.2.1-aaaaaaaaaaaa")]
    assert notnull["l2_accuracy"] == 0
    assert notnull["l1_completion"] == 1, "only the relaxed column changes"
    assert {"ix_scores_session_task_version", "ix_scores_scorer_version"} <= indexes

    with OrmSession(engine) as db:
        db.add(Score(session_id="s", task_id="marbles_risk", l1_completion=1.0,
                     l2_accuracy=None, l3_behavioral=0.5, composite=61.54,
                     details="{}", scorer_version="1.3.0-bbbbbbbbbbbb"))
        db.commit()
        new = db.execute(select(Score).where(Score.task_id == "marbles_risk")).scalar_one()
        assert new.l2_accuracy is None and new.id == 10, "ids continue past the copied rows"

    with engine.begin() as conn:
        assert migrate(conn)["tables_rebuilt"] == 0, "steady state must not rebuild again"
