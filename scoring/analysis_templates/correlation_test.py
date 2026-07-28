from scipy import stats

from scoring.analysis_templates import constant_side, insufficient


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
    # repo-level test scoring each spec against a complete reference dataset —
    # scoring/tests/test_v1_signatures_reach_a_verdict.py does exactly that.
    pairs = [
        (float(t[field_x]), float(t[field_y]))
        for t in filtered
        if t.get(field_x) is not None and t.get(field_y) is not None
    ]

    if len(pairs) < 10:
        return insufficient(f"Insufficient paired data: n={len(pairs)}")

    x_vals, y_vals = zip(*pairs)

    # Both coefficients are undefined when either variable has zero variance,
    # and the two cases mean opposite things — see analysis_templates/__init__.
    # The commonest instance is an agent that answered nothing correctly, so
    # `correct` is uniformly False: that is the absence of the signature, not a
    # failed measurement, and must score 0.0 rather than be excluded.
    if (undef := constant_side((field_x, x_vals), (field_y, y_vals))):
        return undef

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
