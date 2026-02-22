WEIGHTS = {
    "l1_completion": 0.15,
    "l2_accuracy": 0.35,
    "l3_behavioral": 0.50,
}


def compute_composite(l1_score: float, l2_score: float, l3_score: float) -> dict:
    composite = (
        WEIGHTS["l1_completion"] * l1_score
        + WEIGHTS["l2_accuracy"] * l2_score
        + WEIGHTS["l3_behavioral"] * l3_score
    ) * 100

    return {
        "composite_score": round(composite, 2),
        "l1_weighted": round(WEIGHTS["l1_completion"] * l1_score * 100, 2),
        "l2_weighted": round(WEIGHTS["l2_accuracy"] * l2_score * 100, 2),
        "l3_weighted": round(WEIGHTS["l3_behavioral"] * l3_score * 100, 2),
        "l1_raw": round(l1_score, 4),
        "l2_raw": round(l2_score, 4),
        "l3_raw": round(l3_score, 4),
    }
