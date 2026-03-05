"""Tests for lexical_decision task scoring."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "lexical_decision" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion(human_like_lexical_decision_data, lexical_decision_config):
    result = score_completion(human_like_lexical_decision_data, lexical_decision_config)
    assert result["score"] == 1.0


def test_l2_accuracy(human_like_lexical_decision_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_lexical_decision_data, metrics)
    assert result["score"] > 0.0
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    assert vals["overall_accuracy"] > 0.8
    assert vals["word_accuracy"] > 0.8


def test_lexicality_detected(human_like_lexical_decision_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_lexical_decision_data, sigs)
    sig = next(s for s in result["signatures"] if s["name"] == "lexicality_effect")
    assert sig["direction_correct"]
    assert sig["score"] >= 0.5


def test_random_low_behavioral(random_lexical_decision_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_lexical_decision_data, sigs)
    assert result["score"] <= 0.7


def test_empty_data(lexical_decision_config):
    result = score_completion([], lexical_decision_config)
    assert result["score"] == 0.0
