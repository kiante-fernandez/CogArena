from scipy import stats


def run_sequential_regression(trial_data: list[dict], spec: dict) -> dict:
    pred_field = spec["predictor"]["field"]
    lag = spec["predictor"].get("lag", 1)
    invert = spec["predictor"].get("invert", False)
    outcome_field = spec["outcome"]["field"]

    predictors = []
    outcomes = []

    for i in range(lag, len(trial_data)):
        pred_val = trial_data[i - lag].get(pred_field)
        out_val = trial_data[i].get(outcome_field)

        if pred_val is not None and out_val is not None:
            p = float(pred_val)
            if invert:
                p = 1.0 - p
            predictors.append(p)
            outcomes.append(float(out_val))

    if len(predictors) < 10:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "detail": f"Insufficient sequential pairs: {len(predictors)}",
            "testable": False,
        }

    slope, intercept, r_value, p_value, std_err = stats.linregress(predictors, outcomes)

    if spec["expected_direction"] == "positive":
        direction_correct = bool(slope > 0)
        p_one = p_value / 2 if slope > 0 else 1 - p_value / 2
    else:
        direction_correct = bool(slope < 0)
        p_one = p_value / 2 if slope < 0 else 1 - p_value / 2

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_one),
        "effect_size": float(r_value),
        "detail": f"slope={slope:.3f}, r={r_value:.3f}, p={p_one:.4f}",
    }
