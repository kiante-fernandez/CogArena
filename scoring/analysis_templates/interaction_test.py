import numpy as np
from scipy import stats


def run_interaction_test(trial_data: list[dict], spec: dict) -> dict:
    pre_filter = spec.get("pre_filter")
    if pre_filter:
        filtered = []
        for t in trial_data:
            match = True
            for k, v in pre_filter.items():
                if isinstance(v, list):
                    if t.get(k) not in v:
                        match = False
                        break
                elif t.get(k) != v:
                    match = False
                    break
            if match:
                filtered.append(t)
        trial_data = filtered

    fa = spec["factor_a"]
    fb = spec["factor_b"]
    outcome_field = spec["outcome"]["field"]
    lag_a = fa.get("lag", 0)
    lag_b = fb.get("lag", 0)
    max_lag = max(lag_a, lag_b)

    levels_a = fa["levels"]
    levels_b = fb["levels"]

    cells = {}
    for la in levels_a:
        for lb in levels_b:
            cells[(la, lb)] = []

    for i in range(max_lag, len(trial_data)):
        trial_a = trial_data[i - lag_a]
        trial_b = trial_data[i - lag_b]
        current = trial_data[i]

        val_a = trial_a.get(fa["field"])
        val_b = trial_b.get(fb["field"])
        outcome = current.get(outcome_field)

        if val_a in levels_a and val_b in levels_b and outcome is not None:
            cells[(val_a, val_b)].append(float(outcome))

    min_cell = min(len(v) for v in cells.values())
    if min_cell < 3:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "detail": f"Insufficient data in cells (min={min_cell})",
            "testable": False,
        }

    means = {k: np.mean(v) for k, v in cells.items()}

    interaction = (
        (means[(levels_a[0], levels_b[0])] - means[(levels_a[0], levels_b[1])])
        - (means[(levels_a[1], levels_b[0])] - means[(levels_a[1], levels_b[1])])
    )

    all_values = []
    group_labels_a = []
    group_labels_b = []
    for (la, lb), vals in cells.items():
        all_values.extend(vals)
        group_labels_a.extend([la] * len(vals))
        group_labels_b.extend([lb] * len(vals))

    n_perm = 5000
    observed_interaction = interaction
    count_extreme = 0
    all_values_arr = np.array(all_values)

    for _ in range(n_perm):
        shuffled_b = np.random.permutation(group_labels_b)
        perm_cells = {(la, lb): [] for la in levels_a for lb in levels_b}
        for val, la, lb in zip(all_values_arr, group_labels_a, shuffled_b):
            perm_cells[(la, lb)].append(val)

        perm_means = {}
        valid = True
        for k, v in perm_cells.items():
            if len(v) == 0:
                valid = False
                break
            perm_means[k] = np.mean(v)

        if not valid:
            continue

        perm_interaction = (
            (perm_means[(levels_a[0], levels_b[0])] - perm_means[(levels_a[0], levels_b[1])])
            - (perm_means[(levels_a[1], levels_b[0])] - perm_means[(levels_a[1], levels_b[1])])
        )

        if abs(perm_interaction) >= abs(observed_interaction):
            count_extreme += 1

    p_value = (count_extreme + 1) / (n_perm + 1)

    if spec["expected_direction"] == "negative_interaction":
        direction_correct = bool(interaction < 0)
    else:
        direction_correct = bool(interaction > 0)

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(interaction),
        "detail": f"interaction={interaction:.3f}, p={p_value:.4f}",
    }
