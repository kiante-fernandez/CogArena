"""Tests for marbles_risk task scoring (Ciranka risky-choice from description)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "marbles_risk" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_marbles_risk_data, marbles_risk_config):
    result = score_completion(human_like_marbles_risk_data, marbles_risk_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_marbles_risk_data, marbles_risk_config):
    result = score_completion(random_marbles_risk_data, marbles_risk_config)
    assert result["score"] == 1.0


def test_l2_humanlike_picks_higher_ev(human_like_marbles_risk_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_marbles_risk_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Humanlike fixture should pick the higher-EV option more than chance.
    # The absolute prop_chose_risky is hard to predict because most v1 trials
    # have positive ev_diff (EV-rational picks risky on most of them), so we
    # don't assert direction on prop_chose_risky.
    assert vals["prop_chose_higher_ev"] > 0.6


def test_l3_humanlike_recovers_signatures(human_like_marbles_risk_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_marbles_risk_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    # Headline: agents track expected value.
    assert sig_by_name["ev_sensitivity"]["direction_correct"]
    # Above-chance EV-optimal picking.
    assert sig_by_name["above_chance_ev_optimal"]["direction_correct"]
    # Magnitude effect: higher gamble values pull toward risky (correlation positive).
    assert sig_by_name["magnitude_effect_high_payoff"]["direction_correct"]
    # Composite L3 should be substantially above chance.
    assert result["score"] >= 0.6


def test_l3_random_low_score(random_marbles_risk_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_marbles_risk_data, sigs)
    # Random data should not consistently fire the directional signatures.
    assert result["score"] <= 0.55


def test_empty_data_l1_zero(marbles_risk_config):
    result = score_completion([], marbles_risk_config)
    assert result["score"] == 0.0
