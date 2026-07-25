import numpy as np
from scipy import stats


def run_proportion_test(trial_data: list[dict], spec: dict) -> dict:
    filter_spec = spec.get("filter", {})
    filtered = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in filter_spec.items())
    ]

    field = spec["field"]
    values = [t[field] for t in filtered if field in t]

    if len(values) < 10:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "detail": f"Insufficient data: n={len(values)}",
            "testable": False,
        }

    n = len(values)
    p_obs = sum(1 for v in values if v) / n
    p_chance = spec.get("chance_level", 0.5)

    se = np.sqrt(p_chance * (1 - p_chance) / n)
    z = (p_obs - p_chance) / se if se > 0 else 0.0

    expected = spec.get("expected_direction", "above_chance")
    if expected == "above_chance":
        direction_correct = bool(p_obs > p_chance)
        p_value = 1 - stats.norm.cdf(z) if z > 0 else stats.norm.cdf(z)
    else:
        direction_correct = bool(p_obs < p_chance)
        p_value = stats.norm.cdf(z) if z < 0 else 1 - stats.norm.cdf(z)

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(p_obs - p_chance),
        "detail": f"p_obs={p_obs:.3f}, p_chance={p_chance:.3f}, z={z:.3f}, p={p_value:.4f}",
    }
