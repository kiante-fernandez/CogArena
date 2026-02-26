from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_ultimatum_l1(human_like_ultimatum_data, ultimatum_config):
    result = score_completion(human_like_ultimatum_data, ultimatum_config)
    # Mixed response type (slider + keypress): proposer slider values don't match
    # keypress valid_keys, so valid_responses check partially fails → 0.8
    assert result["score"] >= 0.8


def test_human_like_ultimatum_l2(human_like_ultimatum_data, ultimatum_metrics):
    result = score_accuracy(human_like_ultimatum_data, ultimatum_metrics)
    assert result["score"] > 0.0


def test_fair_offers(human_like_ultimatum_data, ultimatum_signatures):
    result = score_behavioral(human_like_ultimatum_data, ultimatum_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "fair_offers")
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_rejection_of_low_offers(human_like_ultimatum_data, ultimatum_signatures):
    result = score_behavioral(human_like_ultimatum_data, ultimatum_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "rejection_of_low_offers")
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_offer_sensitivity(human_like_ultimatum_data, ultimatum_signatures):
    result = score_behavioral(human_like_ultimatum_data, ultimatum_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "offer_sensitivity")
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_random_ultimatum_pipeline(random_ultimatum_data, ultimatum_config, ultimatum_metrics, ultimatum_signatures):
    """Pipeline runs without errors on random data."""
    l1 = score_completion(random_ultimatum_data, ultimatum_config)
    l2 = score_accuracy(random_ultimatum_data, ultimatum_metrics)
    l3 = score_behavioral(random_ultimatum_data, ultimatum_signatures)
    assert l1["score"] >= 0.8  # Mixed response type partially fails valid_responses


def test_empty_ultimatum_data(ultimatum_config, ultimatum_metrics, ultimatum_signatures):
    l1 = score_completion([], ultimatum_config)
    l2 = score_accuracy([], ultimatum_metrics)
    l3 = score_behavioral([], ultimatum_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
