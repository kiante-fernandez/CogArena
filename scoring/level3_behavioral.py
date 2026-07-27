"""Level 3: alignment with canonical task-specific behavioural signatures.

Each signature names a statistical test (run via scoring/analysis_templates/) and
the direction the human literature predicts. A signature scores 1.0 when the
effect is in the predicted direction and significant, 0.5 when the direction is
right but the test does not clear threshold_p, and 0.0 otherwise.

UNTESTABLE SIGNATURES ARE EXCLUDED, NOT ZEROED. A test that could not run — too
few trials after filtering, a predictor that never varied — tells us nothing
about the agent's behaviour. Scoring it 0.0 asserts that the agent failed to
show a human signature, which is a claim the data does not support, and it is
behaviour-dependent in the worst way: an agent that completes less of a task
gets more automatic zeros, which is indistinguishable from a real capability
gap. Untestable signatures are therefore dropped from the weighted mean and
reported separately via ``n_untestable`` / ``untestable_weight`` so a caller can
decide whether the remaining coverage supports a claim at all.

THE EXCLUSION IS NARROW ON PURPOSE, because every widening of it raises L3 for
whichever agent behaved worst. Two cases are explicitly NOT untestable:

* **A spec error** — an unknown test name, a missing ``threshold_p``. That is a
  defect in this repository, not a property of the run, and dropping it from the
  denominator silently raises the score of every session scored against the
  broken spec. Specs are validated up front by :func:`validate_signatures_spec`
  and a bad one raises rather than scoring.
* **A constant outcome** — the agent answered identically on every trial, so the
  outcome has zero variance and the statistic is undefined. The design did vary;
  the agent did not respond to it. That is exactly the absence of the signature,
  and it scores 0.0. Only a constant *predictor* (the design failed to vary, or
  too few trials survived filtering to contain both levels) is untestable.

This changes what L3 means relative to CogArena v1.1.1, where untestable
signatures were scored 0.0 and depressed every agent's L3 — including the random
chance floor, so floor comparisons shift too. Any reported number computed
before this change is not comparable to one computed after it.

"""
import math

from scoring.analysis_templates.paired_ttest import run_paired_ttest, run_paired_proportion_test
from scoring.analysis_templates.sequential_regression import run_sequential_regression
from scoring.analysis_templates.interaction_test import run_interaction_test
from scoring.analysis_templates.proportion_test import run_proportion_test
from scoring.analysis_templates.correlation_test import run_correlation_test
from scoring.analysis_templates.conditional_proportion_contrast import (
    run_conditional_proportion_contrast,
)

TEST_REGISTRY = {
    "paired_ttest_greater": run_paired_ttest,
    "paired_proportion_test": run_paired_proportion_test,
    "sequential_regression": run_sequential_regression,
    "interaction_test": run_interaction_test,
    "proportion_test": run_proportion_test,
    "correlation_test": run_correlation_test,
    "conditional_proportion_contrast": run_conditional_proportion_contrast,
}


def _is_nan(x) -> bool:
    return isinstance(x, float) and math.isnan(x)


def _untestable(sig: dict, reason: str, **extra) -> dict:
    return {
        "name": sig["name"],
        "score": None,
        "testable": False,
        "untestable_reason": reason,
        "weight": sig.get("weight", 1.0),
        **extra,
    }


def _scored(sig: dict, score: float, **extra) -> dict:
    return {
        "name": sig["name"],
        "score": score,
        "testable": True,
        "weight": sig.get("weight", 1.0),
        **extra,
    }


class SignatureSpecError(ValueError):
    """A signature spec in tasks/*/scoring/ is malformed.

    Raised at validation time rather than absorbed per-signature. A spec typo
    that is caught and skipped removes that signature from the L3 denominator,
    which raises the reported score for every session scored against the broken
    spec — a plausible-looking but wrong number, which is the failure mode
    ``level2_accuracy._KNOWN_METRIC_KEYS`` exists to prevent on the L2 side.
    """


def validate_signatures_spec(signatures_spec: dict) -> None:
    """Fail loudly on a malformed signature spec. Called before any scoring."""
    sigs = signatures_spec.get("signatures")
    if not isinstance(sigs, list):
        raise SignatureSpecError("spec has no 'signatures' list")
    for i, sig in enumerate(sigs):
        where = f"signature[{i}]"
        if not isinstance(sig, dict) or "name" not in sig:
            raise SignatureSpecError(f"{where}: missing 'name'")
        where = f"signature {sig['name']!r}"
        if sig.get("test") not in TEST_REGISTRY:
            raise SignatureSpecError(
                f"{where}: unknown test type {sig.get('test')!r}. "
                f"Known: {sorted(TEST_REGISTRY)}")
        # Consumed unguarded when the result is graded; a spec missing it would
        # otherwise surface as a KeyError from deep inside scoring.
        if not isinstance(sig.get("threshold_p"), (int, float)):
            raise SignatureSpecError(f"{where}: missing or non-numeric 'threshold_p'")


# A template that reports an undefined statistic must say which side went
# constant, because the two cases mean opposite things. Anything else is a
# template that has not been updated, and is surfaced as an error rather than
# guessed at — guessing "untestable" would inflate, guessing "absent" would
# penalise a design failure as though it were behaviour.
_UNDEFINED_UNTESTABLE = {"constant_predictor"}   # design never varied
_UNDEFINED_ABSENT = {"constant_outcome"}         # agent never varied


def _grade(sig: dict, result: dict) -> dict:
    # Templates flag insufficient data explicitly; absence means testable,
    # which keeps any template that has not been updated working.
    if result.get("testable", True) is False:
        return _untestable(sig, "insufficient_data", detail=result.get("detail"))

    p_value, effect = result.get("p_value"), result.get("effect_size")
    if p_value is None or _is_nan(p_value) or _is_nan(effect):
        reason = result.get("undefined_reason")
        if reason in _UNDEFINED_UNTESTABLE:
            return _untestable(sig, "constant_predictor", detail=result.get("detail"))
        if reason in _UNDEFINED_ABSENT:
            # Zero variance in the outcome IS the finding: the agent gave the
            # same response regardless of the manipulation, so the human
            # signature is absent. Excluding this would raise L3 for precisely
            # the most degenerate policies.
            return _scored(sig, 0.0, p_value=None, effect_size=None,
                           direction_correct=False,
                           detail=result.get("detail") or "constant outcome — "
                                  "agent did not vary with the manipulation")
        raise ValueError(
            f"{sig['name']}: undefined statistic (p={p_value!r}, effect={effect!r}) "
            f"with undefined_reason={reason!r}; template must declare "
            f"'constant_predictor' or 'constant_outcome'")

    if result["direction_correct"] and p_value < sig["threshold_p"]:
        sig_score = 1.0
    elif result["direction_correct"]:
        sig_score = 0.5
    else:
        sig_score = 0.0

    return _scored(sig, sig_score, p_value=p_value, effect_size=effect,
                   direction_correct=result["direction_correct"],
                   detail=result.get("detail"))


def score_behavioral(trial_data: list[dict], signatures_spec: dict) -> dict:
    validate_signatures_spec(signatures_spec)
    signature_results = []
    n_errors = 0

    for sig in signatures_spec["signatures"]:
        test_func = TEST_REGISTRY[sig["test"]]

        try:
            result = test_func(trial_data, sig)
            # Graded inside the guard so a template returning a malformed dict
            # loses one signature instead of 500-ing the whole session. Such a
            # result is a defect in this repo, so it is counted in n_errors and
            # makes the whole L3 cell non-measurable downstream rather than
            # quietly shrinking the denominator.
            graded = _grade(sig, result)
        except Exception as e:  # noqa: BLE001 — one bad template must not lose the session
            n_errors += 1
            signature_results.append(
                _untestable(sig, "test_raised", error=f"{type(e).__name__}: {e}"))
            continue

        signature_results.append(graded)

    testable = [s for s in signature_results if s.get("testable", True)]
    untestable = [s for s in signature_results if not s.get("testable", True)]
    testable_weight = sum(s["weight"] for s in testable)
    total_weight = sum(s["weight"] for s in signature_results)

    if testable_weight > 0:
        score = sum(s["score"] * s["weight"] for s in testable) / testable_weight
    else:
        # Nothing could be measured. 0.0 keeps the return type stable for the
        # composite, but n_testable == 0 is the field that matters: callers
        # should treat such a cell as unmeasured rather than as a floor score.
        score = 0.0

    return {
        "score": float(score),
        "signatures": signature_results,
        "n_testable": len(testable),
        "n_untestable": len(untestable),
        # Template defects, not properties of the run. Non-zero means this L3 is
        # computed over a denominator this repository broke, so downstream code
        # must treat the cell as unmeasured rather than as a low score.
        "n_errors": n_errors,
        "testable_weight": float(testable_weight),
        "total_weight": float(total_weight),
        # Fraction of the signature set this session could actually speak to.
        "coverage": float(testable_weight / total_weight) if total_weight > 0 else 0.0,
    }
