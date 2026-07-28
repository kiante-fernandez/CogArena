"""The dependence-robust p-value path used by `paired_proportion_test`.

Two properties carry the weight: it must be deterministic (a re-score that
produced a different number would make `scorer_version` meaningless), and it
must be more conservative than the pooled-p normal it replaced on exactly the
serially-dependent data that motivated it.
"""
import numpy as np
import pytest

from scoring.analysis_templates.block_bootstrap import bootstrap_contrast_p
from scoring.analysis_templates.paired_ttest import run_paired_proportion_test

SPEC = {
    "group_a": {"filter": {"phase": "post"}, "field": "correct"},
    "group_b": {"filter": {"phase": "pre"}, "field": "correct"},
    "expected_direction": "a > b",
}


def _trials(a_vals, b_vals):
    """Interleave the two groups in trial order, a-run then b-run."""
    return ([{"phase": "post", "correct": bool(v)} for v in a_vals]
            + [{"phase": "pre", "correct": bool(v)} for v in b_vals])


def test_is_deterministic():
    """Same data -> same p, every time. Seeded from the series, not a global RNG."""
    values = [1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    group = [True] * 6 + [False] * 6
    first = bootstrap_contrast_p(values, group, higher=True)
    assert first is not None
    for _ in range(4):
        assert bootstrap_contrast_p(values, group, higher=True) == first


def test_different_data_gets_a_different_resampling():
    a = bootstrap_contrast_p([1.0] * 6 + [0.0] * 6, [True] * 6 + [False] * 6, True)
    b = bootstrap_contrast_p([1.0] * 5 + [0.0] * 7, [True] * 6 + [False] * 6, True)
    assert a is not None and b is not None
    assert a[0] != b[0]


def test_scoring_the_same_session_twice_is_stable():
    data = _trials([1, 1, 1, 1, 0, 1, 1, 0], [0, 1, 0, 0, 1, 0, 0, 0])
    first = run_paired_proportion_test(data, SPEC)
    for _ in range(3):
        assert run_paired_proportion_test(data, SPEC)["p_value"] == first["p_value"]


def test_a_real_difference_is_still_detected():
    """The correction must not blunt the instrument."""
    data = _trials([1] * 18 + [0] * 2, [0] * 18 + [1] * 2)
    r = run_paired_proportion_test(data, SPEC)
    assert r["direction_correct"] is True
    assert r["p_value"] < 0.05
    assert "moving-block bootstrap" in r["detail"]


def test_serially_dependent_data_is_penalised_versus_the_old_normal():
    """The defect this replaced: a sticky policy looked significant.

    A run of identical responses carries far less independent information than
    its trial count suggests. The pooled-p normal ignored that entirely; the
    bootstrap resamples whole runs, so the same series yields a larger p.
    """
    from scipy import stats
    import numpy as np

    a_vals = [1] * 10 + [0] * 2       # one long sticky run
    b_vals = [0] * 10 + [1] * 2
    data = _trials(a_vals, b_vals)

    r = run_paired_proportion_test(data, SPEC)

    # The pooled-p normal on the same counts, i.e. what this used to report.
    n_a = n_b = 12
    c_a, c_b = sum(a_vals), sum(b_vals)
    pooled = (c_a + c_b) / (n_a + n_b)
    se = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (c_a / n_a - c_b / n_b) / se
    normal_p = 1 - stats.norm.cdf(z)

    assert r["p_value"] > normal_p, (
        f"bootstrap p {r['p_value']:.4f} should exceed the uncorrected normal "
        f"{normal_p:.4f} on serially dependent data")


def test_degenerate_input_returns_none_rather_than_a_number():
    assert bootstrap_contrast_p([1.0, 0.0], [True, True], higher=True) is None
    assert bootstrap_contrast_p([], [], higher=True) is None
