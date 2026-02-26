from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_bart_l1(human_like_bart_data, bart_config):
    result = score_completion(human_like_bart_data, bart_config)
    assert result["score"] == 1.0


def test_human_like_bart_l2(human_like_bart_data, bart_metrics):
    result = score_accuracy(human_like_bart_data, bart_metrics)
    assert result["score"] > 0.0


def test_risk_taking(human_like_bart_data, bart_signatures):
    result = score_behavioral(human_like_bart_data, bart_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "risk_taking")
    assert sig["direction_correct"]


def test_earnings_above_zero(human_like_bart_data, bart_signatures):
    result = score_behavioral(human_like_bart_data, bart_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "earnings_above_zero")
    assert sig["direction_correct"]


def test_random_bart_low_score(random_bart_data, bart_signatures):
    result = score_behavioral(random_bart_data, bart_signatures)
    assert result["score"] <= 0.7


def test_empty_bart_data(bart_config, bart_metrics, bart_signatures):
    l1 = score_completion([], bart_config)
    l2 = score_accuracy([], bart_metrics)
    l3 = score_behavioral([], bart_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
