import json
import argparse
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral
from scoring.composite_score import compute_composite


def score_task(trial_data: list[dict], task_id: str, tasks_dir: Path) -> dict:
    task_dir = tasks_dir / task_id

    with open(task_dir / "task_config.json") as f:
        task_config = json.load(f)
    with open(task_dir / "scoring" / "level2_metrics.json") as f:
        metrics_spec = json.load(f)
    with open(task_dir / "scoring" / "level3_signatures.json") as f:
        signatures_spec = json.load(f)

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
