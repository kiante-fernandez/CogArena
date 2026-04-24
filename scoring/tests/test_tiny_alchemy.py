"""Tests for tiny_alchemy task scoring (Brändle empowerment-driven combinatorial discovery)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "tiny_alchemy" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_tiny_alchemy_data, tiny_alchemy_config):
    result = score_completion(human_like_tiny_alchemy_data, tiny_alchemy_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_tiny_alchemy_data, tiny_alchemy_config):
    result = score_completion(random_tiny_alchemy_data, tiny_alchemy_config)
    assert result["score"] == 1.0


def test_l2_humanlike_high_success_rate(human_like_tiny_alchemy_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_tiny_alchemy_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Humanlike fixture should have substantially above-chance success rate.
    assert vals["success_rate"] > 0.20


def test_l3_humanlike_recovers_signatures(human_like_tiny_alchemy_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_tiny_alchemy_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    # Headline: above-chance discovery.
    assert sig_by_name["above_chance_discovery"]["direction_correct"]
    # Empowerment-preference: high in-degree pairs more likely to succeed.
    assert sig_by_name["empowerment_preference"]["direction_correct"]
    # Composite L3 should be substantially above chance.
    assert result["score"] >= 0.5


def test_l3_random_low_score(random_tiny_alchemy_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_tiny_alchemy_data, sigs)
    # Random data should not consistently fire all directional signatures.
    assert result["score"] <= 0.55


def test_empty_data_l1_zero(tiny_alchemy_config):
    result = score_completion([], tiny_alchemy_config)
    assert result["score"] == 0.0
