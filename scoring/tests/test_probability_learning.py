from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_probability_learning_l1(human_like_probability_learning_data, probability_learning_config):
    result = score_completion(human_like_probability_learning_data, probability_learning_config)
    assert result["score"] == 1.0


def test_human_like_probability_learning_l2(human_like_probability_learning_data, probability_learning_metrics):
    result = score_accuracy(human_like_probability_learning_data, probability_learning_metrics)
    assert 0.1 < result["score"] < 0.9


def test_probability_matching_detected(human_like_probability_learning_data, probability_learning_signatures):
    result = score_behavioral(human_like_probability_learning_data, probability_learning_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "probability_matching")
    assert sig["direction_correct"]


def test_win_stay_detected(human_like_probability_learning_data, probability_learning_signatures):
    result = score_behavioral(human_like_probability_learning_data, probability_learning_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "win_stay_effect")
    assert sig["direction_correct"]


def test_random_probability_learning_low_behavioral(random_probability_learning_data, probability_learning_signatures):
    result = score_behavioral(random_probability_learning_data, probability_learning_signatures)
    assert result["score"] <= 0.7


def test_empty_probability_learning_data(probability_learning_config, probability_learning_metrics, probability_learning_signatures):
    l1 = score_completion([], probability_learning_config)
    l2 = score_accuracy([], probability_learning_metrics)
    l3 = score_behavioral([], probability_learning_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
