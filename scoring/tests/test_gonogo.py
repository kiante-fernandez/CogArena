from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_gonogo_l1(human_like_gonogo_data, gonogo_config):
    result = score_completion(human_like_gonogo_data, gonogo_config)
    assert result["score"] == 1.0


def test_human_like_gonogo_l2(human_like_gonogo_data, gonogo_metrics):
    result = score_accuracy(human_like_gonogo_data, gonogo_metrics)
    assert result["score"] > 0.0


def test_discrimination_detected(human_like_gonogo_data, gonogo_signatures):
    result = score_behavioral(human_like_gonogo_data, gonogo_signatures)
    disc_sig = next(s for s in result["signatures"] if s["name"] == "above_chance_discrimination")
    assert disc_sig["direction_correct"]


def test_commission_over_omission(human_like_gonogo_data, gonogo_signatures):
    result = score_behavioral(human_like_gonogo_data, gonogo_signatures)
    comm_sig = next(s for s in result["signatures"] if s["name"] == "commission_over_omission")
    assert comm_sig["direction_correct"]


def test_random_gonogo_low_score(random_gonogo_data, gonogo_signatures):
    result = score_behavioral(random_gonogo_data, gonogo_signatures)
    assert result["score"] <= 0.7


def test_empty_gonogo_data(gonogo_config, gonogo_metrics, gonogo_signatures):
    l1 = score_completion([], gonogo_config)
    l2 = score_accuracy([], gonogo_metrics)
    l3 = score_behavioral([], gonogo_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
