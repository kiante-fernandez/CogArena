"""Backfill trial data that ran but was never archived.

harness/eval.py archives raw jsPsych data only for tasks that appear in
``task_scores`` — i.e. tasks that were successfully SCORED::

    task_ids = [ts["task_id"] for ts in results.get("task_scores", [])]

An agent that produces hundreds of trials but never reaches a scoreable state
therefore archives nothing, even though incremental_save.js has been PATCHing
that data to the server the whole time and it sits in the shared SQLite DB.

In the v1 pilot this silently discarded thousands of trials: kimi-k2.5 on
grid_bandit archived 0 trials while the DB holds 112; qwen3-vl-30b on
effort_foraging archived 0 while the DB holds 160. Those cells were counted as
outright failures, which conflates "the agent produced no behavior" with "the
harness did not save the behavior it produced" — the measurement-failure
confound raised in review.

This walks a sweep, finds runs whose trial_data/ is missing or shorter than what
the DB holds for that session, and writes the DB copy in. Recovered files are
listed in ``recovery_manifest.json`` so they stay distinguishable from natively
archived data and the recovery is reportable rather than invisible.

Usage::

    python recover_trial_data.py --sweep data/sweeps/<dir> --dry-run
    python recover_trial_data.py --sweep data/sweeps/<dir>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger("recover_trial_data")


def _load(path: Path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def db_rows(db_path: Path, session_id: str) -> list[tuple[str, list, int]]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT task_id, trial_data, is_complete FROM task_results WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    finally:
        con.close()
    out = []
    for task_id, blob, is_complete in rows:
        try:
            data = json.loads(blob)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(data, list) and data:
            out.append((task_id, data, is_complete))
    return out


def scan(sweep: Path, db_path: Path) -> list[dict]:
    actions = []
    for meta_path in sorted(sweep.rglob("runs/*/artifacts/meta.json")):
        artifacts = meta_path.parent
        meta = _load(meta_path) or {}
        sid = meta.get("session_id")
        if not sid:
            continue
        for task_id, data, is_complete in db_rows(db_path, sid):
            target = artifacts / "trial_data" / f"{task_id}.json"
            existing = _load(target)
            have = len(existing) if isinstance(existing, list) else 0
            if len(data) <= have:
                continue  # archived copy is already at least as complete
            actions.append({
                "run": artifacts.parent.name,
                "session_id": sid,
                "task_id": task_id,
                "target": str(target),
                "trials_on_disk": have,
                "trials_in_db": len(data),
                "is_complete": bool(is_complete),
                "_data": data,
            })
    return actions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", required=True)
    ap.add_argument("--db", default="data/cogarena.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")

    sweep, db_path = Path(args.sweep), Path(args.db)
    if not sweep.is_dir():
        logger.error("not a directory: %s", sweep); return 2
    if not db_path.exists():
        logger.error("no database at %s", db_path); return 2

    actions = scan(sweep, db_path)
    if not actions:
        print("Nothing to recover — every run's archive already matches the DB.")
        return 0

    recovered_trials = sum(a["trials_in_db"] - a["trials_on_disk"] for a in actions)
    from_zero = sum(1 for a in actions if a["trials_on_disk"] == 0)
    print(f"{len(actions)} task-results to recover "
          f"({from_zero} from a completely empty archive), "
          f"{recovered_trials} trials total\n")
    for a in sorted(actions, key=lambda x: -x["trials_in_db"])[:25]:
        print(f"  {a['run'][:44]:46s} {a['task_id']:22s} "
              f"{a['trials_on_disk']:4d} -> {a['trials_in_db']:4d} trials")
    if len(actions) > 25:
        print(f"  ... and {len(actions) - 25} more")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    manifest = []
    for a in actions:
        target = Path(a["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w") as f:
            json.dump(a["_data"], f, indent=2)
        manifest.append({k: v for k, v in a.items() if k != "_data"})

    mpath = sweep / "recovery_manifest.json"
    with open(mpath, "w") as f:
        json.dump({
            "recovered_at_utc": _dt.datetime.utcnow().isoformat() + "Z",
            "db": str(db_path),
            "reason": "harness/eval.py archives trial data only for SCORED tasks; "
                      "these ran but never reached a scoreable state",
            "n_task_results": len(manifest),
            "n_trials": recovered_trials,
            "entries": manifest,
        }, f, indent=2)

    print(f"\nRecovered {len(manifest)} task-results ({recovered_trials} trials).")
    print(f"Manifest: {mpath}")
    print("Re-score them with: python -m scripts.rescore_sweeps --sweep " + str(sweep))
    print("Report these as recovered-partial data, not as natively completed runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
