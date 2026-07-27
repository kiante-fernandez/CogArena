from scipy import stats


def run_correlation_test(trial_data: list[dict], spec: dict) -> dict:
    filter_spec = spec.get("filter", {})
    filtered = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in filter_spec.items())
    ]

    field_x = spec["field_x"]
    field_y = spec["field_y"]

    # NOTE: a mistyped field name yields zero pairs and reports
    # "insufficient_data", which drops the signature from the L3 denominator —
    # the same silent inflation as a mistyped test name. It is NOT checked here:
    # a truncated session legitimately contains no trial carrying the field, so
    # a runtime absence check cannot tell a spec typo from sparse data and fired
    # on 48 real sessions when tried. The right home for that check is a
    # repo-level test scoring each spec against a complete reference dataset;
    # see results/CODEBASE_TODO.md.
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

    # Both coefficients are undefined when either variable has zero variance,
    # and the two cases mean opposite things. A constant predictor means the
    # design never varied, so nothing about the agent can be concluded. A
    # constant outcome means the agent gave the same response at every level of
    # the manipulation, which is precisely the absence of the signature — the
    # commonest instance being an agent that answered nothing correctly, so
    # `correct` is uniformly False. Declaring which one occurred lets
    # level3_behavioral exclude the first and score the second 0.0; leaving it
    # to a bare nan check excluded both and raised L3 for the worst agents.
    x_constant = len(set(x_vals)) < 2
    y_constant = len(set(y_vals)) < 2
    if x_constant or y_constant:
        return {
            "direction_correct": False,
            "p_value": float("nan"),
            "effect_size": float("nan"),
            # Predictor takes precedence: if the design never varied, the
            # outcome being constant too says nothing extra.
            "undefined_reason": "constant_predictor" if x_constant else "constant_outcome",
            "testable": True,
            "detail": (f"{field_x} constant at {x_vals[0]!r}" if x_constant
                       else f"{field_y} constant at {y_vals[0]!r} across n={len(pairs)}"),
        }

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
