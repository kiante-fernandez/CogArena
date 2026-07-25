"""Turn repeated sessions into the stability evidence the reviews asked for.

The submitted paper reports one session per cell, so every number is a point
estimate with no measure of run-to-run variation. Given repeats, this produces
the four artifacts the AC and reviewers named:

1. ``cell_stability.csv`` — per (model, task): completion rate and mean/SD of
   composite, L1, L2, L3 across repeats.
2. ``signature_pass_rates.csv`` — per (model, task, signature): k/n pass rate
   with a Wilson 95% interval. Wilson rather than normal-approximation because
   these rates sit at 0 and 1 constantly, where the normal interval is nonsense.
3. ``l3_zero_flips.csv`` — cells whose L3 is zero on some runs and non-zero on
   others. This is the literal question asked in review: "how often does a
   per-cell L3 of zero flip to a pass across re-runs?"
4. ``rank_stability.csv`` — bootstrap over repeats showing how often each model
   takes each rank, under BOTH averaging conventions. The submitted paper's top
   two reverse between the two conventions; this quantifies whether either
   ordering is distinguishable from noise.

Usage::

    python -m scripts.analyze_repeats --results results/rebuttal_v1
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("analyze_repeats")

# Fixed so the reported bootstrap is reproducible from the committed data.
BOOTSTRAP_SEED = 20260724
N_BOOTSTRAP = 2000


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Chosen over the normal approximation because pass rates here are routinely
    0/n or n/n, where the normal interval has zero width and is simply wrong.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _f(x: Any) -> float | None:
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _bool(x: Any) -> bool:
    return str(x).strip().lower() in ("true", "1", "yes")


def _read(path: Path) -> list[dict[str, str]]:
    with open(path) as f:
        return list(csv.DictReader(f))


def _stats(vals: list[float]) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    return statistics.mean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


def cell_stability(runs: list[dict]) -> list[dict]:
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in runs:
        cells[(r["model_id"], r["task_id"])].append(r)

    out = []
    for (model, task), rs in sorted(cells.items()):
        scored = [r for r in rs if _bool(r["scored"])]
        complete = [r for r in rs if _bool(r["l1_complete"])]
        row = {
            "model_id": model, "task_id": task,
            "n_attempts": len(rs),
            "n_scored": len(scored),
            "n_complete": len(complete),
            "completion_rate": round(len(complete) / len(rs), 4) if rs else None,
        }
        for lvl in ("composite", "l1", "l2", "l3"):
            vals = [v for v in (_f(r[lvl]) for r in scored) if v is not None]
            m, sd = _stats(vals)
            row[f"{lvl}_mean"] = round(m, 4) if m is not None else None
            row[f"{lvl}_sd"] = round(sd, 4) if sd is not None else None
            row[f"{lvl}_min"] = round(min(vals), 4) if vals else None
            row[f"{lvl}_max"] = round(max(vals), 4) if vals else None
        out.append(row)
    return out


def signature_pass_rates(sigs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for s in sigs:
        groups[(s["model_id"], s["task_id"], s["signature"])].append(s)

    out = []
    for (model, task, sig), ss in sorted(groups.items()):
        n = len(ss)
        k = sum(1 for s in ss if _bool(s["passed"]))
        lo, hi = wilson(k, n)
        eff = [v for v in (_f(s["effect_size"]) for s in ss) if v is not None]
        out.append({
            "model_id": model, "task_id": task, "signature": sig,
            "n": n, "k_passed": k,
            "pass_rate": round(k / n, 4) if n else None,
            "wilson_lo": round(lo, 4), "wilson_hi": round(hi, 4),
            "effect_size_mean": round(statistics.mean(eff), 4) if eff else None,
            "effect_size_sd": round(statistics.stdev(eff), 4) if len(eff) > 1 else (0.0 if eff else None),
            # A signature that never fires and one that fires sometimes are very
            # different claims; flag the unstable ones explicitly.
            "unstable": 0 < k < n,
        })
    return out


def l3_zero_flips(runs: list[dict]) -> list[dict]:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in runs:
        if not _bool(r["scored"]):
            continue
        v = _f(r["l3"])
        if v is not None:
            cells[(r["model_id"], r["task_id"])].append(v)

    out = []
    for (model, task), vals in sorted(cells.items()):
        zeros = sum(1 for v in vals if v == 0.0)
        if not vals or zeros == 0 or zeros == len(vals):
            continue  # never zero, or always zero — no flip to report
        out.append({
            "model_id": model, "task_id": task,
            "n_scored": len(vals),
            "n_l3_zero": zeros,
            "n_l3_nonzero": len(vals) - zeros,
            "flip_rate": round((len(vals) - zeros) / len(vals), 4),
            "l3_max": round(max(vals), 4),
            "note": "a single session would have reported one of these at random",
        })
    return out


def rank_stability(runs: list[dict], n_boot: int = N_BOOTSTRAP) -> list[dict]:
    """Bootstrap model rankings by resampling whole repeats.

    Repeats are resampled as units (not individual cells) because a repeat is
    the independent replication; resampling cells would treat correlated
    within-session trials as independent, the same error flagged in review.
    """
    rng = random.Random(BOOTSTRAP_SEED)
    by_model_repeat: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in runs:
        by_model_repeat[r["model_id"]][r["repeat_index"]].append(r)
    models = sorted(by_model_repeat)
    if len(models) < 2:
        return []

    # With one repeat per cell, resampling repeats can only return that repeat,
    # so every P(rank) collapses to 0 or 1. That is not certainty, it is the
    # absence of a variance estimate — exactly the flaw the reviews identified.
    # Refuse to emit numbers that would read as confidence.
    max_reps = max(len(v) for v in by_model_repeat.values())
    if max_reps < 2:
        logger.warning(
            "only %d repeat(s) per model: bootstrap is degenerate and would report "
            "P(rank)=1.00 as if certain. Skipping rank_stability.", max_reps)
        return []

    def score(rs: list[dict], zero_fill: bool) -> float | None:
        vals = []
        for r in rs:
            v = _f(r["composite"])
            if _bool(r["scored"]) and v is not None:
                vals.append(v)
            elif zero_fill:
                vals.append(0.0)
        return statistics.mean(vals) if vals else None

    out = []
    for zero_fill in (True, False):
        convention = "failed_cells_as_0" if zero_fill else "ok_cells_only"
        wins: dict[str, list[int]] = {m: [0] * len(models) for m in models}
        point: dict[str, float | None] = {}
        for m in models:
            allr = [r for rs in by_model_repeat[m].values() for r in rs]
            point[m] = score(allr, zero_fill)

        for _ in range(n_boot):
            draw = {}
            for m in models:
                reps = list(by_model_repeat[m])
                picked = [rng.choice(reps) for _ in reps]
                rs = [r for p in picked for r in by_model_repeat[m][p]]
                draw[m] = score(rs, zero_fill)
            ranked = sorted((m for m in models if draw[m] is not None),
                            key=lambda m: -draw[m])
            for pos, m in enumerate(ranked):
                wins[m][pos] += 1

        for m in models:
            row = {
                "convention": convention, "model_id": m,
                "point_estimate": round(point[m], 2) if point[m] is not None else None,
                "p_rank1": round(wins[m][0] / n_boot, 4),
            }
            for pos in range(len(models)):
                row[f"p_rank{pos + 1}"] = round(wins[m][pos] / n_boot, 4)
            out.append(row)
    return out


def _write(path: Path, rows: list[dict]) -> None:
    if not rows:
        logger.info("no rows for %s — skipped", path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("wrote %s (%d rows)", path, len(rows))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="results/rebuttal_v1",
                    help="Directory containing runs.csv and signatures.csv.")
    ap.add_argument("--out", default=None, help="Default: <results>/analysis")
    ap.add_argument("--bootstrap", type=int, default=N_BOOTSTRAP)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")

    res = Path(args.results)
    runs_p, sigs_p = res / "runs.csv", res / "signatures.csv"
    if not runs_p.exists():
        logger.error("missing %s — run scripts.build_results first", runs_p)
        return 2
    runs = _read(runs_p)
    sigs = _read(sigs_p) if sigs_p.exists() else []
    out = Path(args.out) if args.out else res / "analysis"

    cells = cell_stability(runs)
    rates = signature_pass_rates(sigs)
    flips = l3_zero_flips(runs)
    ranks = rank_stability(runs, args.bootstrap)

    _write(out / "cell_stability.csv", cells)
    _write(out / "signature_pass_rates.csv", rates)
    _write(out / "l3_zero_flips.csv", flips)
    _write(out / "rank_stability.csv", ranks)

    n_rep = len({r["repeat_index"] for r in runs})
    print(f"\n{'='*74}\nREPEAT ANALYSIS  ({len(runs)} runs, {n_rep} repeats)\n{'='*74}")

    print("\nCompletion rate by model (fraction of attempts that finished the task):")
    bym: dict[str, list[dict]] = defaultdict(list)
    for c in cells:
        bym[c["model_id"]].append(c)
    for m, cs in sorted(bym.items()):
        att = sum(c["n_attempts"] for c in cs)
        comp = sum(c["n_complete"] for c in cs)
        print(f"   {m:26s} {comp:4d}/{att:<4d} = {comp/att:.0%}" if att else f"   {m:26s}   --")

    unstable = [r for r in rates if r["unstable"]]
    print(f"\nSignatures that fire on some repeats but not others: "
          f"{len(unstable)}/{len(rates)}")
    for r in sorted(unstable, key=lambda x: -abs(x["pass_rate"] - 0.5))[:10]:
        print(f"   {r['model_id']:22s} {r['task_id']:22s} {r['signature']:28s} "
              f"{r['k_passed']}/{r['n']}  [{r['wilson_lo']:.2f},{r['wilson_hi']:.2f}]")

    print(f"\nCells where L3 flips between zero and non-zero across repeats: {len(flips)}")
    for r in flips[:10]:
        print(f"   {r['model_id']:22s} {r['task_id']:22s} "
              f"zero on {r['n_l3_zero']}/{r['n_scored']} runs (max L3 {r['l3_max']})")
    if flips:
        print("   -> each of these would have been reported as a single "
              "point estimate in the submitted paper.")

    for conv in ("failed_cells_as_0", "ok_cells_only"):
        rows = [r for r in ranks if r["convention"] == conv]
        if not rows:
            continue
        print(f"\nRank-1 probability under {conv} ({args.bootstrap} bootstrap resamples):")
        for r in sorted(rows, key=lambda x: -(x["point_estimate"] or 0)):
            print(f"   {r['model_id']:26s} composite={r['point_estimate'] or 0:6.2f}  "
                  f"P(rank 1) = {r['p_rank1']:.2f}")

    print(f"\nTables written to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
