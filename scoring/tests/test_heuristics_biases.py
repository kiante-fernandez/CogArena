"""Tests for heuristics_biases task scoring."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "heuristics_biases" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion(human_like_heuristics_biases_data, heuristics_biases_config):
    result = score_completion(human_like_heuristics_biases_data, heuristics_biases_config)
    assert result["score"] == 1.0


def test_l2_accuracy(human_like_heuristics_biases_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_heuristics_biases_data, metrics)
    assert result["score"] > 0.0
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    assert vals["overall_accuracy"] > 0.5


def test_above_chance_detected(human_like_heuristics_biases_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_heuristics_biases_data, sigs)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_accuracy")
    assert sig["direction_correct"]
    assert sig["score"] >= 0.5


def test_random_low_behavioral(random_heuristics_biases_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_heuristics_biases_data, sigs)
    assert result["score"] <= 0.7


def test_empty_data(heuristics_biases_config):
    result = score_completion([], heuristics_biases_config)
    assert result["score"] == 0.0
