"""Merge sweep runs into canonical result tables, preserving repeat structure.

``results/pilot_v1.csv`` was assembled by hand from per-sweep aggregates. That
does not scale to hundreds of runs across several waves and arms, and it drops
the per-signature detail the rebuttal analyses need.

This writes two tidy tables:

``runs.csv``
    One row per (sweep, model, task, repeat). Carries the scorecard plus the
    provenance a reviewer can check: git SHA, observation mode, trial counts,
    and whether the run produced raw data at all.

``signatures.csv``
    One row per (run, L3 signature) with score, p-value, effect size, and
    direction. This is the table that answers "how often does this signature
    fire across re-runs", which no existing artifact could express.

Usage::

    python -m scripts.build_results \\
        --sweep data/sweeps/rebuttal_v1_launch_20260724_211936 \\
        --out results/rebuttal_v1

Runs that never produced a scorecard are retained with ``scored=False`` rather
than dropped: a cell that fails is evidence about the model/scaffold, and
silently omitting it inflates every average computed downstream.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("build_results")

RUN_FIELDS = [
    "sweep", "run_index", "repeat_index", "model_id", "task_id",
    "rc", "wall_time", "scored", "l1_complete",
    "composite", "l1", "l2", "l3",
    "n_trials", "observation_mode", "git_sha", "session_id",
]
SIG_FIELDS = [
    "sweep", "repeat_index", "model_id", "task_id",
    "signature", "score", "passed", "p_value", "effect_size", "direction_correct",
]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _run_dir(sweep_dir: Path, repeat_index: int, model_id: str, task_id: str) -> Path:
    """Mirror the id scheme in harness/sweep.py:expand_runs."""
    return sweep_dir / "runs" / f"r{repeat_index:02d}_{model_id}_{task_id}"


def _aggregate_rows(sweep_dir: Path) -> list[dict[str, str]]:
    """Prefer the audited aggregate when a re-score has been applied."""
    for name in ("aggregate_audited.csv", "aggregate.csv"):
        path = sweep_dir / name
        if path.exists():
            with open(path) as f:
                rows = list(csv.DictReader(f))
            logger.info("%s: %d rows from %s", sweep_dir.name, len(rows), name)
            return rows
    logger.warning("%s: no aggregate CSV; sweep may still be running", sweep_dir.name)
    return []


def _score_for(artifacts: Path) -> dict[str, Any] | None:
    direct = artifacts / "score.json"
    if direct.exists():
        return _read_json(direct)
    for p in artifacts.rglob("score.json"):
        return _read_json(p)
    return None


def _task_entry(score: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for t in score.get("task_scores") or []:
        if t.get("task_id") == task_id:
            return t
    return None


def _float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def collect(sweep_dir: Path) -> tuple[list[dict], list[dict]]:
    runs: list[dict] = []
    sigs: list[dict] = []
    for row in _aggregate_rows(sweep_dir):
        repeat_index = int(row["repeat_index"])
        model_id, task_id = row["model_id"], row["task_id"]
        artifacts = _run_dir(sweep_dir, repeat_index, model_id, task_id) / "artifacts"

        meta = _read_json(artifacts / "meta.json") or {}
        score = _score_for(artifacts)
        entry = _task_entry(score, task_id) if score else None

        trial_file = artifacts / "trial_data" / f"{task_id}.json"
        trials = _read_json(trial_file)
        n_trials = len(trials) if isinstance(trials, list) else None

        l1 = _float(row.get("l1")) if row.get("l1") else (
            entry.get("l1_completion") if entry else None)
        runs.append({
            "sweep": sweep_dir.name,
            "run_index": row.get("run_index"),
            "repeat_index": repeat_index,
            "model_id": model_id,
            "task_id": task_id,
            "rc": row.get("rc"),
            "wall_time": row.get("wall_time"),
            # `scored` = a scorecard exists at all; `l1_complete` = the agent
            # actually finished the experiment. Keeping them apart is what lets
            # the analysis separate "no signature" from "harness/agent broke".
            "scored": entry is not None,
            "l1_complete": (l1 is not None and l1 >= 1.0),
            "composite": row.get("composite") or (entry.get("composite") if entry else None),
            "l1": row.get("l1") or (entry.get("l1_completion") if entry else None),
            "l2": row.get("l2") or (entry.get("l2_accuracy") if entry else None),
            "l3": row.get("l3") or (entry.get("l3_behavioral") if entry else None),
            "n_trials": n_trials,
            "observation_mode": (meta.get("model") or {}).get("observation_mode")
                                or meta.get("observation_mode"),
            "git_sha": (meta.get("env") or {}).get("git_sha"),
            "session_id": meta.get("session_id"),
        })

        if not entry:
            continue
        for s in ((entry.get("details") or {}).get("l3") or {}).get("signatures") or []:
            score_val = _float(s.get("score"))
            sigs.append({
                "sweep": sweep_dir.name,
                "repeat_index": repeat_index,
                "model_id": model_id,
                "task_id": task_id,
                "signature": s.get("name"),
                "score": score_val,
                # A signature "passes" only on a full 1.0 (correct direction AND
                # significant). The 0.5 partial credit is deliberately not a pass.
                "passed": (score_val is not None and score_val >= 1.0),
                "p_value": s.get("p_value"),
                "effect_size": s.get("effect_size"),
                "direction_correct": s.get("direction_correct"),
            })
    return runs, sigs


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("wrote %s (%d rows)", path, len(rows))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="append", required=True,
                    help="Sweep directory. Repeatable to merge several arms.")
    ap.add_argument("--out", default="results/rebuttal_v1",
                    help="Output directory for runs.csv and signatures.csv.")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")

    all_runs: list[dict] = []
    all_sigs: list[dict] = []
    for s in args.sweep:
        d = Path(s)
        if not d.is_dir():
            logger.error("not a directory: %s", d)
            return 2
        r, g = collect(d)
        all_runs += r
        all_sigs += g

    if not all_runs:
        logger.error("no runs collected — has the sweep written an aggregate yet?")
        return 1

    out = Path(args.out)
    _write(out / "runs.csv", RUN_FIELDS, all_runs)
    _write(out / "signatures.csv", SIG_FIELDS, all_sigs)

    scored = sum(1 for r in all_runs if r["scored"])
    complete = sum(1 for r in all_runs if r["l1_complete"])
    print(f"\n{len(all_runs)} runs | {scored} scored ({scored/len(all_runs):.0%}) | "
          f"{complete} fully completed ({complete/len(all_runs):.0%}) | "
          f"{len(all_sigs)} signature observations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
