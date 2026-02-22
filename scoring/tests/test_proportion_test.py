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


def test_insufficient_data():
    data = [{"field": True} for _ in range(5)]
    spec = {"field": "field", "chance_level": 0.5, "expected_direction": "above_chance", "threshold_p": 0.05}
    result = run_proportion_test(data, spec)
    assert not result["direction_correct"]
    assert result["p_value"] == 1.0


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
