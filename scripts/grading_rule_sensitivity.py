"""Does any conclusion depend on Level 3's 1 / 0.5 / 0 grading rule?

Regrades every testable signature observation under three alternative rules,
recomputes each session's weighted L3 and composite from the stored L1/L2, and
reports the panel and floor means, their gap, and the model ranking. The
``current`` rule must reproduce the stored scores exactly; the script refuses
to report otherwise, so the other rows are known to differ only in the rule.

Read-only over ``results/``; nothing is re-scored or re-run.

    python -m scripts.grading_rule_sensitivity
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from scoring.composite_score import composite_value
from scripts.analyze_repeats import _bool, _f, is_measurable

REPO_ROOT = Path(__file__).resolve().parent.parent
PANEL = REPO_ROOT / "results" / "rebuttal_v1"
FLOOR = REPO_ROOT / "results" / "random_floor"
W = (0.15, 0.35, 0.50)


def _six_bins(p: float) -> float:
    for cut, g in ((0.01, 1.0), (0.05, 0.8), (0.10, 0.6), (0.20, 0.4), (0.50, 0.2)):
        if p < cut:
            return g
    return 0.0


# Each rule grades a direction-correct observation from its one-sided p or its
# effect size; a wrong-direction observation scores 0 under every rule.
RULES = {
    "current 1 / 0.5 / 0": lambda p, e: 1.0 if p < 0.05 else 0.5,
    "six bins on p": lambda p, e: _six_bins(p),
    "continuous in p": lambda p, e: max(0.0, 1.0 - 2.0 * p),
    "continuous in effect size": lambda p, e: min(2.0 * abs(e), 1.0),
}


def grade(rule, s: dict) -> float:
    p, e = _f(s["p_value"]), _f(s["effect_size"])
    # A constant outcome (no statistic) is scored 0 by the scorer under every rule.
    if p is None or e is None:
        return float(s["score"])
    return rule(p, e) if _bool(s["direction_correct"]) else 0.0


def weights() -> dict[tuple[str, str], float]:
    out = {}
    for spec in (REPO_ROOT / "tasks").glob("*/scoring/level3_signatures.json"):
        for sig in json.load(open(spec))["signatures"]:
            out[(spec.parent.parent.name, sig["name"])] = sig.get("weight", 1.0)
    return out


def sessions(base: Path, w: dict) -> list[dict]:
    sigs = defaultdict(list)
    for s in csv.DictReader(open(base / "signatures.csv")):
        if _bool(s["testable"]):
            sigs[(s["sweep"], s["repeat_index"], s["model_id"], s["task_id"])].append(s)
    out = []
    for r in csv.DictReader(open(base / "runs.csv")):
        if not is_measurable(r):
            continue
        key = (r["sweep"], r["repeat_index"], r["model_id"], r["task_id"])
        r["_sigs"] = [(w[(r["task_id"], s["signature"])], s) for s in sigs[key]]
        out.append(r)
    return out


def l3(r: dict, rule) -> float:
    return (sum(wt * grade(rule, s) for wt, s in r["_sigs"])
            / sum(wt for wt, _ in r["_sigs"]))


def composite(r: dict, l3v: float) -> float:
    # The scorer's own rule, so a task with no Level 2 is reweighted as it was scored.
    return composite_value(float(r["l1"]), _f(r["l2"]), l3v, W)


def main() -> int:
    w = weights()
    panel, floor = sessions(PANEL, w), sessions(FLOOR, w)

    bad = [r for r in panel + floor
           if not math.isclose(l3(r, RULES["current 1 / 0.5 / 0"]), float(r["l3"]), abs_tol=1e-3)]
    if bad:
        print(f"current rule fails to reproduce stored L3 in {len(bad)} sessions", file=sys.stderr)
        return 1

    print(f"panel n={len(panel)} measurable sessions, floor n={len(floor)}")
    print(f"{'rule':27s} {'floor L3':>8s} {'panel L3':>8s} {'L3 gap':>7s} {'comp gap':>8s}  ranking")
    for name, rule in RULES.items():
        fl = [l3(r, rule) for r in floor]
        pl = [l3(r, rule) for r in panel]
        fc = statistics.mean(composite(r, v) for r, v in zip(floor, fl))
        pc = statistics.mean(composite(r, v) for r, v in zip(panel, pl))
        by_model = defaultdict(list)
        for r, v in zip(panel, pl):
            by_model[r["model_id"]].append(composite(r, v))
        rank = " > ".join(sorted(by_model, key=lambda m: -statistics.mean(by_model[m])))
        print(f"{name:27s} {statistics.mean(fl):8.3f} {statistics.mean(pl):8.3f} "
              f"{statistics.mean(pl) - statistics.mean(fl):7.3f} {pc - fc:8.2f}  {rank}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
