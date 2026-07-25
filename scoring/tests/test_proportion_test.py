import random

import pytest
from scoring.analysis_templates.proportion_test import run_proportion_test


def _interleaved(n_true, n_false, seed=0):
    """Trial order matters now that n_eff corrects for serial dependence.

    A blocked sequence (all successes, then all failures) has lag-1 rho near 1
    and collapses to a handful of independent observations -- correctly, since
    such a sequence carries about one bit. Real trial data interleaves, so
    fixtures must too.
    """
    vals = [True] * n_true + [False] * n_false
    random.Random(seed).shuffle(vals)
    return [{"field": v} for v in vals]


def test_above_chance_detected():
    data = _interleaved(80, 20)
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05
    assert result["effect_size"] > 0


def test_at_chance_not_significant():
    data = [{"field": True} for _ in range(50)] + [{"field": False} for _ in range(50)]
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["p_value"] > 0.05


def test_below_chance_detected():
    data = _interleaved(20, 80, seed=1)
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "below_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05


def test_no_data_is_untestable():
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test([{"field": True}], spec)
    assert result["testable"] is False
    assert "Insufficient data" in result["detail"]


def test_small_n_now_passes_under_exact_test():
    """n=5 all-successes is a real result: exact binomial p = 0.5**5 = 0.031.

    The old normal-approximation path rejected everything below n=10, which
    discarded genuine signal from the small conditional subsets this benchmark
    produces.
    """
    data = [{"field": True} for _ in range(5)]
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["testable"] is True
    assert result["direction_correct"] is True
    assert result["p_value"] == pytest.approx(0.03125)


def test_underpowered_by_construction_is_untestable():
    """At n=4 vs chance 0.5, a perfect result gives p=0.0625 — unreachable.

    This is moral_machine/intervention_aversion. The signature cannot be passed
    by any behaviour, so it must be excluded rather than scored 0, which would
    assert the agent failed a test that could not be run.
    """
    data = [{"field": True} for _ in range(4)]
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["testable"] is False
    assert "Underpowered" in result["detail"]


def test_six_trials_is_passable():
    """moral_machine/legality_preference_save_lawful: n=6, best p=0.0156.

    Previously unreachable behind the n>=10 guard; now testable and passable.
    """
    data = [{"field": True} for _ in range(6)]
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["testable"] is True
    assert result["p_value"] == pytest.approx(0.015625)


def test_filter_applied():
    vals_a = [True] * 20 + [False] * 5
    vals_b = [True] * 5 + [False] * 20
    random.Random(2).shuffle(vals_a)
    random.Random(3).shuffle(vals_b)
    data = ([{"field": v, "cond": "a"} for v in vals_a] +
            [{"field": v, "cond": "b"} for v in vals_b])
    spec = {"field": "field", "filter": {"cond": "a"}, "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05


def test_serial_dependence_shrinks_effective_n():
    """igZ7 W3b: within-session trials are not independent.

    The same success rate is significant when trials alternate and untestable
    when they arrive in one block, because a blocked sequence carries far fewer
    independent observations than its length suggests.
    """
    shuffled = run_proportion_test(_interleaved(40, 10, seed=4), SPEC)
    blocked = run_proportion_test(
        [{"field": True} for _ in range(40)] + [{"field": False} for _ in range(10)], SPEC)
    assert shuffled["testable"] is True
    assert shuffled["p_value"] < 0.05
    assert shuffled["n_effective"] > blocked.get("n_effective", 0) if blocked["testable"] else True
    # The blocked version must not claim the same confidence from the same rate.
    assert blocked["testable"] is False or blocked["p_value"] > shuffled["p_value"]


def test_negative_autocorrelation_does_not_add_power():
    """Alternating responses would inflate n_eff above n; that is declined."""
    alternating = [{"field": i % 2 == 0} for i in range(40)]
    r = run_proportion_test(alternating, SPEC)
    assert r["lag1_autocorrelation"] < 0
    assert r["n_effective"] <= 40


SPEC = {"field": "field", "chance_level": 0.5,
        "expected_direction": "above_chance", "threshold_p": 0.05}
