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

from scoring.analysis_templates import underpowered

# Only guards against a rate that does not exist. The exact test carries the
# small-sample penalty itself, and the underpowering check below catches the
# cases a blanket minimum was previously (and too bluntly) standing in for.
MIN_N = 2


def _effective_n(values: list) -> tuple[int, float]:
    """Sample size adjusted for serial dependence, and the lag-1 autocorrelation.

    Trials within a session are not independent, but the test treats them as if
    they were, which inflates the effective sample size and makes the nominal
    significance threshold anti-conservative. Measured on the archived sweep,
    the median lag-1 autocorrelation is near zero but the tail is severe:
    effort_foraging's above_chance_total_reward runs at rho = +0.83, so the test
    believed it had roughly eleven times more independent observations than it
    did.

    Uses the standard first-order correction n_eff = n(1-rho)/(1+rho), clamped to
    at most n. Negative autocorrelation (alternating responses, which several
    agents show) would otherwise *increase* n_eff and hand the test extra power;
    declining that keeps the adjustment one-directional and conservative.
    """
    n = len(values)
    if n < 6:
        return n, 0.0
    x = [1.0 if v else 0.0 for v in values]
    mean = sum(x) / n
    denom = sum((v - mean) ** 2 for v in x)
    if denom == 0:
        return n, 0.0
    rho = sum((x[i] - mean) * (x[i + 1] - mean) for i in range(n - 1)) / denom
    rho = max(-0.99, min(0.99, rho))
    n_eff = n * (1 - rho) / (1 + rho)
    return max(MIN_N, min(n, int(round(n_eff)))), rho


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

    # Serial dependence is assessed before the power check, so "underpowered by
    # construction" is judged against the sample size the test really has.
    n_eff, rho = _effective_n(values)

    best = _best_attainable_p(n_eff, p_chance, expected)
    if best > threshold:
        return underpowered(best, threshold,
                            f"n={n}, n_eff={n_eff} (lag-1 rho={rho:+.2f}), "
                            f"chance={p_chance:.3f}.")

    successes = sum(1 for v in values if v)
    p_obs = successes / n
    # Rescale to the effective sample size; the rate is estimated from all
    # trials, but the test is run at the number of independent observations.
    successes_eff = int(round(p_obs * n_eff))

    if expected == "above_chance":
        direction_correct = bool(p_obs > p_chance)
        p_value = stats.binomtest(successes_eff, n_eff, p_chance, alternative="greater").pvalue
    else:
        direction_correct = bool(p_obs < p_chance)
        p_value = stats.binomtest(successes_eff, n_eff, p_chance, alternative="less").pvalue

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(p_obs - p_chance),
        "testable": True,
        "n": n,
        "n_effective": n_eff,
        "lag1_autocorrelation": float(rho),
        "detail": (f"p_obs={p_obs:.3f} ({successes}/{n}), p_chance={p_chance:.3f}, "
                   f"exact binomial on n_eff={n_eff} (lag-1 rho={rho:+.2f}) "
                   f"p={p_value:.4f}"),
    }
