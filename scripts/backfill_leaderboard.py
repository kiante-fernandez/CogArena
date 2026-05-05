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
    m = meta.get("model", {})
    mid = m.get("id") or "unknown"
    return f"{mid}@cogarena-pilot"


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
        "observation_mode": "screenshot",
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
    parser.add_argument("--include-failures", action="store_true",
                        help="Also push runs that exited non-zero locally.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be pushed; do not contact the server.")
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
                # Skip sessions whose run.log shows a Python traceback (these
                # are the timeouts and schema rejections we don't want to
                # publish under "ran successfully").
                tail = run_log.read_text()[-2000:]
                if "Traceback" in tail or "RuntimeError" in tail:
                    continue
            candidates.append(artifacts)

    logger.info("candidates: %d session(s)", len(candidates))
    if args.dry_run:
        for c in candidates:
            print(f"  {c.parent.name}")
        return 0

    pushed = 0
    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        try:
            r = client.get("/api/health")
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("health check failed: %s", e)
            return 1

        for c in candidates:
            try:
                if _push_session(client, c):
                    pushed += 1
            except httpx.HTTPError as e:
                logger.warning("push failed for %s: %s", c.parent.name, e)

    logger.info("done: pushed %d / %d", pushed, len(candidates))
    return 0


if __name__ == "__main__":
    sys.exit(main())
