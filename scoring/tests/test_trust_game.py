from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_trust_l1(human_like_trust_data, trust_config):
    result = score_completion(human_like_trust_data, trust_config)
    assert result["score"] == 1.0
    names = {c["name"]: c["passed"] for c in result["checks"]}
    assert names["valid_responses"]


def test_human_like_trust_l2(human_like_trust_data, trust_metrics):
    result = score_accuracy(human_like_trust_data, trust_metrics)
    assert 0.1 < result["score"] < 0.9


def test_above_zero_trust_detected(human_like_trust_data, trust_signatures):
    result = score_behavioral(human_like_trust_data, trust_signatures)
    trust_sig = next(s for s in result["signatures"] if s["name"] == "above_zero_trust")
    assert trust_sig["direction_correct"]
    assert trust_sig["score"] >= 0.5


def test_trustee_adaptation_detected(human_like_trust_data, trust_signatures):
    result = score_behavioral(human_like_trust_data, trust_signatures)
    adapt_sig = next(s for s in result["signatures"] if s["name"] == "trustee_type_adaptation")
    assert adapt_sig["direction_correct"]


def test_empty_trust_data(trust_config, trust_metrics, trust_signatures):
    l1 = score_completion([], trust_config)
    l2 = score_accuracy([], trust_metrics)
    l3 = score_behavioral([], trust_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
