"""Re-run the cells of a sweep that produced no usable scorecard.

``harness/sweep.py`` records a run's return code but never retries it. In the v1
pilot 15 of 60 cells died that way (``grid_bandit`` scored 2/6), and a failed
cell is indistinguishable in the results from a model that genuinely lacks a
signature — the confound reviewers flagged directly.

Retries are written to a SEPARATE sweep directory (``<sweep>_retry``) using the
same run-id scheme, never overwriting the original attempt. Both outcomes stay
on disk, so the retry policy is auditable and the analysis can choose whether to
substitute or to report attempts-and-successes. Merge them with::

    python -m scripts.build_results --sweep <sweep> --sweep <sweep>_retry ...

IMPORTANT: retries are capped at one attempt per cell by default. Retrying until
a cell succeeds selects for lucky runs and silently inflates every score built on
top of it. Whatever cap you use, report it.

Usage::

    python -m scripts.retry_failed --sweep data/sweeps/rebuttal_v1_... --dry-run
    python -m scripts.retry_failed --sweep data/sweeps/rebuttal_v1_... --max-parallel 4
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("retry_failed")


def _read_json(p: Path) -> dict[str, Any] | None:
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _rid(repeat_index: int, model_id: str, task_id: str) -> str:
    return f"r{repeat_index:02d}_{model_id}_{task_id}"


def _has_usable_result(artifacts: Path, task_id: str) -> bool:
    """A cell is usable if it archived raw trial data AND produced a scorecard
    entry for the task. Either alone is not enough: trial_data without a score
    means scoring failed, a score without trial_data cannot be re-scored later."""
    # Cheap checks first. Parsing trial_data to test "non-empty list" costs a
    # full JSON decode of up to 1.6 MB per cell; a stat plus the small score.json
    # rules out most rows for ~0.4% of that.
    trial_file = artifacts / "trial_data" / f"{task_id}.json"
    if not trial_file.exists() or trial_file.stat().st_size <= 2:  # "[]" or empty
        return False
    score = _read_json(artifacts / "score.json")
    if not score or not any(t.get("task_id") == task_id
                            for t in score.get("task_scores") or []):
        return False
    trials = _read_json(trial_file)
    return isinstance(trials, list) and bool(trials)


def find_failed(sweep_dir: Path, max_repeat: int | None = None,
                models: list[str] | None = None,
                tasks: list[str] | None = None) -> list[dict[str, Any]]:
    """Cells with no usable scorecard, optionally narrowed.

    The filters exist because a sweep's aggregate can contain repeats that the
    analysis deliberately excludes — `rebuttal_v1_launch` holds 400 rows but only
    repeats 0-4 are used, the rest having died on an OpenRouter spend cap and
    been dropped via `build_results --max-repeat 4`. Retrying those would spend
    money re-running cells no reported number depends on, so the retry set must
    be narrowable to the same slice the analysis actually uses.
    """
    agg = None
    for name in ("aggregate_audited.csv", "aggregate.csv"):
        if (sweep_dir / name).exists():
            agg = sweep_dir / name
            break
    if agg is None:
        raise SystemExit(f"No aggregate CSV in {sweep_dir} — is the sweep still running?")

    failed = []
    with open(agg) as f:
        for row in csv.DictReader(f):
            repeat_index = int(row["repeat_index"])
            model_id, task_id = row["model_id"], row["task_id"]
            if max_repeat is not None and repeat_index > max_repeat:
                continue
            if models and model_id not in models:
                continue
            if tasks and task_id not in tasks:
                continue
            artifacts = sweep_dir / "runs" / _rid(repeat_index, model_id, task_id) / "artifacts"
            if _has_usable_result(artifacts, task_id):
                continue
            failed.append({
                "repeat_index": repeat_index,
                "model_id": model_id,
                "task_id": task_id,
                "original_rc": row.get("rc"),
            })
    return failed


def _load_suite(sweep_dir: Path) -> dict[str, Any]:
    """The suite the original sweep ran, with its recorded conditions restored.

    The suite YAML may have moved or changed since the sweep, so anything the
    manifest recorded about the run condition wins over the file. `no_vision` in
    particular must survive: retrying a vision-off arm with vision produces runs
    of a different condition inside a directory named for the first one, and
    `build_results --substitute-retries` would then fold them together.
    """
    manifest = _read_json(sweep_dir / "suite_manifest.json") or {}
    suite: dict[str, Any] = {}
    suite_path = manifest.get("suite_path")
    if suite_path and Path(suite_path).exists():
        with open(suite_path) as f:
            suite = yaml.safe_load(f) or {}
    else:
        logger.warning("suite YAML not found; falling back to harness defaults")
    if "no_vision" in manifest:
        suite["no_vision"] = manifest["no_vision"]
    if suite.get("no_vision"):
        logger.info("parent sweep ran vision-off; retries will too")
    return suite


def _execute(cell: dict[str, Any], out_dir: Path, suite: dict[str, Any],
             port: int) -> dict[str, Any]:
    rid = _rid(cell["repeat_index"], cell["model_id"], cell["task_id"])
    run_root = out_dir / "runs" / rid
    artifacts = run_root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    log_path = run_root / "run.log"

    args = [
        sys.executable, "-m", "harness", "eval",
        "--model", cell["model_id"],
        "--tasks", cell["task_id"],
        "--base-url", f"http://localhost:{port}",
        "--start-server",
        "--task-timeout", str(suite.get("task_timeout_seconds", 1800)),
        "--trace-dir", str(artifacts),
        "--agent-name", f"{cell['model_id']}@cogarena-harness",
    ]
    if suite.get("n_trials_override"):
        args += ["--n-trials", str(suite["n_trials_override"])]
    # Same key as harness/sweep.py: a retried cell must run the condition the
    # original ran, or it is a different experiment wearing the same directory.
    if suite.get("no_vision"):
        args.append("--no-vision")
    if not suite.get("no_deadline", True):
        args += ["--use-deadline"]

    start = time.time()
    with open(log_path, "w") as fh:
        proc = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT,
                              cwd=str(REPO_ROOT), check=False)
    elapsed = time.time() - start

    score = _read_json(artifacts / "score.json") or {}
    return {
        **cell,
        "retry_rc": proc.returncode,
        "retry_wall_time": round(elapsed, 1),
        "retry_usable": _has_usable_result(artifacts, cell["task_id"]),
        "composite": score.get("composite_score"),
        "l1": score.get("l1_overall"),
        "l2": score.get("l2_overall"),
        "l3": score.get("l3_overall"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", required=True, help="Sweep directory to scan for failed cells.")
    ap.add_argument("--out", default=None,
                    help="Retry output dir. Default: <sweep>_retry (never overwrites originals).")
    ap.add_argument("--max-parallel", type=int, default=4)
    ap.add_argument("--base-port", type=int, default=9500)
    ap.add_argument("--max-retries", type=int, default=1,
                    help="Attempts per failed cell. Keep at 1; more selects for lucky runs.")
    ap.add_argument("--max-repeat", type=int, default=None,
                    help="Ignore repeats above this index. Use to match the slice the "
                         "analysis keeps, so retries do not spend money on excluded waves.")
    ap.add_argument("--model", action="append", default=None,
                    help="Only retry this model_id. Repeatable.")
    ap.add_argument("--task", action="append", default=None,
                    help="Only retry this task_id. Repeatable.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")

    sweep_dir = Path(args.sweep)
    if not sweep_dir.is_dir():
        logger.error("not a directory: %s", sweep_dir)
        return 2

    failed = find_failed(sweep_dir, max_repeat=args.max_repeat,
                         models=args.model, tasks=args.task)
    if not failed:
        print("No failed cells — nothing to retry.")
        return 0

    by_model: dict[str, int] = {}
    by_task: dict[str, int] = {}
    for c in failed:
        by_model[c["model_id"]] = by_model.get(c["model_id"], 0) + 1
        by_task[c["task_id"]] = by_task.get(c["task_id"], 0) + 1

    print(f"{len(failed)} cells produced no usable result.\n")
    print("  by model:")
    for m, n in sorted(by_model.items(), key=lambda x: -x[1]):
        print(f"    {m:26s} {n:4d}")
    print("  by task:")
    for t, n in sorted(by_task.items(), key=lambda x: -x[1]):
        print(f"    {t:26s} {n:4d}")

    if args.dry_run:
        print("\n--dry-run: nothing executed.")
        return 0

    out_dir = Path(args.out) if args.out else sweep_dir.parent / f"{sweep_dir.name}_retry"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "suite_manifest.json", "w") as f:
        json.dump({
            "suite_name": f"{sweep_dir.name}_retry",
            "suite_path": (_read_json(sweep_dir / "suite_manifest.json") or {}).get("suite_path"),
            "retry_of": str(sweep_dir),
            "max_retries_per_cell": args.max_retries,
            "total_runs": len(failed),
            "started_at_utc": _dt.datetime.utcnow().isoformat() + "Z",
        }, f, indent=2)

    suite = _load_suite(sweep_dir)
    print(f"\nRetrying {len(failed)} cells into {out_dir} "
          f"(max_parallel={args.max_parallel}, {args.max_retries} attempt/cell)\n")

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as ex:
        futures = {
            ex.submit(_execute, c, out_dir, suite, args.base_port + i): c
            for i, c in enumerate(failed)
        }
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            results.append(r)
            flag = "RECOVERED" if r["retry_usable"] else "still failing"
            comp = f"{r['composite']:.1f}" if r.get("composite") is not None else "  -  "
            print(f"  [{n}/{len(failed)}] {flag:14s} {r['model_id']:<24} "
                  f"{r['task_id']:<24} composite={comp:>6} ({r['retry_wall_time']:.0f}s)")

    fields = ["repeat_index", "model_id", "task_id", "original_rc",
              "retry_rc", "retry_wall_time", "retry_usable",
              "composite", "l1", "l2", "l3"]
    with open(out_dir / "aggregate.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    recovered = sum(1 for r in results if r["retry_usable"])
    print(f"\n{recovered}/{len(results)} cells recovered on retry "
          f"({recovered/len(results):.0%}). Results in {out_dir}")
    print("Report the one-retry policy and this recovery rate alongside any "
          "score computed from the merged set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
