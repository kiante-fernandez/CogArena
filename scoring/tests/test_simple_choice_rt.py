from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_simple_choice_rt_l1(human_like_simple_choice_rt_data, simple_choice_rt_config):
    result = score_completion(human_like_simple_choice_rt_data, simple_choice_rt_config)
    assert result["score"] == 1.0


def test_human_like_simple_choice_rt_l2(human_like_simple_choice_rt_data, simple_choice_rt_metrics):
    result = score_accuracy(human_like_simple_choice_rt_data, simple_choice_rt_metrics)
    assert result["score"] > 0.0


def test_hicks_law(human_like_simple_choice_rt_data, simple_choice_rt_signatures):
    result = score_behavioral(human_like_simple_choice_rt_data, simple_choice_rt_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "hicks_law")
    assert sig["direction_correct"]


def test_choice2_slower_than_simple(human_like_simple_choice_rt_data, simple_choice_rt_signatures):
    result = score_behavioral(human_like_simple_choice_rt_data, simple_choice_rt_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "choice2_slower_than_simple")
    assert sig["direction_correct"]


def test_above_chance_accuracy(human_like_simple_choice_rt_data, simple_choice_rt_signatures):
    result = score_behavioral(human_like_simple_choice_rt_data, simple_choice_rt_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_accuracy")
    assert sig["direction_correct"]


def test_random_simple_choice_rt_low_score(random_simple_choice_rt_data, simple_choice_rt_signatures):
    result = score_behavioral(random_simple_choice_rt_data, simple_choice_rt_signatures)
    assert result["score"] <= 0.7


def test_empty_simple_choice_rt_data(simple_choice_rt_config, simple_choice_rt_metrics, simple_choice_rt_signatures):
    l1 = score_completion([], simple_choice_rt_config)
    l2 = score_accuracy([], simple_choice_rt_metrics)
    l3 = score_behavioral([], simple_choice_rt_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
