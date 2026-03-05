from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_safe_exploration_l1(human_like_safe_exploration_data, safe_exploration_config):
    result = score_completion(human_like_safe_exploration_data, safe_exploration_config)
    assert result["score"] == 1.0


def test_human_like_safe_exploration_l2(human_like_safe_exploration_data, safe_exploration_metrics):
    result = score_accuracy(human_like_safe_exploration_data, safe_exploration_metrics)
    assert 0.1 < result["score"] < 0.9


def test_risk_sensitivity_detected(human_like_safe_exploration_data, safe_exploration_signatures):
    result = score_behavioral(human_like_safe_exploration_data, safe_exploration_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "risk_sensitivity")
    assert sig["direction_correct"]


def test_random_safe_exploration_low_behavioral(random_safe_exploration_data, safe_exploration_signatures):
    result = score_behavioral(random_safe_exploration_data, safe_exploration_signatures)
    assert result["score"] <= 0.8


def test_empty_safe_exploration_data(safe_exploration_config, safe_exploration_metrics, safe_exploration_signatures):
    l1 = score_completion([], safe_exploration_config)
    l2 = score_accuracy([], safe_exploration_metrics)
    l3 = score_behavioral([], safe_exploration_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
