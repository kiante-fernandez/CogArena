"""Tests for insider_attack task scoring."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "insider_attack" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion(human_like_insider_attack_data, insider_attack_config):
    result = score_completion(human_like_insider_attack_data, insider_attack_config)
    assert result["score"] == 1.0


def test_l2_accuracy(human_like_insider_attack_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_insider_attack_data, metrics)
    assert result["score"] > 0.0


def test_ev_maximization_detected(human_like_insider_attack_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_insider_attack_data, sigs)
    sig = next(s for s in result["signatures"] if s["name"] == "ev_maximization")
    assert sig["direction_correct"]
    assert sig["score"] >= 0.5


def test_random_low_behavioral(random_insider_attack_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_insider_attack_data, sigs)
    assert result["score"] <= 0.75


def test_empty_data(insider_attack_config):
    result = score_completion([], insider_attack_config)
    assert result["score"] == 0.0
