from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_navon_l1(human_like_navon_data, navon_config):
    result = score_completion(human_like_navon_data, navon_config)
    assert result["score"] == 1.0


def test_human_like_navon_l2(human_like_navon_data, navon_metrics):
    result = score_accuracy(human_like_navon_data, navon_metrics)
    assert result["score"] > 0.0


def test_global_precedence_rt(human_like_navon_data, navon_signatures):
    result = score_behavioral(human_like_navon_data, navon_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "global_precedence_rt")
    assert sig["direction_correct"]


def test_congruency_effect(human_like_navon_data, navon_signatures):
    result = score_behavioral(human_like_navon_data, navon_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "congruency_effect")
    assert sig["direction_correct"]


def test_random_navon_low_score(random_navon_data, navon_signatures):
    result = score_behavioral(random_navon_data, navon_signatures)
    assert result["score"] <= 0.7


def test_empty_navon_data(navon_config, navon_metrics, navon_signatures):
    l1 = score_completion([], navon_config)
    l2 = score_accuracy([], navon_metrics)
    l3 = score_behavioral([], navon_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
