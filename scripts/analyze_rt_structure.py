"""Test whether agent reaction times carry human-like within-task structure.

Absolute RT is the wrong instrument for agents. Their responses run 10-16x
slower than human (12,009 ms vs 750 ms on random_dot_motion_v2), because that
number is dominated by LLM inference latency, and the runs extend deadlines with
no_deadline=true. Scoring absolute RT against a human baseline, as the L2
mean_correct_rt metrics do, therefore awards ~0 to every agent on every task and
measures API speed rather than cognition.

What is cognitively meaningful is the RELATIVE structure. A human is faster on
easy trials than hard ones; an agent could be uniformly slower and still show
that ordering. This script tests the canonical within-task RT relations:

    random_dot_motion_v2   RT falls as coherence rises (chronometric function)
    marbles_risk           RT falls as the EV difference grows (easy = fast)
    serial_recall_v2       RT falls as cue-target similarity rises
    grid_bandit            RT falls across clicks within a block (speedup)
    phishing_detection_v2  RT falls across trials within a phase (practice)
    repeated_games         RT falls across rounds (practice)
    effort_foraging        RT falls across harvests within a patch

Correlations are computed WITHIN each session and then sign-tested across
sessions. Pooling would be wrong: absolute latency varies by model, by provider
load and over time, so only the ordering within a session is about the task.

A control is reported alongside, because a null is only interpretable if the
instrument could have seen an effect. If agent RT were a near-constant API
latency, no correlation could appear regardless of behaviour. Measured
within-session coefficient of variation is 0.26-0.59, comparable to the 0.3-0.5
humans show on these paradigms, so RT does vary enough for a real relation to
surface.

Usage::

    python -m scripts.analyze_rt_structure
    python -m scripts.analyze_rt_structure --sweep 'data/sweeps/rebuttal_v1_launch_*'
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
from typing import Callable

from scipy import stats

# (task, predictor, trial filter, human-expected direction, description)
RELATIONS: list[tuple[str, str, Callable[[dict], bool], str, str]] = [
    ("random_dot_motion_v2", "coherence",
     lambda t: t.get("trial_part") == "stimulus" and not t.get("timed_out") and t.get("correct"),
     "negative", "RT vs coherence (chronometric function, Roitman & Shadlen 2002)"),
    ("marbles_risk", "ev_diff",
     lambda t: t.get("trial_part") == "stimulus" and not t.get("timed_out"),
     "negative", "RT vs |EV difference| (easier choice, faster response)"),
    ("serial_recall_v2", "similarity_level",
     lambda t: t.get("rt") and not t.get("timed_out"),
     "negative", "RT vs cue-target semantic similarity"),
    ("grid_bandit", "click_in_block",
     lambda t: t.get("trial_part") == "click",
     "negative", "RT vs click position within block (within-block speedup)"),
    ("phishing_detection_v2", "trial_in_phase",
     lambda t: not t.get("timed_out"),
     "negative", "RT vs trial number within phase (practice speedup)"),
    ("repeated_games", "round",
     lambda t: not t.get("timed_out"),
     "negative", "RT vs round number (practice speedup)"),
    ("effort_foraging", "harvest_in_patch",
     lambda t: t.get("rt"),
     "negative", "RT vs harvest number within patch"),
]

MIN_TRIALS_PER_SESSION = 8


def _sessions(task: str, pattern: str):
    for f in sorted(glob.glob(f"{pattern}/runs/*/artifacts/trial_data/{task}.json")):
        try:
            yield json.load(open(f))
        except (OSError, json.JSONDecodeError):
            continue


def within_session_rhos(task, predictor, keep, pattern) -> list[float]:
    rhos = []
    for trials in _sessions(task, pattern):
        pts = [(t[predictor], t["rt"]) for t in trials
               if keep(t) and t.get("rt") is not None and t.get(predictor) is not None]
        if len(pts) < MIN_TRIALS_PER_SESSION:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if len(set(xs)) < 2 or len(set(ys)) < 2:
            continue
        rho, _ = stats.spearmanr(xs, ys)
        if rho == rho:  # not nan
            rhos.append(float(rho))
    return rhos


def rt_dispersion(task: str, pattern: str) -> tuple[int, float, float] | None:
    """Median RT and median within-session CV — the control on the null."""
    cvs, meds = [], []
    for trials in _sessions(task, pattern):
        rts = [t["rt"] for t in trials if t.get("rt") and not t.get("timed_out")]
        if len(rts) < 10:
            continue
        meds.append(statistics.median(rts))
        cvs.append(statistics.stdev(rts) / statistics.mean(rts))
    if not cvs:
        return None
    return len(cvs), statistics.median(meds), statistics.median(cvs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", default="data/sweeps/rebuttal_v1_launch_*",
                    help="Glob for sweep directories.")
    args = ap.parse_args(argv)

    print("WITHIN-SESSION RT STRUCTURE")
    print("Spearman rho per session, sign-tested across sessions.\n")
    print(f"{'relation':52s} {'exp':>8s} {'n':>4s} {'med rho':>8s} {'agree':>10s} {'p':>7s}")
    reproduced = 0
    tested = 0
    for task, predictor, keep, expected, label in RELATIONS:
        rhos = within_session_rhos(task, predictor, keep, args.sweep)
        if not rhos:
            print(f"{label:52s} {'--':>8s}  insufficient data")
            continue
        tested += 1
        want_neg = expected == "negative"
        agree = sum(1 for r in rhos if (r < 0) == want_neg)
        p = stats.binomtest(agree, len(rhos), 0.5, alternative="greater").pvalue
        if p < 0.05:
            reproduced += 1
        flag = " **" if p < 0.05 else ("  (inverted)" if statistics.median(rhos) > 0 and want_neg else "")
        print(f"{label:52s} {expected:>8s} {len(rhos):4d} {statistics.median(rhos):+8.3f} "
              f"{agree:4d}/{len(rhos):<5d} {p:7.3f}{flag}")

    print(f"\n{reproduced}/{tested} canonical RT relations reproduced above chance.")

    print("\nCONTROL — could an effect have been detected?")
    print("Humans show CV ~0.3-0.5 on these paradigms. A near-zero CV would mean")
    print("latency swamps any structure and the null above is uninterpretable.\n")
    print(f"{'task':24s} {'sessions':>8s} {'median RT':>11s} {'median CV':>10s}")
    for task, *_ in RELATIONS:
        d = rt_dispersion(task, args.sweep)
        if d:
            n, med, cv = d
            print(f"{task:24s} {n:8d} {med:10.0f}ms {cv:10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
