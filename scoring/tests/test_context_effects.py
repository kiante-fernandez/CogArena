from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_context_effects_l1(human_like_context_effects_data, context_effects_config):
    result = score_completion(human_like_context_effects_data, context_effects_config)
    assert result["score"] == 1.0


def test_human_like_context_effects_l2(human_like_context_effects_data, context_effects_metrics):
    result = score_accuracy(human_like_context_effects_data, context_effects_metrics)
    assert 0.1 < result["score"] < 0.9


def test_attraction_effect_detected(human_like_context_effects_data, context_effects_signatures):
    result = score_behavioral(human_like_context_effects_data, context_effects_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "attraction_effect")
    assert sig["direction_correct"]


def test_random_context_effects_low_behavioral(random_context_effects_data, context_effects_signatures):
    result = score_behavioral(random_context_effects_data, context_effects_signatures)
    assert result["score"] <= 0.7


def test_empty_context_effects_data(context_effects_config, context_effects_metrics, context_effects_signatures):
    l1 = score_completion([], context_effects_config)
    l2 = score_accuracy([], context_effects_metrics)
    l3 = score_behavioral([], context_effects_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
