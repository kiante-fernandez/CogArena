from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_reversal_l1(human_like_reversal_data, reversal_config):
    result = score_completion(human_like_reversal_data, reversal_config)
    assert result["score"] == 1.0


def test_human_like_reversal_l2(human_like_reversal_data, reversal_metrics):
    result = score_accuracy(human_like_reversal_data, reversal_metrics)
    assert result["score"] > 0.0


def test_above_chance_pre_reversal(human_like_reversal_data, reversal_signatures):
    result = score_behavioral(human_like_reversal_data, reversal_signatures)
    pre_sig = next(s for s in result["signatures"] if s["name"] == "above_chance_pre_reversal")
    assert pre_sig["direction_correct"]


def test_perseveration_effect(human_like_reversal_data, reversal_signatures):
    result = score_behavioral(human_like_reversal_data, reversal_signatures)
    pers_sig = next(s for s in result["signatures"] if s["name"] == "perseveration_effect")
    assert pers_sig["direction_correct"]


def test_random_reversal_low_score(random_reversal_data, reversal_signatures):
    result = score_behavioral(random_reversal_data, reversal_signatures)
    assert result["score"] <= 0.7


def test_empty_reversal_data(reversal_config, reversal_metrics, reversal_signatures):
    l1 = score_completion([], reversal_config)
    l2 = score_accuracy([], reversal_metrics)
    l3 = score_behavioral([], reversal_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
