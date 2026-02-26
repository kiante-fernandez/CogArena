from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_category_learning_l1(human_like_category_learning_data, category_learning_config):
    result = score_completion(human_like_category_learning_data, category_learning_config)
    assert result["score"] == 1.0


def test_human_like_category_learning_l2(human_like_category_learning_data, category_learning_metrics):
    result = score_accuracy(human_like_category_learning_data, category_learning_metrics)
    assert result["score"] > 0.0


def test_learning_curve(human_like_category_learning_data, category_learning_signatures):
    result = score_behavioral(human_like_category_learning_data, category_learning_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "learning_curve")
    assert sig["direction_correct"]


def test_above_chance_learning(human_like_category_learning_data, category_learning_signatures):
    result = score_behavioral(human_like_category_learning_data, category_learning_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_learning")
    assert sig["direction_correct"]


def test_transfer_generalization(human_like_category_learning_data, category_learning_signatures):
    result = score_behavioral(human_like_category_learning_data, category_learning_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "transfer_generalization")
    assert sig["direction_correct"]


def test_random_category_learning_low_score(random_category_learning_data, category_learning_signatures):
    result = score_behavioral(random_category_learning_data, category_learning_signatures)
    assert result["score"] <= 0.7


def test_empty_category_learning_data(category_learning_config, category_learning_metrics, category_learning_signatures):
    l1 = score_completion([], category_learning_config)
    l2 = score_accuracy([], category_learning_metrics)
    l3 = score_behavioral([], category_learning_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
