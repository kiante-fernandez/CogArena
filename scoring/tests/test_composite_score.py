import pytest

from scoring.composite_score import composite_value, compute_composite, effective_weights


def test_task_without_level2_stays_on_the_0_100_scale():
    """L2's weight is split over L1 and L3 in proportion, not dropped."""
    assert compute_composite(1.0, None, 1.0)["composite_score"] == 100.0
    assert compute_composite(0.0, None, 1.0)["composite_score"] == round(100 * 0.50 / 0.65, 2)
    c = compute_composite(0.4, None, 0.2)
    assert c["l2_raw"] is None and c["l2_weighted"] is None
    assert c["l1_weighted"] + c["l3_weighted"] == pytest.approx(c["composite_score"], abs=0.02)


def test_task_with_level2_is_scored_as_before():
    assert compute_composite(1.0, 0.5, 0.25)["composite_score"] == round(
        100 * (0.15 * 1.0 + 0.35 * 0.5 + 0.50 * 0.25), 2)


def test_alternative_weights_follow_the_same_rule():
    """The weight-sensitivity analyses reuse this rule rather than re-deriving it."""
    assert effective_weights(None, (0.0, 0.0, 1.0)) == (0.0, 0.0, 1.0)
    assert composite_value(0.4, None, 0.8, (0.2, 0.4, 0.4)) == pytest.approx(
        100 * (0.2 * 0.4 + 0.4 * 0.8) / 0.6)
