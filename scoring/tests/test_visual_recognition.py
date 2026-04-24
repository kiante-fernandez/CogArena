"""Tests for visual_recognition task scoring (Brady-style old/new recognition memory)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "visual_recognition" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_visual_recognition_data, visual_recognition_config):
    result = score_completion(human_like_visual_recognition_data, visual_recognition_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_visual_recognition_data, visual_recognition_config):
    result = score_completion(random_visual_recognition_data, visual_recognition_config)
    assert result["score"] == 1.0


def test_l2_humanlike_high_accuracy(human_like_visual_recognition_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_visual_recognition_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    assert vals["overall_accuracy"] > 0.7
    assert vals["hit_rate"] > 0.7
    assert vals["false_alarm_rate"] < 0.3


def test_l3_humanlike_recovers_signatures(human_like_visual_recognition_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_visual_recognition_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    # Headline: hit > false-alarm.
    assert sig_by_name["above_chance_discrimination"]["direction_correct"]
    # Above-chance accuracy.
    assert sig_by_name["above_chance_accuracy"]["direction_correct"]
    # Low false alarm.
    assert sig_by_name["low_false_alarm_rate"]["direction_correct"]
    # Composite L3 should be high.
    assert result["score"] >= 0.7


def test_l3_random_low_score(random_visual_recognition_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_visual_recognition_data, sigs)
    # Random data (50/50 old/new responses regardless of truth) should score
    # well below the human-like fixture. Some signatures may fire by sampling chance.
    assert result["score"] <= 0.7


def test_empty_data_l1_zero(visual_recognition_config):
    result = score_completion([], visual_recognition_config)
    assert result["score"] == 0.0
