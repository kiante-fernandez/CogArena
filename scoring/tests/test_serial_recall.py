from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_serial_recall_l1(human_like_serial_recall_data, serial_recall_config):
    result = score_completion(human_like_serial_recall_data, serial_recall_config)
    assert result["score"] == 1.0


def test_human_like_serial_recall_l2(human_like_serial_recall_data, serial_recall_metrics):
    result = score_accuracy(human_like_serial_recall_data, serial_recall_metrics)
    assert result["score"] > 0.0


def test_primacy_effect(human_like_serial_recall_data, serial_recall_signatures):
    result = score_behavioral(human_like_serial_recall_data, serial_recall_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "primacy_effect")
    assert sig["direction_correct"]


def test_recency_effect(human_like_serial_recall_data, serial_recall_signatures):
    result = score_behavioral(human_like_serial_recall_data, serial_recall_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "recency_effect")
    assert sig["direction_correct"]


def test_above_chance_recall(human_like_serial_recall_data, serial_recall_signatures):
    result = score_behavioral(human_like_serial_recall_data, serial_recall_signatures)
    sig = next(s for s in result["signatures"] if s["name"] == "above_chance_recall")
    assert sig["direction_correct"]


def test_random_serial_recall_low_score(random_serial_recall_data, serial_recall_signatures):
    result = score_behavioral(random_serial_recall_data, serial_recall_signatures)
    # With low base recall and no primacy/recency boost, signatures should not pass
    assert result["score"] <= 0.7


def test_empty_serial_recall_data(serial_recall_config, serial_recall_metrics, serial_recall_signatures):
    l1 = score_completion([], serial_recall_config)
    l2 = score_accuracy([], serial_recall_metrics)
    l3 = score_behavioral([], serial_recall_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
