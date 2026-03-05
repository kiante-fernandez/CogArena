from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_observe_or_bet_l1(human_like_observe_or_bet_data, observe_or_bet_config):
    result = score_completion(human_like_observe_or_bet_data, observe_or_bet_config)
    assert result["score"] == 1.0


def test_human_like_observe_or_bet_l2(human_like_observe_or_bet_data, observe_or_bet_metrics):
    result = score_accuracy(human_like_observe_or_bet_data, observe_or_bet_metrics)
    assert 0.1 < result["score"] < 0.9


def test_bet_above_chance_detected(human_like_observe_or_bet_data, observe_or_bet_signatures):
    result = score_behavioral(human_like_observe_or_bet_data, observe_or_bet_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "bet_above_chance")
    assert sig["direction_correct"]


def test_random_observe_or_bet_low_behavioral(random_observe_or_bet_data, observe_or_bet_signatures):
    result = score_behavioral(random_observe_or_bet_data, observe_or_bet_signatures)
    assert result["score"] <= 0.8


def test_empty_observe_or_bet_data(observe_or_bet_config, observe_or_bet_metrics, observe_or_bet_signatures):
    l1 = score_completion([], observe_or_bet_config)
    l2 = score_accuracy([], observe_or_bet_metrics)
    l3 = score_behavioral([], observe_or_bet_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
