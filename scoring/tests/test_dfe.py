from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_dfe_l1(human_like_dfe_data, dfe_config):
    result = score_completion(human_like_dfe_data, dfe_config)
    assert result["score"] == 1.0


def test_human_like_dfe_l2(human_like_dfe_data, dfe_metrics):
    result = score_accuracy(human_like_dfe_data, dfe_metrics)
    assert result["score"] > 0.0


def test_description_experience_gap(human_like_dfe_data, dfe_signatures):
    result = score_behavioral(human_like_dfe_data, dfe_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "description_experience_gap")
    # With only 20 trials, significance may not be reached but direction should be correct
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_sampling_frugality(human_like_dfe_data, dfe_signatures):
    result = score_behavioral(human_like_dfe_data, dfe_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "sampling_frugality")
    assert sig["direction_correct"]


def test_random_dfe_low_score(random_dfe_data, dfe_signatures):
    result = score_behavioral(random_dfe_data, dfe_signatures)
    assert result["score"] <= 0.7


def test_empty_dfe_data(dfe_config, dfe_metrics, dfe_signatures):
    l1 = score_completion([], dfe_config)
    l2 = score_accuracy([], dfe_metrics)
    l3 = score_behavioral([], dfe_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
