WEIGHTS = {
    "l1_completion": 0.15,
    "l2_accuracy": 0.35,
    "l3_behavioral": 0.50,
}
DEFAULT_WEIGHTS = (WEIGHTS["l1_completion"], WEIGHTS["l2_accuracy"], WEIGHTS["l3_behavioral"])


def effective_weights(l2_score: float | None,
                      weights: tuple[float, float, float] = DEFAULT_WEIGHTS) -> tuple[float, float, float]:
    """The (w1, w2, w3) a task is actually scored with.

    A task with no Level 2 metric (l2_score None) splits L2's weight over L1 and
    L3 in proportion, so its composite stays on the same 0-100 scale as every
    other task's. Scripts that recompute composites under other weights call
    this too, so the rule lives in one place.
    """
    w1, w2, w3 = weights
    if l2_score is None:
        return w1 / (w1 + w3), 0.0, w3 / (w1 + w3)
    return w1, w2, w3


def composite_value(l1_score: float, l2_score: float | None, l3_score: float,
                    weights: tuple[float, float, float] = DEFAULT_WEIGHTS) -> float:
    w1, w2, w3 = effective_weights(l2_score, weights)
    return (w1 * l1_score + w2 * (l2_score or 0.0) + w3 * l3_score) * 100


def compute_composite(l1_score: float, l2_score: float | None, l3_score: float) -> dict:
    w1, w2, w3 = effective_weights(l2_score)
    return {
        "composite_score": round(composite_value(l1_score, l2_score, l3_score), 2),
        "l1_weighted": round(w1 * l1_score * 100, 2),
        "l2_weighted": None if l2_score is None else round(w2 * l2_score * 100, 2),
        "l3_weighted": round(w3 * l3_score * 100, 2),
        "l1_raw": round(l1_score, 4),
        "l2_raw": None if l2_score is None else round(l2_score, 4),
        "l3_raw": round(l3_score, 4),
    }
