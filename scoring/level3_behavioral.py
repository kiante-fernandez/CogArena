from scoring.analysis_templates.paired_ttest import run_paired_ttest, run_paired_proportion_test
from scoring.analysis_templates.sequential_regression import run_sequential_regression
from scoring.analysis_templates.interaction_test import run_interaction_test
from scoring.analysis_templates.proportion_test import run_proportion_test
from scoring.analysis_templates.correlation_test import run_correlation_test

TEST_REGISTRY = {
    "paired_ttest_greater": run_paired_ttest,
    "paired_proportion_test": run_paired_proportion_test,
    "sequential_regression": run_sequential_regression,
    "interaction_test": run_interaction_test,
    "proportion_test": run_proportion_test,
    "correlation_test": run_correlation_test,
}


def score_behavioral(trial_data: list[dict], signatures_spec: dict) -> dict:
    signature_results = []

    for sig in signatures_spec["signatures"]:
        test_func = TEST_REGISTRY.get(sig["test"])
        if test_func is None:
            signature_results.append({
                "name": sig["name"],
                "score": 0.0,
                "weight": sig.get("weight", 1.0),
                "error": f"Unknown test type: {sig['test']}",
            })
            continue

        try:
            result = test_func(trial_data, sig)

            if result["direction_correct"] and result["p_value"] < sig["threshold_p"]:
                sig_score = 1.0
            elif result["direction_correct"]:
                sig_score = 0.5
            else:
                sig_score = 0.0

            signature_results.append({
                "name": sig["name"],
                "score": sig_score,
                "p_value": result["p_value"],
                "effect_size": result["effect_size"],
                "direction_correct": result["direction_correct"],
                "detail": result["detail"],
                "weight": sig.get("weight", 1.0),
            })
        except Exception as e:
            signature_results.append({
                "name": sig["name"],
                "score": 0.0,
                "weight": sig.get("weight", 1.0),
                "error": str(e),
            })

    total_weight = sum(s["weight"] for s in signature_results)
    if total_weight > 0:
        score = sum(s["score"] * s["weight"] for s in signature_results) / total_weight
    else:
        score = 0.0

    return {"score": float(score), "signatures": signature_results}
