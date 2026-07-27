"""Recompute every empirical L2 human baseline from its source dataset.

Eight of the ten v1 tasks score against statistics derived from the original
authors' released participant data (see
``scoring/human_baselines/sources/README.md``). Those numbers were computed
once, by hand, and written into ``tasks/{task}/scoring/level2_metrics.json``.
Without this script nothing checks that they still match the data they claim to
come from, and a reviewer has no way to verify them at all.

    python -m scripts.derive_baselines            # recompute and diff against the specs
    python -m scripts.derive_baselines --update   # write the recomputed values back

Every derivation below mirrors the corresponding metric's own definition in
``level2_metrics.json`` — same field, same filter, same aggregation — and takes
the mean across participants of each participant's own value, so ``human_sd`` is
between-person variation and is the right denominator for a per-session z-score.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
import struct
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "scoring" / "human_baselines" / "sources"
# Rounding tolerance. Proportions are stored to 3 dp, but reward-scale metrics
# run to ~70, where 3 dp of the stored value is a much coarser absolute figure,
# so the tolerance scales with magnitude.
TOL = 0.002


def _tol(x: float) -> float:
    return max(TOL, abs(x) * 0.001)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _agg(per_subject: dict[str, list[float]], min_n: int = 1):
    vals = [st.mean(v) for v in per_subject.values() if len(v) >= min_n]
    if not vals:
        return None, None, 0
    return st.mean(vals), (st.stdev(vals) if len(vals) > 1 else 0.0), len(vals)


def _rows(name: str):
    with open(SOURCES / name, newline="") as f:
        yield from csv.DictReader(f)


# --------------------------------------------------------------------------
# One function per task. Each returns {metric_name: (mean, sd, n)}.
# --------------------------------------------------------------------------

def grid_bandit():
    per = defaultdict(lambda: defaultdict(list))
    for r in _rows("witte_2024_grid_bandit_study1.csv"):
        z, kp, kc = _f(r["z"]), r["krakenPres"], _f(r["krakenCaught"])
        if z is None:
            continue
        pid = r["ID"]
        per[pid]["mean_reward_per_click"].append(z)
        per[pid]["prop_high_value_clicks"].append(1.0 if z > 50 else 0.0)  # spec threshold
        if kp == "0":
            per[pid]["mean_reward_safe"].append(z)
        elif kp == "1":
            per[pid]["mean_reward_risky"].append(z)
            if kc is not None:
                per[pid]["kraken_caught_rate_risky"].append(kc)
    keys = ["mean_reward_per_click", "mean_reward_safe", "mean_reward_risky",
            "prop_high_value_clicks", "kraken_caught_rate_risky"]
    return {k: _agg({p: d[k] for p, d in per.items() if d[k]}) for k in keys}


def repeated_games():
    # action 1 pays 8 on mutual agreement and 0 when exploited, so 1 is COOPERATE.
    per = defaultdict(lambda: defaultdict(list))
    for r in _rows("akata_2025_repeated_games_human.csv"):
        k = (r["id"], r["opponent"])
        if r["game"] == "PD":
            per[k]["coop_rate_pd"].append(1.0 if r["action"] == "1" else 0.0)
            per[k]["mean_payoff_pd"].append(float(r["score"]))
        elif r["game"] == "BoS":
            per[k]["coordination_rate_bos"].append(float(r["coordination"]))
            per[k]["mean_payoff_bos"].append(float(r["score"]))
    keys = ["coop_rate_pd", "mean_payoff_pd", "coordination_rate_bos", "mean_payoff_bos"]
    return {k: _agg({p: d[k] for p, d in per.items() if d[k]}) for k in keys}


def marbles_risk():
    # description + solo, matching this port; EV ties dropped (has_clear_better).
    per = defaultdict(list)
    for r in _rows("ciranka_2025_marbles_trials.csv"):
        if r["DFE1DFD0"] != "0" or r["Social1Ind0"] != "0":
            continue
        v, p, s, ch = (_f(r["valueGamble"]), _f(r["probGamble"]),
                       _f(r["valueSure"]), _f(r["ChooseRisk"]))
        if None in (v, p, s, ch):
            continue
        ev = v * p
        if abs(ev - s) < 1e-9:
            continue
        per[r["subject"]].append(1.0 if ((ch == 1 and ev > s) or (ch == 0 and ev < s)) else 0.0)
    return {"prop_chose_higher_ev": _agg(per, min_n=5)}


def moral_machine():
    """Parse the nine AMCEs out of the Figure 2a RData, then p = (1 + dP) / 2."""
    import gzip
    raw = gzip.decompress((SOURCES / "awad_2018_moral_machine_amce_fig2a.rdata").read_bytes())
    est = None
    i = 0
    while i < len(raw) - 8:
        if (struct.unpack(">I", raw[i:i + 4])[0] & 0xFF) == 14:          # REALSXP
            n = struct.unpack(">I", raw[i + 4:i + 8])[0]
            if n == 9 and i + 8 + 72 <= len(raw):
                vals = list(struct.unpack(">9d", raw[i + 8:i + 80]))
                if all(-2 < v < 2 for v in vals) and est is None:
                    est = vals
        i += 1
    if est is None:
        raise RuntimeError("could not parse AMCE vector from the RData")
    # Factor levels are ordered descending by effect size; confirmed against the
    # Fig 2 caption, which states the Age effect as 0.49.
    by_attr = dict(zip(["Species", "No. Characters", "Age", "Law", "Social Status",
                        "Fitness", "Gender", "Relation to AV", "Intervention"],
                       sorted(est, reverse=True)))
    m = {"prop_save_human": ("Species", +1), "prop_utilitarian": ("No. Characters", +1),
         "prop_save_young": ("Age", +1), "prop_save_legal": ("Law", +1),
         "prop_intervention": ("Intervention", -1)}   # reported preference is for INACTION
    return {k: ((1 + s * by_attr[a]) / 2, None, None) for k, (a, s) in m.items()}


def serial_recall_v2():
    # ListLength 16 matches this port's 16 word pairs; validID is the
    # preregistered participant exclusion.
    per = defaultdict(lambda: defaultdict(list))
    for r in _rows("haridi_2025_serial_recall_exp1.csv"):
        if r["validID"] != "True" or r["ListLength"] != "16.0":
            continue
        c = _f(r["correct_01"])
        if c is None:
            continue
        pid, b = r["subject_id"], r["SimBins"]
        per[pid]["overall_accuracy"].append(c)
        if b in ("1", "2"):
            per[pid]["accuracy_low_sim"].append(c)
        elif b in ("4", "5"):
            per[pid]["accuracy_high_sim"].append(c)
    keys = ["overall_accuracy", "accuracy_low_sim", "accuracy_high_sim"]
    return {k: _agg({p: d[k] for p, d in per.items() if d[k]}) for k in keys}


def phishing_detection_v2():
    # 50_OutFeed is the arm at this port's 50% phishing rate; within it, phase 2
    # is the only phase actually run at 50%.
    rows = [r for r in _rows("singh_2019_phishing_exp1_outcomefeedback.csv")
            if r["base_rate"] == "50_OutFeed" and r["email_type"] in ("ham", "phishing")]
    out = {}
    hit, fa, acc = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        if r["phase"] != "2":
            continue
        said_phish = 1.0 if r["user_action1"] == "1" else 0.0
        (hit if r["email_type"] == "phishing" else fa)[r["Mturk_id"]].append(said_phish)
        acc[r["Mturk_id"]].append(1.0 if r["score"] == "1" else 0.0)
    out["hit_rate"] = _agg(hit)
    out["false_alarm_rate"] = _agg(fa)
    out["overall_accuracy"] = _agg(acc)
    # Phases 1 and 3 ran at a 20% base rate, so each participant's accuracy is
    # recomputed at this port's 50% rate before averaging.
    for name, phase in (("pre_training_accuracy", "1"), ("post_training_accuracy", "3")):
        h, f = defaultdict(list), defaultdict(list)
        for r in rows:
            if r["phase"] != phase:
                continue
            v = 1.0 if r["user_action1"] == "1" else 0.0
            (h if r["email_type"] == "phishing" else f)[r["Mturk_id"]].append(v)
        vals = [0.5 * st.mean(h[p]) + 0.5 * (1 - st.mean(f[p]))
                for p in set(h) & set(f) if h[p] and f[p]]
        out[name] = (st.mean(vals), st.stdev(vals), len(vals))
    return out


def random_dot_motion_v2():
    per = defaultdict(lambda: defaultdict(list))
    for r in _rows("desender_2021_random_dot_motion.csv"):
        if (r["Training"] != "0" or r["Volatility"] != "0"
                or r["Response"] not in ("0", "1") or r["Coherence"] == "0"):
            continue
        per[r["Subj_idx"]][float(r["Coherence"])].append(
            1.0 if r["Response"] == r["Stimulus"] else 0.0)
    cohs = [0.05, 0.1, 0.2, 0.4]
    grp = [st.mean([st.mean(d[c]) for d in per.values() if d[c]]) for c in cohs]

    # Weibull with the 2AFC floor fixed at 0.5, fitted to extrapolate the .80
    # level this port has and Desender does not.
    def wb(c, a, b):
        return 0.5 + 0.5 * (1 - math.exp(-((c / a) ** b)))

    best, err = None, float("inf")
    for a in [0.02 + 0.002 * i for i in range(200)]:
        for b in [0.5 + 0.01 * i for i in range(200)]:
            e = sum((wb(c, a, b) - g) ** 2 for c, g in zip(cohs, grp))
            if e < err:
                err, best = e, (a, b)
    a, b = best
    shift = wb(0.8, a, b) - wb(0.4, a, b)

    low, med, high, overall = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for pid, d in per.items():
        if not (d[0.05] and d[0.1] and d[0.2] and d[0.4]):
            continue
        p4 = st.mean(d[0.4])
        p8 = min(0.999, p4 + shift)
        low[pid] = [x for c in (0.05, 0.1) for x in d[c]]
        med[pid] = d[0.2]
        high[pid] = [p4, p8]
        overall[pid] = [st.mean(d[0.05]), st.mean(d[0.1]), st.mean(d[0.2]), p4, p8]
    return {"accuracy_low_coherence": _agg(low), "accuracy_medium_coherence": _agg(med),
            "accuracy_high_coherence": _agg(high), "overall_accuracy": _agg(overall)}


def effort_foraging():
    # patch_n_harvests counts stays within a patch and resets at exit, so the
    # residence time is the last value before each exit.
    per = defaultdict(lambda: defaultdict(list))
    stay = defaultdict(list)
    prev = defaultdict(lambda: (None, None))
    for r in _rows("bustamante_2023_effort_foraging_exp1_slim.csv"):
        if r["is_practice"] not in ("false", "FALSE", "0"):
            continue
        sid, dec, el = r["subject_id"], r["decision"], r["effort_level"]
        if dec in ("stay", "exit"):
            stay[sid].append(1.0 if dec == "stay" else 0.0)
        n = _f(r["patch_n_harvests"])
        if dec == "exit":
            ln, le = prev[sid]
            if ln and ln > 0 and le in ("low", "high"):
                per[sid][le].append(ln)
        elif dec == "stay" and n is not None:
            prev[sid] = (n, el)
    return {"prop_stay_overall": _agg(stay, min_n=20),
            "_observed_residence_low": _agg({p: d["low"] for p, d in per.items() if d["low"]}, 5),
            "_observed_residence_high": _agg({p: d["high"] for p, d in per.items() if d["high"]}, 5)}


DERIVATIONS = {
    "grid_bandit": grid_bandit,
    "repeated_games": repeated_games,
    "marbles_risk": marbles_risk,
    "moral_machine": moral_machine,
    "serial_recall_v2": serial_recall_v2,
    "phishing_detection_v2": phishing_detection_v2,
    "random_dot_motion_v2": random_dot_motion_v2,
    "effort_foraging": effort_foraging,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true",
                    help="Write recomputed values into level2_metrics.json.")
    ap.add_argument("--task", action="append", default=None)
    args = ap.parse_args(argv)

    mismatches = 0
    for task, fn in DERIVATIONS.items():
        if args.task and task not in args.task:
            continue
        spec_path = REPO_ROOT / "tasks" / task / "scoring" / "level2_metrics.json"
        spec = json.loads(spec_path.read_text())
        by_name = {m["name"]: m for m in spec["metrics"]}
        print(f"\n{task}")
        derived = fn()
        changed = False
        for name, (mean, sd, n) in derived.items():
            if name.startswith("_"):
                print(f"   {name:28s} {mean:8.3f}  (sd {sd:.3f}, n={n})  [reference only]")
                continue
            m = by_name.get(name)
            if m is None or mean is None:
                continue
            cur = m.get("human_mean")
            ok = cur is not None and abs(cur - mean) <= _tol(mean)
            flag = "ok " if ok else "DIFF"
            nn = f"n={n}" if n else "n/a"
            print(f"   {flag} {name:28s} spec={cur!s:>8s}  derived={mean:8.4f}  {nn}")
            if not ok:
                mismatches += 1
                if args.update:
                    m["human_mean"] = round(mean, 3)
                    if sd is not None:
                        m["human_sd"] = round(sd, 3)
                    changed = True
        if changed:
            spec_path.write_text(json.dumps(spec, indent=2) + "\n")
            print(f"   -> updated {spec_path.relative_to(REPO_ROOT)}")

    print(f"\n{mismatches} metric(s) differ from their source data beyond rounding")
    return 1 if (mismatches and not args.update) else 0


if __name__ == "__main__":
    sys.exit(main())
