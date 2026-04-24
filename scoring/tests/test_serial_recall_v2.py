"""Tests for serial_recall_v2 task scoring (Haridi cued paired-associate recall)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "serial_recall_v2" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_serial_recall_v2_data, serial_recall_v2_config):
    result = score_completion(human_like_serial_recall_v2_data, serial_recall_v2_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_serial_recall_v2_data, serial_recall_v2_config):
    result = score_completion(random_serial_recall_v2_data, serial_recall_v2_config)
    assert result["score"] == 1.0


def test_l2_humanlike_recovers_similarity_gradient(human_like_serial_recall_v2_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_serial_recall_v2_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Headline: high-similarity pairs are recalled more accurately than low-similarity pairs.
    assert vals["accuracy_high_sim"] > vals["accuracy_low_sim"]
    assert vals["overall_accuracy"] > 0.4


def test_l3_humanlike_recovers_signatures(human_like_serial_recall_v2_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_serial_recall_v2_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    assert sig_by_name["above_chance_recall"]["direction_correct"]
    assert sig_by_name["similarity_aids_recall"]["direction_correct"]
    assert sig_by_name["high_vs_low_sim_advantage"]["direction_correct"]
    assert result["score"] >= 0.7


def test_l3_random_low_score(random_serial_recall_v2_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_serial_recall_v2_data, sigs)
    # Random typing gives near-zero accuracy; signatures should not fire.
    assert result["score"] <= 0.3


def test_empty_data_l1_zero(serial_recall_v2_config):
    result = score_completion([], serial_recall_v2_config)
    assert result["score"] == 0.0
