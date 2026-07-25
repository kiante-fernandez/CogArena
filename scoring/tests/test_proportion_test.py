import pytest
from scoring.analysis_templates.proportion_test import run_proportion_test


def test_above_chance_detected():
    data = [{"field": True} for _ in range(80)] + [{"field": False} for _ in range(20)]
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
    data = [{"field": True} for _ in range(20)] + [{"field": False} for _ in range(80)]
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
    assert "Underpowered by construction" in result["detail"]


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
    data = (
        [{"field": True, "cond": "a"} for _ in range(20)] +
        [{"field": False, "cond": "a"} for _ in range(5)] +
        [{"field": True, "cond": "b"} for _ in range(5)] +
        [{"field": False, "cond": "b"} for _ in range(20)]
    )
    spec = {"field": "field", "filter": {"cond": "a"}, "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05
