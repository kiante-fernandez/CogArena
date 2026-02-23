from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_igt_l1(human_like_igt_data, igt_config):
    result = score_completion(human_like_igt_data, igt_config)
    assert result["score"] == 1.0


def test_human_like_igt_l2(human_like_igt_data, igt_metrics):
    result = score_accuracy(human_like_igt_data, igt_metrics)
    assert result["score"] > 0.0


def test_learning_effect(human_like_igt_data, igt_signatures):
    result = score_behavioral(human_like_igt_data, igt_signatures)
    learn_sig = next(s for s in result["signatures"] if s["name"] == "learning_effect")
    assert learn_sig["direction_correct"]


def test_above_chance_advantageous(human_like_igt_data, igt_signatures):
    result = score_behavioral(human_like_igt_data, igt_signatures)
    chance_sig = next(s for s in result["signatures"] if s["name"] == "above_chance_advantageous")
    assert chance_sig["direction_correct"]


def test_random_igt_low_learning(random_igt_data, igt_signatures):
    result = score_behavioral(random_igt_data, igt_signatures)
    learn_sig = next(s for s in result["signatures"] if s["name"] == "learning_effect")
    # Random data should NOT show learning
    assert not learn_sig["direction_correct"] or learn_sig["p_value"] > 0.05


def test_empty_igt_data(igt_config, igt_metrics, igt_signatures):
    l1 = score_completion([], igt_config)
    l2 = score_accuracy([], igt_metrics)
    l3 = score_behavioral([], igt_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
