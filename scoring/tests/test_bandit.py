from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_bandit_l1(human_like_bandit_data, bandit_config):
    result = score_completion(human_like_bandit_data, bandit_config)
    assert result["score"] == 1.0


def test_human_like_bandit_l2(human_like_bandit_data, bandit_metrics):
    result = score_accuracy(human_like_bandit_data, bandit_metrics)
    assert 0.2 < result["score"] < 0.9


def test_horizon_effect_detected(human_like_bandit_data, bandit_signatures):
    result = score_behavioral(human_like_bandit_data, bandit_signatures)
    horizon_sig = next(s for s in result["signatures"] if s["name"] == "horizon_effect_exploration")
    assert horizon_sig["direction_correct"]


def test_win_stay_detected(human_like_bandit_data, bandit_signatures):
    result = score_behavioral(human_like_bandit_data, bandit_signatures)
    ws_sig = next(s for s in result["signatures"] if s["name"] == "win_stay")
    assert ws_sig["direction_correct"]
    assert ws_sig["score"] >= 0.5


def test_random_bandit_low_score(random_bandit_data, bandit_signatures):
    result = score_behavioral(random_bandit_data, bandit_signatures)
    assert result["score"] <= 0.6


def test_empty_bandit_data(bandit_config, bandit_metrics, bandit_signatures):
    l1 = score_completion([], bandit_config)
    l2 = score_accuracy([], bandit_metrics)
    l3 = score_behavioral([], bandit_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
