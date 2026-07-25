from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_public_goods_l1(human_like_public_goods_data, public_goods_config):
    result = score_completion(human_like_public_goods_data, public_goods_config)
    assert result["score"] == 1.0


def test_human_like_public_goods_l2(human_like_public_goods_data, public_goods_metrics):
    result = score_accuracy(human_like_public_goods_data, public_goods_metrics)
    assert result["score"] > 0.0


def test_conditional_cooperation(human_like_public_goods_data, public_goods_signatures):
    result = score_behavioral(human_like_public_goods_data, public_goods_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "conditional_cooperation")
    assert sig["direction_correct"]


def test_declining_contributions(human_like_public_goods_data, public_goods_signatures):
    result = score_behavioral(human_like_public_goods_data, public_goods_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "declining_contributions")
    # Untestable signatures now score None and are excluded from the weighted
    # mean, so a smoke test must allow either outcome.
    assert sig["score"] is None or 0.0 <= sig["score"] <= 1.0


def test_group_sensitivity(human_like_public_goods_data, public_goods_signatures):
    result = score_behavioral(human_like_public_goods_data, public_goods_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "group_sensitivity")
    # Untestable signatures now score None and are excluded from the weighted
    # mean, so a smoke test must allow either outcome.
    assert sig["score"] is None or 0.0 <= sig["score"] <= 1.0


def test_random_public_goods_pipeline(random_public_goods_data, public_goods_config, public_goods_metrics, public_goods_signatures):
    """Pipeline runs without errors on random data."""
    l1 = score_completion(random_public_goods_data, public_goods_config)
    l2 = score_accuracy(random_public_goods_data, public_goods_metrics)
    l3 = score_behavioral(random_public_goods_data, public_goods_signatures)
    assert l1["score"] == 1.0  # random data still has correct trial count


def test_empty_public_goods_data(public_goods_config, public_goods_metrics, public_goods_signatures):
    l1 = score_completion([], public_goods_config)
    l2 = score_accuracy([], public_goods_metrics)
    l3 = score_behavioral([], public_goods_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
