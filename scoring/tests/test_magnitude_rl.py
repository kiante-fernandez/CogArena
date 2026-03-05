from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_magnitude_rl_l1(human_like_magnitude_rl_data, magnitude_rl_config):
    result = score_completion(human_like_magnitude_rl_data, magnitude_rl_config)
    assert result["score"] == 1.0


def test_human_like_magnitude_rl_l2(human_like_magnitude_rl_data, magnitude_rl_metrics):
    result = score_accuracy(human_like_magnitude_rl_data, magnitude_rl_metrics)
    assert 0.1 < result["score"] < 0.9


def test_magnitude_effect_detected(human_like_magnitude_rl_data, magnitude_rl_signatures):
    result = score_behavioral(human_like_magnitude_rl_data, magnitude_rl_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "magnitude_effect")
    assert sig["direction_correct"]


def test_reference_point_adaptation_detected(human_like_magnitude_rl_data, magnitude_rl_signatures):
    result = score_behavioral(human_like_magnitude_rl_data, magnitude_rl_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "reference_point_adaptation")
    assert sig["direction_correct"]


def test_random_magnitude_rl_low_behavioral(random_magnitude_rl_data, magnitude_rl_signatures):
    result = score_behavioral(random_magnitude_rl_data, magnitude_rl_signatures)
    assert result["score"] <= 0.7


def test_empty_magnitude_rl_data(magnitude_rl_config, magnitude_rl_metrics, magnitude_rl_signatures):
    l1 = score_completion([], magnitude_rl_config)
    l2 = score_accuracy([], magnitude_rl_metrics)
    l3 = score_behavioral([], magnitude_rl_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
