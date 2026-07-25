from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_two_step_l1(human_like_two_step_data, two_step_config):
    result = score_completion(human_like_two_step_data, two_step_config)
    assert result["score"] == 1.0


def test_human_like_two_step_l2(human_like_two_step_data, two_step_metrics):
    result = score_accuracy(human_like_two_step_data, two_step_metrics)
    assert result["score"] > 0.0


def test_win_stay(human_like_two_step_data, two_step_signatures):
    result = score_behavioral(human_like_two_step_data, two_step_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "win_stay")
    assert sig["direction_correct"]


def test_above_chance_reward(human_like_two_step_data, two_step_signatures):
    result = score_behavioral(human_like_two_step_data, two_step_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_reward")
    assert sig["direction_correct"]


def test_model_based_index(human_like_two_step_data, two_step_signatures):
    result = score_behavioral(human_like_two_step_data, two_step_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "model_based_index")
    # Untestable signatures now score None and are excluded from the weighted
    # mean, so a smoke test must allow either outcome.
    assert sig["score"] is None or 0.0 <= sig["score"] <= 1.0


def test_random_two_step_low_score(random_two_step_data, two_step_signatures):
    result = score_behavioral(random_two_step_data, two_step_signatures)
    assert result["score"] <= 0.7


def test_empty_two_step_data(two_step_config, two_step_metrics, two_step_signatures):
    l1 = score_completion([], two_step_config)
    l2 = score_accuracy([], two_step_metrics)
    l3 = score_behavioral([], two_step_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
