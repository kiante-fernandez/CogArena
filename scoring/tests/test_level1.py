from scoring.level1_completion import score_completion


def test_human_like_data_passes_all_checks(human_like_stroop_data, stroop_config):
    result = score_completion(human_like_stroop_data, stroop_config)
    assert result["score"] == 1.0
    for check in result["checks"]:
        assert check["passed"], f"Check '{check['name']}' failed: {check['detail']}"


def test_incomplete_data_fails_trial_count(incomplete_stroop_data, stroop_config):
    result = score_completion(incomplete_stroop_data, stroop_config)
    names = {c["name"]: c["passed"] for c in result["checks"]}
    assert not names["sufficient_trials"]
    assert not names["experiment_completed"]
    assert result["score"] < 1.0


def test_high_timeout_rate_fails(stroop_config):
    from scoring.tests.conftest import _generate_stroop_trials
    data = _generate_stroop_trials(n_trials=96, timeout_rate=0.5, seed=55)
    result = score_completion(data, stroop_config)
    names = {c["name"]: c["passed"] for c in result["checks"]}
    assert not names["low_timeout_rate"]


def test_empty_data_scores_zero(stroop_config):
    result = score_completion([], stroop_config)
    assert result["score"] == 0.0


def test_invalid_keys_detected(stroop_config):
    bad_data = [
        {"trial_index": i, "response": "x", "rt": 500, "correct": False, "timed_out": False}
        for i in range(96)
    ]
    result = score_completion(bad_data, stroop_config)
    names = {c["name"]: c["passed"] for c in result["checks"]}
    assert not names["valid_responses"]
