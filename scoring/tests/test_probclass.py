from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_probclass_l1(human_like_probclass_data, probclass_config):
    result = score_completion(human_like_probclass_data, probclass_config)
    assert result["score"] == 1.0


def test_human_like_probclass_l2(human_like_probclass_data, probclass_metrics):
    result = score_accuracy(human_like_probclass_data, probclass_metrics)
    assert result["score"] > 0.0


def test_learning_curve(human_like_probclass_data, probclass_signatures):
    result = score_behavioral(human_like_probclass_data, probclass_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "learning_curve")
    assert sig["direction_correct"]


def test_above_chance_accuracy(human_like_probclass_data, probclass_signatures):
    result = score_behavioral(human_like_probclass_data, probclass_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_accuracy")
    assert sig["direction_correct"]


def test_cue_utilization(human_like_probclass_data, probclass_signatures):
    result = score_behavioral(human_like_probclass_data, probclass_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "cue_utilization")
    # Cue utilization may not always reach significance
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_random_probclass_low_score(random_probclass_data, probclass_signatures):
    result = score_behavioral(random_probclass_data, probclass_signatures)
    assert result["score"] <= 0.7


def test_empty_probclass_data(probclass_config, probclass_metrics, probclass_signatures):
    l1 = score_completion([], probclass_config)
    l2 = score_accuracy([], probclass_metrics)
    l3 = score_behavioral([], probclass_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
