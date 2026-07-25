from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_contingency_l1(human_like_contingency_data, contingency_config):
    result = score_completion(human_like_contingency_data, contingency_config)
    assert result["score"] == 1.0


def test_human_like_contingency_l2(human_like_contingency_data, contingency_metrics):
    result = score_accuracy(human_like_contingency_data, contingency_metrics)
    assert result["score"] > 0.0


def test_delta_p_sensitivity(human_like_contingency_data, contingency_signatures):
    result = score_behavioral(human_like_contingency_data, contingency_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "delta_p_sensitivity")
    # Only 4 rating trials, but correlation_test requires n>=10. The spec is
    # untestable by construction, so it must be EXCLUDED from L3 rather than
    # scored 0.0 -- zeroing it would assert the agent lacks a signature we
    # never measured.
    assert sig["testable"] is False
    assert sig["untestable_reason"] == "insufficient_data"
    assert sig["score"] is None


def test_cause_discrimination(human_like_contingency_data, contingency_signatures):
    result = score_behavioral(human_like_contingency_data, contingency_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "cause_discrimination")
    # 1 trial per block, below paired_proportion_test's minimum: untestable,
    # therefore excluded rather than zeroed.
    assert sig["testable"] is False
    assert sig["score"] is None


def test_random_contingency_low_score(random_contingency_data, contingency_signatures):
    result = score_behavioral(random_contingency_data, contingency_signatures)
    assert result["score"] <= 0.7


def test_empty_contingency_data(contingency_config, contingency_metrics, contingency_signatures):
    l1 = score_completion([], contingency_config)
    l2 = score_accuracy([], contingency_metrics)
    l3 = score_behavioral([], contingency_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
