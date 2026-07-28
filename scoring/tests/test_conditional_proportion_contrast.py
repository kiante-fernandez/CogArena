"""Tests for the conditional-proportion contrast used by reciprocity signatures.

The template replaced a Pearson correlation that was undefined against a
deterministic opponent. The properties that matter are: it discriminates a
reciprocating agent from a random one, it stays defined when a policy is
constant, and it reports "cannot tell" rather than "failed" when a conditioning
bin is empty.
"""
import pytest

from scoring.analysis_templates.conditional_proportion_contrast import (
    run_conditional_proportion_contrast,
)

SPEC = {
    "field": "player_cooperate",
    "condition_field": "prev_opp_coop_pd",
    "filter": {"timed_out": False, "game": "pd"},
    "expected_direction": "positive",
}


def _trials(pairs):
    """pairs: list of (prev_opp_coop, player_cooperate)."""
    return [
        {"game": "pd", "timed_out": False,
         "prev_opp_coop_pd": cond, "player_cooperate": coop}
        for cond, coop in pairs
    ]


def test_reciprocator_is_detected():
    data = _trials([(True, True)] * 11 + [(True, False)] + [(False, False)] * 2)
    r = run_conditional_proportion_contrast(data, SPEC)
    assert r["testable"] is True
    assert r["direction_correct"] is True
    assert r["p_value"] < 0.05
    assert r["effect_size"] > 0.9


def test_no_difference_does_not_pass():
    data = _trials([(True, True)] * 6 + [(True, False)] * 6
                   + [(False, True)] * 3 + [(False, False)] * 3)
    r = run_conditional_proportion_contrast(data, SPEC)
    assert r["testable"] is True
    assert r["p_value"] > 0.05


def test_anti_reciprocator_scores_wrong_direction():
    data = _trials([(True, False)] * 8 + [(False, True)] * 6)
    r = run_conditional_proportion_contrast(data, SPEC)
    assert r["testable"] is True
    assert r["direction_correct"] is False
    assert r["effect_size"] < 0


def test_constant_policy_stays_defined():
    """The exact failure of the old Pearson test: zero variance in the outcome.

    An always-cooperating agent has no variance in player_cooperate, which made
    the correlation return nan. The contrast is still well defined — it simply
    finds no difference, which is the honest answer.
    """
    data = _trials([(True, True)] * 10 + [(False, True)] * 4)
    r = run_conditional_proportion_contrast(data, SPEC)
    assert r["testable"] is True
    assert r["p_value"] == pytest.approx(1.0, abs=0.01)
    assert r["effect_size"] == pytest.approx(0.0, abs=1e-9)


def test_empty_bin_is_untestable_not_failed():
    """An agent that never elicits a defection cannot be assessed for reciprocity.

    Reporting 'untestable' matters: scoring 0 would assert the agent lacks
    reciprocity on evidence that cannot speak to it either way.
    """
    data = _trials([(True, True)] * 12)
    r = run_conditional_proportion_contrast(data, SPEC)
    assert r["testable"] is False
    assert "unidentifiable" in r["detail"]


def test_filter_is_applied():
    data = _trials([(True, True)] * 11 + [(True, False)] + [(False, False)] * 2)
    data += [{"game": "bos", "timed_out": False,
              "prev_opp_coop_pd": False, "player_cooperate": True}] * 20
    r = run_conditional_proportion_contrast(data, SPEC)
    # The 20 BoS rows must be excluded; including them would flip the direction.
    assert r["direction_correct"] is True
    assert "n=2" in r["detail"]


def test_bins_too_small_to_ever_pass_are_untestable_not_scored():
    """A 2-vs-2 split cannot reach p<0.05 even under perfect separation.

    Best attainable one-sided Fisher p is 0.167 there, so scoring such a
    signature reports a property of the task's trial allocation as a property of
    the agent — the failure `proportion_test._best_attainable_p` already guards
    against. An agent reciprocating flawlessly in these bins must be reported as
    unmeasured, not as scoring 0.5.
    """
    data = _trials([(True, True)] * 2 + [(False, False)] * 2)
    r = run_conditional_proportion_contrast(data, {**SPEC, "threshold_p": 0.05})
    assert r["testable"] is False
    assert "Underpowered" in r["detail"]
    assert "0.1667" in r["detail"]


def test_three_versus_three_is_the_boundary_case():
    """3-vs-3 gives exactly p=0.0500, which is not < 0.05."""
    data = _trials([(True, True)] * 3 + [(False, False)] * 3)
    r = run_conditional_proportion_contrast(data, {**SPEC, "threshold_p": 0.05})
    assert r["testable"] is False, "p=0.05 is not < 0.05"

    # ...but it passes at a threshold that admits it.
    r = run_conditional_proportion_contrast(data, {**SPEC, "threshold_p": 0.10})
    assert r["testable"] is True
    assert r["direction_correct"] is True


def test_adequately_powered_bins_still_score():
    """The check must not swallow signatures that can genuinely be tested."""
    data = _trials([(True, True)] * 5 + [(False, False)] * 5)
    r = run_conditional_proportion_contrast(data, {**SPEC, "threshold_p": 0.05})
    assert r["testable"] is True
    assert r["p_value"] < 0.05
