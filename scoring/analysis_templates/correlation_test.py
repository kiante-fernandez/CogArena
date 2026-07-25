from scipy import stats


def run_correlation_test(trial_data: list[dict], spec: dict) -> dict:
    filter_spec = spec.get("filter", {})
    filtered = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in filter_spec.items())
    ]

    field_x = spec["field_x"]
    field_y = spec["field_y"]

    pairs = [
        (float(t[field_x]), float(t[field_y]))
        for t in filtered
        if t.get(field_x) is not None and t.get(field_y) is not None
    ]

    if len(pairs) < 10:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "detail": f"Insufficient paired data: n={len(pairs)}",
            "testable": False,
        }

    x_vals, y_vals = zip(*pairs)
    # Spearman for anything heavy-tailed. Reaction times here are dominated by
    # LLM inference latency and carry occasional multi-second provider stalls,
    # which a Pearson coefficient chases; rank correlation asks the question the
    # signature actually poses — does the ordering hold — and is unaffected by
    # the constant offset between agent and human timescales.
    method = spec.get("method", "pearson")
    if method == "spearman":
        r, p_two = stats.spearmanr(x_vals, y_vals)
    elif method == "pearson":
        r, p_two = stats.pearsonr(x_vals, y_vals)
    else:
        raise ValueError(f"Unknown correlation method: {method!r}")

    expected = spec.get("expected_direction", "positive")
    if expected == "positive":
        direction_correct = bool(r > 0)
        p_value = p_two / 2 if r > 0 else 1 - p_two / 2
    else:
        direction_correct = bool(r < 0)
        p_value = p_two / 2 if r < 0 else 1 - p_two / 2

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(r),
        "testable": True,
        "detail": f"{method} r={r:.3f}, p={p_value:.4f}, n={len(pairs)}",
    }
