"""CogArena harness CLI dispatcher.

Three subcommands:
    eval    Run one (model, task[,task,...]) pass with full artifact capture.
    sweep   Expand a YAML suite into many eval calls; run in parallel.
    replay  Build a self-contained replay.html from a session's artifacts.

The harness intentionally wraps (not replaces) the existing agent modules in
``agents/`` — those modules remain a usable lower-level API.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Disable third-party telemetry by default for a clean reproducible run.
# Set explicitly to "true" to opt back in.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_TELEMETRY", "false")


def _add_eval_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default="random",
                   help="Model id or 'random'. Bare model ids resolve via harness/models.yaml. "
                        "OpenRouter-style 'provider/model' strings are passed straight through to Browser-Use.")
    p.add_argument("--scaffold", default=None, choices=[None, "random", "browser-use"],
                   help="Override scaffold. Default: 'random' if --model=random, else 'browser-use'.")
    p.add_argument("--tasks", nargs="+", required=True,
                   help="One or more task IDs (e.g. random_dot_motion_v2).")
    p.add_argument("--base-url", default="http://localhost:8000",
                   help="CogArena server URL.")
    p.add_argument("--start-server", action="store_true",
                   help="Start the FastAPI server automatically (uvicorn subprocess).")
    p.add_argument("--task-timeout", type=float, default=1800.0,
                   help="Max seconds per task (default 1800).")
    p.add_argument("--n-trials", type=int, default=None,
                   help="Override per-task n_trials via URL param.")
    p.add_argument("--use-deadline", action="store_true",
                   help="Honor per-task response deadlines (default: extend).")
    p.add_argument("--agent-name", default=None,
                   help="Friendly agent name recorded in session metadata.")
    p.add_argument("--trace-dir", default=None,
                   help="Directory to write per-session artifacts. Default: data/sessions/<session_id>/.")
    p.add_argument("--replay", action="store_true",
                   help="Build replay.html immediately after the run.")
    p.add_argument("--replay-inline", action="store_true",
                   help="With --replay, base64-inline screenshots into the HTML (single-file artifact).")
    p.add_argument("--verbose", "-v", action="store_true")


def _add_sweep_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--suite", required=True,
                   help="Path to a suite YAML (see harness/suites/headline.yaml).")
    p.add_argument("--max-parallel", type=int, default=1,
                   help="Number of (model, task, repeat) runs to fan out concurrently (default 1).")
    p.add_argument("--base-port", type=int, default=8765,
                   help="First port assigned to subprocess servers; subsequent runs get base_port+1, +2, ...")
    p.add_argument("--results-dir", default=None,
                   help="Sweep results directory. Default: data/sweeps/<suite_name>_<timestamp>/.")
    p.add_argument("--repeats", type=int, default=None,
                   help="Override the suite's `repeats` field.")
    p.add_argument("--n-trials", type=int, default=None,
                   help="Override the suite's `n_trials_override` field.")
    p.add_argument("--tasks", nargs="*", default=None,
                   help="Restrict the suite's tasks to this subset.")
    p.add_argument("--models", nargs="*", default=None,
                   help="Restrict the suite's models to this subset (by id).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the expanded run plan and exit without running anything.")
    p.add_argument("--verbose", "-v", action="store_true")


def _add_replay_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--session", required=True,
                   help="Session id, OR path to a session artifact directory.")
    p.add_argument("--inline", action="store_true",
                   help="Base64-inline screenshots so the HTML is a single self-contained file.")
    p.add_argument("--out", default=None,
                   help="Output path (default: <session-dir>/replay.html).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="CogArena reference harness for running multimodal-agent evaluations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_p = subparsers.add_parser("eval", help="Run one model on one or more tasks.")
    _add_eval_args(eval_p)

    sweep_p = subparsers.add_parser("sweep", help="Run a YAML-defined suite of (model, task, repeat) runs.")
    _add_sweep_args(sweep_p)

    replay_p = subparsers.add_parser("replay", help="Build replay.html from a session's artifacts.")
    _add_replay_args(replay_p)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "eval":
        from harness.eval import run_eval
        return run_eval(args)
    if args.command == "sweep":
        from harness.sweep import run_sweep
        return run_sweep(args)
    if args.command == "replay":
        from harness.replay import build_replay_for_session
        from harness.eval import resolve_session_dir
        session_dir = resolve_session_dir(args.session)
        out = Path(args.out) if args.out else session_dir / "replay.html"
        build_replay_for_session(session_dir, out, inline=args.inline)
        print(out)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
