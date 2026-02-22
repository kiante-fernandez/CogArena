from scoring.level3_behavioral import score_behavioral


def test_stroop_effect_detected_in_human_like_data(human_like_stroop_data, stroop_signatures):
    result = score_behavioral(human_like_stroop_data, stroop_signatures)
    rt_sig = next(s for s in result["signatures"] if s["name"] == "stroop_interference_rt")
    assert rt_sig["direction_correct"]
    assert rt_sig["score"] >= 0.5


def test_no_stroop_effect_in_random_data(random_stroop_data, stroop_signatures):
    result = score_behavioral(random_stroop_data, stroop_signatures)
    rt_sig = next(s for s in result["signatures"] if s["name"] == "stroop_interference_rt")
    assert rt_sig["score"] <= 0.5


def test_post_error_slowing_detected(human_like_stroop_data, stroop_signatures):
    result = score_behavioral(human_like_stroop_data, stroop_signatures)
    pes_sig = next(s for s in result["signatures"] if s["name"] == "post_error_slowing")
    assert pes_sig["direction_correct"]
    assert pes_sig["score"] >= 0.5


def test_overall_score_higher_for_human_like(human_like_stroop_data, random_stroop_data, stroop_signatures):
    human_result = score_behavioral(human_like_stroop_data, stroop_signatures)
    random_result = score_behavioral(random_stroop_data, stroop_signatures)
    assert human_result["score"] >= random_result["score"]


def test_empty_data_handled(stroop_signatures):
    result = score_behavioral([], stroop_signatures)
    assert result["score"] == 0.0
    for sig in result["signatures"]:
        assert sig["score"] == 0.0
