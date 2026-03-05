from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_moral_judgment_l1(human_like_moral_judgment_data, moral_judgment_config):
    result = score_completion(human_like_moral_judgment_data, moral_judgment_config)
    assert result["score"] == 1.0


def test_human_like_moral_judgment_l2(human_like_moral_judgment_data, moral_judgment_metrics):
    result = score_accuracy(human_like_moral_judgment_data, moral_judgment_metrics)
    assert 0.1 < result["score"] < 0.9


def test_utilitarian_preference_detected(human_like_moral_judgment_data, moral_judgment_signatures):
    result = score_behavioral(human_like_moral_judgment_data, moral_judgment_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "utilitarian_preference")
    assert sig["direction_correct"]


def test_random_moral_judgment_low_behavioral(random_moral_judgment_data, moral_judgment_signatures):
    result = score_behavioral(random_moral_judgment_data, moral_judgment_signatures)
    assert result["score"] <= 0.7


def test_empty_moral_judgment_data(moral_judgment_config, moral_judgment_metrics, moral_judgment_signatures):
    l1 = score_completion([], moral_judgment_config)
    l2 = score_accuracy([], moral_judgment_metrics)
    l3 = score_behavioral([], moral_judgment_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
