"""Contrast a binary outcome's rate between two conditions.

Written for reciprocity-style signatures of the form

    P(cooperate | opponent cooperated last round)
      > P(cooperate | opponent defected last round)

which were previously operationalised as a Pearson correlation between the two
binary variables. That is the wrong instrument here: against a deterministic
opponent such as tit-for-tat, an agent with a constant policy drives one or both
variables to zero variance, so r is undefined and returns nan. The archived
sessions show exactly that — repeated_games/tit_for_tat_reciprocity_pd returned
``r=nan`` in every session that reached it, including an agent that cooperated
after 100% of opponent cooperations.

A conditional contrast is well defined under constant policies and is a direct
encoding of the hypothesis. Fisher's exact test is used rather than a normal
approximation because these conditional bins are small by construction.

An important honest case: if one bin is empty — e.g. an always-cooperating agent
facing tit-for-tat never observes an opponent defection — reciprocity is not
identifiable from that session at all. This returns ``testable: False`` rather
than a score. That is the correct verdict; scoring 0 would assert the agent
lacks reciprocity on evidence that cannot speak to it either way.
"""
from scipy import stats

# Both bins need at least two observations for a within-bin rate to exist at all.
#
# Deliberately low: Fisher's exact test already carries the small-sample penalty
# in the p-value, so an additional hard threshold only discards real signal. The
# conditioning bins here are small by construction — an agent that reciprocates
# against tit-for-tat rarely elicits a defection, so the opponent-defected bin
# stays tiny however well the agent behaves. At n=2 in that bin, only near-perfect
# separation clears p<0.05 (an 11/1 vs 0/2 split gives p=0.033, while 6/6 vs 1/1
# gives p=0.77), which is the conservatism we want and is better placed in the
# test statistic than in an arbitrary cutoff.
MIN_PER_BIN = 2


def run_conditional_proportion_contrast(trial_data: list[dict], spec: dict) -> dict:
    filter_spec = spec.get("filter", {})
    filtered = [
        t for t in trial_data
        if all(t.get(k) == v for k, v in filter_spec.items())
    ]

    outcome_field = spec["field"]
    condition_field = spec["condition_field"]

    cond_true, cond_false = [], []
    for t in filtered:
        if outcome_field not in t or condition_field not in t:
            continue
        if t[condition_field] is None:
            continue
        (cond_true if t[condition_field] else cond_false).append(bool(t[outcome_field]))

    n_true, n_false = len(cond_true), len(cond_false)
    if n_true < MIN_PER_BIN or n_false < MIN_PER_BIN:
        return {
            "direction_correct": False,
            "p_value": 1.0,
            "effect_size": 0.0,
            "testable": False,
            "detail": (f"Insufficient data in one or both conditions: "
                       f"n_true={n_true}, n_false={n_false} (need >= {MIN_PER_BIN} each). "
                       f"The contrast is unidentifiable from this session."),
        }

    a, b = sum(cond_true), n_true - sum(cond_true)
    c, d = sum(cond_false), n_false - sum(cond_false)
    p_true, p_false = a / n_true, c / n_false

    expected = spec.get("expected_direction", "positive")
    alternative = "greater" if expected == "positive" else "less"
    # Rows are [condition true, condition false], columns [outcome true, false].
    _, p_value = stats.fisher_exact([[a, b], [c, d]], alternative=alternative)

    diff = p_true - p_false
    direction_correct = bool(diff > 0) if expected == "positive" else bool(diff < 0)

    return {
        "direction_correct": direction_correct,
        "p_value": float(p_value),
        "effect_size": float(diff),
        "testable": True,
        "detail": (f"P({outcome_field}|{condition_field}=T)={p_true:.3f} (n={n_true}), "
                   f"P({outcome_field}|{condition_field}=F)={p_false:.3f} (n={n_false}), "
                   f"diff={diff:+.3f}, fisher p={p_value:.4f}"),
    }
