"""The committed results tables must still reproduce under the current specs.

``results/*/runs.csv`` is reviewer-facing: the headline table, the random floor,
the vision ablation and the flagship run are all read straight off these files,
and the leaderboard is backfilled from the same sweeps. Nothing regenerates them
when a spec changes, so editing one threshold in ``level3_signatures.json`` moves
the scorer while these files keep the old numbers, and the divergence is
invisible — every one of them still parses, still has plausible values, and still
sums to a plausible mean.

That already happened once. Adding ``underpowered`` as an untestable reason
during v1.2.1 rewrote 100 rows of the archive; the scores were identical, so
nothing complained, and the CSVs were regenerated only because someone thought to
re-run the builder before committing.

The check is a re-score: take each row's session, run its archived trial_data
through the live specs, and compare. A spec edit that changes any published
number now fails here instead of shipping.

Rows join by ``session_id`` and nothing else. ``run_index`` looks like a key and
is not — it restarts per replicate, so joining on it silently pairs rows with
other sessions' scores and reports differences that are pure join error.

``results/pilot_v1.csv`` and ``results/random_floor_v1.csv`` are out of scope:
they predate the tidy tables, carry no ``session_id``, and describe the May pilot
under a scorer that no longer exists. They are historical records, not current
claims.

The archives under ``data/sweeps/`` are gitignored, so this skips on a fresh
clone. It is a guard for the repo where the specs are edited.
"""
import csv
import json
from functools import lru_cache
from pathlib import Path

import pytest

from scoring.score_session import score_task

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = REPO_ROOT / "tasks"

# Every results table carrying session ids. Add a directory here when
# build_results.py starts writing one.
RESULT_DIRS = ["rebuttal_v1", "random_floor", "vision_ablation", "flagship"]

# Composites are stored to 2dp and the level scores to 4dp, so compare at half a
# unit in the last place they were written.
TOLERANCE = 5e-5

REBUILD = "python -m scripts.build_results --sweep data/sweeps/<sweep> --out results/{label}"


@lru_cache(maxsize=None)
def _session_index():
    """session_id -> artifacts dir, over every sweep on disk.

    Cached because each parametrised case needs the same map and the glob walks
    ~1k sessions.
    """
    out = {}
    for meta in REPO_ROOT.glob("data/sweeps/*/runs/*/artifacts/meta.json"):
        try:
            sid = json.load(open(meta)).get("session_id")
        except (OSError, ValueError):
            continue
        if sid:
            out[sid] = meta.parent
    return out


def _archived_trials(artifacts, task_id):
    path = artifacts / "trial_data" / f"{task_id}.json"
    if not path.exists():
        return None
    try:
        trials = json.load(open(path))
    except (OSError, ValueError):
        return None
    if isinstance(trials, dict):
        trials = trials.get("trials", [])
    return trials or None


@pytest.mark.parametrize("label", RESULT_DIRS)
def test_committed_runs_csv_matches_current_scorer(label):
    csv_path = REPO_ROOT / "results" / label / "runs.csv"
    if not csv_path.exists():
        pytest.skip(f"{csv_path.relative_to(REPO_ROOT)} not present")

    sessions = _session_index()
    rows = list(csv.DictReader(open(csv_path)))
    scored_rows = [r for r in rows if r["scored"] == "True"]

    moved, checked = [], 0
    for row in scored_rows:
        artifacts = sessions.get(row["session_id"])
        if artifacts is None:
            continue  # archive for this sweep is not on this machine
        trials = _archived_trials(artifacts, row["task_id"])
        if trials is None:
            continue  # run produced no raw data; the CSV records that as-is
        result = score_task(trials, row["task_id"], TASKS_DIR)
        checked += 1
        now = {
            "composite": result["composite"]["composite_score"],
            "l1": result["l1"]["score"],
            "l2": result["l2"]["score"],
            "l3": result["l3"]["score"],
        }
        diff = {k: (float(row[k]), round(v, 4))
                for k, v in now.items() if abs(float(row[k]) - v) > TOLERANCE}
        if diff:
            moved.append(f"{row['model_id']}/{row['task_id']} {diff}")

    if checked == 0:
        pytest.skip(f"no archived sessions for {label} under data/sweeps/")

    assert not moved, (
        f"{label}: {len(moved)} of {checked} committed rows no longer reproduce "
        f"under the current specs. These numbers are reviewer-facing, so either "
        f"the spec change was unintended or the table needs rebuilding:\n  "
        + REBUILD.format(label=label) + "\n"
        + "\n".join(f"  {m}" for m in moved[:20])
        + (f"\n  ... and {len(moved) - 20} more" if len(moved) > 20 else "")
    )
