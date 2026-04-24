"""Tests for phishing_detection_v2 task scoring (Singh 2019 dataset, 3-phase paradigm)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "phishing_detection_v2" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_phishing_detection_v2_data, phishing_detection_v2_config):
    result = score_completion(human_like_phishing_detection_v2_data, phishing_detection_v2_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_phishing_detection_v2_data, phishing_detection_v2_config):
    result = score_completion(random_phishing_detection_v2_data, phishing_detection_v2_config)
    assert result["score"] == 1.0


def test_l2_humanlike_above_chance(human_like_phishing_detection_v2_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_phishing_detection_v2_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    assert vals["overall_accuracy"] > 0.55
    assert vals["hit_rate"] > 0.55
    assert vals["false_alarm_rate"] < 0.45


def test_l3_humanlike_recovers_signatures(human_like_phishing_detection_v2_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_phishing_detection_v2_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    # Headline: hit rate > false alarm rate.
    assert sig_by_name["above_chance_discrimination"]["direction_correct"]
    # Above-chance overall accuracy.
    assert sig_by_name["above_chance_overall"]["direction_correct"]
    # Composite L3 should be high.
    assert result["score"] >= 0.5


def test_l3_random_low_score(random_phishing_detection_v2_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_phishing_detection_v2_data, sigs)
    # Random data should not consistently fire all directional signatures.
    assert result["score"] <= 0.7


def test_empty_data_l1_zero(phishing_detection_v2_config):
    result = score_completion([], phishing_detection_v2_config)
    assert result["score"] == 0.0
