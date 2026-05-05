"""Re-score archived sweep sessions against the current spec JSONs.

Walks every ``data/sweeps/<sweep>/runs/<r##>/artifacts/trial_data/<task>.json``,
re-runs scoring.score_session.score_task with the live specs, and writes a
fresh ``score.json`` next to it. After re-scoring all runs of a sweep, builds
a fresh ``aggregate_audited.csv`` matching the column shape of the original
``aggregate.csv``.

Usage::

    python -m scripts.rescore_sweeps \\
        --sweep data/sweeps/pilot_v1_20260505_000538 \\
        --sweep data/sweeps/pilot_v1_cheap_20260505_005356

Sessions that lack ``trial_data/`` (i.e. failed runs that never produced raw
data) are carried forward unchanged from the original aggregate.csv so the
output rows are 1:1 with the input.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

from scoring.score_session import score_task

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
logger = logging.getLogger("rescore")


def _rescore_session(artifacts: Path) -> dict[str, Any] | None:
    trial_dir = artifacts / "trial_data"
    if not trial_dir.exists():
        return None
    task_files = list(trial_dir.glob("*.json"))
    if not task_files:
        return None

    task_scores: list[dict] = []
    for tf in task_files:
        task_id = tf.stem
        trial_data = json.loads(tf.read_text())
        result = score_task(trial_data, task_id, TASKS_DIR)
        task_scores.append({
            "task_id": result["task_id"],
            "l1_completion": result["l1"]["score"],
            "l2_accuracy": result["l2"]["score"],
            "l3_behavioral": result["l3"]["score"],
            "composite": result["composite"]["composite_score"],
            "details": result,
        })

    if not task_scores:
        return None

    overall = {
        "session_id": artifacts.parent.name,
        "task_scores": task_scores,
        "composite_score": sum(t["composite"] for t in task_scores) / len(task_scores),
        "l1_overall": sum(t["l1_completion"] for t in task_scores) / len(task_scores),
        "l2_overall": sum(t["l2_accuracy"] for t in task_scores) / len(task_scores),
        "l3_overall": sum(t["l3_behavioral"] for t in task_scores) / len(task_scores),
    }
    out_path = artifacts / "score.json"
    out_path.write_text(json.dumps(overall, indent=2))
    return overall


def _read_aggregate(sweep_dir: Path) -> list[dict]:
    p = sweep_dir / "aggregate.csv"
    if not p.exists():
        return []
    with p.open() as f:
        return list(csv.DictReader(f))


def _write_aggregate_audited(sweep_dir: Path, rows: list[dict]) -> Path:
    out = sweep_dir / "aggregate_audited.csv"
    fields = ["run_index", "repeat_index", "model_id", "task_id",
              "rc", "wall_time", "composite", "l1", "l2", "l3"]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return out


def _process_sweep(sweep_dir: Path) -> Path | None:
    if not (sweep_dir / "runs").exists():
        logger.error("no runs/ under %s", sweep_dir)
        return None

    original = _read_aggregate(sweep_dir)
    by_run = {r["run_index"]: dict(r) for r in original}

    rescored = 0
    skipped = 0
    for run_dir in sorted((sweep_dir / "runs").iterdir()):
        artifacts = run_dir / "artifacts"
        if not artifacts.exists():
            continue
        # Pull run_index from the rebuilt score.json or the directory name.
        # Easiest: match against original aggregate by directory order, so we
        # use the artifact's score.json's task_scores[0].task_id and meta.json
        # to find which original row corresponds.
        meta_path = artifacts / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        # The original aggregate row's run_index is just the index field;
        # we identify by (model_id, task_id) since trial_data/ has only one
        # task per session in the current sweep layout.
        task_files = list((artifacts / "trial_data").glob("*.json")) if (artifacts / "trial_data").exists() else []
        if not task_files:
            skipped += 1
            continue
        task_id = task_files[0].stem
        model_id = meta.get("model", {}).get("id", "?")

        # Find the matching original row
        match_rows = [r for r in original if r["model_id"] == model_id and r["task_id"] == task_id]
        if not match_rows:
            logger.warning("no aggregate row for model=%s task=%s", model_id, task_id)
            skipped += 1
            continue
        agg_row = match_rows[0]

        result = _rescore_session(artifacts)
        if result is None:
            skipped += 1
            continue

        # Update the row in place with new scores
        ts = result["task_scores"][0]
        by_run[agg_row["run_index"]] = {
            **agg_row,
            "composite": f"{ts['composite']:.2f}",
            "l1": f"{ts['l1_completion']:.4f}",
            "l2": f"{ts['l2_accuracy']:.4f}",
            "l3": f"{ts['l3_behavioral']:.4f}",
        }
        rescored += 1

    # Write the audited aggregate (preserves rows we couldn't rescore)
    rows = [by_run[r["run_index"]] for r in original]
    out = _write_aggregate_audited(sweep_dir, rows)
    logger.info("%s: rescored %d, carried %d -> %s", sweep_dir.name, rescored, skipped, out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sweep", action="append", required=True,
                        help="Sweep directory under data/sweeps/. Repeatable.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    for sweep in args.sweep:
        _process_sweep(Path(sweep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
