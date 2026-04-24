"""Tests for random_dot_motion_v2 task scoring (motion-direction RDM)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "random_dot_motion_v2" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_random_dot_motion_v2_data, random_dot_motion_v2_config):
    result = score_completion(human_like_random_dot_motion_v2_data, random_dot_motion_v2_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_random_dot_motion_v2_data, random_dot_motion_v2_config):
    # Random-but-valid responses should still pass L1 completion.
    result = score_completion(random_random_dot_motion_v2_data, random_dot_motion_v2_config)
    assert result["score"] == 1.0


def test_l2_accuracy_human_recovers_psychometric(human_like_random_dot_motion_v2_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_random_dot_motion_v2_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # The headline psychometric: high coherence accuracy beats low coherence accuracy.
    assert vals["accuracy_high_coherence"] > vals["accuracy_low_coherence"]
    assert vals["overall_accuracy"] > 0.6


def test_l3_humanlike_recovers_signatures(human_like_random_dot_motion_v2_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_random_dot_motion_v2_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    assert sig_by_name["coherence_accuracy_psychometric"]["direction_correct"]
    assert sig_by_name["coherence_accuracy_psychometric"]["score"] >= 0.5
    assert sig_by_name["coherence_rt_chronometric"]["direction_correct"]
    # Overall result should be substantially above chance floor.
    assert result["score"] >= 0.7


def test_l3_random_low_score(random_random_dot_motion_v2_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_random_dot_motion_v2_data, sigs)
    # Random data should not fire the directional signatures.
    assert result["score"] <= 0.5


def test_empty_data_l1_zero(random_dot_motion_v2_config):
    result = score_completion([], random_dot_motion_v2_config)
    assert result["score"] == 0.0
