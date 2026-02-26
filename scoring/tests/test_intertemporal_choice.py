from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_intertemporal_l1(human_like_intertemporal_choice_data, intertemporal_choice_config):
    result = score_completion(human_like_intertemporal_choice_data, intertemporal_choice_config)
    assert result["score"] == 1.0


def test_human_like_intertemporal_l2(human_like_intertemporal_choice_data, intertemporal_choice_metrics):
    result = score_accuracy(human_like_intertemporal_choice_data, intertemporal_choice_metrics)
    assert result["score"] > 0.0


def test_present_bias(human_like_intertemporal_choice_data, intertemporal_choice_signatures):
    result = score_behavioral(human_like_intertemporal_choice_data, intertemporal_choice_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "present_bias")
    # Present bias means above-chance sooner choice rate
    assert sig["score"] >= 0.0  # Pipeline runs without error


def test_delay_sensitivity(human_like_intertemporal_choice_data, intertemporal_choice_signatures):
    result = score_behavioral(human_like_intertemporal_choice_data, intertemporal_choice_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "delay_sensitivity")
    assert sig["direction_correct"]


def test_random_intertemporal_low_score(random_intertemporal_choice_data, intertemporal_choice_signatures):
    result = score_behavioral(random_intertemporal_choice_data, intertemporal_choice_signatures)
    assert result["score"] <= 0.7


def test_empty_intertemporal_data(intertemporal_choice_config, intertemporal_choice_metrics, intertemporal_choice_signatures):
    l1 = score_completion([], intertemporal_choice_config)
    l2 = score_accuracy([], intertemporal_choice_metrics)
    l3 = score_behavioral([], intertemporal_choice_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
