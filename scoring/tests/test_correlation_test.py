from scoring.analysis_templates.correlation_test import run_correlation_test


def test_positive_correlation_detected():
    data = [{"x": i, "y": i * 2 + 1} for i in range(50)]
    spec = {"field_x": "x", "field_y": "y", "expected_direction": "positive", "threshold_p": 0.05}
    result = run_correlation_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05
    assert result["effect_size"] > 0.9


def test_negative_correlation_detected():
    data = [{"x": i, "y": -i * 2 + 100} for i in range(50)]
    spec = {"field_x": "x", "field_y": "y", "expected_direction": "negative", "threshold_p": 0.05}
    result = run_correlation_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05
    assert result["effect_size"] < -0.9


def test_no_correlation():
    import random
    rng = random.Random(42)
    data = [{"x": rng.random(), "y": rng.random()} for _ in range(50)]
    spec = {"field_x": "x", "field_y": "y", "expected_direction": "positive", "threshold_p": 0.05}
    result = run_correlation_test(data, spec)
    assert abs(result["effect_size"]) < 0.3


def test_insufficient_data():
    data = [{"x": 1, "y": 2} for _ in range(5)]
    spec = {"field_x": "x", "field_y": "y", "expected_direction": "positive", "threshold_p": 0.05}
    result = run_correlation_test(data, spec)
    assert not result["direction_correct"]
    assert result["p_value"] == 1.0


def test_filter_applied():
    data = (
        [{"x": i, "y": i * 2, "group": "a"} for i in range(30)] +
        [{"x": i, "y": -i, "group": "b"} for i in range(30)]
    )
    spec = {"field_x": "x", "field_y": "y", "filter": {"group": "a"}, "expected_direction": "positive", "threshold_p": 0.05}
    result = run_correlation_test(data, spec)
    assert result["direction_correct"]
    assert result["p_value"] < 0.05
