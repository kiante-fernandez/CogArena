"""Idempotent schema migrations.

This repo has no migration tooling, and ``Base.metadata.create_all`` runs with
``checkfirst=True`` — it issues CREATE TABLE only for tables that do not exist
and never adds a column to one that does. Adding a mapped column without an
ALTER therefore leaves the deployed database one column short, and because every
Score read goes through the ORM (which emits an explicit column list), the very
next request raises ``no such column: scores.scorer_version`` on the leaderboard,
the scorecard, the admin list *and* /api/evaluate. That is a site outage, not a
degraded page.

Precedent for getting this wrong is already in the history: commit dd338b0 added
four columns to ``sessions`` two days after Turso went live and shipped no
migration code at all, so whatever fixed production left no reproducible record.

Hence this module, called from ``_ensure_db`` on both database paths so a deploy
migrates itself and there is no window in which the code is ahead of the schema.

WHAT TO ADD WHEN A COLUMN IS ADDED: nothing. The column set is derived by
diffing the mapped models against the live schema, so a new nullable column in
``models.py`` migrates itself. A hardcoded list would reproduce dd338b0 one step
later — forgetting to append to it is invisible to the whole test suite, because
every test builds its schema from the models and therefore never sees a database
missing a column.

Only the BACKFILL is per-column policy, since only the author knows what an
existing row should read; ``_BACKFILLS`` holds those.
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn, CreateIndex

from harness.db.models import Base
from scoring.version import LEGACY_VERSION

logger = logging.getLogger(__name__)

# column -> value for rows that predate it. Everything not listed stays NULL.
_BACKFILLS = {
    ("scores", "scorer_version"): LEGACY_VERSION,
}

# Indexes are DERIVED from the models for the same reason columns are: a
# hardcoded list drifts. It already did — the first deploy created only the
# composite index, because `ix_scores_scorer_version` comes from
# Column(index=True) and was not in the hand-written list, leaving production
# with a different schema from any fresh clone.


def _missing_columns(conn) -> list[tuple[str, object]]:
    """Mapped columns absent from the live schema, as (table, Column)."""
    insp = inspect(conn)
    existing_tables = set(insp.get_table_names())
    out = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all will make it whole
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in have:
                out.append((table.name, col))
    return out


def migrate(conn) -> dict[str, int]:
    """Bring `conn`'s schema up to date. Returns a summary of what it did.

    Takes a *sync* Connection: the async path calls it through ``run_sync`` and
    the libsql path calls it directly, matching how ``create_all`` is invoked.

    Reflecting first makes the steady state cheap, which matters because this
    runs on every serverless cold start against a remote database: an
    already-migrated schema costs one read and no write transaction, where
    attempting the ALTERs unconditionally cost a failed statement per column
    plus a write commit to discover zero rows to backfill.
    """
    summary = {"columns_added": 0, "rows_backfilled": 0, "indexes_created": 0}

    missing = _missing_columns(conn)
    if not missing:
        # Steady state for columns, but an index may still be absent — the
        # reflection below is a read, so this stays cheap and write-free.
        summary["indexes_created"] = _create_missing_indexes(conn)
        return summary

    for table_name, col in missing:
        # Compile from the mapped column so the DDL type always matches what
        # SQLAlchemy would have created, rather than a hand-written string.
        ddl = CreateColumn(col).compile(conn.engine).string
        try:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
            summary["columns_added"] += 1
            logger.info("migration: added %s.%s", table_name, col.name)
        except Exception as exc:  # noqa: BLE001 - driver-specific error types
            # Another process won the race between our reflection and this
            # statement. Narrow on purpose: any other failure must surface.
            if "duplicate column" not in str(exc).lower():
                raise

        value = _BACKFILLS.get((table_name, col.name))
        if value is not None:
            result = conn.execute(
                text(f"UPDATE {table_name} SET {col.name} = :v "
                     f"WHERE {col.name} IS NULL"),
                {"v": value},
            )
            n = result.rowcount or 0
            summary["rows_backfilled"] += n
            if n:
                logger.info("migration: labelled %d pre-existing %s rows %r",
                            n, table_name, value)

    summary["indexes_created"] = _create_missing_indexes(conn)
    return summary


def _create_missing_indexes(conn) -> int:
    """Create every model-declared index the live schema lacks."""
    insp = inspect(conn)
    existing_tables = set(insp.get_table_names())
    created = 0
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {i["name"] for i in insp.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in have:
                continue
            try:
                conn.execute(CreateIndex(index, if_not_exists=True))
                created += 1
                logger.info("migration: created index %s", index.name)
            except Exception as exc:  # noqa: BLE001
                # An index is a performance affordance, not a correctness one.
                # A driver that rejects one must not take the site down.
                logger.warning("migration: could not create index %s: %s",
                               index.name, exc)
    return created


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database-url", required=True,
                    help="SYNC SQLAlchemy URL, e.g. sqlite:///data/cogarena.db")
    args = ap.parse_args(argv)

    from sqlalchemy import create_engine

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = create_engine(args.database_url)
    with engine.begin() as conn:
        summary = migrate(conn)
    print(f"columns added: {summary['columns_added']}  "
          f"rows backfilled: {summary['rows_backfilled']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
