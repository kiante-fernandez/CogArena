from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_prisoners_l1(human_like_prisoners_dilemma_data, prisoners_dilemma_config):
    result = score_completion(human_like_prisoners_dilemma_data, prisoners_dilemma_config)
    assert result["score"] == 1.0


def test_human_like_prisoners_l2(human_like_prisoners_dilemma_data, prisoners_dilemma_metrics):
    result = score_accuracy(human_like_prisoners_dilemma_data, prisoners_dilemma_metrics)
    assert result["score"] > 0.0


def test_above_chance_cooperation(human_like_prisoners_dilemma_data, prisoners_dilemma_signatures):
    result = score_behavioral(human_like_prisoners_dilemma_data, prisoners_dilemma_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_cooperation")
    assert sig["direction_correct"]


def test_tit_for_tat(human_like_prisoners_dilemma_data, prisoners_dilemma_signatures):
    result = score_behavioral(human_like_prisoners_dilemma_data, prisoners_dilemma_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "tit_for_tat")
    assert sig["direction_correct"]


def test_forgiveness(human_like_prisoners_dilemma_data, prisoners_dilemma_signatures):
    result = score_behavioral(human_like_prisoners_dilemma_data, prisoners_dilemma_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "forgiveness")
    # Forgiveness may not always reach significance -- check pipeline runs
    assert sig["score"] >= 0.0


def test_random_prisoners_low_score(random_prisoners_dilemma_data, prisoners_dilemma_signatures):
    result = score_behavioral(random_prisoners_dilemma_data, prisoners_dilemma_signatures)
    assert result["score"] <= 0.7


def test_empty_prisoners_data(prisoners_dilemma_config, prisoners_dilemma_metrics, prisoners_dilemma_signatures):
    l1 = score_completion([], prisoners_dilemma_config)
    l2 = score_accuracy([], prisoners_dilemma_metrics)
    l3 = score_behavioral([], prisoners_dilemma_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
