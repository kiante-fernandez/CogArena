"""Level 3: alignment with canonical task-specific behavioural signatures.

Each signature names a statistical test (run via scoring/analysis_templates/) and
the direction the human literature predicts. A signature scores 1.0 when the
effect is in the predicted direction and significant, 0.5 when the direction is
right but the test does not clear threshold_p, and 0.0 otherwise.

UNTESTABLE SIGNATURES ARE EXCLUDED, NOT ZEROED. A test that could not run — too
few trials after filtering, an undefined statistic, a spec error — tells us
nothing about the agent's behaviour. Scoring it 0.0 asserts that the agent
failed to show a human signature, which is a claim the data does not support,
and it is behaviour-dependent in the worst way: an agent that completes less of
a task gets more automatic zeros, which is indistinguishable from a real
capability gap. Untestable signatures are therefore dropped from the weighted
mean and reported separately via ``n_untestable`` / ``untestable_weight`` so a
caller can decide whether the remaining coverage supports a claim at all.

This changes what L3 means relative to CogArena v1.1.1, where untestable
signatures were scored 0.0 and depressed every agent's L3 — including the random
chance floor, so floor comparisons shift too. Any reported number computed
before this change is not comparable to one computed after it.
"""
import math

from scoring.analysis_templates.paired_ttest import run_paired_ttest, run_paired_proportion_test
from scoring.analysis_templates.sequential_regression import run_sequential_regression
from scoring.analysis_templates.interaction_test import run_interaction_test
from scoring.analysis_templates.proportion_test import run_proportion_test
from scoring.analysis_templates.correlation_test import run_correlation_test
from scoring.analysis_templates.conditional_proportion_contrast import (
    run_conditional_proportion_contrast,
)

TEST_REGISTRY = {
    "paired_ttest_greater": run_paired_ttest,
    "paired_proportion_test": run_paired_proportion_test,
    "sequential_regression": run_sequential_regression,
    "interaction_test": run_interaction_test,
    "proportion_test": run_proportion_test,
    "correlation_test": run_correlation_test,
    "conditional_proportion_contrast": run_conditional_proportion_contrast,
}


def _is_nan(x) -> bool:
    return isinstance(x, float) and math.isnan(x)


def _untestable(sig: dict, reason: str, **extra) -> dict:
    return {
        "name": sig["name"],
        "score": None,
        "testable": False,
        "untestable_reason": reason,
        "weight": sig.get("weight", 1.0),
        **extra,
    }


def score_behavioral(trial_data: list[dict], signatures_spec: dict) -> dict:
    signature_results = []

    for sig in signatures_spec["signatures"]:
        test_func = TEST_REGISTRY.get(sig["test"])
        if test_func is None:
            # A spec error, not agent behaviour.
            signature_results.append(
                _untestable(sig, "unknown_test_type",
                            error=f"Unknown test type: {sig['test']}"))
            continue

        try:
            result = test_func(trial_data, sig)
        except Exception as e:
            # A crash tells us nothing about the agent either.
            signature_results.append(_untestable(sig, "test_raised", error=str(e)))
            continue

        # Templates flag insufficient data explicitly; absence means testable,
        # which keeps any template that has not been updated working.
        if result.get("testable", True) is False:
            signature_results.append(
                _untestable(sig, "insufficient_data", detail=result.get("detail")))
            continue

        p_value, effect = result.get("p_value"), result.get("effect_size")
        # An undefined statistic (e.g. Pearson r when either variable has zero
        # variance) surfaces as nan. That is "the test does not apply here", not
        # "the agent lacks the signature".
        if p_value is None or _is_nan(p_value) or _is_nan(effect):
            signature_results.append(
                _untestable(sig, "undefined_statistic", detail=result.get("detail"),
                            p_value=p_value, effect_size=effect))
            continue

        if result["direction_correct"] and p_value < sig["threshold_p"]:
            sig_score = 1.0
        elif result["direction_correct"]:
            sig_score = 0.5
        else:
            sig_score = 0.0

        signature_results.append({
            "name": sig["name"],
            "score": sig_score,
            "testable": True,
            "p_value": p_value,
            "effect_size": effect,
            "direction_correct": result["direction_correct"],
            "detail": result.get("detail"),
            "weight": sig.get("weight", 1.0),
        })

    testable = [s for s in signature_results if s.get("testable", True)]
    untestable = [s for s in signature_results if not s.get("testable", True)]
    testable_weight = sum(s["weight"] for s in testable)
    total_weight = sum(s["weight"] for s in signature_results)

    if testable_weight > 0:
        score = sum(s["score"] * s["weight"] for s in testable) / testable_weight
    else:
        # Nothing could be measured. 0.0 keeps the return type stable for the
        # composite, but n_testable == 0 is the field that matters: callers
        # should treat such a cell as unmeasured rather than as a floor score.
        score = 0.0

    return {
        "score": float(score),
        "signatures": signature_results,
        "n_testable": len(testable),
        "n_untestable": len(untestable),
        "testable_weight": float(testable_weight),
        "total_weight": float(total_weight),
        # Fraction of the signature set this session could actually speak to.
        "coverage": float(testable_weight / total_weight) if total_weight > 0 else 0.0,
    }
