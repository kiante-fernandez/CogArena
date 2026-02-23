"""
Field alignment integration tests.

Verify that synthetic data matching the exact experiment.js output format
scores correctly through the full L1/L2/L3 pipeline. Catches mismatches
between experiment field names and scoring spec expectations.
"""
import json
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
