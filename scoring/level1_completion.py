def score_completion(trial_data: list[dict], task_config: dict) -> dict:
    checks = []
    params = task_config["parameters"]
    expected_trials = params["n_trials"]
    response_type = params.get("response_type", "keypress")

    # Require at least 3 trials so a single-trial submission can't earn
    # 0.20+ L1 just by sending one stub. Below this floor the agent
    # accomplished essentially nothing scorable.
    min_trials_received = 3
    has_data = len(trial_data) >= min_trials_received
    checks.append({
        "name": "data_received",
        "passed": has_data,
        "detail": f"Received {len(trial_data)} trials (need >= {min_trials_received})",
    })

    trial_ratio = len(trial_data) / expected_trials if expected_trials > 0 else 0
    checks.append({
        "name": "sufficient_trials",
        "passed": trial_ratio >= 0.80,
        "detail": f"{len(trial_data)}/{expected_trials} trials ({trial_ratio:.0%})",
    })

    if trial_data:
        # Use explicit timed_out field; only fall back to response=None
        # when timed_out is absent (handles go/no-go withhold correctly)
        timed_out = sum(
            1 for t in trial_data
            if t.get("timed_out", False)
            or ("timed_out" not in t and t.get("response") is None)
        )
        timeout_rate = timed_out / len(trial_data)
    else:
        timeout_rate = 1.0
    checks.append({
        "name": "low_timeout_rate",
        "passed": timeout_rate < 0.20,
        "detail": f"Timeout rate: {timeout_rate:.1%}",
    })

    if trial_data:
        if response_type == "slider":
            response_field = params.get("response_field", "response")
            slider_min, slider_max = params.get("slider_range", [0, 100])
            valid_responses = sum(
                1 for t in trial_data
                if t.get(response_field) is not None
                and slider_min <= t.get(response_field, -1) <= slider_max
            )
        elif response_type == "text_input":
            # Typed-text tasks: accept any string response (including empty) or
            # an explicit timeout. The actual content is scored at L2/L3.
            valid_responses = sum(
                1 for t in trial_data
                if isinstance(t.get("response"), str) or t.get("timed_out", False)
            )
        else:
            valid_keys = set(params.get("response_keys", []))
            valid_responses = sum(
                1 for t in trial_data
                if t.get("response") in valid_keys or t.get("response") is None
            )
        valid_rate = valid_responses / len(trial_data)
    else:
        valid_rate = 0
    checks.append({
        "name": "valid_responses",
        "passed": valid_rate >= 0.80,
        "detail": f"Valid response rate: {valid_rate:.1%}",
    })

    if trial_data:
        # Defensive int() — some custom plugins emit string trial_index, which
        # crashes max() with TypeError and 500s the whole /api/evaluate.
        def _as_int(v) -> int:
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0
        max_trial_idx = max(_as_int(t.get("trial_index", 0)) for t in trial_data)
        completed = max_trial_idx >= expected_trials * 0.8
    else:
        max_trial_idx = 0
        completed = False
    checks.append({
        "name": "experiment_completed",
        "passed": completed,
        "detail": f"Max trial index: {max_trial_idx}",
    })

    score = sum(1 for c in checks if c["passed"]) / len(checks) if checks else 0.0

    return {"score": score, "checks": checks}
