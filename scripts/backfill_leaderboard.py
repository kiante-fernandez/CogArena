"""Replay locally-archived raw trial data to a CogArena production server.

Reads the per-session artifacts produced by ``harness sweep`` (specifically the
``trial_data/<task_id>.json`` files written by ``fetch_and_save_raw_trial_data``)
and re-submits them to a remote server so the public leaderboard reflects them.

This does NOT re-run the agent. It uses the original raw jsPsych trial data, so
re-scoring on the server side is identical to the original local scoring (any
divergence is a server-side scoring change, not agent variance).

Usage:
    python -m scripts.backfill_leaderboard \\
        --base-url https://cog-arena.vercel.app \\
        --sweep data/sweeps/pilot_v1_20260505_000538 \\
        --sweep data/sweeps/pilot_v1_cheap_20260505_005356

By default skips sessions that returned a non-zero exit code locally (timeouts,
schema rejections). Use --include-failures to also push those (they will create
sessions with no trial data and effectively be ignored by the leaderboard).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import httpx

logger = logging.getLogger("backfill")


def _scaffold_for(meta: dict) -> str:
    return meta.get("model", {}).get("scaffold", "browser-use")


def _model_api_id(meta: dict) -> str:
    """Pick the publicly-meaningful model identifier for the leaderboard."""
    m = meta.get("model", {})
    return m.get("api") or m.get("id") or "unknown"


def _agent_label(meta: dict) -> str:
    """The agent name recorded by the run itself.

    This used to hardcode ``@cogarena-pilot``, which was right when the only
    thing ever backfilled was the pilot. Applied to any later sweep it labels
    those sessions as the very arm they supersede — 400 ten-repeat runs landing
    on the leaderboard calling themselves "pilot". meta.json already carries the
    name the harness used, so use it.
    """
    if meta.get("agent_name"):
        return meta["agent_name"]
    mid = (meta.get("model") or {}).get("id") or "unknown"
    return f"{mid}@cogarena"


def _observation_mode(meta: dict) -> str:
    """Screenshot unless the run recorded otherwise.

    Load-bearing since v1.2.1: the leaderboard groups on observation_mode, so a
    hardcoded value would fold a DOM-only ablation arm into that model's
    screenshot row and drag its composite toward the ablated condition.
    """
    return (meta.get("model") or {}).get("observation_mode") or "screenshot"


def _admin_key() -> str:
    key = os.environ.get("ADMIN_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(".env"):
        for line in open(".env"):
            if line.strip().startswith("ADMIN_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("--approve needs ADMIN_API_KEY in env or .env")


def _approve(client: httpx.Client, session_id: str, key: str) -> bool:
    r = client.post(f"/api/admin/submissions/{session_id}/approve",
                    headers={"X-Admin-Key": key})
    if r.status_code != 200:
        logger.warning("  approve failed for %s (HTTP %d)", session_id, r.status_code)
        return False
    return True


def _push_session(client: httpx.Client, sdir: Path) -> str | None:
    meta_path = sdir / "meta.json"
    if not meta_path.exists():
        logger.warning("skip %s: no meta.json", sdir)
        return None
    meta = json.loads(meta_path.read_text())

    trial_dir = sdir / "trial_data"
    if not trial_dir.exists():
        logger.info("skip %s: no trial_data/ (likely a failed run)", sdir.parent.name)
        return None

    task_files = sorted(trial_dir.glob("*.json"))
    if not task_files:
        logger.info("skip %s: trial_data/ empty", sdir.parent.name)
        return None

    body = {
        "agent_name": _agent_label(meta),
        "scaffold": _scaffold_for(meta),
        "model_name": _model_api_id(meta),
        "observation_mode": _observation_mode(meta),
    }
    r = client.post("/api/sessions", json=body)
    r.raise_for_status()
    session_id = r.json()["session_id"]

    pushed = 0
    for tf in task_files:
        task_id = tf.stem
        trial_data = json.loads(tf.read_text())
        r = client.post(
            f"/api/data/{session_id}/{task_id}",
            json={"trial_data": trial_data},
        )
        if r.status_code != 200:
            logger.warning("  %s: push failed (HTTP %d): %s",
                           task_id, r.status_code, r.text[:200])
            continue
        pushed += 1

    if pushed == 0:
        return None

    r = client.post(f"/api/evaluate/{session_id}")
    r.raise_for_status()
    logger.info("  -> session %s: %d task(s) submitted, evaluation triggered",
                session_id, pushed)
    return session_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True,
                        help="Target server, e.g. https://cog-arena.vercel.app")
    parser.add_argument("--sweep", action="append", required=True,
                        help="Sweep directory (data/sweeps/<name>). Repeatable.")
    parser.add_argument("--runs-csv", default=None,
                        help="Publish EXACTLY the runs listed in a results "
                             "runs.csv (e.g. results/rebuttal_v1/runs.csv). "
                             "Without it the sweep directories are walked whole, "
                             "which includes repeats the analysis excluded via "
                             "--max-repeat and so publishes a board that does not "
                             "equal the reported numbers. Use this whenever the "
                             "board is meant to match a paper.")
    parser.add_argument("--include-failures", action="store_true",
                        help="Also push runs that exited non-zero locally. Use this "
                             "to match the analysis: since v1.2 a run that raised "
                             "may still carry scorable data, and excluding those "
                             "biases the board upward. Runs with no trial_data are "
                             "skipped regardless.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be pushed; do not contact the server.")
    parser.add_argument("--approve", action="store_true",
                        help="Approve each pushed session. Without this they are "
                             "stored but invisible: the leaderboard reads only "
                             "approved sessions, so a backfill that omits this "
                             "silently does nothing. Needs ADMIN_API_KEY.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    candidates: list[Path] = []
    for sweep in args.sweep:
        runs = Path(sweep) / "runs"
        if not runs.exists():
            logger.error("no runs/ under %s", sweep)
            return 1
        for rd in sorted(runs.iterdir()):
            artifacts = rd / "artifacts"
            if not artifacts.exists():
                continue
            run_log = rd / "run.log"
            if not args.include_failures and run_log.exists():
                # Skip sessions whose run.log shows a Python traceback.
                #
                # CAUTION: this predates v1.2, which archives and scores partial
                # runs. A run that raised can still carry scorable trial data,
                # and the analysis counts it — on the ten-repeat study this
                # filter drops 16 of 400 scored runs averaging 36.95 composite
                # against the survivors' 42.55, so publishing only the survivors
                # reports a board that is both selectively covered and unequal
                # to the paper. Use --include-failures to match the analysis;
                # _push_session still skips runs with no trial_data at all.
                tail = run_log.read_text()[-2000:]
                if "Traceback" in tail or "RuntimeError" in tail:
                    continue
            candidates.append(artifacts)

    if args.runs_csv:
        import csv as _csv
        wanted = set()
        with open(args.runs_csv) as fh:
            for row in _csv.DictReader(fh):
                if row.get("scored") != "True":
                    continue
                name = "r%02d_%s_%s" % (int(row["repeat_index"]),
                                        row["model_id"], row["task_id"])
                # A substituted retry keeps the PARENT sweep in `sweep` (that is
                # what --substitute-retries means) while its trial_data lives in
                # <parent>_retry. The parent directory still exists and is empty,
                # so matching on `sweep` alone silently resolves to the failed
                # attempt and drops the recovered cell — which is exactly the 12
                # cells the retry arm was run to recover.
                sweep = row["sweep"]
                if row.get("retried") == "True":
                    sweep += "_retry"
                wanted.add((sweep, name))
        before = len(candidates)
        candidates = [c for c in candidates
                      if (c.parents[2].name, c.parent.name) in wanted]
        missing = wanted - {(c.parents[2].name, c.parent.name) for c in candidates}
        logger.info("--runs-csv: %d of %d candidates match the analysis "
                    "(%d listed, %d not found on disk)",
                    len(candidates), before, len(wanted), len(missing))
        if missing:
            for m in sorted(missing)[:5]:
                logger.warning("  listed but no trial_data on disk: %s/%s", *m)

    logger.info("candidates: %d session(s)", len(candidates))
    if args.dry_run:
        for c in candidates:
            print(f"  {c.parent.name}")
        return 0

    key = _admin_key() if args.approve else None
    pushed = approved = 0
    with httpx.Client(base_url=args.base_url, timeout=120.0) as client:
        try:
            r = client.get("/api/health")
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("health check failed: %s", e)
            return 1

        for i, c in enumerate(candidates, 1):
            try:
                session_id = _push_session(client, c)
            except httpx.HTTPError as e:
                logger.warning("push failed for %s: %s", c.parent.name, e)
                continue
            if not session_id:
                continue
            pushed += 1
            if key and _approve(client, session_id, key):
                approved += 1
            if i % 25 == 0:
                logger.info("progress: %d/%d pushed, %d approved",
                            pushed, len(candidates), approved)

    logger.info("done: pushed %d / %d, approved %d", pushed, len(candidates), approved)
    if pushed and not args.approve:
        logger.warning("nothing was approved, so none of this reaches the "
                       "leaderboard — re-run with --approve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
