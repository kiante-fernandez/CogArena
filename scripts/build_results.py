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

from scoring.level3_behavioral import is_l3_measurable
from scripts._aggregate_schema import normalize

REPO_ROOT = Path(__file__).resolve().parents[1]

logger = logging.getLogger("build_results")

RUN_FIELDS = [
    "sweep", "run_index", "repeat_index", "replicate_id", "model_id", "task_id",
    "rc", "wall_time", "scored", "l1_complete", "l3_measurable",
    "composite", "l1", "l2", "l3",
    "l3_n_testable", "l3_n_untestable", "l3_n_errors", "l3_coverage",
    "n_trials", "observation_mode", "git_sha", "session_id",
    "retried", "retry_of_rc",
]

# The measurability rule itself lives in scoring.level3_behavioral, next to the
# fields it reads, so the producer here and the consumers in scripts/ cannot
# hold different copies of it. Both l3_n_testable and l3_coverage are written to
# runs.csv alongside the flag, so a reader can re-derive it at another threshold
# without regenerating anything.
MIN_L3_COVERAGE = 0.5
SIG_FIELDS = [
    "sweep", "repeat_index", "model_id", "task_id",
    "signature", "testable", "untestable_reason", "score", "passed",
    "p_value", "effect_size", "direction_correct",
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
            # retry sweeps use a different column set (no run_index, retry_rc
            # instead of rc); normalise rather than teach every reader about it.
            return normalize(rows)
    logger.warning("%s: no aggregate CSV; sweep may still be running", sweep_dir.name)
    return []


def _score_for(artifacts: Path) -> dict[str, Any] | None:
    # Every score.json the harness has ever written sits directly here (verified
    # across all 748 in data/sweeps/). A recursive fallback walked the whole
    # artifacts subtree — which now grows by one screenshot per agent step — and
    # never once matched.
    return _read_json(artifacts / "score.json")


def _task_entry(score: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for t in score.get("task_scores") or []:
        if t.get("task_id") == task_id:
            return t
    return None


def _observation_mode(meta: dict, artifacts: Path) -> str | None:
    """Modality the run actually used.

    Prefer meta.json, but fall back to the per-step record in
    interactions.jsonl: sweeps run before meta.json carried the field still hold
    the answer, and reviewers asked specifically which modality each run used.
    """
    direct = (meta.get("model") or {}).get("observation_mode") or meta.get("observation_mode")
    if direct:
        return direct
    inter = artifacts / "interactions.jsonl"
    if not inter.exists():
        return None
    modes = set()
    try:
        with open(inter) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = (rec.get("extra") or {}).get("observation_mode")
                if m:
                    modes.add(m)
    except OSError:
        return None
    if not modes:
        return None
    return modes.pop() if len(modes) == 1 else "mixed:" + ",".join(sorted(modes))


def _float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def collect(sweep_dir: Path, max_repeat: int | None = None) -> tuple[list[dict], list[dict]]:
    runs: list[dict] = []
    sigs: list[dict] = []
    skipped = 0
    # retry_failed records which sweep it is a retry of. Reading it here means
    # substitution keys on recorded provenance rather than on the directory
    # name, so `--out` can name the retry dir anything without silently
    # disabling the fold-in.
    manifest = _read_json(sweep_dir / "suite_manifest.json") or {}
    retry_of = manifest.get("retry_of")
    retry_of_sweep = Path(retry_of).name if retry_of else None
    for row in _aggregate_rows(sweep_dir):
        repeat_index = int(row["repeat_index"])
        if max_repeat is not None and repeat_index > max_repeat:
            skipped += 1
            continue
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

        l3_detail = ((entry.get("details") or {}).get("l3") or {}) if entry else {}
        n_testable = l3_detail.get("n_testable")
        coverage = l3_detail.get("coverage")
        # A template that raised is a defect in this repository, not a property
        # of the run: the signature drops out of the denominator, so the L3 that
        # remains is computed over a set we broke. Such a cell is not a low
        # score, it is an unmeasured one.
        # Older scorecards predate these fields; absence is unknown, not zero,
        # so the flag stays None rather than False and the run is reported as
        # having an unknown measurability rather than a failed one.
        measurable = None
        if n_testable is not None and coverage is not None:
            measurable = is_l3_measurable(l3_detail, MIN_L3_COVERAGE)

        runs.append({
            "sweep": sweep_dir.name,
            "retry_of_sweep": retry_of_sweep,
            "run_index": row.get("run_index"),
            "repeat_index": repeat_index,
            # Repeat indices restart at 0 in every sweep, so merging two batches
            # would silently collapse their replicates. The replicate_id is the
            # unit of independent replication and is what the bootstrap resamples.
            "replicate_id": f"{sweep_dir.name}#{repeat_index}",
            "model_id": model_id,
            "task_id": task_id,
            "rc": row.get("rc"),
            "wall_time": row.get("wall_time"),
            # `scored` = a scorecard exists at all; `l1_complete` = the agent
            # actually finished the experiment. Keeping them apart is what lets
            # the analysis separate "no signature" from "harness/agent broke".
            "scored": entry is not None,
            "l1_complete": (l1 is not None and l1 >= 1.0),
            "l3_measurable": measurable,
            "l3_n_testable": n_testable,
            "l3_n_untestable": l3_detail.get("n_untestable"),
            "l3_n_errors": l3_detail.get("n_errors"),
            "l3_coverage": round(coverage, 4) if coverage is not None else None,
            "composite": row.get("composite") or (entry.get("composite") if entry else None),
            "l1": row.get("l1") or (entry.get("l1_completion") if entry else None),
            "l2": row.get("l2") or (entry.get("l2_accuracy") if entry else None),
            "l3": row.get("l3") or (entry.get("l3_behavioral") if entry else None),
            "n_trials": n_trials,
            "observation_mode": _observation_mode(meta, artifacts),
            "git_sha": (meta.get("env") or {}).get("git_sha"),
            "session_id": meta.get("session_id"),
        })

        if not entry:
            continue
        for s in ((entry.get("details") or {}).get("l3") or {}).get("signatures") or []:
            score_val = _float(s.get("score"))
            testable = s.get("testable", True)
            sigs.append({
                "sweep": sweep_dir.name,
                "repeat_index": repeat_index,
                "model_id": model_id,
                "task_id": task_id,
                "signature": s.get("name"),
                # Untestable signatures must not land in a pass-rate denominator:
                # counting "could not be tested" as "did not pass" is the same
                # conflation the scorer was fixed to avoid.
                "testable": testable,
                "untestable_reason": s.get("untestable_reason"),
                "score": score_val,
                # A signature "passes" only on a full 1.0 (correct direction AND
                # significant). The 0.5 partial credit is deliberately not a pass.
                "passed": (score_val is not None and score_val >= 1.0),
                "p_value": s.get("p_value"),
                "effect_size": s.get("effect_size"),
                "direction_correct": s.get("direction_correct"),
            })
    if skipped:
        logger.info("%s: skipped %d runs above --max-repeat", sweep_dir.name, skipped)
    return runs, sigs


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("wrote %s (%d rows)", path, len(rows))


RETRY_SUFFIX = "_retry"


def substitute_retries(runs: list[dict], sigs: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Fold a ``<parent>_retry`` sweep back into its parent's cells.

    A retry sweep re-runs cells that produced nothing, into a separate directory
    so both outcomes stay on disk. Merging the two naively yields two rows for
    the same cell — one failed, one recovered — which double-counts it in every
    attempt-based denominator (completion rate, n_attempts) and makes the design
    read as 412 cells rather than 400.

    Substitution is deliberately narrow: **only** a sweep whose name is
    ``<parent>_retry`` folds into ``<parent>``, and only where the parent row is
    unscored and the retry row is scored. It must never dedup across
    independently launched sweeps — ``rebuttal_v1_launch`` and
    ``rebuttal_v1_batch2`` both number their repeats from 0 and are distinct
    replicates, which is exactly what ``replicate_id`` exists to keep apart.

    The parent's ``replicate_id`` is retained so the bootstrap resamples the same
    units as before; only the scorecard fields change. ``retry_of_rc`` records
    the original failure so the substitution stays auditable.
    """
    def key(r):
        return (str(r["repeat_index"]), r["model_id"], r["task_id"])

    by_sweep_key = {(r["sweep"], key(r)): r for r in runs}
    substituted = 0
    drop_run_ids: set[int] = set()
    drop_sig_sweeps: dict = {}  # (sweep, cell key) -> parent sweep name

    for r in runs:
        sweep = r["sweep"]
        # Recorded provenance first; the name suffix is only a fallback for
        # retry dirs written before `retry_of` was in the manifest.
        parent_name = r.get("retry_of_sweep")
        if not parent_name:
            if not sweep.endswith(RETRY_SUFFIX):
                continue
            parent_name = sweep[: -len(RETRY_SUFFIX)]
        parent = by_sweep_key.get((parent_name, key(r)))
        if parent is None:
            continue  # retry of a cell outside the merged slice; leave it alone
        if parent["scored"] or not r["scored"]:
            continue  # nothing to gain, or the retry failed too
        retry_of_rc = parent.get("rc")
        for f in ("rc", "wall_time", "scored", "l1_complete", "l3_measurable",
                  "composite", "l1", "l2", "l3", "l3_n_testable", "l3_n_untestable",
                  "l3_n_errors", "l3_coverage", "n_trials", "observation_mode",
                  "git_sha", "session_id"):
            parent[f] = r[f]
        parent["retry_of_rc"] = retry_of_rc
        parent["retried"] = True
        drop_run_ids.add(id(r))
        drop_sig_sweeps[(sweep, key(r))] = parent_name
        substituted += 1

    runs_out = [r for r in runs if id(r) not in drop_run_ids]
    # The retry's signature rows now describe the parent cell, so re-stamp them
    # onto the parent sweep rather than dropping the detail.
    sigs_out = []
    for s in sigs:
        k = (s["sweep"], (str(s["repeat_index"]), s["model_id"], s["task_id"]))
        if k in drop_sig_sweeps:
            s = dict(s, sweep=drop_sig_sweeps[k])
        sigs_out.append(s)
    # Drop the parent's stale (empty) signature rows for substituted cells —
    # a failed run has none, so there is nothing to remove in practice.
    return runs_out, sigs_out, substituted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="append", required=True,
                    help="Sweep directory. Repeatable to merge several arms.")
    ap.add_argument("--out", default="results/rebuttal_v1",
                    help="Output directory for runs.csv and signatures.csv.")
    ap.add_argument("--max-repeat", type=int, default=None,
                    help="Drop repeats above this index. Use to exclude waves lost to an "
                         "infrastructure failure, which would otherwise read as agent failures.")
    ap.add_argument("--substitute-retries", action="store_true",
                    help="Fold a <parent>_retry sweep into its parent's cells instead "
                         "of adding rows. Without this a retried cell appears twice, "
                         "once failed and once recovered.")
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
        r, g = collect(d, args.max_repeat)
        all_runs += r
        all_sigs += g

    if not all_runs:
        logger.error("no runs collected — has the sweep written an aggregate yet?")
        return 1

    n_sub = 0
    if args.substitute_retries:
        all_runs, all_sigs, n_sub = substitute_retries(all_runs, all_sigs)
        logger.info("substituted %d retried cell(s) into their parent sweep", n_sub)

    out = Path(args.out)
    _write(out / "runs.csv", RUN_FIELDS, all_runs)
    _write(out / "signatures.csv", SIG_FIELDS, all_sigs)

    scored = sum(1 for r in all_runs if r["scored"])
    complete = sum(1 for r in all_runs if r["l1_complete"])
    print(f"\n{len(all_runs)} runs | {scored} scored ({scored/len(all_runs):.0%}) | "
          f"{complete} fully completed ({complete/len(all_runs):.0%}) | "
          f"{len(all_sigs)} signature observations")
    if n_sub:
        print(f"{n_sub} cell(s) are one-retry substitutions (original attempt produced "
              f"no scorecard); report the retry policy alongside any score built on this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
