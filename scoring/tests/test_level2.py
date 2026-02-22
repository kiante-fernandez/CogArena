from scoring.level2_accuracy import score_accuracy


def test_human_like_accuracy_near_midpoint(human_like_stroop_data, stroop_metrics):
    result = score_accuracy(human_like_stroop_data, stroop_metrics)
    assert 0.3 < result["score"] < 0.8


def test_perfect_accuracy_scores_high(perfect_stroop_data, stroop_metrics):
    result = score_accuracy(perfect_stroop_data, stroop_metrics)
    overall = next(m for m in result["metrics"] if m["name"] == "overall_accuracy")
    assert overall["raw_value"] == 1.0
    assert overall["normalized_score"] > 0.8


def test_random_accuracy_scores_low(random_stroop_data, stroop_metrics):
    result = score_accuracy(random_stroop_data, stroop_metrics)
    overall = next(m for m in result["metrics"] if m["name"] == "overall_accuracy")
    assert overall["raw_value"] < 0.6
    assert overall["normalized_score"] < 0.2


def test_filter_by_condition(human_like_stroop_data, stroop_metrics):
    result = score_accuracy(human_like_stroop_data, stroop_metrics)
    names = {m["name"]: m for m in result["metrics"]}
    assert "congruent_accuracy" in names
    assert "incongruent_accuracy" in names
    assert names["congruent_accuracy"]["raw_value"] > 0
    assert names["incongruent_accuracy"]["raw_value"] > 0


def test_empty_data_scores_zero(stroop_metrics):
    result = score_accuracy([], stroop_metrics)
    assert result["score"] == 0.0
