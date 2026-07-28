import numpy as np
from scipy import stats

from scoring.analysis_templates import constant_side, insufficient
from scoring.analysis_templates.block_bootstrap import bootstrap_contrast_p


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
        return insufficient(
            f"Insufficient data: group_a={len(values_a)}, group_b={len(values_b)}")

    mean_a = np.mean(values_a)
    mean_b = np.mean(values_b)

    # Group membership varies by construction, so only the outcome side can go
    # constant: the agent produced one identical value in both conditions, so
    # the contrast the signature asks about is absent. predictor=None encodes
    # exactly the "both groups constant" condition this replaces.
    if (undef := constant_side(None, ("both groups", values_a + values_b))):
        return undef

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
    """Contrast two groups' success rates, with a dependence-robust p-value.

    This used to be a pooled-p normal z with no correction for either small n or
    within-session dependence, and it was measurably the worst-calibrated test in
    the suite: against a moving-block bootstrap its median p-value ran **2.4x too
    small**, the only template that was anti-conservative rather than
    conservative. It backs five weighted signatures, including both
    `above_chance_discrimination` variants at w=2.0, and `primacy_effect`, which
    compares 4 primacy trials against 8 middle ones — exactly the small-n regime
    the sibling `proportion_test` docstring calls "both inaccurate and harder to
    defend".

    The bootstrap fixes both problems at once and makes no distributional
    assumption. It is preferred here over an AR(1) `n_eff` correction because
    measurement shows AR(1) over-charges: applying it to `proportion_test` raises
    29 grades under the bootstrap and lowers none.

    Effect of the switch on the archive: 4 grades of 1,315, panel L3 unchanged to
    three decimals, model ranking identical.
    """
    field_a = spec["group_a"]["field"]
    field_b = spec["group_b"]["field"]

    # ONE pass, in TRIAL ORDER with group membership tagged. Order matters
    # because the bootstrap resamples runs of adjacent trials, and building the
    # two groups separately as well would define prop_a/prop_b over a different
    # membership rule than the p-value — two answers to one question, free to
    # disagree the first time a spec's group filters overlap. A trial matching
    # BOTH filters is ambiguous and dropped; every shipped spec has mutually
    # exclusive filters, so that is a guard rather than a behaviour.
    values, group = [], []
    for t in trial_data:
        in_a = (all(t.get(k) == v for k, v in spec["group_a"]["filter"].items())
                and field_a in t)
        in_b = (all(t.get(k) == v for k, v in spec["group_b"]["filter"].items())
                and field_b in t)
        if in_a and not in_b:
            values.append(1.0 if t[field_a] else 0.0); group.append(True)
        elif in_b and not in_a:
            values.append(1.0 if t[field_b] else 0.0); group.append(False)

    values_a = [v for v, g in zip(values, group) if g]
    values_b = [v for v, g in zip(values, group) if not g]
    if len(values_a) < 3 or len(values_b) < 3:
        return insufficient(
            f"Insufficient data: group_a={len(values_a)}, group_b={len(values_b)}")

    prop_a = sum(values_a) / len(values_a)
    prop_b = sum(values_b) / len(values_b)
    higher = spec["expected_direction"] == "a > b"
    direction_correct = bool(prop_a > prop_b) if higher else bool(prop_a < prop_b)

    boot = bootstrap_contrast_p(values, group, higher)
    if boot is None:
        # Resampling retained too few draws with both groups populated. The
        # guard above already excludes everything small enough for this to be
        # likely, so report it honestly rather than silently substituting a
        # second, weaker statistical method for the one this template documents.
        return insufficient(
            f"Bootstrap degenerate: group_a={len(values_a)}, group_b={len(values_b)}")

    p_value, block_len = boot
    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(prop_a - prop_b),
        "detail": (f"prop_a={prop_a:.3f} (n={len(values_a)}), "
                   f"prop_b={prop_b:.3f} (n={len(values_b)}), "
                   f"diff={prop_a - prop_b:+.3f}, moving-block bootstrap "
                   f"(l={block_len}) p={p_value:.4f}"),
    }
