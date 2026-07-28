"""Moving-block bootstrap over trials: dependence-robust p-values for Level 3.

Most analysis templates compute p under an independence assumption that agent
sessions violate. ``proportion_test`` repairs this with an AR(1)
effective-sample-size correction ``n_eff = n(1-rho)/(1+rho)``; ``correlation_test``
does nothing; ``paired_proportion_test`` uses the bootstrap in production, having
been measured here as the one anti-conservative template. AR(1) is itself a
parametric guess: it assumes dependence decays geometrically with a single rho,
whereas agent traces show runs of repeated actions, mode switches and drift.

The moving-block bootstrap assumes no dependence structure at all. Contiguous
blocks of trials are resampled, so whatever dependence exists *within* a block
of length l is carried along intact while structure across blocks is destroyed.
The spread of the resampled statistic then reflects how much genuinely
independent information the series holds, whatever shape the dependence has.
Because only the statistic function changes, one implementation covers every
template rather than a correction per template.

    p = (1 + #{theta* on the null side}) / (B + 1)

which inverts the percentile confidence interval. Block length defaults to the
standard MBB rule l = n^(1/3); ``--block-rule`` runs the sensitivity check.

Read-only over archived ``trial_data/``: it re-scores nothing and writes only a
CSV. The resampler itself is imported from
``scoring.analysis_templates.block_bootstrap`` — the same code the scorer runs —
so this stays a description of the deployed estimator rather than a second
implementation free to drift from it. Results and interpretation are written up alongside the manuscript, not here.

    python -m scripts.block_bootstrap                       # default l = n^(1/3)
    python -m scripts.block_bootstrap --block-rule fixed10  # sensitivity
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

# The estimator itself comes from the SCORING module, not a copy. The robustness
# table this script produces is published as a description of what actually
# scores, and two implementations would drift apart with nothing to catch it.
from harness.task_sets import V1_TASK_IDS
from scoring.analysis_templates.block_bootstrap import (
    block_index, contrast_resamples, p_from_resamples,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

V1_TASKS = sorted(V1_TASK_IDS)

# (sweep directory, arm) pairs the reported analysis covers.
SWEEPS = [("rebuttal_v1_launch_20260724_211936", "panel"),
          ("rebuttal_v1_batch2_20260725_150651", "panel"),
          ("rebuttal_v1_launch_20260724_211936_retry", "panel"),
          ("random_floor_v12_20260726_201120", "floor")]

# "n13" is the scoring module's own default_block_length; the others exist only
# to show the conclusion is stable across block lengths.
BLOCK_RULES = {
    "n13": lambda n: n ** (1 / 3),      # standard MBB rule, = the deployed rule
    "2n13": lambda n: 2 * n ** (1 / 3),
    "n12": lambda n: n ** 0.5,
    "fixed10": lambda n: 10.0,
}

B_DEFAULT = 2000


# --------------------------------------------------------------- extraction
def _filtered(trials, spec_filter):
    return [t for t in trials
            if all(t.get(k) == v for k, v in (spec_filter or {}).items())]


def extract(trials, sig):
    """The trial-ORDERED series a signature's test consumes, mirroring each
    template's own filtering. Returns (kind, payload), or None when the session
    cannot supply it.

    Order matters here in a way it does not in the templates: the bootstrap
    resamples contiguous runs, so the series must stay in the sequence the agent
    actually produced.
    """
    test = sig["test"]

    if test == "proportion_test":
        vals = [t[sig["field"]] for t in _filtered(trials, sig.get("filter"))
                if sig["field"] in t]
        if len(vals) < 2:
            return None
        return "prop", (np.array([1.0 if v else 0.0 for v in vals]),
                        float(sig.get("chance_level", 0.5)),
                        sig.get("expected_direction", "above_chance"))

    if test == "correlation_test":
        fx, fy = sig["field_x"], sig["field_y"]
        pairs = [(float(t[fx]), float(t[fy]))
                 for t in _filtered(trials, sig.get("filter"))
                 if t.get(fx) is not None and t.get(fy) is not None]
        if len(pairs) < 10:
            return None
        x, y = (np.array(a, dtype=float) for a in zip(*pairs))
        if sig.get("method", "pearson") == "spearman":
            # Rank-transform once, then Pearson on the resampled ranks. Ranks
            # must be tie-AVERAGED: `coherence` takes five distinct values, so
            # ordinal ranks break ties arbitrarily and do not reproduce the rho
            # scipy reports, which breaks validation against the archive.
            x, y = rankdata(x).astype(float), rankdata(y).astype(float)
        if x.std() == 0 or y.std() == 0:
            return None
        return "corr", (x, y, sig.get("expected_direction", "positive"))

    if test == "paired_proportion_test":
        ga, gb = sig["group_a"], sig["group_b"]
        vals, grp = [], []
        for t in trials:  # keep trial order; tag group membership
            in_a = all(t.get(k) == v for k, v in ga["filter"].items()) and ga["field"] in t
            in_b = all(t.get(k) == v for k, v in gb["filter"].items()) and gb["field"] in t
            if in_a and not in_b:
                vals.append(1.0 if t[ga["field"]] else 0.0); grp.append(True)
            elif in_b and not in_a:
                vals.append(1.0 if t[gb["field"]] else 0.0); grp.append(False)
        grp = np.array(grp, dtype=bool)
        if grp.sum() < 3 or (~grp).sum() < 3:
            return None
        return "contrast", (np.array(vals), grp,
                            "positive" if sig["expected_direction"] == "a > b" else "negative")

    if test == "conditional_proportion_contrast":
        of, cf = sig["field"], sig["condition_field"]
        vals, grp = [], []
        for t in _filtered(trials, sig.get("filter")):
            if of not in t or cf not in t or t[cf] is None:
                continue
            vals.append(1.0 if t[of] else 0.0); grp.append(bool(t[cf]))
        grp = np.array(grp, dtype=bool)
        if grp.sum() < 2 or (~grp).sum() < 2:
            return None
        return "contrast", (np.array(vals), grp,
                            sig.get("expected_direction", "positive"))

    return None


# --------------------------------------------------------------- bootstrap
def _pearson_rows(X, Y):
    Xc, Yc = X - X.mean(1, keepdims=True), Y - Y.mean(1, keepdims=True)
    den = np.sqrt((Xc ** 2).sum(1) * (Yc ** 2).sum(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (Xc * Yc).sum(1) / den, np.nan)


def bootstrap_p(kind, payload, rule, b, rng):
    """(theta, null, bootstrap p, block length, n, direction_correct).

    The `contrast` branch delegates to the scoring module so the sensitivity
    analysis and the deployed scorer share one implementation; `prop` and `corr`
    statistics have no scoring-side counterpart yet and resample here, through
    the same `block_index`.
    """
    length_rule = BLOCK_RULES[rule]

    if kind == "contrast":
        values, group, expected = payload
        higher, n = expected == "positive", len(values)
        values = np.asarray(values, dtype=float)
        group = np.asarray(group, dtype=bool)
        theta, null = values[group].mean() - values[~group].mean(), 0.0
        boot, length = contrast_resamples(values, group, rng, b, length_rule)
    elif kind == "prop":
        vals, chance, expected = payload
        higher, n = expected == "above_chance", len(vals)
        idx, length = block_index(n, rng, b, length_rule)
        theta, null, boot = vals.mean(), chance, vals[idx].mean(1)
    else:  # corr
        x, y, expected = payload
        higher, n = expected == "positive", len(x)
        idx, length = block_index(n, rng, b, length_rule)
        theta, null = _pearson_rows(x[None, :], y[None, :])[0], 0.0
        boot = _pearson_rows(x[idx], y[idx])
        boot = boot[~np.isnan(boot)]

    if np.isnan(theta):
        return None
    p = p_from_resamples(boot, null, higher)
    if p is None:
        return None
    dir_ok = bool(theta > null) if higher else bool(theta < null)
    return float(theta), float(null), p, length, n, dir_ok


# --------------------------------------------------------------------- drive
def load_specs():
    out = {}
    for task in V1_TASKS:
        path = REPO_ROOT / "tasks" / task / "scoring" / "level3_signatures.json"
        out[task] = json.load(open(path))["signatures"]
    return out


def iter_sessions(sweep):
    for run in sorted(glob.glob(str(REPO_ROOT / "data/sweeps" / sweep / "runs" / "*"))):
        art = Path(run) / "artifacts"
        if not (art / "meta.json").exists() or not (art / "trial_data").is_dir():
            continue
        model = json.load(open(art / "meta.json")).get("model") or "random"
        if isinstance(model, dict):
            model = model.get("id", "random")
        m = re.match(r"r(\d+)_", Path(run).name)
        repeat = int(m.group(1)) if m else -1
        for td in sorted((art / "trial_data").glob("*.json")):
            if td.stem not in V1_TASKS:
                continue
            try:
                trials = json.load(open(td))
            except (OSError, ValueError):
                continue
            if isinstance(trials, dict):
                trials = trials.get("trials", [])
            yield model, repeat, td.stem, trials


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block-rule", choices=sorted(BLOCK_RULES), default="n13")
    ap.add_argument("--resamples", type=int, default=B_DEFAULT)
    ap.add_argument("--seed", type=int, default=20260727)
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "results" / "bootstrap_signatures.csv")
    args = ap.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    specs, rows = load_specs(), []
    for sweep, arm in SWEEPS:
        for model, repeat, task, trials in iter_sessions(sweep):
            for sig in specs.get(task, []):
                got = extract(trials, sig)
                if got is None:
                    continue
                res = bootstrap_p(*got, args.block_rule, args.resamples, rng)
                if res is None:
                    continue
                theta, null, p, length, n, dir_ok = res
                rows.append({"arm": arm, "sweep": sweep, "model": model,
                             "repeat_index": repeat, "task": task,
                             "signature": sig["name"], "test": sig["test"],
                             "weight": sig.get("weight", 1.0),
                             "threshold_p": sig["threshold_p"], "n": n,
                             "block_len": length, "theta": theta, "null": null,
                             "boot_p": p, "direction_correct": dir_ok})
            print(f"\r{len(rows):6d} signature fits", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    if not rows:
        print("no sessions found; are the sweeps present in data/sweeps/ ?", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} signature tests (block rule {args.block_rule}) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
