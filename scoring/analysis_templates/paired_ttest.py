import numpy as np
from scipy import stats


def run_paired_ttest(trial_data: list[dict], spec: dict) -> dict:
    group_a_trials = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in spec["group_a"]["filter"].items())
    ]
    group_b_trials = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in spec["group_b"]["filter"].items())
    ]

    field_a = spec["group_a"]["field"]
    field_b = spec["group_b"]["field"]

    values_a = [t[field_a] for t in group_a_trials if t.get(field_a) is not None]
    values_b = [t[field_b] for t in group_b_trials if t.get(field_b) is not None]

    if len(values_a) < 3 or len(values_b) < 3:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "detail": f"Insufficient data: group_a={len(values_a)}, group_b={len(values_b)}",
            "testable": False,
        }

    mean_a = np.mean(values_a)
    mean_b = np.mean(values_b)

    t_stat, p_two = stats.ttest_ind(values_a, values_b)

    if spec["expected_direction"] == "a > b":
        direction_correct = bool(mean_a > mean_b)
        p_value = p_two / 2 if t_stat > 0 else 1 - p_two / 2
    else:
        direction_correct = bool(mean_a < mean_b)
        p_value = p_two / 2 if t_stat < 0 else 1 - p_two / 2

    var_a = np.var(values_a, ddof=1)
    var_b = np.var(values_b, ddof=1)
    pooled_sd = np.sqrt((var_a + var_b) / 2)
    cohens_d = (mean_a - mean_b) / pooled_sd if pooled_sd > 0 else 0.0

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(cohens_d),
        "detail": f"mean_a={mean_a:.1f}, mean_b={mean_b:.1f}, d={cohens_d:.3f}, p={p_value:.4f}",
    }


def run_paired_proportion_test(trial_data: list[dict], spec: dict) -> dict:
    group_a_trials = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in spec["group_a"]["filter"].items())
    ]
    group_b_trials = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in spec["group_b"]["filter"].items())
    ]

    field_a = spec["group_a"]["field"]
    field_b = spec["group_b"]["field"]

    values_a = [t[field_a] for t in group_a_trials if field_a in t]
    values_b = [t[field_b] for t in group_b_trials if field_b in t]

    if len(values_a) < 3 or len(values_b) < 3:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "detail": f"Insufficient data: group_a={len(values_a)}, group_b={len(values_b)}",
            "testable": False,
        }

    prop_a = sum(1 for v in values_a if v) / len(values_a)
    prop_b = sum(1 for v in values_b if v) / len(values_b)

    count_a = sum(1 for v in values_a if v)
    count_b = sum(1 for v in values_b if v)
    n_a = len(values_a)
    n_b = len(values_b)

    pooled_p = (count_a + count_b) / (n_a + n_b)
    se = np.sqrt(pooled_p * (1 - pooled_p) * (1 / n_a + 1 / n_b)) if pooled_p > 0 and pooled_p < 1 else 1.0
    z_stat = (prop_a - prop_b) / se if se > 0 else 0.0

    if spec["expected_direction"] == "a > b":
        direction_correct = bool(prop_a > prop_b)
        p_value = 1 - stats.norm.cdf(z_stat) if z_stat > 0 else stats.norm.cdf(z_stat)
    else:
        direction_correct = bool(prop_a < prop_b)
        p_value = stats.norm.cdf(z_stat) if z_stat < 0 else 1 - stats.norm.cdf(z_stat)

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(prop_a - prop_b),
        "detail": f"prop_a={prop_a:.3f}, prop_b={prop_b:.3f}, z={z_stat:.3f}, p={p_value:.4f}",
    }
