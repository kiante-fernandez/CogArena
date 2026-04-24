"""Tests for effort_foraging task scoring (Bustamante 2023 patch foraging)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "effort_foraging" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_effort_foraging_data, effort_foraging_config):
    result = score_completion(human_like_effort_foraging_data, effort_foraging_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_effort_foraging_data, effort_foraging_config):
    result = score_completion(random_effort_foraging_data, effort_foraging_config)
    assert result["score"] == 1.0


def test_l2_humanlike_recovers_residence_gradient(human_like_effort_foraging_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_effort_foraging_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Headline MVT prediction: longer residence in high-cost than low-cost.
    assert vals["mean_residence_time_high"] > vals["mean_residence_time_low"]
    # MVT match should beat chance.
    assert vals["mvt_optimal_match_rate"] > 0.5


def test_l3_humanlike_recovers_signatures(human_like_effort_foraging_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_effort_foraging_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    assert sig_by_name["travel_cost_residence_effect"]["direction_correct"]
    assert sig_by_name["above_chance_mvt_match"]["direction_correct"]
    assert result["score"] >= 0.6


def test_l3_random_low_score(random_effort_foraging_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_effort_foraging_data, sigs)
    # Random play should not reliably fire the directional MVT signatures.
    assert result["score"] <= 0.6


def test_empty_data_l1_zero(effort_foraging_config):
    result = score_completion([], effort_foraging_config)
    assert result["score"] == 0.0
