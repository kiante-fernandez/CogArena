"""Suite runner: expand a YAML suite into many ``harness eval`` calls and
fan them out to a configurable parallel pool.

Each (model, task, repeat) tuple becomes one subprocess call to::

    python -m harness eval --model <id> --tasks <task> --start-server \\
        --base-url http://localhost:<base_port + run_index>

Subprocesses get unique ports so their FastAPI servers don't collide.
Per-run logs go under ``<results_dir>/runs/<run_id>/run.log``.
After all runs finish, ``aggregate.csv`` summarises the per-run scorecards.

Repeat-waves: wave-K of every (model, task) finishes before wave-(K+1) starts.
This gives the user "all-models-at-once early signal" instead of finishing
one model's full sweep before another starts.
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("harness.sweep")

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Run:
    run_index: int
    repeat_index: int
    model_id: str
    task_id: str
    base_url: str
    log_path: Path
    artifact_dir: Path
    rc: int | None = None
    composite: float | None = None
    l1: float | None = None
    l2: float | None = None
    l3: float | None = None
    wall_time: float | None = None


def _load_suite(path: Path) -> dict[str, Any]:
    with open(path) as f:
        suite = yaml.safe_load(f)
    if not suite or "tasks" not in suite or "models" not in suite:
        raise ValueError(f"Invalid suite YAML at {path}: must define `tasks` and `models`.")
    return suite


def expand_runs(suite: dict[str, Any], *, base_port: int,
                tasks_filter: list[str] | None = None,
                models_filter: list[str] | None = None,
                repeats_override: int | None = None,
                results_dir: Path) -> list[Run]:
    """Expand the suite to a flat list of Run objects, ordered by wave.

    Within a wave (= one repeat across all (model, task) cells), runs are in
    the order they appear in the YAML. Wave-K of every cell finishes before
    wave-(K+1) starts.
    """
    tasks = suite["tasks"]
    if tasks_filter:
        tasks = [t for t in tasks if t in tasks_filter]
    models = [m["id"] for m in suite["models"]]
    if models_filter:
        models = [m for m in models if m in models_filter]
    repeats = repeats_override or suite.get("repeats", 1)

    runs: list[Run] = []
    run_index = 0
    for repeat_index in range(repeats):
        for model_id in models:
            for task_id in tasks:
                base_url = f"http://localhost:{base_port + run_index}"
                rid = f"r{repeat_index:02d}_{model_id}_{task_id}"
                log_path = results_dir / "runs" / rid / "run.log"
                artifact_dir = results_dir / "runs" / rid / "artifacts"
                runs.append(Run(
                    run_index=run_index, repeat_index=repeat_index,
                    model_id=model_id, task_id=task_id,
                    base_url=base_url,
                    log_path=log_path, artifact_dir=artifact_dir,
                ))
                run_index += 1
    return runs


def _execute_run(run: Run, suite: dict[str, Any], n_trials: int | None) -> Run:
    """Spawn one ``harness eval`` subprocess and capture its result."""
    run.log_path.parent.mkdir(parents=True, exist_ok=True)
    run.artifact_dir.mkdir(parents=True, exist_ok=True)

    args = [
        sys.executable, "-m", "harness", "eval",
        "--model", run.model_id,
        "--tasks", run.task_id,
        "--base-url", run.base_url,
        "--start-server",
        "--task-timeout", str(suite.get("task_timeout_seconds", 1800)),
        "--trace-dir", str(run.artifact_dir),
        "--agent-name", f"{run.model_id}@cogarena-harness",
    ]
    if n_trials is not None:
        args += ["--n-trials", str(n_trials)]
    elif suite.get("n_trials_override"):
        args += ["--n-trials", str(suite["n_trials_override"])]
    # Observation modality belongs in the suite, not only on the eval CLI: a
    # sweep and a retry of that sweep must run the same condition, and a
    # vision-off arm that silently retries with vision would land both
    # conditions in one results table under one directory name.
    if suite.get("no_vision"):
        args.append("--no-vision")
    if not suite.get("no_deadline", True):
        args += ["--use-deadline"]

    start = time.time()
    with open(run.log_path, "w") as logfile:
        proc = subprocess.run(
            args, stdout=logfile, stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT), check=False,
        )
    run.rc = proc.returncode
    run.wall_time = time.time() - start

    # Parse the score.json that harness eval drops into the artifact dir.
    # Shape: {composite_score, l1_overall, l2_overall, l3_overall, task_scores: [...]}
    score_path = _find_score_json(run.artifact_dir)
    if score_path:
        try:
            with open(score_path) as f:
                results = json.load(f)
            run.composite = results.get("composite_score")
            run.l1 = results.get("l1_overall")
            run.l2 = results.get("l2_overall")
            run.l3 = results.get("l3_overall")
        except Exception as e:
            logger.warning("Failed to parse %s: %s", score_path, e)
    return run


def _find_score_json(artifact_dir: Path) -> Path | None:
    """The eval subprocess writes data/sessions/<sid>/score.json by default;
    when --trace-dir is passed it writes into that directory instead."""
    direct = artifact_dir / "score.json"
    if direct.exists():
        return direct
    # Fall back: search for any score.json under artifact_dir or sibling sessions/.
    for p in artifact_dir.rglob("score.json"):
        return p
    return None


def _write_aggregate_csv(runs: list[Run], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_index", "repeat_index", "model_id", "task_id",
                    "rc", "wall_time", "composite", "l1", "l2", "l3"])
        for r in runs:
            w.writerow([r.run_index, r.repeat_index, r.model_id, r.task_id,
                        r.rc, f"{r.wall_time:.1f}" if r.wall_time else "",
                        f"{r.composite:.2f}" if r.composite is not None else "",
                        f"{r.l1:.4f}" if r.l1 is not None else "",
                        f"{r.l2:.4f}" if r.l2 is not None else "",
                        f"{r.l3:.4f}" if r.l3 is not None else ""])


def run_sweep(args) -> int:
    """Entry point invoked by ``harness.cli.main`` for the ``sweep`` subcommand."""
    suite_path = Path(args.suite)
    suite = _load_suite(suite_path)
    suite_name = suite.get("suite_name", suite_path.stem)

    if args.results_dir:
        results_dir = Path(args.results_dir)
    else:
        stamp = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        results_dir = REPO_ROOT / "data" / "sweeps" / f"{suite_name}_{stamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    # CLI overrides the suite so an ablation can be driven either way, but the
    # resolved value is written into the manifest below — the sweep dir must
    # record which condition it ran, since retries read it back from there.
    if args.no_vision:
        suite["no_vision"] = True

    runs = expand_runs(
        suite, base_port=args.base_port,
        tasks_filter=args.tasks, models_filter=args.models,
        repeats_override=args.repeats, results_dir=results_dir,
    )

    n_repeats = max((r.repeat_index for r in runs), default=-1) + 1
    n_per_wave = len(runs) // n_repeats if n_repeats else len(runs)
    print(f"Sweep: suite={suite_name}, total_runs={len(runs)}, "
          f"waves={n_repeats}, runs_per_wave={n_per_wave}, "
          f"max_parallel={args.max_parallel}")
    print(f"Results dir: {results_dir}")

    if args.dry_run:
        print()
        print(f"{'idx':>4} {'wave':>4} {'model':<22} {'task':<24} {'port':>6}")
        for r in runs:
            port = r.base_url.rsplit(":", 1)[-1]
            print(f"{r.run_index:>4} {r.repeat_index:>4} {r.model_id:<22} {r.task_id:<24} {port:>6}")
        return 0

    # Persist suite manifest + run plan up-front so the run is recoverable.
    with open(results_dir / "suite_manifest.json", "w") as f:
        json.dump({
            "suite_name": suite_name, "suite_path": str(suite_path),
            "total_runs": len(runs), "max_parallel": args.max_parallel,
            "started_at_utc": _dt.datetime.utcnow().isoformat() + "Z",
            "n_repeats": n_repeats,
            # Recorded so a retry of this sweep reproduces the same condition
            # rather than silently running the default one.
            "no_vision": bool(suite.get("no_vision")),
        }, f, indent=2)

    # Execute wave-by-wave with bounded parallelism.
    completed: list[Run] = []
    for wave_idx in range(n_repeats):
        wave = [r for r in runs if r.repeat_index == wave_idx]
        print(f"\n=== Wave {wave_idx + 1}/{n_repeats} ({len(wave)} runs) ===")
        with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as ex:
            futures = {ex.submit(_execute_run, r, suite, args.n_trials): r for r in wave}
            done = 0
            for fut in as_completed(futures):
                r = fut.result()
                done += 1
                completed.append(r)
                status = "OK " if r.rc == 0 else "FAIL"
                comp = f"{r.composite:.1f}" if r.composite is not None else "  -  "
                print(f"  [{done}/{len(wave)}] {status} {r.model_id:<22} "
                      f"{r.task_id:<24} composite={comp:>6} ({r.wall_time:.0f}s)")

        # Persist incremental aggregate after each wave so partial results
        # are usable if the sweep is interrupted.
        _write_aggregate_csv(completed, results_dir / "aggregate.csv")

    print(f"\nSweep complete. Aggregate: {results_dir / 'aggregate.csv'}")
    return 0
