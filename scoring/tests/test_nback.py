from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_nback_l1(human_like_nback_data, nback_config):
    result = score_completion(human_like_nback_data, nback_config)
    assert result["score"] == 1.0


def test_human_like_nback_l2(human_like_nback_data, nback_metrics):
    result = score_accuracy(human_like_nback_data, nback_metrics)
    assert 0.1 < result["score"] < 0.9


def test_dprime_computed(human_like_nback_data, nback_metrics):
    result = score_accuracy(human_like_nback_data, nback_metrics)
    dprime_metric = next(m for m in result["metrics"] if m["name"] == "d_prime")
    assert dprime_metric["raw_value"] is not None
    assert dprime_metric["raw_value"] > 0


def test_dprime_random_near_zero(random_nback_data, nback_metrics):
    result = score_accuracy(random_nback_data, nback_metrics)
    dprime_metric = next(m for m in result["metrics"] if m["name"] == "d_prime")
    assert dprime_metric["raw_value"] is not None
    assert abs(dprime_metric["raw_value"]) < 1.0


def test_above_chance_discrimination(human_like_nback_data, nback_signatures):
    result = score_behavioral(human_like_nback_data, nback_signatures)
    disc_sig = next(s for s in result["signatures"] if s["name"] == "above_chance_discrimination")
    assert disc_sig["direction_correct"]
    assert disc_sig["score"] >= 0.5


def test_human_like_higher_than_random(human_like_nback_data, random_nback_data, nback_signatures):
    human_result = score_behavioral(human_like_nback_data, nback_signatures)
    random_result = score_behavioral(random_nback_data, nback_signatures)
    assert human_result["score"] >= random_result["score"]


def test_empty_nback_data(nback_config, nback_metrics, nback_signatures):
    l1 = score_completion([], nback_config)
    l2 = score_accuracy([], nback_metrics)
    l3 = score_behavioral([], nback_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
