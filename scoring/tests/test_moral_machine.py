"""Tests for moral_machine task scoring (autonomous-vehicle dilemmas)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "moral_machine" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_moral_machine_data, moral_machine_config):
    result = score_completion(human_like_moral_machine_data, moral_machine_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_moral_machine_data, moral_machine_config):
    result = score_completion(random_moral_machine_data, moral_machine_config)
    assert result["score"] == 1.0


def test_l2_humanlike_recovers_preferences(human_like_moral_machine_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_moral_machine_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Each canonical preference fires above chance.
    assert vals["prop_utilitarian"] > 0.5
    assert vals["prop_save_young"] > 0.5
    assert vals["prop_save_human"] > 0.5
    # Legality and intervention have small effects and few trials per dimension;
    # require only that the direction is at least at chance, not statistically above.
    assert vals["prop_save_legal"] >= 0.5
    assert vals["prop_intervention"] <= 0.55


def test_l3_humanlike_recovers_signatures(human_like_moral_machine_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_moral_machine_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    assert sig_by_name["utilitarian_preference"]["direction_correct"]
    assert sig_by_name["age_preference_save_young"]["direction_correct"]
    assert sig_by_name["species_preference_save_human"]["direction_correct"]
    # Composite L3 should be substantially above chance.
    assert result["score"] >= 0.6


def test_l3_random_low_score(random_moral_machine_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_moral_machine_data, sigs)
    # Random data should not consistently fire the directional signatures.
    assert result["score"] <= 0.6


def test_empty_data_l1_zero(moral_machine_config):
    result = score_completion([], moral_machine_config)
    assert result["score"] == 0.0
