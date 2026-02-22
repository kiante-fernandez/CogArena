from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_risky_l1(human_like_risky_choice_data, risky_choice_config):
    result = score_completion(human_like_risky_choice_data, risky_choice_config)
    assert result["score"] == 1.0


def test_human_like_risky_l2(human_like_risky_choice_data, risky_choice_metrics):
    result = score_accuracy(human_like_risky_choice_data, risky_choice_metrics)
    assert 0.1 < result["score"] < 0.9


def test_risk_aversion_detected(human_like_risky_choice_data, risky_choice_signatures):
    result = score_behavioral(human_like_risky_choice_data, risky_choice_signatures)
    ra_sig = next(s for s in result["signatures"] if s["name"] == "risk_aversion_gains")
    assert ra_sig["direction_correct"]
    assert ra_sig["score"] >= 0.5


def test_loss_aversion_detected(human_like_risky_choice_data, risky_choice_signatures):
    result = score_behavioral(human_like_risky_choice_data, risky_choice_signatures)
    la_sig = next(s for s in result["signatures"] if s["name"] == "loss_aversion_framing")
    assert la_sig["direction_correct"]


def test_random_risky_low_behavioral(random_risky_choice_data, risky_choice_signatures):
    result = score_behavioral(random_risky_choice_data, risky_choice_signatures)
    assert result["score"] <= 0.6


def test_empty_risky_data(risky_choice_config, risky_choice_metrics, risky_choice_signatures):
    l1 = score_completion([], risky_choice_config)
    l2 = score_accuracy([], risky_choice_metrics)
    l3 = score_behavioral([], risky_choice_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
