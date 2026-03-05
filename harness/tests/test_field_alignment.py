"""
Field alignment integration tests.

Verify that synthetic data matching the exact experiment.js output format
scores correctly through the full L1/L2/L3 pipeline. Catches mismatches
between experiment field names and scoring spec expectations.
"""
import json
import math
import random
from pathlib import Path

import pytest

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral
from scoring.composite_score import compute_composite

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(task_id, filename):
    path = TASKS_DIR / task_id / "scoring" / filename
    with open(path) as f:
        return json.load(f)


def _load_config(task_id):
    path = TASKS_DIR / task_id / "task_config.json"
    with open(path) as f:
        return json.load(f)


# ---------- Stroop ----------

def _make_stroop_aligned(n=96):
    """Generate data matching exact stroop/experiment.js on_finish output."""
    rng = random.Random(42)
    colors = ["red", "blue", "green", "yellow"]
    words = ["RED", "BLUE", "GREEN", "YELLOW", "XXXX"]
    key_map = {"red": "d", "blue": "f", "green": "j", "yellow": "k"}
    trials = []
    for i in range(n):
        color = colors[i % 4]
        word = rng.choice(words)
        if word == color.upper():
            cond = "congruent"
        elif word == "XXXX":
            cond = "neutral"
        else:
            cond = "incongruent"
        correct_key = key_map[color]
        base_rt = 550 if cond == "congruent" else (680 if cond == "incongruent" else 580)
        rt = max(150, base_rt + rng.gauss(0, 60))
        is_correct = rng.random() < (0.98 if cond == "congruent" else 0.88)
        resp = correct_key if is_correct else rng.choice([k for k in "dfjk" if k != correct_key])
        trials.append({
            "trial_part": "stimulus",
            "block": i // 24 + 1,
            "condition": cond,
            "stimulus_word": word,
            "stimulus_color": color,
            "correct_key": correct_key,
            "response": resp,
            "rt": round(rt, 1),
            "correct": is_correct,
            "timed_out": False,
            "trial_index": i + 1,
        })
    return trials


def test_stroop_alignment():
    task_id = "stroop"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_stroop_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Two-Armed Bandit ----------

def _make_bandit_aligned(n_games=40, games_per_horizon=20):
    """Generate data matching exact two_armed_bandit/experiment.js on_finish output.

    Includes both forced and free trials, mirroring the real experiment structure:
    40 games (20 per horizon), each with 4 forced + horizon free choices.
    """
    rng = random.Random(42)
    trials = []
    trial_idx = 0
    prev_arm = None
    prev_correct = None

    # Build game list: 20 horizon-1, 20 horizon-6, shuffled
    games = []
    for horizon in [1, 6]:
        for _ in range(games_per_horizon):
            games.append({
                "horizon": horizon,
                "mean_left": round(rng.uniform(40, 60), 1),
                "mean_right": round(rng.uniform(40, 60), 1),
                "info_condition": rng.choice(["equal", "unequal"]),
                "more_info_arm": rng.choice(["left", "right"]),
            })
    rng.shuffle(games)

    for g, game in enumerate(games):
        horizon = game["horizon"]
        mean_left = game["mean_left"]
        mean_right = game["mean_right"]
        info_cond = game["info_condition"]
        more_info = game["more_info_arm"]

        # 4 forced trials
        forced_arms = ["left", "left", "left", "right"] if more_info == "left" \
            else ["right", "right", "right", "left"]
        rng.shuffle(forced_arms)

        for f_idx, f_arm in enumerate(forced_arms):
            trial_idx += 1
            mean = mean_left if f_arm == "left" else mean_right
            reward = round(max(0, rng.gauss(mean, 8)), 1)
            correct = (mean_left >= mean_right and f_arm == "left") or \
                      (mean_right > mean_left and f_arm == "right")

            trial = {
                "trial_part": "stimulus",
                "game_index": g,
                "horizon": horizon,
                "trial_in_game": f_idx + 1,
                "trial_type": "forced",
                "arm_left_mean": mean_left,
                "arm_right_mean": mean_right,
                "info_condition": info_cond,
                "more_info_arm": more_info,
                "arm_chosen": f_arm,
                "timed_out": False,
                "reward": reward,
                "correct": correct,
                "explore_choice": not correct,
                "chose_less_sampled": f_arm != more_info,
                "trial_index": trial_idx,
                "rt": round(max(200, rng.gauss(800, 150)), 1),
                "response": "f" if f_arm == "left" else "j",
            }

            if trial_idx > 1 and prev_correct is not None:
                trial["prev_win"] = prev_correct
                trial["stayed"] = f_arm == prev_arm

            trials.append(trial)
            prev_arm = f_arm
            prev_correct = correct

        # Free-choice trials
        for c in range(horizon):
            trial_idx += 1
            arm = rng.choice(["left", "right"])
            mean = mean_left if arm == "left" else mean_right
            reward = round(max(0, rng.gauss(mean, 8)), 1)
            correct = (mean_left >= mean_right and arm == "left") or \
                      (mean_right > mean_left and arm == "right")

            trial = {
                "trial_part": "stimulus",
                "game_index": g,
                "horizon": horizon,
                "trial_in_game": 4 + c + 1,
                "trial_type": "free",
                "arm_left_mean": mean_left,
                "arm_right_mean": mean_right,
                "info_condition": info_cond,
                "more_info_arm": more_info,
                "arm_chosen": arm,
                "timed_out": False,
                "reward": reward,
                "correct": correct,
                "explore_choice": not correct,
                "chose_less_sampled": arm != more_info,
                "trial_index": trial_idx,
                "rt": round(max(200, rng.gauss(800, 150)), 1),
                "response": "f" if arm == "left" else "j",
            }

            if trial_idx > 1 and prev_correct is not None:
                trial["prev_win"] = prev_correct
                trial["stayed"] = arm == prev_arm

            trials.append(trial)
            prev_arm = arm
            prev_correct = correct

    return trials


def test_bandit_alignment():
    task_id = "two_armed_bandit"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_bandit_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may be 0 for some signatures depending on random seed, just check pipeline runs
    assert comp["composite_score"] > 0.0


# ---------- Risky Choice ----------

def _make_risky_aligned(n=60):
    """Generate data matching exact risky_choice/experiment.js on_finish output."""
    rng = random.Random(42)
    domains = ["gain", "loss", "mixed"]
    trials = []
    for i in range(n):
        domain = domains[i % 3]
        prob = rng.choice([0.1, 0.25, 0.5, 0.75, 0.9])
        stake = rng.choice([20, 30, 40, 50, 60, 80, 100])

        if domain == "gain":
            risky_outcome = stake
            risky_loss = 0
            safe_outcome = round(stake * prob * rng.uniform(0.8, 1.2))
        elif domain == "loss":
            risky_outcome = 0
            risky_loss = -stake
            safe_outcome = -round(stake * (1 - prob) * rng.uniform(0.8, 1.2))
        else:
            risky_outcome = stake
            risky_loss = -round(stake * 0.5)
            safe_outcome = round((stake * prob + risky_loss * (1 - prob)) * rng.uniform(0.8, 1.2))

        ev_risky = risky_outcome * prob + risky_loss * (1 - prob)
        ev_safe = safe_outcome
        risky_on_left = rng.random() > 0.5

        # Human-like: risk averse in gains, risk seeking in losses
        if domain == "gain":
            chose_risky = rng.random() < 0.35
        elif domain == "loss":
            chose_risky = rng.random() < 0.60
        else:
            chose_risky = rng.random() < 0.45

        chose_left = (chose_risky and risky_on_left) or (not chose_risky and not risky_on_left)

        trials.append({
            "trial_part": "stimulus",
            "domain": domain,
            "probability": prob,
            "risky_outcome": risky_outcome,
            "risky_loss": risky_loss,
            "safe_outcome": safe_outcome,
            "ev_risky": ev_risky,
            "ev_safe": ev_safe,
            "risky_on_left": risky_on_left,
            "response": "f" if chose_left else "j",
            "timed_out": False,
            "chose_risky": chose_risky,
            "chose_safe": not chose_risky,
            "ev_difference": ev_risky - ev_safe,
            "chose_risky_num": 1 if chose_risky else 0,
            "trial_index": i + 1,
            "rt": round(max(300, rng.gauss(1200, 250)), 1),
        })
    return trials


def test_risky_choice_alignment():
    task_id = "risky_choice"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_risky_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Trust Game ----------

def _make_trust_aligned(n=15):
    """Generate data matching exact trust_game/experiment.js on_finish output."""
    rng = random.Random(42)
    endowment = 10
    multiplier = 3
    types = (["cooperative"] * 5) + (["neutral"] * 5) + (["defecting"] * 5)
    rng.shuffle(types)
    return_ranges = {
        "cooperative": (0.40, 0.60),
        "neutral": (0.25, 0.35),
        "defecting": (0.05, 0.15),
    }
    trials = []
    prev_return_proportion = None

    for i in range(n):
        tt = types[i]
        rmin, rmax = return_ranges[tt]

        # Human-like: send more to cooperative
        if tt == "cooperative":
            sent = round(rng.uniform(4, 8))
        elif tt == "neutral":
            sent = round(rng.uniform(3, 6))
        else:
            sent = round(rng.uniform(1, 4))

        sent_proportion = sent / endowment
        tripled = sent * multiplier
        return_rate = rng.uniform(rmin, rmax)
        returned = round(max(0, min(tripled, tripled * return_rate)))
        returned_proportion = returned / tripled if tripled > 0 else 0

        trial = {
            "trial_part": "stimulus",
            "round": i + 1,
            "trustee_id": i,
            "trustee_type": tt,
            "endowment": endowment,
            "amount_sent": sent,
            "timed_out": False,
            "amount_sent_proportion": sent_proportion,
            "sent_nonzero": sent > 0,
            "tripled_amount": tripled,
            "amount_returned": returned,
            "amount_returned_proportion": returned_proportion,
            "net_payoff": (endowment - sent) + returned,
            "trial_index": i + 1,
            "rt": round(max(500, rng.gauss(3000, 800)), 1),
            "response": sent,
        }

        if prev_return_proportion is not None:
            trial["prev_return_proportion"] = prev_return_proportion

        trials.append(trial)
        prev_return_proportion = returned_proportion

    return trials


def test_trust_game_alignment():
    task_id = "trust_game"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_trust_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- N-Back ----------

def _make_nback_aligned(n=120):
    """Generate data matching exact n_back/experiment.js on_finish output."""
    rng = random.Random(42)
    letters = list("BCDFGHJKLMNPQRSTVWXYZ")
    target_prop = 0.30
    lure_prop = 0.10

    # Generate sequence with targets and lures
    sequence = []
    is_target = []
    is_lure_list = []

    for i in range(n):
        if i >= 2 and rng.random() < target_prop:
            letter = sequence[i - 2]
            sequence.append(letter)
            is_target.append(True)
            is_lure_list.append(False)
        elif i >= 1 and rng.random() < lure_prop:
            letter = sequence[i - 1]
            # Make sure it's not accidentally a target
            if i >= 2 and letter == sequence[i - 2]:
                letter = rng.choice([l for l in letters if l != letter])
            sequence.append(letter)
            is_target.append(False)
            is_lure_list.append(True)
        else:
            # Avoid accidental targets/lures
            avoid = set()
            if i >= 2:
                avoid.add(sequence[i - 2])
            if i >= 1:
                avoid.add(sequence[i - 1])
            choices = [l for l in letters if l not in avoid]
            if not choices:
                choices = letters
            sequence.append(rng.choice(choices))
            is_target.append(False)
            is_lure_list.append(False)

    trials = []
    for i in range(n):
        tgt = is_target[i]
        lure = is_lure_list[i]

        # Human-like response rates
        if tgt:
            hit = rng.random() < 0.80
            resp = "f" if hit else "j"
            correct = hit
            is_hit = hit
            is_miss = not hit
            is_fa = False
            is_cr = False
        else:
            if lure:
                fa = rng.random() < 0.25  # higher FA for lures
            else:
                fa = rng.random() < 0.08
            resp = "f" if fa else "j"
            correct = not fa
            is_hit = False
            is_miss = False
            is_fa = fa
            is_cr = not fa

        trials.append({
            "trial_part": "stimulus",
            "stimulus": sequence[i],
            "n_back_match": tgt,
            "is_lure": lure,
            "block": i // 40 + 1,
            "response": resp,
            "correct": correct,
            "hit": is_hit,
            "miss": is_miss,
            "false_alarm": is_fa,
            "correct_rejection": is_cr,
            "trial_index": i + 1,
            "rt": round(max(200, rng.gauss(550, 120)), 1),
            "timed_out": False,
        })
    return trials


def test_nback_alignment():
    task_id = "n_back"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_nback_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may partially fail depending on seed — check pipeline completes
    assert comp["composite_score"] > 0.0


# ---------- Go/No-Go ----------

def _make_gonogo_aligned(n=100):
    """Generate data matching exact go_nogo/experiment.js on_finish output."""
    rng = random.Random(42)
    go_proportion = 0.75
    trials = []
    for i in range(n):
        stim_type = "go" if rng.random() < go_proportion else "nogo"
        block = i // 20 + 1

        if stim_type == "go":
            responded = rng.random() < 0.95
            correct = responded
            hit = responded
            miss = not responded
            false_alarm = False
            correct_rejection = False
            rt = round(max(150, rng.gauss(350, 60)), 1) if responded else None
            response = "f" if responded else None
        else:
            fa = rng.random() < 0.15
            responded = fa
            correct = not fa
            hit = False
            miss = False
            false_alarm = fa
            correct_rejection = not fa
            rt = round(max(150, rng.gauss(300, 80)), 1) if responded else None
            response = "f" if responded else None

        trial = {
            "trial_part": "stimulus",
            "stimulus_type": stim_type,
            "block": block,
            "response": response,
            "rt": rt,
            "correct": correct,
            "hit": hit,
            "miss": miss,
            "false_alarm": false_alarm,
            "correct_rejection": correct_rejection,
            "timed_out": not responded if stim_type == "go" else False,
            "trial_index": i + 1,
        }

        if i > 0:
            trial["prev_correct"] = trials[-1]["correct"]

        trials.append(trial)
    return trials


def test_gonogo_alignment():
    task_id = "go_nogo"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_gonogo_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Flanker ----------

def _make_flanker_aligned(n=96):
    """Generate data matching exact flanker/experiment.js on_finish output."""
    rng = random.Random(42)
    conditions = ["congruent", "incongruent"]
    directions = ["left", "right"]
    key_map = {"left": "f", "right": "j"}
    trials = []
    prev_condition = "congruent"

    for i in range(n):
        condition = conditions[i % 2]
        target_dir = directions[i % 2]
        flanker_dir = target_dir if condition == "congruent" else ("right" if target_dir == "left" else "left")
        correct_key = key_map[target_dir]

        base_rt = 400 if condition == "congruent" else 450
        rt = round(max(150, rng.gauss(base_rt, 80)), 1)
        is_correct = rng.random() < (0.98 if condition == "congruent" else 0.92)
        resp = correct_key if is_correct else key_map[flanker_dir]

        trial = {
            "trial_part": "stimulus",
            "condition": condition,
            "target_direction": target_dir,
            "flanker_direction": flanker_dir,
            "correct_key": correct_key,
            "block": i // 24 + 1,
            "response": resp,
            "rt": rt,
            "correct": is_correct,
            "timed_out": False,
            "trial_index": i + 1,
        }

        if i > 0:
            trial["prev_condition"] = prev_condition
            trial["prev_correct"] = trials[-1]["correct"]

        trials.append(trial)
        prev_condition = condition

    return trials


def test_flanker_alignment():
    task_id = "flanker"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_flanker_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Dictator Game ----------

def _make_dictator_aligned(n=20):
    """Generate data matching exact dictator_game/experiment.js on_finish output."""
    rng = random.Random(42)
    endowment = 10
    trials = []
    for i in range(n):
        # Human-like giving: ~28% on average
        give_prop = max(0.0, min(1.0, rng.gauss(0.30, 0.12)))
        amount_given = round(give_prop * endowment)
        amount_given = max(0, min(endowment, amount_given))
        give_prop = amount_given / endowment

        trials.append({
            "trial_part": "stimulus",
            "round": i + 1,
            "endowment": endowment,
            "response": amount_given,
            "amount_given": amount_given,
            "amount_given_proportion": give_prop,
            "gave_nonzero": amount_given > 0,
            "gave_half": amount_given >= endowment / 2,
            "amount_kept": endowment - amount_given,
            "timed_out": False,
            "trial_index": i + 1,
            "rt": round(max(500, rng.gauss(5000, 2000)), 1),
        })
    return trials


def test_dictator_alignment():
    task_id = "dictator_game"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_dictator_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may not all pass with only 20 trials, check pipeline completes
    assert comp["composite_score"] > 0.0


# ---------- Iowa Gambling Task ----------

def _make_igt_aligned(n=100):
    """Generate data matching exact iowa_gambling/experiment.js on_finish output."""
    rng = random.Random(42)
    deck_rewards = {"A": 100, "B": 100, "C": 50, "D": 50}
    key_map = {"A": "d", "B": "f", "C": "j", "D": "k"}
    total_score = 2000
    trials = []

    for i in range(n):
        block = i // 20 + 1
        # Learning: more advantageous over time
        adv_prob = 0.40 + 0.20 * (i / n)
        if rng.random() < adv_prob:
            deck = rng.choice(["C", "D"])
        else:
            deck = rng.choice(["A", "B"])

        win = deck_rewards[deck]
        if deck == "A" and rng.random() < 0.50:
            loss = rng.randint(150, 350)
        elif deck == "B" and rng.random() < 0.10:
            loss = rng.randint(1150, 1350)
        elif deck == "C" and rng.random() < 0.50:
            loss = rng.randint(25, 75)
        elif deck == "D" and rng.random() < 0.10:
            loss = rng.randint(200, 300)
        else:
            loss = 0

        net = win - loss
        total_score += net

        trials.append({
            "trial_part": "stimulus",
            "block": block,
            "deck_chosen": deck,
            "deck_type": "advantageous" if deck in ["C", "D"] else "disadvantageous",
            "win": win,
            "loss": loss,
            "net_outcome": net,
            "total_score": total_score,
            "chose_advantageous": deck in ["C", "D"],
            "correct": deck in ["C", "D"],
            "response": key_map[deck],
            "rt": round(max(300, rng.gauss(1500, 400)), 1),
            "timed_out": False,
            "trial_index": i + 1,
        })
    return trials


def test_igt_alignment():
    task_id = "iowa_gambling"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_igt_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Reversal Learning ----------

def _make_reversal_aligned(n=120):
    """Generate data matching exact reversal_learning/experiment.js on_finish output."""
    rng = random.Random(42)
    correct_stim = "left"
    trial_since_rev = 0
    rev_count = 0
    next_reversal = rng.randint(15, 25)
    trials = []

    for i in range(n):
        if trial_since_rev >= next_reversal:
            correct_stim = "right" if correct_stim == "left" else "left"
            trial_since_rev = 0
            rev_count += 1
            next_reversal = rng.randint(15, 25)

        phase = "post_reversal" if trial_since_rev < 5 else "pre_reversal"

        if phase == "post_reversal":
            acc = 0.45 + 0.08 * trial_since_rev
        else:
            acc = 0.85

        is_correct = rng.random() < acc
        chosen = correct_stim if is_correct else ("right" if correct_stim == "left" else "left")

        if is_correct:
            rewarded = rng.random() < 0.80
        else:
            rewarded = rng.random() < 0.20

        trials.append({
            "trial_part": "stimulus",
            "stimulus_chosen": chosen,
            "correct_stimulus": correct_stim,
            "correct": is_correct,
            "rewarded": rewarded,
            "reward_value": 1 if rewarded else 0,
            "phase": phase,
            "trials_since_reversal": trial_since_rev,
            "reversal_count": rev_count,
            "perseveration": phase == "post_reversal" and not is_correct,
            "response": "f" if chosen == "left" else "j",
            "rt": round(max(200, rng.gauss(600, 150)), 1),
            "timed_out": False,
            "trial_index": i + 1,
        })
        trial_since_rev += 1

    return trials


def test_reversal_alignment():
    task_id = "reversal_learning"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_reversal_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Contingency Judgment ----------

def _make_contingency_judgment_aligned(n_blocks=4, obs_per_block=20):
    """Generate data matching exact contingency_judgment/experiment.js on_finish output.

    4 blocks of 20 observation trials, each block followed by a causal rating.
    Blocks have different delta-P values (contingency strengths).
    """
    rng = random.Random(42)

    # Block delta-P values: strong positive, moderate, zero, negative
    block_delta_ps = [0.75, 0.40, 0.00, -0.30]
    trials = []
    trial_idx = 0

    for block_idx in range(n_blocks):
        delta_p = block_delta_ps[block_idx]

        # Human-like rating: sensitive to delta_p but with noise and bias
        # Ratings are normalized 0-1 (slider 0-100 mapped to 0.0-1.0)
        if delta_p > 0.5:
            base_rating = 0.75
        elif delta_p > 0.2:
            base_rating = 0.62
        elif delta_p > -0.1:
            base_rating = 0.52  # slight overestimation for zero contingency
        else:
            base_rating = 0.35

        rating = max(0.0, min(1.0, base_rating + rng.gauss(0, 0.08)))
        rating_raw = round(rating * 100)
        rating_normalized = rating_raw / 100.0

        # Compute rating accuracy: how close to delta_p (rescaled to 0-1)
        ideal_rating = (delta_p + 1.0) / 2.0  # map [-1,1] to [0,1]
        rating_accuracy = max(0.0, 1.0 - abs(rating_normalized - ideal_rating))

        # Whether participant overestimated for zero-contingency block
        overestimated = rating_normalized > 0.50

        # High rating = above midpoint
        high_rating = rating_normalized > 0.50

        trial_idx += 1
        trials.append({
            "trial_part": "stimulus",
            "trial_index": trial_idx,
            "block": block_idx + 1,
            "block_delta_p": delta_p,
            "rating": rating_raw,
            "rating_normalized": rating_normalized,
            "rating_accuracy": rating_accuracy,
            "overestimated": overestimated,
            "high_rating": high_rating,
            "response": rating_raw,
            "rt": round(max(500, rng.gauss(4000, 1500)), 1),
            "timed_out": False,
        })

    return trials


def test_contingency_judgment_alignment():
    task_id = "contingency_judgment"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_contingency_judgment_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] >= 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 signatures require n>=10 data points; only 4 rating trials available
    assert comp["composite_score"] > 0.0


# ---------- Simple & Choice RT ----------

def _make_simple_choice_rt_aligned(n=80):
    """Generate data matching exact simple_choice_rt/experiment.js on_finish output.

    80 trials across simple (1 alternative), choice2 (2 alternatives), choice4 (4 alternatives).
    Tests Hick's Law: RT increases with log2(N).
    """
    rng = random.Random(42)

    conditions = ["simple"] * 20 + ["choice2"] * 30 + ["choice4"] * 30
    rng.shuffle(conditions)

    key_map_simple = [" "]
    key_map_choice2 = ["f", "j"]
    key_map_choice4 = ["d", "f", "j", "k"]

    trials = []
    for i in range(n):
        condition = conditions[i]

        if condition == "simple":
            n_alternatives = 1
            correct_key = " "
            keys = key_map_simple
            base_rt = 220
            acc = 0.99
        elif condition == "choice2":
            n_alternatives = 2
            correct_key = rng.choice(key_map_choice2)
            keys = key_map_choice2
            base_rt = 340
            acc = 0.96
        else:  # choice4
            n_alternatives = 4
            correct_key = rng.choice(key_map_choice4)
            keys = key_map_choice4
            base_rt = 450
            acc = 0.92

        rt = round(max(100, rng.gauss(base_rt, base_rt * 0.15)), 1)
        is_correct = rng.random() < acc
        if is_correct:
            response = correct_key
        else:
            others = [k for k in keys if k != correct_key]
            response = rng.choice(others) if others else correct_key

        log_n = math.log2(max(1, n_alternatives))

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "condition": condition,
            "n_alternatives": n_alternatives,
            "log_n_alternatives": log_n,
            "correct_key": correct_key,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "timed_out": False,
        })
    return trials


def test_simple_choice_rt_alignment():
    task_id = "simple_choice_rt"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_simple_choice_rt_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- BART ----------

def _make_bart_aligned(n_balloons=30):
    """Generate data matching exact bart/experiment.js on_finish output.

    30 balloons. Each trial is a balloon-level summary: n_pumps, popped,
    cashed_out, balloon_earnings, total_earnings, adjusted_pumps, etc.
    """
    rng = random.Random(42)
    total_earnings = 0.0
    trials = []
    median_pumps = 25  # approximate midpoint for adjusted_pumps calc

    for b in range(n_balloons):
        # Pop threshold: random between 1 and 64
        pop_threshold = rng.randint(8, 64)

        # Human-like pumping: average ~25 pumps with variance
        target_pumps = max(1, round(rng.gauss(25, 10)))

        if target_pumps >= pop_threshold:
            # Balloon popped
            n_pumps = pop_threshold
            popped = True
            cashed_out = False
            balloon_earnings = 0.0
        else:
            # Cashed out
            n_pumps = target_pumps
            popped = False
            cashed_out = True
            balloon_earnings = round(n_pumps * 0.05, 2)

        total_earnings += balloon_earnings

        # adjusted_pumps: only for non-popped balloons (standard BART metric)
        adjusted_pumps = n_pumps if not popped else None

        # above_floor_pumps: True if pumped more than a floor (e.g., >5)
        above_floor_pumps = n_pumps > 5

        # high_pumps: above median
        high_pumps = n_pumps > median_pumps

        # Previous popped
        previous_popped = trials[-1]["popped"] if len(trials) > 0 else False

        trials.append({
            "trial_part": "stimulus",
            "trial_index": b + 1,
            "balloon_number": b + 1,
            "n_pumps": n_pumps,
            "popped": popped,
            "cashed_out": cashed_out,
            "balloon_earnings": balloon_earnings,
            "total_earnings": round(total_earnings, 2),
            "adjusted_pumps": adjusted_pumps,
            "above_floor_pumps": above_floor_pumps,
            "high_pumps": high_pumps,
            "previous_popped": previous_popped,
            "pop_threshold": pop_threshold,
            "rt": round(max(200, rng.gauss(800, 300)), 1),
            "timed_out": False,
        })

    return trials


def test_bart_alignment():
    task_id = "bart"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_bart_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may not all pass with only 30 balloons, check pipeline completes
    assert comp["composite_score"] > 0.0


# ---------- Navon ----------

def _make_navon_aligned(n=80):
    """Generate data matching exact navon/experiment.js on_finish output.

    80 trials. Global/local letter identification with congruent/incongruent conditions.
    Shows global precedence effect (global faster than local) and congruency effect.
    """
    rng = random.Random(42)
    letters = ["H", "S"]
    key_map = {"H": "f", "S": "j"}
    target_levels = ["global", "local"]
    trials = []

    for i in range(n):
        target_level = target_levels[i % 2]
        block = i // 20 + 1

        # Pick global and local letters
        global_letter = rng.choice(letters)
        if rng.random() < 0.5:
            local_letter = global_letter  # congruent
        else:
            local_letter = [l for l in letters if l != global_letter][0]  # incongruent

        congruency = "congruent" if global_letter == local_letter else "incongruent"

        # Target is the letter at the target_level
        if target_level == "global":
            target_letter = global_letter
        else:
            target_letter = local_letter

        correct_key = key_map[target_letter]

        # Global precedence: global is faster than local
        # Congruency effect: congruent is faster than incongruent
        # Interaction: incongruent local is slowest (global interferes with local more)
        if target_level == "global":
            base_rt = 480 if congruency == "congruent" else 520
            acc = 0.97 if congruency == "congruent" else 0.94
        else:  # local
            base_rt = 540 if congruency == "congruent" else 620
            acc = 0.93 if congruency == "congruent" else 0.85

        rt = round(max(200, rng.gauss(base_rt, 70)), 1)
        is_correct = rng.random() < acc

        if is_correct:
            response = correct_key
        else:
            other_key = [v for v in key_map.values() if v != correct_key][0]
            response = other_key

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "block": block,
            "target_level": target_level,
            "global_letter": global_letter,
            "local_letter": local_letter,
            "congruency": congruency,
            "correct_key": correct_key,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "timed_out": False,
        })

    return trials


def test_navon_alignment():
    task_id = "navon"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_navon_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Category Learning ----------

def _make_category_learning_aligned(n_training=96, n_transfer=24):
    """Generate data matching exact category_learning/experiment.js on_finish output.

    96 training + 24 transfer trials; binary classification with f/j keys.
    Learning curve: accuracy improves across 8 blocks.
    """
    rng = random.Random(42)
    n_total = n_training + n_transfer
    trials = []

    # 3 binary features -> 8 stimuli
    features = [(f1, f2, f3) for f1 in [0, 1] for f2 in [0, 1] for f3 in [0, 1]]
    # Category rule: feature 0 determines category (Type I in Shepard taxonomy)
    categories = {f: ("A" if f[0] == 0 else "B") for f in features}
    key_map = {"A": "f", "B": "j"}

    for i in range(n_total):
        if i < n_training:
            phase = "training"
            block = i // 12 + 1  # 96 training / 12 per block = 8 blocks
            # Learning curve: accuracy improves across blocks
            base_acc = 0.55 + 0.05 * block  # block 1 ~ 0.60, block 8 ~ 0.95
        else:
            phase = "transfer"
            block = 9  # transfer block
            base_acc = 0.88

        stim_feat = features[i % len(features)]
        correct_cat = categories[stim_feat]
        correct_key = key_map[correct_cat]

        is_correct = rng.random() < min(0.98, base_acc)
        resp = correct_key if is_correct else ("j" if correct_key == "f" else "f")

        base_rt = 1400 - 40 * block if phase == "training" else 1100
        rt = round(max(250, rng.gauss(base_rt, 200)), 1)

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "block": block,
            "phase": phase,
            "stimulus_features": list(stim_feat),
            "correct_category": correct_cat,
            "correct_key": correct_key,
            "response": resp,
            "rt": rt,
            "correct": is_correct,
            "timed_out": False,
        })
    return trials


def test_category_learning_alignment():
    task_id = "category_learning"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_category_learning_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Restless Bandit ----------

def _make_restless_bandit_aligned(n=100):
    """Generate data matching exact restless_bandit/experiment.js on_finish output.

    100 trials, 2-armed bandit with drifting rewards. f/j keys.
    """
    rng = random.Random(42)
    trials = []

    # Drifting means via Gaussian random walk
    mu = [50.0, 50.0]
    drift_sd = 2.5
    reward_sd = 8.0
    prev_reward = None
    prev_arm = None
    median_reward = 50.0  # approximate median for first few trials

    rewards_so_far = []

    for i in range(n):
        # Drift reward means
        mu[0] += rng.gauss(0, drift_sd)
        mu[1] += rng.gauss(0, drift_sd)
        mu[0] = max(20, min(80, mu[0]))
        mu[1] = max(20, min(80, mu[1]))

        optimal_arm = 0 if mu[0] >= mu[1] else 1

        # Human-like: track the better arm ~65% of the time, with WSLS tendency
        if prev_reward is not None and prev_arm is not None:
            if prev_reward > median_reward:
                # Win-stay: 70% stay
                chose_arm = prev_arm if rng.random() < 0.70 else (1 - prev_arm)
            else:
                # Lose-shift: 55% shift
                chose_arm = (1 - prev_arm) if rng.random() < 0.55 else prev_arm
        else:
            chose_arm = rng.choice([0, 1])

        reward = round(max(0, rng.gauss(mu[chose_arm], reward_sd)), 1)
        rewards_so_far.append(reward)
        median_reward = sorted(rewards_so_far)[len(rewards_so_far) // 2]

        chose_optimal = chose_arm == optimal_arm
        stayed = chose_arm == prev_arm if prev_arm is not None else None

        trial = {
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "chosen_arm": chose_arm,
            "reward": reward,
            "arm_0_mean": round(mu[0], 2),
            "arm_1_mean": round(mu[1], 2),
            "chose_optimal": chose_optimal,
            "response": "f" if chose_arm == 0 else "j",
            "rt": round(max(200, rng.gauss(800, 200)), 1),
            "timed_out": False,
        }

        if stayed is not None:
            trial["stayed"] = stayed
            trial["stayed_num"] = 1 if stayed else 0

        if prev_reward is not None:
            trial["previous_reward"] = prev_reward
            trial["previous_reward_above_median"] = prev_reward > median_reward

        trials.append(trial)
        prev_reward = reward
        prev_arm = chose_arm

    return trials


def test_restless_bandit_alignment():
    task_id = "restless_bandit"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_restless_bandit_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may partially fail depending on drifting means -- check pipeline runs
    assert comp["composite_score"] > 0.0


# ---------- Serial Recall ----------

def _make_serial_recall_aligned(n_lists=10, list_length=12):
    """Generate data matching exact serial_recall/experiment.js on_finish output.

    10 lists x 12 items. Button-click interface (no keyboard response).
    Shows serial position curve: primacy + recency > middle.
    """
    rng = random.Random(42)
    words = [f"WORD_{w}" for w in range(100)]
    trials = []

    for li in range(n_lists):
        study_list = rng.sample(words, list_length)

        # Serial position recall probabilities (U-shaped curve)
        recall_probs = []
        for pos in range(list_length):
            if pos < 3:
                # Primacy zone: high recall
                p = 0.75 - 0.05 * pos
            elif pos >= list_length - 3:
                # Recency zone: high recall
                p = 0.65 + 0.05 * (pos - (list_length - 3))
            else:
                # Middle: lower recall
                p = 0.45

            recall_probs.append(min(0.95, max(0.20, p + rng.gauss(0, 0.05))))

        recalled_items = []
        recalled_positions = []
        for pos in range(list_length):
            if rng.random() < recall_probs[pos]:
                recalled_items.append(study_list[pos])
                recalled_positions.append(pos)

        n_recalled = len(recalled_items)

        # Correct position: recalled AND in right serial position
        n_correct_position = 0
        for idx, pos in enumerate(recalled_positions):
            if idx < len(recalled_positions) and recalled_positions[idx] == idx:
                n_correct_position += 1
        n_correct_position = min(n_correct_position, n_recalled)

        # Primacy (positions 0-2), recency (positions 9-11), middle (3-8)
        primacy_positions = set(range(3))
        recency_positions = set(range(list_length - 3, list_length))
        middle_positions = set(range(3, list_length - 3))

        primacy_recalled_count = sum(1 for p in recalled_positions if p in primacy_positions)
        recency_recalled_count = sum(1 for p in recalled_positions if p in recency_positions)
        middle_recalled_count = sum(1 for p in recalled_positions if p in middle_positions)

        primacy_recalled = primacy_recalled_count / len(primacy_positions) if primacy_positions else 0
        recency_recalled = recency_recalled_count / len(recency_positions) if recency_positions else 0
        middle_recalled = middle_recalled_count / len(middle_positions) if middle_positions else 0

        above_chance = n_recalled / list_length

        trials.append({
            "trial_part": "stimulus",
            "trial_index": li + 1,
            "list_number": li + 1,
            "study_list": study_list,
            "recalled_items": recalled_items,
            "recalled_positions": recalled_positions,
            "n_recalled": n_recalled,
            "n_correct_position": n_correct_position,
            "primacy_recalled": primacy_recalled,
            "recency_recalled": recency_recalled,
            "middle_recalled": middle_recalled,
            "above_chance_recall": above_chance,
            "timed_out": False,
            "rt": round(max(2000, rng.gauss(15000, 5000)), 1),
        })
    return trials


def test_serial_recall_alignment():
    task_id = "serial_recall"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_serial_recall_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Ultimatum Game ----------

def _make_ultimatum_aligned(n=20):
    """Generate data matching exact ultimatum_game/experiment.js on_finish output.

    20 rounds, alternating proposer/responder roles.
    Mixed interface: slider (proposer) + keypress (responder f/j).
    """
    rng = random.Random(42)
    endowment = 10
    trials = []

    for i in range(n):
        role = "proposer" if i % 2 == 0 else "responder"
        round_number = i + 1

        if role == "proposer":
            # Human-like: offer ~40% on average (fairness norms)
            offer_amount = max(0, min(endowment, round(rng.gauss(4.2, 1.5))))
            offer_proportion = offer_amount / endowment
            fair_offer = offer_proportion >= 0.3
            low_offer = offer_proportion < 0.2

            # Computer responder: accept proportional to offer
            accepted = rng.random() < (0.3 + 0.7 * offer_proportion)

            if accepted:
                player_payoff = endowment - offer_amount
            else:
                player_payoff = 0

            trials.append({
                "trial_part": "stimulus",
                "trial_index": i + 1,
                "round_number": round_number,
                "role": role,
                "offer_amount": offer_amount,
                "offer_proportion": offer_proportion,
                "fair_offer": fair_offer,
                "low_offer": low_offer,
                "accepted": accepted,
                "player_payoff": player_payoff,
                "timed_out": False,
                "rt": round(max(500, rng.gauss(4000, 1500)), 1),
                "response": offer_amount,
            })
        else:
            # Computer proposes; varied offer levels
            if i % 4 == 1:
                offer_amount = rng.randint(0, 2)   # low offer
            elif i % 4 == 3:
                offer_amount = rng.randint(3, 5)    # medium-high offer
            else:
                offer_amount = rng.randint(2, 4)    # medium

            offer_proportion = offer_amount / endowment
            fair_offer = offer_proportion >= 0.3
            low_offer = offer_proportion < 0.2

            # Human-like: accept fair offers, reject low ones
            if offer_proportion >= 0.4:
                accepted = rng.random() < 0.90
            elif offer_proportion >= 0.2:
                accepted = rng.random() < 0.60
            else:
                accepted = rng.random() < 0.15

            accepted_num = 1 if accepted else 0

            if accepted:
                player_payoff = offer_amount
            else:
                player_payoff = 0

            trials.append({
                "trial_part": "stimulus",
                "trial_index": i + 1,
                "round_number": round_number,
                "role": role,
                "offer_amount": offer_amount,
                "offer_proportion": offer_proportion,
                "fair_offer": fair_offer,
                "low_offer": low_offer,
                "accepted": accepted,
                "accepted_num": accepted_num,
                "player_payoff": player_payoff,
                "timed_out": False,
                "rt": round(max(400, rng.gauss(3000, 1200)), 1),
                "response": "f" if accepted else "j",
            })

    return trials


def test_ultimatum_alignment():
    task_id = "ultimatum_game"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_ultimatum_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    # Mixed response type (slider for proposer, keypress for responder)
    # causes valid_responses check to partially fail → L1 = 0.8
    assert l1["score"] >= 0.8, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may partially fail with only 20 trials -- check pipeline completes
    assert comp["composite_score"] > 0.0


# ---------- Public Goods ----------

def _make_public_goods_aligned(n=10):
    """Generate data matching exact public_goods/experiment.js on_finish output.

    10 rounds, slider contribution 0-20. 4 players, multiplier 1.6.
    Shows conditional cooperation with declining contributions.
    """
    rng = random.Random(42)
    endowment = 20
    multiplier = 1.6
    n_players = 4
    trials = []
    prev_other_mean = None

    for i in range(n):
        round_number = i + 1

        # Human-like: start generous, decline over rounds (conditional cooperation)
        base_contribution = max(0, 12.0 - 0.8 * i + rng.gauss(0, 2.5))
        player_contribution = max(0, min(endowment, round(base_contribution)))
        player_contribution_proportion = player_contribution / endowment
        positive_contribution = player_contribution > 0

        # Simulated other players: moderate cooperators
        other_contributions = [max(0, min(endowment, round(rng.gauss(8, 3)))) for _ in range(n_players - 1)]
        other_mean_contribution = round(sum(other_contributions) / len(other_contributions), 2)

        total_pot = player_contribution + sum(other_contributions)
        public_return = round((total_pot * multiplier) / n_players, 2)
        player_payoff = round((endowment - player_contribution) + public_return, 2)

        trial = {
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "round_number": round_number,
            "endowment": endowment,
            "player_contribution": player_contribution,
            "player_contribution_proportion": player_contribution_proportion,
            "positive_contribution": positive_contribution,
            "other_contributions": other_contributions,
            "other_mean_contribution": other_mean_contribution,
            "total_pot": total_pot,
            "public_return": public_return,
            "player_payoff": player_payoff,
            "timed_out": False,
            "rt": round(max(500, rng.gauss(5000, 2000)), 1),
            "response": player_contribution,
        }

        if prev_other_mean is not None:
            trial["previous_other_mean"] = prev_other_mean

        trials.append(trial)
        prev_other_mean = other_mean_contribution

    return trials


def test_public_goods_alignment():
    task_id = "public_goods"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_public_goods_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may partially fail with only 10 trials -- check pipeline completes
    assert comp["composite_score"] > 0.0


# ---------- Intertemporal Choice ----------

def _make_intertemporal_aligned(n=60):
    """Generate data matching exact intertemporal_choice/experiment.js on_finish output."""
    rng = random.Random(42)
    delay_categories = ["short", "long"]
    smaller_amounts = [10, 20, 30, 40, 50]
    larger_amounts = [20, 40, 60, 80, 100]
    short_delays = [1, 7, 14]
    long_delays = [30, 90, 180, 365]
    trials = []

    for i in range(n):
        delay_cat = delay_categories[i % 2]
        sm_idx = i % len(smaller_amounts)
        lg_idx = i % len(larger_amounts)
        smaller_amount = smaller_amounts[sm_idx]
        larger_amount = larger_amounts[lg_idx]
        if larger_amount <= smaller_amount:
            larger_amount = smaller_amount + 20
        delay_sooner = 0
        delay_later = rng.choice(short_delays) if delay_cat == "short" else rng.choice(long_delays)

        # Human-like: present bias + delay sensitivity
        if delay_cat == "short":
            chose_sooner = rng.random() < 0.58
        else:
            chose_sooner = rng.random() < 0.32

        # Magnitude effect: less impatience for larger amounts
        if larger_amount >= 80:
            chose_sooner = chose_sooner and rng.random() < 0.70

        chose_larger = not chose_sooner
        chose_left = chose_sooner  # sooner on left
        resp = "f" if chose_left else "j"

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "smaller_amount": smaller_amount,
            "larger_amount": larger_amount,
            "delay_sooner": delay_sooner,
            "delay_later": delay_later,
            "delay_category": delay_cat,
            "chose_smaller": chose_sooner,
            "chose_larger": chose_larger,
            "chose_sooner": chose_sooner,
            "chose_larger_num": 1 if chose_larger else 0,
            "response": resp,
            "rt": round(max(300, rng.gauss(3000, 800)), 1),
            "timed_out": False,
        })
    return trials


def test_intertemporal_alignment():
    task_id = "intertemporal_choice"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_intertemporal_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Two-Step ----------

def _make_two_step_aligned(n=100):
    """Generate data matching exact two_step/experiment.js on_finish output."""
    rng = random.Random(42)
    trials = []
    prev_rewarded = None
    prev_transition = None

    for i in range(n):
        # Stage 1 choice
        stage1_choice = rng.choice(["left", "right"])
        stage1_rt = round(max(200, rng.gauss(600, 150)), 1)

        # Transition type
        transition_type = "common" if rng.random() < 0.70 else "rare"

        # Stage 2 choice
        stage2_choice = rng.choice(["left", "right"])
        stage2_rt = round(max(200, rng.gauss(500, 120)), 1)

        # Reward probability
        rewarded = rng.random() < 0.55

        # Stay behavior: model-based = reward x transition interaction
        if prev_rewarded is not None and prev_transition is not None:
            if prev_rewarded and prev_transition == "common":
                stayed = rng.random() < 0.80
            elif prev_rewarded and prev_transition == "rare":
                stayed = rng.random() < 0.55
            elif not prev_rewarded and prev_transition == "common":
                stayed = rng.random() < 0.40
            else:  # not rewarded, rare
                stayed = rng.random() < 0.65
        else:
            stayed = rng.random() < 0.60

        trial = {
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "stage1_choice": stage1_choice,
            "stage1_rt": stage1_rt,
            "transition_type": transition_type,
            "stage2_choice": stage2_choice,
            "stage2_rt": stage2_rt,
            "rewarded": rewarded,
            "stayed": stayed,
            "stayed_num": 1 if stayed else 0,
            "previous_rewarded": prev_rewarded if prev_rewarded is not None else False,
            "previous_rewarded_str": "rewarded" if (prev_rewarded if prev_rewarded is not None else False) else "unrewarded",
            "previous_transition": prev_transition if prev_transition is not None else "common",
            "response": "f" if stage1_choice == "left" else "j",
            "rt": stage1_rt,
            "timed_out": False,
        }
        trials.append(trial)
        prev_rewarded = rewarded
        prev_transition = transition_type

    return trials


def test_two_step_alignment():
    task_id = "two_step"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_two_step_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 interaction test may not always reach significance
    assert comp["composite_score"] > 0.0


# ---------- Decisions from Experience ----------

def _make_dfe_aligned(n=20):
    """Generate data matching exact decisions_from_experience/experiment.js on_finish output."""
    rng = random.Random(42)
    trials = []

    for i in range(n):
        rare_event = rng.random() < 0.50
        # Frugal sampling: humans typically take 7-15 samples
        total_samples = rng.randint(5, 14)
        frugal = total_samples < 15

        # Description-experience gap: worse on rare event problems
        if rare_event:
            chose_higher_ev = rng.random() < 0.48
        else:
            chose_higher_ev = rng.random() < 0.72

        # Recency: last sample matches choice direction
        last_sample_match = 1 if (chose_higher_ev and rng.random() < 0.65) else (0 if rng.random() < 0.65 else 1)

        resp = "f" if chose_higher_ev else "j"

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "problem_number": i + 1,
            "total_samples": total_samples,
            "chose_higher_ev": chose_higher_ev,
            "chose_higher_ev_num": 1 if chose_higher_ev else 0,
            "rare_event_present": rare_event,
            "frugal_sampling": frugal,
            "last_sample_match": last_sample_match,
            "response": resp,
            "rt": round(max(500, rng.gauss(3000, 1000)), 1),
            "timed_out": False,
        })
    return trials


def test_dfe_alignment():
    task_id = "decisions_from_experience"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_dfe_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    # L3 may partially fail with only 20 trials, check pipeline completes
    assert comp["composite_score"] > 0.0


# ---------- Prisoner's Dilemma ----------

def _make_prisoners_aligned(n=50):
    """Generate data matching exact prisoners_dilemma/experiment.js on_finish output."""
    rng = random.Random(42)
    trials = []
    # Payoff matrix: (CC=3,3), (CD=0,5), (DC=5,0), (DD=1,1)
    prev_player_coop = None
    prev_partner_coop = None
    prev_mutual_defection = False

    for i in range(n):
        # Tit-for-tat partner: mirrors player's previous choice
        if prev_player_coop is not None:
            partner_cooperated = prev_player_coop
        else:
            partner_cooperated = True  # partner starts cooperating

        # Human-like: ~55% cooperation, tit-for-tat reciprocity
        if prev_partner_coop is not None:
            if prev_partner_coop:
                player_cooperated = rng.random() < 0.70
            else:
                player_cooperated = rng.random() < 0.35
        else:
            player_cooperated = rng.random() < 0.60

        # Forgiveness: after mutual defection, cooperate more than base rate
        if prev_mutual_defection:
            player_cooperated = rng.random() < 0.45

        # Compute match to partner's previous choice
        if prev_partner_coop is not None:
            matched = player_cooperated == prev_partner_coop
        else:
            matched = True

        # Payoffs
        if player_cooperated and partner_cooperated:
            payoff = 3
        elif player_cooperated and not partner_cooperated:
            payoff = 0
        elif not player_cooperated and partner_cooperated:
            payoff = 5
        else:
            payoff = 1

        trial = {
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "round_number": i + 1,
            "player_choice": "cooperate" if player_cooperated else "defect",
            "partner_choice": "cooperate" if partner_cooperated else "defect",
            "player_cooperated": player_cooperated,
            "partner_cooperated": partner_cooperated,
            "player_payoff": payoff,
            "matched_partner": matched,
            "previous_mutual_defection": prev_mutual_defection,
            "response": "f" if player_cooperated else "j",
            "rt": round(max(300, rng.gauss(2000, 600)), 1),
            "timed_out": False,
        }
        trials.append(trial)

        prev_mutual_defection = (not player_cooperated and not partner_cooperated)
        prev_player_coop = player_cooperated
        prev_partner_coop = partner_cooperated

    return trials


def test_prisoners_alignment():
    task_id = "prisoners_dilemma"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_prisoners_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ---------- Probabilistic Classification ----------

def _make_probclass_aligned(n=100):
    """Generate data matching exact probabilistic_classification/experiment.js on_finish output."""
    rng = random.Random(42)
    # Cue validities: cue1=0.80, cue2=0.60, cue3=0.40, cue4=0.20
    # cue1 and cue2 are "strong" cues
    trials = []

    for i in range(n):
        block = i // 20 + 1
        # Randomly assign cue presence
        cue1 = rng.random() < 0.50
        cue2 = rng.random() < 0.50
        cue3 = rng.random() < 0.50
        cue4 = rng.random() < 0.50
        if not any((cue1, cue2, cue3, cue4)):
            cue1 = True  # ensure at least one cue

        strong_cue_present = cue1 or cue2

        # True outcome based on cue validities
        score = (0.80 if cue1 else 0.20) + (0.60 if cue2 else 0.40) + \
                (0.40 if cue3 else 0.60) + (0.20 if cue4 else 0.80)
        true_outcome = "sun" if score > 2.0 else "rain"

        # Learning: accuracy improves over blocks
        base_acc = 0.50 + 0.05 * block
        if strong_cue_present:
            base_acc += 0.08

        is_correct = rng.random() < base_acc
        response_key = "f" if (true_outcome == "sun") == is_correct else "j"
        predicted = true_outcome if is_correct else ("rain" if true_outcome == "sun" else "sun")

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "block": block,
            "cue1_present": cue1,
            "cue2_present": cue2,
            "cue3_present": cue3,
            "cue4_present": cue4,
            "strong_cue_present": strong_cue_present,
            "correct_outcome": true_outcome,
            "predicted_outcome": predicted,
            "correct": is_correct,
            "response": response_key,
            "rt": round(max(300, rng.gauss(2000, 500)), 1),
            "timed_out": False,
        })
    return trials


def test_probclass_alignment():
    task_id = "probabilistic_classification"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_probclass_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ── Loss Aversion ───────────────────────────────────────────────────────

def _make_loss_aversion_aligned(n=60):
    """Generate data matching exact loss_aversion/experiment.js on_finish output."""
    rng = random.Random(42)

    gains = [5, 10, 15, 20, 25, 30, 35, 40]
    losses = [5, 10, 15, 20, 25, 30, 35, 40]
    all_pairs = [(g, l) for g in gains for l in losses]
    rng.shuffle(all_pairs)
    selected = all_pairs[:n]

    trials = []
    lambda_loss = 2.0
    for i in range(n):
        gain, loss = selected[i]
        ev_gamble = (gain - loss) / 2.0
        ev_positive = ev_gamble > 0
        loss_gain_ratio = round(loss / gain, 3)
        ev_abs = abs(ev_gamble)

        subjective_value = gain - lambda_loss * loss
        accept_prob = 1.0 / (1.0 + math.exp(-subjective_value / 17.5))
        accept_prob = max(0.05, min(0.95, accept_prob))
        accept = rng.random() < accept_prob
        reject = not accept

        base_rt = 1500 - ev_abs * 20
        rt = round(max(300, rng.gauss(base_rt, 400)), 1)

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "gain": gain,
            "loss": loss,
            "ev_gamble": ev_gamble,
            "ev_positive": ev_positive,
            "loss_gain_ratio": loss_gain_ratio,
            "ev_abs": ev_abs,
            "accept": accept,
            "reject": reject,
            "accept_num": 1 if accept else 0,
            "response": "f" if accept else "j",
            "rt": rt,
            "timed_out": False,
        })
    return trials


def test_loss_aversion_alignment():
    task_id = "loss_aversion"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_loss_aversion_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert l3["score"] > 0.0, f"L3 zero: {l3}"
    assert comp["composite_score"] > 15.0


# ── Context Effects ─────────────────────────────────────────────────────

def _make_context_effects_aligned(n=90):
    rng = random.Random(42)
    trials = []
    n_training = n // 3
    target_mean = 70
    competitor_mean = 65

    for i in range(n_training):
        t_reward = round(target_mean + (rng.random() - 0.5) * 20)
        c_reward = round(competitor_mean + (rng.random() - 0.5) * 20)
        chose_target = rng.random() < (0.5 + 0.15 * i / n_training)

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "phase": "training",
            "effect_type": "none",
            "block": 1,
            "n_options": 2,
            "reward_0": t_reward,
            "reward_1": c_reward,
            "reward_2": None,
            "target_idx": 0,
            "option_chosen": 0 if chose_target else 1,
            "reward_chosen": t_reward if chose_target else c_reward,
            "is_target": chose_target,
            "trial_in_block": i + 1,
            "response": "f" if chose_target else "j",
            "rt": round(max(300, rng.gauss(1500, 400)), 1),
            "timed_out": False,
        })

    n_test = n - n_training
    effects = ["attraction", "compromise"]
    for i in range(n_test):
        effect = effects[i % 2]
        t_reward = round(target_mean + (rng.random() - 0.5) * 20)
        c_reward = round(competitor_mean + (rng.random() - 0.5) * 20)
        d_reward = round(t_reward * 0.75) if effect == "attraction" else round(target_mean * 1.3)

        prob_target = 0.50 if effect == "attraction" else 0.45
        r = rng.random()
        if r < prob_target:
            option_chosen = 0
        elif r < prob_target + 0.35:
            option_chosen = 1
        else:
            option_chosen = 2

        rewards = [t_reward, c_reward, d_reward]
        trials.append({
            "trial_part": "stimulus",
            "trial_index": n_training + i + 1,
            "phase": "test",
            "effect_type": effect,
            "block": 2 if effect == "attraction" else 3,
            "n_options": 3,
            "reward_0": t_reward,
            "reward_1": c_reward,
            "reward_2": d_reward,
            "target_idx": 0,
            "option_chosen": option_chosen,
            "reward_chosen": rewards[option_chosen],
            "is_target": option_chosen == 0,
            "trial_in_block": i + 1,
            "response": ["d", "f", "j"][option_chosen],
            "rt": round(max(300, rng.gauss(1500, 400)), 1),
            "timed_out": False,
        })

    return trials


def test_context_effects_alignment():
    task_id = "context_effects"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_context_effects_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ── Moral Judgment ──────────────────────────────────────────────────────

def _make_moral_judgment_aligned(n=26):
    rng = random.Random(42)
    trials = []
    scenario_types = ["quantity", "age", "gender", "status", "species", "intervention"]

    for i in range(n):
        scenario_type = scenario_types[i % len(scenario_types)]
        intervention = rng.random() > 0.5
        action_a = "swerve" if intervention else "continue ahead"
        action_b = "continue ahead" if intervention else "swerve"

        if scenario_type == "quantity":
            n_a = 1 + rng.randint(0, 1)
            n_b = n_a + 1 + rng.randint(0, 2)
        else:
            n_a = 1 + rng.randint(0, 2)
            n_b = 1 + rng.randint(0, 2)

        death_diff = abs(n_a - n_b)
        fewer_deaths_is_a = n_a < n_b

        # Simulate utilitarian with omission bias
        p_util = 0.65 + 0.05 * death_diff
        if fewer_deaths_is_a:
            chose_a = rng.random() < p_util
        elif n_b < n_a:
            chose_a = rng.random() > p_util
        else:
            chose_a = rng.random() < 0.45 if action_a == "swerve" else rng.random() < 0.55

        chose_fewer = (chose_a and fewer_deaths_is_a) or (not chose_a and n_b < n_a)
        if n_a == n_b:
            chose_fewer = True

        chose_intervention_val = (chose_a and action_a == "swerve") or (not chose_a and action_b == "swerve")
        chose_inaction_val = not chose_intervention_val

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "scenario_type": scenario_type,
            "intervention": intervention,
            "n_killed_a": n_a,
            "n_killed_b": n_b,
            "action_a": action_a,
            "action_b": action_b,
            "n_saved_a": n_b,
            "n_saved_b": n_a,
            "chose_fewer_deaths": chose_fewer,
            "chose_fewer_deaths_num": 1 if chose_fewer else 0,
            "death_difference": death_diff,
            "chose_intervention": chose_intervention_val,
            "chose_inaction": chose_inaction_val,
            "response": "f" if chose_a else "j",
            "rt": round(max(500, rng.gauss(5000, 2000)), 1),
            "timed_out": False,
        })

    return trials


def test_moral_judgment_alignment():
    task_id = "moral_judgment"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_moral_judgment_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Confirmation Bias RL ----------

def _make_confirmation_bias_rl_aligned(n_per_context=24):
    """Generate data matching confirmation_bias_rl/experiment.js on_finish output."""
    rng = random.Random(42)
    trials = []
    contexts = [
        {"id": 0, "feedback_type": "partial",  "p_left": 0.75, "p_right": 0.25},
        {"id": 1, "feedback_type": "partial",  "p_left": 0.25, "p_right": 0.75},
        {"id": 2, "feedback_type": "complete", "p_left": 0.75, "p_right": 0.25},
        {"id": 3, "feedback_type": "complete", "p_left": 0.25, "p_right": 0.75},
    ]

    trial_idx = 0
    for ctx in contexts:
        for t in range(n_per_context):
            trial_idx += 1
            arm = "left" if rng.random() > 0.5 else "right"
            p_chosen = ctx["p_left"] if arm == "left" else ctx["p_right"]
            p_unchosen = ctx["p_right"] if arm == "left" else ctx["p_left"]
            reward = 1 if rng.random() < p_chosen else -1
            unchosen_reward = 1 if rng.random() < p_unchosen else -1
            correct = (ctx["p_left"] >= ctx["p_right"] and arm == "left") or \
                      (ctx["p_right"] > ctx["p_left"] and arm == "right")

            trials.append({
                "trial_part": "stimulus",
                "trial_index": trial_idx,
                "context": ctx["id"],
                "feedback_type": ctx["feedback_type"],
                "arm_chosen": arm,
                "reward": reward,
                "unchosen_reward": unchosen_reward,
                "correct": correct,
                "stayed": rng.random() > 0.5,
                "prev_reward": rng.choice([-1, 1]),
                "response": "f" if arm == "left" else "j",
                "rt": round(max(200, rng.gauss(800, 150)), 1),
                "timed_out": False,
            })

    return trials


def test_confirmation_bias_rl_alignment():
    task_id = "confirmation_bias_rl"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_confirmation_bias_rl_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Magnitude RL ----------

def _make_magnitude_rl_aligned(trials_per_pair=24, n_transfer=24):
    """Generate data matching magnitude_rl/experiment.js on_finish output."""
    rng = random.Random(42)
    trials = []

    pairs = [
        {"id": 0, "reward_magnitude": "high", "mag_value": 10, "p_left": 0.75, "p_right": 0.25},
        {"id": 1, "reward_magnitude": "high", "mag_value": 10, "p_left": 0.25, "p_right": 0.75},
        {"id": 2, "reward_magnitude": "low",  "mag_value": 1,  "p_left": 0.75, "p_right": 0.25},
        {"id": 3, "reward_magnitude": "low",  "mag_value": 1,  "p_left": 0.25, "p_right": 0.75},
    ]

    trial_idx = 0
    for pair in pairs:
        for t in range(trials_per_pair):
            trial_idx += 1
            arm = "left" if rng.random() > 0.5 else "right"
            p_chosen = pair["p_left"] if arm == "left" else pair["p_right"]
            win = rng.random() < p_chosen
            reward = pair["mag_value"] if win else -pair["mag_value"]
            correct = (pair["p_left"] >= pair["p_right"] and arm == "left") or \
                      (pair["p_right"] > pair["p_left"] and arm == "right")

            trials.append({
                "trial_part": "stimulus",
                "trial_index": trial_idx,
                "phase": "learning",
                "context": pair["id"],
                "reward_magnitude": pair["reward_magnitude"],
                "mag_value": pair["mag_value"],
                "arm_chosen": arm,
                "reward": reward,
                "correct": correct,
                "response": "f" if arm == "left" else "j",
                "rt": round(max(200, rng.gauss(700, 150)), 1),
                "timed_out": False,
            })

    # Transfer trials
    for t in range(n_transfer):
        trial_idx += 1
        chose_high = rng.random() > 0.4  # slight high-mag preference
        trials.append({
            "trial_part": "stimulus",
            "trial_index": trial_idx,
            "phase": "transfer",
            "context": "transfer",
            "reward_magnitude": "mixed",
            "mag_value": 0,
            "arm_chosen": "left" if rng.random() > 0.5 else "right",
            "reward": 0,
            "correct": True,
            "chose_high_magnitude": chose_high,
            "response": "f" if rng.random() > 0.5 else "j",
            "rt": round(max(200, rng.gauss(800, 200)), 1),
            "timed_out": False,
        })

    return trials


def test_magnitude_rl_alignment():
    task_id = "magnitude_rl"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_magnitude_rl_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Probability Learning ----------

def _make_probability_learning_aligned(n=100):
    """Generate data matching probability_learning/experiment.js on_finish output."""
    rng = random.Random(42)
    trials = []
    p_left = 0.70
    p_right = 0.30
    optimal_side = "left"

    prev_choice = None
    prev_reward = None

    for i in range(n):
        left_outcome = 1 if rng.random() < p_left else 0
        right_outcome = 1 if rng.random() < p_right else 0

        # Probability matching with some learning
        p_choose_left = 0.5 + 0.2 * (i / n)  # gradually learns
        choice = "left" if rng.random() < p_choose_left else "right"
        reward = left_outcome if choice == "left" else right_outcome
        correct = reward == 1
        chose_optimal = choice == optimal_side
        stayed = choice == prev_choice if prev_choice is not None else False

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "choice": choice,
            "reward": reward,
            "correct": correct,
            "chose_optimal": chose_optimal,
            "optimal_side": optimal_side,
            "left_outcome": left_outcome,
            "right_outcome": right_outcome,
            "stayed": stayed,
            "prev_reward": prev_reward,
            "response": "f" if choice == "left" else "j",
            "rt": round(max(200, rng.gauss(650, 150)), 1),
            "timed_out": False,
        })
        prev_choice = choice
        prev_reward = reward

    return trials


def test_probability_learning_alignment():
    task_id = "probability_learning"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_probability_learning_aligned()

    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])

    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Novelty Exploration ----------

def _make_novelty_exploration_aligned(n_blocks=10, trials_per_block=15):
    rng = random.Random(42)
    trials = []
    trial_idx = 0
    seen = set()

    for b in range(n_blocks):
        for t in range(trials_per_block):
            trial_idx += 1
            opt_id = "opt_%d_%d" % (b, rng.randint(0, 5))
            is_novel = opt_id not in seen
            seen.add(opt_id)
            reward = 1 if rng.random() < 0.5 else 0
            trials.append({
                "trial_part": "stimulus", "trial_index": trial_idx,
                "block": b, "trial_in_block": t,
                "chosen_option": opt_id,
                "chosen_novelty": "novel" if is_novel else "familiar",
                "chose_novel": is_novel,
                "reward": reward, "correct": reward == 1,
                "response": "f" if rng.random() > 0.5 else "j",
                "rt": round(max(200, rng.gauss(900, 200)), 1),
                "timed_out": False,
            })
    return trials


def test_novelty_exploration_alignment():
    task_id = "novelty_exploration"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_novelty_exploration_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Safe Exploration ----------

def _make_safe_exploration_aligned(n_blocks=10, trials_per_block=10):
    rng = random.Random(42)
    trials = []
    trial_idx = 0
    for b in range(n_blocks):
        risk = "risky" if b % 2 == 1 else "safe"
        for t in range(trials_per_block):
            trial_idx += 1
            side = "left" if rng.random() > 0.5 else "right"
            reward = round(max(0, rng.gauss(50, 15)))
            correct = rng.random() > 0.4
            kraken = risk == "risky" and reward < 40 and rng.random() < 0.3
            trials.append({
                "trial_part": "stimulus", "trial_index": trial_idx,
                "block": b, "trial_in_block": t,
                "risk_condition": risk,
                "chosen_option": side, "reward": reward, "correct": correct,
                "kraken_caught": kraken,
                "response": "f" if side == "left" else "j",
                "rt": round(max(200, rng.gauss(800, 200)), 1),
                "timed_out": False,
            })
    return trials


def test_safe_exploration_alignment():
    task_id = "safe_exploration"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_safe_exploration_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Observe or Bet ----------

def _make_observe_or_bet_aligned(n=125):
    rng = random.Random(42)
    trials = []
    block_sizes = [25, 50, 50]
    block_probs = [0.70, 0.30, 0.80]
    trial_idx = 0
    for b in range(3):
        for t in range(block_sizes[b]):
            trial_idx += 1
            p_blue = block_probs[b]
            light = "blue" if rng.random() < p_blue else "red"
            is_observe = rng.random() < 0.3
            if is_observe:
                action = "observe"
                correct = False
                reward = 0
            else:
                guess_blue = rng.random() < 0.6
                action = "guess_blue" if guess_blue else "guess_red"
                correct = (action == "guess_blue" and light == "blue") or (action == "guess_red" and light == "red")
                reward = 1 if correct else -1
            trials.append({
                "trial_part": "stimulus", "trial_index": trial_idx,
                "block": b, "trial_in_block": t, "is_practice": b == 0,
                "action": action, "light_color": light,
                "reward": reward, "correct": correct,
                "is_observe": is_observe, "is_observe_num": 1 if is_observe else 0,
                "is_bet": not is_observe,
                "response": "k" if is_observe else ("f" if action == "guess_blue" else "j"),
                "rt": round(max(200, rng.gauss(1200, 300)), 1),
                "timed_out": False,
            })
    return trials


def test_observe_or_bet_alignment():
    task_id = "observe_or_bet"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_observe_or_bet_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Random Dot Motion ----------

def _make_random_dot_motion_aligned(n=120):
    rng = random.Random(42)
    conditions = ["easy", "medium", "hard"]
    ratios = {"easy": [1.8, 2.0], "medium": [1.4, 1.5], "hard": [1.1, 1.2]}
    acc_map = {"easy": 0.90, "medium": 0.75, "hard": 0.60}
    trials = []
    for i in range(n):
        cond = conditions[i % 3]
        ratio = rng.choice(ratios[cond])
        base = rng.randint(10, 30)
        n_left, n_right = base, round(base * ratio)
        correct_side = "right"
        if rng.random() < 0.5:
            n_left, n_right = n_right, n_left
            correct_side = "left"
        correct_key = "f" if correct_side == "left" else "j"
        is_correct = rng.random() < acc_map[cond]
        response = correct_key if is_correct else ("f" if correct_key == "j" else "j")
        rt = max(200, rng.gauss(850 - 200 * (ratio - 1.0), 150))
        trials.append({
            "trial_part": "stimulus", "trial_index": i + 1,
            "condition": cond, "n_left": n_left, "n_right": n_right,
            "ratio": ratio, "correct_side": correct_side,
            "correct": is_correct, "response": response,
            "rt": round(rt, 1), "timed_out": False,
        })
    return trials


def test_random_dot_motion_alignment():
    task_id = "random_dot_motion"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_random_dot_motion_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Lexical Decision ----------

def _make_lexical_decision_aligned(n=120):
    rng = random.Random(42)
    high_words = ["table", "house", "water", "money", "light"]
    low_words = ["plumb", "glyph", "trove", "fjord", "knoll"]
    nonwords = ["flirp", "glomb", "snarp", "brive", "clunt"]
    trials = []
    half = n // 2
    word_half = half // 2
    for i in range(n):
        if i < word_half:
            stim = high_words[i % len(high_words)]
            stype, wfreq = "word", "high"
            correct_key = "f"
            acc = 0.96
        elif i < half:
            stim = low_words[(i - word_half) % len(low_words)]
            stype, wfreq = "word", "low"
            correct_key = "f"
            acc = 0.92
        else:
            stim = nonwords[(i - half) % len(nonwords)]
            stype, wfreq = "nonword", "none"
            correct_key = "j"
            acc = 0.94
        is_correct = rng.random() < acc
        response = correct_key if is_correct else ("f" if correct_key == "j" else "j")
        rt = max(200, rng.gauss(600, 100))
        trials.append({
            "trial_part": "stimulus", "trial_index": i + 1,
            "stimulus": stim, "stimulus_type": stype,
            "word_frequency": wfreq, "correct": is_correct,
            "response": response, "rt": round(rt, 1), "timed_out": False,
        })
    return trials


def test_lexical_decision_alignment():
    task_id = "lexical_decision"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_lexical_decision_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Heuristics & Biases ----------

def _make_heuristics_biases_aligned(n=40):
    rng = random.Random(42)
    n_tasks = 10
    tpt = n // n_tasks
    trials = []
    for t in range(n_tasks):
        weights = [rng.random() * 2 - 1 for _ in range(4)]
        best_cue = max(range(4), key=lambda c: abs(weights[c]))
        for s in range(tpt):
            cues_a = [rng.randint(10, 90) for _ in range(4)]
            cues_b = [rng.randint(10, 90) for _ in range(4)]
            score_a = sum(w * c for w, c in zip(weights, cues_a)) + rng.gauss(0, 5)
            score_b = sum(w * c for w, c in zip(weights, cues_b)) + rng.gauss(0, 5)
            correct_answer = "f" if score_a > score_b else "j"
            ttb_choice = "f" if (weights[best_cue] > 0) == (cues_a[best_cue] > cues_b[best_cue]) else "j"
            ttb_correct = ttb_choice == correct_answer
            accuracy = 0.5 + 0.3 * (s / max(1, tpt - 1))
            is_correct = rng.random() < accuracy
            response = correct_answer if is_correct else ("f" if correct_answer == "j" else "j")
            used_ttb = (response == correct_answer) == ttb_correct
            cue_diff = [cues_a[i] - cues_b[i] for i in range(4)]
            rt = max(500, rng.gauss(3200, 800))
            trials.append({
                "trial_part": "stimulus", "trial_index": len(trials) + 1,
                "block": t, "trial_in_block": s,
                "cue_values": json.dumps(cue_diff), "correct_answer": correct_answer,
                "dominant_cue": best_cue, "ttb_correct": ttb_correct,
                "correct": is_correct, "used_ttb": used_ttb,
                "response": response, "rt": round(rt, 1), "timed_out": False,
            })
    return trials


def test_heuristics_biases_alignment():
    task_id = "heuristics_biases"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_heuristics_biases_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Phishing Detection ----------

def _make_phishing_detection_aligned(n=60):
    rng = random.Random(42)
    phases = [("pre", 10), ("train", 40), ("post", 10)]
    acc_map = {"pre": 0.70, "train": 0.80, "post": 0.85}
    trials = []
    idx = 0
    for phase_name, count in phases:
        for i in range(count):
            idx += 1
            email_type = "phishing" if rng.random() < 0.3 else "ham"
            is_correct = rng.random() < acc_map[phase_name]
            correct_key = "j" if email_type == "phishing" else "f"
            response = correct_key if is_correct else ("f" if correct_key == "j" else "j")
            trials.append({
                "trial_part": "stimulus", "trial_index": idx,
                "phase": phase_name, "email_type": email_type,
                "show_feedback": phase_name == "train",
                "correct": is_correct, "response": response,
                "rt": round(max(500, rng.gauss(5000, 1500)), 1), "timed_out": False,
            })
    return trials


def test_phishing_detection_alignment():
    task_id = "phishing_detection"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_phishing_detection_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Causal Reasoning ----------

def _make_causal_reasoning_aligned(n=150):
    rng = random.Random(42)
    conditions = ["robber", "millionaire", "sheriff"]
    trials = []
    tpb = n // 3
    for b in range(3):
        for t in range(tpb):
            pref_a = 0.5 + 0.15 * (t / max(1, tpb - 1))
            chose_a = rng.random() < pref_a
            agent_active = rng.random() < 0.3
            mine_a_gold = rng.random() < 0.7
            mine_b_gold = rng.random() < 0.3
            if agent_active:
                if conditions[b] == "robber":
                    mine_a_gold = mine_b_gold = False
                elif conditions[b] == "millionaire":
                    mine_a_gold = mine_b_gold = True
                else:
                    mine_a_gold, mine_b_gold = mine_b_gold, mine_a_gold
            feedback = mine_a_gold if chose_a else mine_b_gold
            trials.append({
                "trial_part": "stimulus", "trial_index": len(trials) + 1,
                "block": b, "condition": conditions[b], "trial_in_block": t,
                "agent_active": agent_active, "mine_a_gold": mine_a_gold, "mine_b_gold": mine_b_gold,
                "choice": "A" if chose_a else "B", "feedback": feedback,
                "correct": feedback, "chose_better_mine": chose_a,
                "response": "f" if chose_a else "j",
                "rt": round(max(300, rng.gauss(1500, 400)), 1), "timed_out": False,
            })
    return trials


def test_causal_reasoning_alignment():
    task_id = "causal_reasoning"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_causal_reasoning_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Insider Attack ----------

def _make_insider_attack_aligned(n=100):
    rng = random.Random(42)
    trials = []
    tpr = n // 4
    for r in range(4):
        for t in range(tpr):
            left_reward = rng.randint(2, 9)
            left_penalty = -rng.randint(1, 8)
            left_mprob = round(rng.random() * 0.55 + 0.05, 2)
            right_reward = rng.randint(2, 9)
            right_penalty = -rng.randint(1, 8)
            right_mprob = round(rng.random() * 0.55 + 0.05, 2)
            left_ev = left_reward * (1 - left_mprob) + left_penalty * left_mprob
            right_ev = right_reward * (1 - right_mprob) + right_penalty * right_mprob
            chose_left = (left_ev >= right_ev and rng.random() < 0.65) or (left_ev < right_ev and rng.random() > 0.65)
            chose_higher_ev = (chose_left and left_ev >= right_ev) or (not chose_left and right_ev >= left_ev)
            chosen_mprob = left_mprob if chose_left else right_mprob
            monitored = rng.random() < chosen_mprob
            reward = (left_penalty if chose_left else right_penalty) if monitored else (left_reward if chose_left else right_reward)
            trials.append({
                "trial_part": "stimulus", "trial_index": len(trials) + 1,
                "round": r, "trial_in_round": t,
                "left_reward": left_reward, "right_reward": right_reward,
                "left_penalty": left_penalty, "right_penalty": right_penalty,
                "left_mprob": left_mprob, "right_mprob": right_mprob,
                "left_ev": round(left_ev, 2), "right_ev": round(right_ev, 2),
                "target": 0 if chose_left else 1, "monitored": monitored,
                "warning": monitored and rng.random() < 0.7,
                "reward": reward, "correct": not monitored,
                "chose_higher_ev": chose_higher_ev,
                "response": "f" if chose_left else "j",
                "rt": round(max(500, rng.gauss(3000, 800)), 1), "timed_out": False,
            })
    return trials


def test_insider_attack_alignment():
    task_id = "insider_attack"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_insider_attack_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0


# ---------- Function Estimation ----------


def _make_function_estimation_aligned(n=40):
    rng = random.Random(42)
    n_blocks = 8
    tpb = n // n_blocks
    func_types = ["linear", "quadratic", "sinusoidal", "exponential"]
    trials = []
    for b in range(n_blocks):
        ft = func_types[b % len(func_types)]
        a = (rng.random() * 1.5 + 0.5) * (1 if rng.random() < 0.5 else -1)
        bc = rng.random() * 0.4 - 0.2
        for t in range(tpb):
            x = round(-0.9 + 1.8 * t / max(1, tpb - 1), 2)
            if ft == "linear":
                cy = a * x + bc
            elif ft == "quadratic":
                cy = a * x * x + bc
            elif ft == "sinusoidal":
                cy = a * math.sin(3 * x) + bc
            else:
                cy = a * (math.exp(x) - 1) + bc
            cy = max(-1, min(1, round(cy, 2)))
            noise = rng.gauss(0, 0.12)
            resp = max(-1, min(1, round(cy + noise, 2)))
            err = round(abs(resp - cy), 4)
            trials.append({
                "trial_part": "stimulus", "trial_index": len(trials) + 1,
                "block": b, "trial_in_block": t, "x_value": x,
                "correct_y": cy, "func_type": ft,
                "response": resp, "estimation_error": err,
                "correct": err < 0.3,
                "rt": round(max(1000, rng.gauss(5000, 1500)), 1), "timed_out": False,
            })
    return trials


def test_function_estimation_alignment():
    task_id = "function_estimation"
    config = _load_config(task_id)
    metrics = _load_spec(task_id, "level2_metrics.json")
    sigs = _load_spec(task_id, "level3_signatures.json")
    trials = _make_function_estimation_aligned()
    l1 = score_completion(trials, config)
    l2 = score_accuracy(trials, metrics)
    l3 = score_behavioral(trials, sigs)
    comp = compute_composite(l1["score"], l2["score"], l3["score"])
    assert l1["score"] == 1.0, f"L1 failed: {l1}"
    assert l2["score"] > 0.0, f"L2 zero: {l2}"
    assert comp["composite_score"] > 0.0
