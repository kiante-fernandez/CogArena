"""What L3 excludes from its denominator, and what it must not.

Every widening of the untestable exemption raises L3 for whichever agent
behaved worst, because a degenerate policy produces more undefined statistics
than a competent one. These tests pin the boundary: a failed *measurement* is
excluded, a failed *agent* is scored 0.0, and a defect in this repository
raises instead of quietly shrinking the denominator.
"""
import json
import pathlib

import pytest

from scoring.level3_behavioral import (
    SignatureSpecError,
    score_behavioral,
    validate_signatures_spec,
)

CORRELATION_SIG = {
    "name": "similarity_aids_recall",
    "test": "correlation_test",
    "field_x": "similarity_level",
    "field_y": "correct",
    "expected_direction": "positive",
    "threshold_p": 0.05,
    "weight": 1.5,
}


def _spec(*sigs):
    return {"signatures": list(sigs)}


# --------------------------------------------------------------------------
# Spec defects must fail loudly, never inflate.
# --------------------------------------------------------------------------

def test_unknown_test_name_raises_rather_than_dropping_the_signature():
    """A typo used to score the session as if the signature did not exist.

    Dropping it from the denominator raises L3 for every session scored against
    the broken spec — silently, and by an amount that depends on how the rest of
    the signatures happened to score.
    """
    bad = dict(CORRELATION_SIG, test="corelation_test")
    with pytest.raises(SignatureSpecError, match="unknown test type"):
        score_behavioral([{"similarity_level": 1, "correct": 1}] * 20, _spec(bad))


def test_missing_threshold_p_raises_at_validation_not_mid_scoring():
    bad = {k: v for k, v in CORRELATION_SIG.items() if k != "threshold_p"}
    with pytest.raises(SignatureSpecError, match="threshold_p"):
        score_behavioral([{"similarity_level": 1, "correct": 1}] * 20, _spec(bad))


def test_every_shipped_spec_validates():
    """Guards against a task shipping a spec whose signatures never run."""
    root = pathlib.Path(__file__).resolve().parents[2] / "tasks"
    specs = sorted(root.glob("*/scoring/level3_signatures.json"))
    assert specs, "no signature specs discovered"
    for path in specs:
        validate_signatures_spec(json.loads(path.read_text()))


def test_a_broken_signature_is_counted_in_n_errors_not_absorbed():
    """A template that raises must be visible, not absorbed.

    n_errors is what marks the cell unmeasurable downstream; without it the
    session reports a normal-looking L3 computed over a set we broke. The
    session itself must survive — one bad signature is not grounds for 500-ing
    an entire evaluation.
    """
    sig = dict(CORRELATION_SIG, expected_direction="sideways", method="kendall")
    result = score_behavioral(
        [{"similarity_level": i % 3, "correct": i % 2} for i in range(30)], _spec(sig))
    assert result["n_errors"] == 1
    assert result["signatures"][0]["untestable_reason"] == "test_raised"
    assert result["score"] == 0.0  # nothing testable remained, not a floor score


# --------------------------------------------------------------------------
# A constant OUTCOME is behaviour: score it 0.0.
# --------------------------------------------------------------------------

def test_constant_outcome_scores_zero_and_stays_in_the_denominator():
    """The agent answered identically at every level of the manipulation.

    The design varied and the agent did not respond to it, which is exactly the
    absence of the signature. Excluding it would hand a free pass to the most
    degenerate policy — an agent that recalls nothing has zero variance in
    `correct`, so it would escape the very test it failed.
    """
    trials = [{"similarity_level": i % 3, "correct": 0} for i in range(30)]
    result = score_behavioral(trials, _spec(CORRELATION_SIG))
    assert result["n_testable"] == 1
    assert result["n_untestable"] == 0
    assert result["score"] == 0.0
    assert result["signatures"][0]["testable"] is True


def test_constant_predictor_is_untestable():
    """The design never varied, so nothing about the agent follows."""
    trials = [{"similarity_level": 1, "correct": i % 2} for i in range(30)]
    result = score_behavioral(trials, _spec(CORRELATION_SIG))
    assert result["n_testable"] == 0
    assert result["signatures"][0]["untestable_reason"] == "constant_predictor"


def test_constant_predictor_takes_precedence_over_constant_outcome():
    trials = [{"similarity_level": 1, "correct": 0} for _ in range(30)]
    result = score_behavioral(trials, _spec(CORRELATION_SIG))
    assert result["signatures"][0]["untestable_reason"] == "constant_predictor"


def test_a_real_effect_still_scores():
    trials = [{"similarity_level": i % 3, "correct": 1 if i % 3 == 2 else 0}
              for i in range(30)]
    result = score_behavioral(trials, _spec(CORRELATION_SIG))
    assert result["score"] == 1.0
    assert result["n_errors"] == 0


def test_degenerate_agent_does_not_outscore_a_partial_one():
    """The property the exemption boundary exists to protect.

    An agent that answers nothing must not end up with a higher L3 than one that
    shows a weak but real effect, purely because its own uniformity made the
    statistic undefined.
    """
    degenerate = [{"similarity_level": i % 3, "correct": 0} for i in range(30)]
    partial = [{"similarity_level": i % 3, "correct": 1 if i % 3 == 2 else 0}
               for i in range(30)]
    assert (score_behavioral(degenerate, _spec(CORRELATION_SIG))["score"]
            < score_behavioral(partial, _spec(CORRELATION_SIG))["score"])


# --------------------------------------------------------------------------
# Coverage reporting — what callers use to exclude unmeasured cells.
# --------------------------------------------------------------------------

def test_all_untestable_reports_zero_coverage_not_a_floor_score():
    trials = [{"similarity_level": 1, "correct": i % 2} for i in range(30)]
    result = score_behavioral(trials, _spec(CORRELATION_SIG))
    # score is 0.0 only to keep the composite's return type stable; n_testable
    # is the field a caller must branch on.
    assert result["n_testable"] == 0
    assert result["coverage"] == 0.0
