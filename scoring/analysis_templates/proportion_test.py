"""One-sided test of a binary rate against a chance level.

Uses an exact binomial test rather than a normal approximation. The conditional
subsets this benchmark produces are routinely 4-20 trials, where the normal
approximation is both inaccurate and harder to defend, and where an exact test
costs nothing.

The exact test also makes structural underpowering visible. With a chance level
of 0.5 and n=4, a perfect result gives p=0.0625, so a signature with
threshold_p=0.05 cannot be passed no matter how the agent behaves. That is a
property of the task's trial allocation, not of the agent, and it is reported as
untestable rather than scored 0 — the same distinction the scorer draws for
insufficient data. moral_machine's intervention_aversion (4 trials) is exactly
this case; its legality_preference_save_lawful (6 trials) becomes passable under
the exact test at p=0.0156, having been unreachable under the old n>=10 guard.
"""
from scipy import stats

# Only guards against a rate that does not exist. The exact test carries the
# small-sample penalty itself, and the underpowering check below catches the
# cases a blanket minimum was previously (and too bluntly) standing in for.
MIN_N = 2


def _best_attainable_p(n: int, p_chance: float, expected: str) -> float:
    """Smallest p-value achievable at this n, i.e. every trial in the predicted
    direction. If this exceeds threshold_p the signature cannot be passed."""
    if expected == "above_chance":
        return stats.binomtest(n, n, p_chance, alternative="greater").pvalue
    return stats.binomtest(0, n, p_chance, alternative="less").pvalue


def run_proportion_test(trial_data: list[dict], spec: dict) -> dict:
    filter_spec = spec.get("filter", {})
    filtered = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in filter_spec.items())
    ]

    field = spec["field"]
    values = [t[field] for t in filtered if field in t]
    n = len(values)

    if n < MIN_N:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "testable": False,
            "detail": f"Insufficient data: n={n}",
        }

    p_chance = spec.get("chance_level", 0.5)
    expected = spec.get("expected_direction", "above_chance")
    threshold = spec.get("threshold_p", 0.05)

    best = _best_attainable_p(n, p_chance, expected)
    if best > threshold:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "testable": False,
            "detail": (f"Underpowered by construction: n={n}, chance={p_chance:.3f}, "
                       f"best attainable p={best:.4f} > threshold_p={threshold}. "
                       f"No behaviour could pass this signature."),
        }

    successes = sum(1 for v in values if v)
    p_obs = successes / n

    if expected == "above_chance":
        direction_correct = bool(p_obs > p_chance)
        p_value = stats.binomtest(successes, n, p_chance, alternative="greater").pvalue
    else:
        direction_correct = bool(p_obs < p_chance)
        p_value = stats.binomtest(successes, n, p_chance, alternative="less").pvalue

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(p_obs - p_chance),
        "testable": True,
        "detail": (f"p_obs={p_obs:.3f} ({successes}/{n}), p_chance={p_chance:.3f}, "
                   f"exact binomial p={p_value:.4f}"),
    }
