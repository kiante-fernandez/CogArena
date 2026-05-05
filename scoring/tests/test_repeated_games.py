"""Tests for repeated_games task scoring (Akata 2023 PD + BoS)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "repeated_games" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_repeated_games_data, repeated_games_config):
    result = score_completion(human_like_repeated_games_data, repeated_games_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_repeated_games_data, repeated_games_config):
    result = score_completion(random_repeated_games_data, repeated_games_config)
    assert result["score"] == 1.0


def test_l2_humanlike_above_chance(human_like_repeated_games_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_repeated_games_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Cooperation in PD is non-zero.
    assert vals["coop_rate_pd"] > 0.2
    # Coordination in BoS beats chance.
    assert vals["coordination_rate_bos"] > 0.5
    # PD payoff above mutual-defect floor (5).
    assert vals["mean_payoff_pd"] > 5.0


def test_l3_humanlike_recovers_signatures(human_like_repeated_games_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_repeated_games_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    # Reciprocity in PD: previous opp cooperate predicts current cooperate.
    assert sig_by_name["tit_for_tat_reciprocity_pd"]["direction_correct"]
    # Above-chance coordination in BoS.
    assert sig_by_name["above_chance_coordination_bos"]["direction_correct"]
    # Conditional cooperation: when opp cooperated last round, player cooperates >0.5.
    # (Replaced the old non-discriminative non_zero_cooperation_pd >0.10 signature
    #  in the v1.1 audit.)
    assert sig_by_name["cooperation_when_opp_cooperated"]["direction_correct"]
    # Composite L3 should be substantially above the random floor.
    assert result["score"] >= 0.6


def test_l3_random_low_score(random_repeated_games_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_repeated_games_data, sigs)
    # Random play should not reliably fire any signature. The audit raised
    # cooperation_when_opp_cooperated's chance level to 0.5 (was 0.10), which
    # is the major reason the random floor here is now expected to be low.
    assert result["score"] <= 0.5


def test_empty_data_l1_zero(repeated_games_config):
    result = score_completion([], repeated_games_config)
    assert result["score"] == 0.0
