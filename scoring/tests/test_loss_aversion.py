from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_loss_aversion_l1(human_like_loss_aversion_data, loss_aversion_config):
    result = score_completion(human_like_loss_aversion_data, loss_aversion_config)
    assert result["score"] == 1.0


def test_human_like_loss_aversion_l2(human_like_loss_aversion_data, loss_aversion_metrics):
    result = score_accuracy(human_like_loss_aversion_data, loss_aversion_metrics)
    assert 0.1 < result["score"] < 0.9


def test_loss_aversion_effect_detected(human_like_loss_aversion_data, loss_aversion_signatures):
    result = score_behavioral(human_like_loss_aversion_data, loss_aversion_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "loss_aversion_effect")
    assert sig["direction_correct"]
    assert sig["score"] >= 0.5


def test_status_quo_bias_detected(human_like_loss_aversion_data, loss_aversion_signatures):
    result = score_behavioral(human_like_loss_aversion_data, loss_aversion_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "status_quo_bias")
    assert sig["direction_correct"]


def test_random_loss_aversion_low_behavioral(random_loss_aversion_data, loss_aversion_signatures):
    result = score_behavioral(random_loss_aversion_data, loss_aversion_signatures)
    assert result["score"] <= 0.7


def test_empty_loss_aversion_data(loss_aversion_config, loss_aversion_metrics, loss_aversion_signatures):
    l1 = score_completion([], loss_aversion_config)
    l2 = score_accuracy([], loss_aversion_metrics)
    l3 = score_behavioral([], loss_aversion_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
