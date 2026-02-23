from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral


def test_human_like_dictator_l1(human_like_dictator_data, dictator_config):
    result = score_completion(human_like_dictator_data, dictator_config)
    assert result["score"] == 1.0


def test_human_like_dictator_l2(human_like_dictator_data, dictator_metrics):
    result = score_accuracy(human_like_dictator_data, dictator_metrics)
    assert result["score"] > 0.0


def test_nonzero_giving(human_like_dictator_data, dictator_signatures):
    result = score_behavioral(human_like_dictator_data, dictator_signatures)
    give_sig = next(s for s in result["signatures"] if s["name"] == "nonzero_giving")
    assert give_sig["direction_correct"]


def test_random_dictator_pipeline(random_dictator_data, dictator_config, dictator_metrics, dictator_signatures):
    """Pipeline runs without errors on random data."""
    l1 = score_completion(random_dictator_data, dictator_config)
    l2 = score_accuracy(random_dictator_data, dictator_metrics)
    l3 = score_behavioral(random_dictator_data, dictator_signatures)
    assert l1["score"] == 1.0  # random data still has correct trial count


def test_empty_dictator_data(dictator_config, dictator_metrics, dictator_signatures):
    l1 = score_completion([], dictator_config)
    l2 = score_accuracy([], dictator_metrics)
    l3 = score_behavioral([], dictator_signatures)
    assert l1["score"] == 0.0
    assert l2["score"] == 0.0
    assert l3["score"] == 0.0
