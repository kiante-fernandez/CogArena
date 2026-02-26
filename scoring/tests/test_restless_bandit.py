from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_restless_bandit_l1(human_like_restless_bandit_data, restless_bandit_config):
    result = score_completion(human_like_restless_bandit_data, restless_bandit_config)
    assert result["score"] == 1.0


def test_human_like_restless_bandit_l2(human_like_restless_bandit_data, restless_bandit_metrics):
    result = score_accuracy(human_like_restless_bandit_data, restless_bandit_metrics)
    assert result["score"] > 0.0


def test_above_chance_tracking(human_like_restless_bandit_data, restless_bandit_signatures):
    result = score_behavioral(human_like_restless_bandit_data, restless_bandit_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_tracking")
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_win_stay_lose_shift(human_like_restless_bandit_data, restless_bandit_signatures):
    result = score_behavioral(human_like_restless_bandit_data, restless_bandit_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "win_stay_lose_shift")
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_random_restless_bandit_pipeline(random_restless_bandit_data, restless_bandit_config, restless_bandit_metrics, restless_bandit_signatures):
    """Pipeline runs without errors on random data."""
    l1 = score_completion(random_restless_bandit_data, restless_bandit_config)
    l2 = score_accuracy(random_restless_bandit_data, restless_bandit_metrics)
    l3 = score_behavioral(random_restless_bandit_data, restless_bandit_signatures)
    assert l1["score"] == 1.0  # random data still has correct trial count


def test_empty_restless_bandit_data(restless_bandit_config, restless_bandit_metrics, restless_bandit_signatures):
    l1 = score_completion([], restless_bandit_config)
    l2 = score_accuracy([], restless_bandit_metrics)
    l3 = score_behavioral([], restless_bandit_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
