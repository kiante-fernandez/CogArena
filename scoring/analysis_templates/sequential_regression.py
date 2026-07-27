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

    # linregress is undefined when either side is constant. A constant predictor
    # means the lagged manipulation never varied and nothing about the agent
    # follows; a constant outcome means the agent responded identically whatever
    # happened on the previous trial, which is the absence of the sequential
    # effect. level3_behavioral scores those differently, so say which it was.
    if len(set(predictors)) < 2 or len(set(outcomes)) < 2:
        x_constant = len(set(predictors)) < 2
        return {
            "direction_correct": False,
            "p_value": float("nan"),
            "effect_size": float("nan"),
            "undefined_reason": "constant_predictor" if x_constant else "constant_outcome",
            "testable": True,
            "detail": (f"{pred_field} (lag {lag}) constant at {predictors[0]!r}" if x_constant
                       else f"{outcome_field} constant at {outcomes[0]!r} "
                            f"across n={len(outcomes)}"),
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
