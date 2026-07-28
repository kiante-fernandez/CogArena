"""Shared result vocabulary for the L3 analysis templates.

A template returns a dict describing one statistical test.
``scoring.level3_behavioral._grade`` reads that dict and decides whether the
signature is scored, excluded, or an error. The two sides agree on a small set
of string constants, and they must agree *exactly*: a template that reports an
undefined statistic without a recognised ``undefined_reason`` raises out of
``_grade``, which is caught as ``test_raised``, which sets ``n_errors``, which
makes ``build_results`` mark the whole cell unmeasurable, which drops the run
from every mean and from the bootstrap.

One typo therefore deletes runs from the reported tables, silently. Importing
these names instead of retyping the literals turns that typo into an
ImportError at module load.
"""

# Which side of the relation went constant. The distinction is load-bearing:
# a constant predictor means the design never varied, so nothing about the
# agent follows and the signature is excluded; a constant outcome means the
# agent answered identically whatever the manipulation did, which IS the
# absence of the signature and scores 0.0.
CONSTANT_PREDICTOR = "constant_predictor"
CONSTANT_OUTCOME = "constant_outcome"

# The task's trial allocation cannot reach threshold_p even under a perfect
# result, so no behaviour could pass. A distinct reason rather than a detail
# string: it is the difference between "this run was too short" and "this
# signature is unpassable by construction", and the second is a spec defect.
UNDERPOWERED = "underpowered"


def insufficient(detail: str) -> dict:
    """Not enough data survived filtering for the test to run at all.

    ``p_value``/``effect_size`` are inert placeholders — ``testable: False``
    is what ``_grade`` branches on — but they are filled so that a caller
    reading the raw result never sees a missing key.
    """
    return {
        "direction_correct": False,
        "p_value": 1.0,
        "effect_size": 0.0,
        "testable": False,
        "detail": detail,
    }


def underpowered(best_p: float, threshold: float, detail: str) -> dict:
    """No behaviour could clear ``threshold`` at this trial allocation.

    Reported as untestable rather than scored, because a score here would
    describe the task's trial budget as a property of the agent. Carries its own
    ``untestable_reason`` so callers can separate it from genuinely sparse data
    without string-matching the prose — ``moral_machine/intervention_aversion``
    (n=4, best attainable p=0.0625) shipped for a whole study on the wrong side
    of that distinction.
    """
    return {
        "direction_correct": False,
        "p_value": 1.0,
        "effect_size": 0.0,
        "testable": False,
        "untestable_reason": UNDERPOWERED,
        "detail": f"Underpowered: {detail} best attainable p={best_p:.4f} > "
                  f"threshold_p={threshold}. No behaviour could pass.",
    }


def undefined(reason: str, detail: str) -> dict:
    """The test ran but its statistic is undefined (zero variance somewhere).

    ``testable: True`` because the data were adequate; it is the statistic that
    does not exist. ``_grade`` uses ``reason`` to decide exclude-vs-score-zero.
    """
    if reason not in (CONSTANT_PREDICTOR, CONSTANT_OUTCOME):
        raise ValueError(f"unrecognised undefined_reason: {reason!r}")
    return {
        "direction_correct": False,
        "p_value": float("nan"),
        "effect_size": float("nan"),
        "testable": True,
        "undefined_reason": reason,
        "detail": detail,
    }


def constant_side(predictor: tuple[str, list] | None,
                  outcome: tuple[str, list]) -> dict | None:
    """Return an ``undefined`` result if either side has zero variance.

    ``None`` when both vary, so callers read as::

        if (undef := constant_side((field_x, xs), (field_y, ys))):
            return undef

    Pass ``predictor=None`` where the predictor is group membership and so
    varies by construction. The predictor takes precedence: if the design never
    varied, the outcome being constant too says nothing extra.
    """
    x_constant = predictor is not None and len(set(predictor[1])) < 2
    y_constant = len(set(outcome[1])) < 2
    if not (x_constant or y_constant):
        return None
    if x_constant:
        name, values = predictor
        return undefined(CONSTANT_PREDICTOR, f"{name} constant at {values[0]!r}")
    name, values = outcome
    return undefined(CONSTANT_OUTCOME,
                     f"{name} constant at {values[0]!r} across n={len(values)}")
