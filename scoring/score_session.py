import json
import argparse
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral
from scoring.composite_score import compute_composite


def _augment_derived_fields(trial_data: list[dict], task_id: str) -> list[dict]:
    """Add per-task derived fields to each trial in place.

    Some L2/L3 metrics need quantities that are easier to compute over the
    full session than to log per-trial in experiment.js. Implementations live
    here so jsPsych code stays simple. Returns the (mutated) trial list.
    """
    if task_id == "tiny_alchemy":
        seen_pairs: set[tuple[int, int]] = set()
        for trial in trial_data:
            a = trial.get("element_a_idx")
            b = trial.get("element_b_idx")
            if a is None or b is None:
                trial["is_unique_pair"] = None
                continue
            pair = (min(a, b), max(a, b))  # unordered
            trial["is_unique_pair"] = pair not in seen_pairs
            seen_pairs.add(pair)
    return trial_data


def score_task(trial_data: list[dict], task_id: str, tasks_dir: Path) -> dict:
    task_dir = tasks_dir / task_id

    with open(task_dir / "task_config.json") as f:
        task_config = json.load(f)
    with open(task_dir / "scoring" / "level2_metrics.json") as f:
        metrics_spec = json.load(f)
    with open(task_dir / "scoring" / "level3_signatures.json") as f:
        signatures_spec = json.load(f)

    trial_data = _augment_derived_fields(trial_data, task_id)

    l1_result = score_completion(trial_data, task_config)
    l2_result = score_accuracy(trial_data, metrics_spec)
    l3_result = score_behavioral(trial_data, signatures_spec)

    composite = compute_composite(l1_result["score"], l2_result["score"], l3_result["score"])

    return {
        "task_id": task_id,
        "composite": composite,
        "l1": l1_result,
        "l2": l2_result,
        "l3": l3_result,
    }


def main():
    parser = argparse.ArgumentParser(description="CogArena Scoring Pipeline")
    parser.add_argument("--trial-data", type=Path, required=True)
    parser.add_argument("--task-id", type=str, default="stroop")
    parser.add_argument("--tasks-dir", type=Path, default=Path("tasks"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    with open(args.trial_data) as f:
        data = json.load(f)

    trial_data = data.get("trial_data", data) if isinstance(data, dict) else data

    result = score_task(trial_data, args.task_id, args.tasks_dir)

    output = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(output)
    print(output)


if __name__ == "__main__":
    main()
