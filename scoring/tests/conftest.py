import json
import math
import random
import pytest
import numpy as np


def _generate_stroop_trials(
    n_trials=96,
    accuracy=0.95,
    mean_rt_congruent=600,
    stroop_effect=80,
    post_error_slowing=30,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    colors = ["red", "blue", "green", "yellow"]
    key_map = {"red": "d", "blue": "f", "green": "j", "yellow": "k"}
    conditions = ["congruent", "incongruent", "neutral"]
    trials = []
    prev_correct = True

    for i in range(n_trials):
        condition = conditions[i % 3]
        color = colors[i % len(colors)]
        correct_key = key_map[color]

        base_rt = mean_rt_congruent
        if condition == "incongruent":
            base_rt += stroop_effect
        if not prev_correct:
            base_rt += post_error_slowing

        rt = max(150, float(np_rng.normal(base_rt, 100)))

        timed_out = rng.random() < timeout_rate
        if timed_out:
            is_correct = False
            response = None
            rt = None
        else:
            is_correct = rng.random() < accuracy
            if is_correct:
                response = correct_key
            else:
                others = [k for k in key_map.values() if k != correct_key]
                response = rng.choice(others)

        word = color.upper() if condition == "congruent" else "XXXX" if condition == "neutral" else colors[(colors.index(color) + 1) % len(colors)].upper()

        trial = {
            "trial_index": i + 1,
            "block": i // 24 + 1,
            "condition": condition,
            "stimulus_word": word,
            "stimulus_color": color,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "correct_key": correct_key,
            "timed_out": timed_out,
        }
        trials.append(trial)
        prev_correct = is_correct

    return trials


@pytest.fixture
def stroop_config():
    return {
        "task_id": "stroop",
        "parameters": {
            "n_trials": 96,
            "n_blocks": 4,
            "trials_per_block": 24,
            "response_keys": ["d", "f", "j", "k"],
            "color_key_mapping": {"red": "d", "blue": "f", "green": "j", "yellow": "k"},
        },
    }


@pytest.fixture
def stroop_metrics():
    return {
        "task_id": "stroop",
        "metrics": [
            {
                "name": "overall_accuracy",
                "type": "proportion_correct",
                "field": "correct",
                "human_mean": 0.95,
                "human_sd": 0.04,
            },
            {
                "name": "congruent_accuracy",
                "type": "proportion_correct",
                "field": "correct",
                "filter": {"condition": "congruent"},
                "human_mean": 0.97,
                "human_sd": 0.03,
            },
            {
                "name": "incongruent_accuracy",
                "type": "proportion_correct",
                "field": "correct",
                "filter": {"condition": "incongruent"},
                "human_mean": 0.92,
                "human_sd": 0.06,
            },
            {
                "name": "mean_correct_rt",
                "type": "mean",
                "field": "rt",
                "filter": {"correct": True},
                "human_mean": 680,
                "human_sd": 120,
                "direction": "lower_is_better",
            },
        ],
    }


@pytest.fixture
def stroop_signatures():
    return {
        "task_id": "stroop",
        "signatures": [
            {
                "name": "stroop_interference_rt",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"condition": "incongruent"}, "field": "rt"},
                "group_b": {"filter": {"condition": "congruent"}, "field": "rt"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "post_error_slowing",
                "test": "sequential_regression",
                "predictor": {"field": "correct", "lag": 1, "invert": True},
                "outcome": {"field": "rt"},
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
        ],
    }


@pytest.fixture
def human_like_stroop_data():
    return _generate_stroop_trials(accuracy=0.95, stroop_effect=80, post_error_slowing=30)


@pytest.fixture
def random_stroop_data():
    return _generate_stroop_trials(accuracy=0.50, stroop_effect=0, post_error_slowing=0, seed=99)


@pytest.fixture
def perfect_stroop_data():
    return _generate_stroop_trials(accuracy=1.0, mean_rt_congruent=200, stroop_effect=0, post_error_slowing=0)


@pytest.fixture
def incomplete_stroop_data():
    return _generate_stroop_trials(n_trials=20, accuracy=0.70, timeout_rate=0.3, seed=77)


# ── 2-Armed Bandit ──────────────────────────────────────────

def _generate_bandit_trials(
    n_trials=80,
    accuracy=0.65,
    horizon_effect=0.15,
    win_stay_rate=0.7,
    directed_exploration_rate=0.60,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    prev_arm = None
    prev_won = False

    horizons = []
    for _ in range(n_trials // 2):
        horizons.append(6)
    for _ in range(n_trials // 2):
        horizons.append(1)
    rng.shuffle(horizons)

    for i in range(n_trials):
        horizon = horizons[i]
        game_index = i
        info_condition = "unequal" if rng.random() > 0.3 else "equal"

        if horizon == 6:
            base_acc = accuracy - horizon_effect / 2
        else:
            base_acc = accuracy + horizon_effect / 2

        arm_left_mean = 50 + rng.randint(-5, 5)
        arm_right_mean = arm_left_mean + rng.choice([-1, 1]) * rng.randint(4, 12)
        higher_arm = "left" if arm_left_mean >= arm_right_mean else "right"

        is_correct = rng.random() < base_acc
        arm_chosen = higher_arm if is_correct else ("left" if higher_arm == "right" else "right")

        more_info_arm = rng.choice(["left", "right"])
        chose_less = arm_chosen != more_info_arm

        if horizon == 6 and info_condition == "unequal":
            if rng.random() < directed_exploration_rate:
                chose_less = True
            else:
                chose_less = False

        mean = arm_left_mean if arm_chosen == "left" else arm_right_mean
        reward = int(np_rng.normal(mean, 8))

        timed_out = rng.random() < timeout_rate
        rt = max(200, float(np_rng.normal(800, 150))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "game_index": game_index,
            "horizon": horizon,
            "trial_in_game": 1,
            "trial_type": "free",
            "arm_chosen": arm_chosen,
            "reward": reward,
            "arm_left_mean": arm_left_mean,
            "arm_right_mean": arm_right_mean,
            "info_condition": info_condition,
            "more_info_arm": more_info_arm,
            "correct": is_correct,
            "explore_choice": not is_correct,
            "chose_less_sampled": chose_less,
            "rt": rt,
            "timed_out": timed_out,
            "response": "f" if arm_chosen == "left" else "j",
        }

        if prev_arm is not None:
            trial["stayed"] = arm_chosen == prev_arm
            trial["prev_win"] = prev_won
        else:
            trial["stayed"] = False
            trial["prev_win"] = False

        trials.append(trial)
        prev_arm = arm_chosen
        prev_won = is_correct

    return trials


@pytest.fixture
def bandit_config():
    return {
        "task_id": "two_armed_bandit",
        "parameters": {
            "n_trials": 80,
            "n_games": 40,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def bandit_metrics():
    return {
        "task_id": "two_armed_bandit",
        "metrics": [
            {"name": "overall_optimal_choice", "type": "proportion_correct", "field": "correct", "human_mean": 0.65, "human_sd": 0.10},
            {"name": "horizon1_optimal", "type": "proportion_correct", "field": "correct", "filter": {"horizon": 1}, "human_mean": 0.70, "human_sd": 0.12},
            {"name": "horizon6_optimal", "type": "proportion_correct", "field": "correct", "filter": {"horizon": 6}, "human_mean": 0.62, "human_sd": 0.12},
            {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"correct": True}, "human_mean": 800, "human_sd": 200, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def bandit_signatures():
    return {
        "task_id": "two_armed_bandit",
        "signatures": [
            {
                "name": "horizon_effect_exploration",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"horizon": 6}, "field": "explore_choice"},
                "group_b": {"filter": {"horizon": 1}, "field": "explore_choice"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "win_stay",
                "test": "proportion_test",
                "filter": {"prev_win": True},
                "field": "stayed",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
            {
                "name": "directed_exploration",
                "test": "proportion_test",
                "filter": {"horizon": 6, "info_condition": "unequal"},
                "field": "chose_less_sampled",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
        ],
    }


@pytest.fixture
def human_like_bandit_data():
    return _generate_bandit_trials(accuracy=0.65, horizon_effect=0.20, win_stay_rate=0.7, directed_exploration_rate=0.65)


@pytest.fixture
def random_bandit_data():
    return _generate_bandit_trials(accuracy=0.50, horizon_effect=0.0, win_stay_rate=0.5, directed_exploration_rate=0.5, seed=99)


# ── Risky Choice ────────────────────────────────────────────

def _generate_risky_choice_trials(
    n_trials=60,
    risk_aversion=0.6,
    loss_aversion=0.15,
    ev_sensitivity=0.3,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    choice_rng = random.Random(seed + 1000)
    np_rng = np.random.RandomState(seed)
    trials = []
    domains = ["gain", "loss", "mixed"]
    probabilities = [0.1, 0.25, 0.5, 0.75, 0.9]

    for i in range(n_trials):
        domain = domains[i % 3]
        prob = probabilities[i % len(probabilities)]
        stake = rng.choice([20, 30, 40, 50, 60, 80])

        if domain == "gain":
            ev_risky = stake * prob
            safe = round(ev_risky * (0.8 + rng.random() * 0.4))
            ev_safe = safe
        elif domain == "loss":
            ev_risky = -stake * (1 - prob)
            safe = round(ev_risky * (0.8 + rng.random() * 0.4))
            ev_safe = safe
        else:
            ev_risky = stake * prob - stake * 0.5 * (1 - prob)
            safe = round(ev_risky * (0.8 + rng.random() * 0.4))
            ev_safe = safe

        ev_diff = ev_risky - ev_safe

        base_risky_prob = 1 - risk_aversion
        if domain == "loss":
            base_risky_prob += loss_aversion
        elif domain == "gain":
            base_risky_prob -= loss_aversion * 0.5

        base_risky_prob += ev_diff * ev_sensitivity * 0.001
        base_risky_prob = max(0.05, min(0.95, base_risky_prob))

        timed_out = choice_rng.random() < timeout_rate
        chose_risky = choice_rng.random() < base_risky_prob and not timed_out
        rt = max(300, float(np_rng.normal(2500, 600))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "domain": domain,
            "probability": prob,
            "risky_outcome": stake if domain != "loss" else 0,
            "safe_outcome": safe,
            "ev_risky": ev_risky,
            "ev_safe": ev_safe,
            "ev_difference": ev_diff,
            "chose_risky": chose_risky,
            "chose_risky_num": 1 if chose_risky else 0,
            "chose_safe": not chose_risky and not timed_out,
            "response": "f" if chose_risky else "j",
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def risky_choice_config():
    return {
        "task_id": "risky_choice",
        "parameters": {
            "n_trials": 60,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def risky_choice_metrics():
    return {
        "task_id": "risky_choice",
        "metrics": [
            {"name": "overall_risky_choice_rate", "type": "proportion_correct", "field": "chose_risky", "human_mean": 0.45, "human_sd": 0.15},
            {"name": "gain_risky_rate", "type": "proportion_correct", "field": "chose_risky", "filter": {"domain": "gain"}, "human_mean": 0.35, "human_sd": 0.18},
            {"name": "loss_risky_rate", "type": "proportion_correct", "field": "chose_risky", "filter": {"domain": "loss"}, "human_mean": 0.55, "human_sd": 0.18},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 2500, "human_sd": 800, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def risky_choice_signatures():
    return {
        "task_id": "risky_choice",
        "signatures": [
            {
                "name": "risk_aversion_gains",
                "test": "proportion_test",
                "filter": {"domain": "gain"},
                "field": "chose_safe",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "loss_aversion_framing",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"domain": "loss"}, "field": "chose_risky"},
                "group_b": {"filter": {"domain": "gain"}, "field": "chose_risky"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "ev_sensitivity",
                "test": "correlation_test",
                "field_x": "ev_difference",
                "field_y": "chose_risky_num",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_risky_choice_data():
    return _generate_risky_choice_trials(risk_aversion=0.65, loss_aversion=0.20, ev_sensitivity=0.3)


@pytest.fixture
def random_risky_choice_data():
    return _generate_risky_choice_trials(risk_aversion=0.5, loss_aversion=0.0, ev_sensitivity=0.0, seed=99)


# ── Trust Game ──────────────────────────────────────────────

def _generate_trust_trials(
    n_rounds=15,
    mean_investment=0.5,
    reciprocity=0.3,
    adaptation=0.2,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    endowment = 10
    multiplier = 3

    trustee_types = []
    for _ in range(5):
        trustee_types.append(("cooperative", 0.40, 0.60))
    for _ in range(5):
        trustee_types.append(("neutral", 0.25, 0.35))
    for _ in range(5):
        trustee_types.append(("defecting", 0.05, 0.15))
    rng.shuffle(trustee_types)

    prev_return_proportion = None

    for i in range(n_rounds):
        tt_type, ret_min, ret_max = trustee_types[i]

        base = mean_investment
        if tt_type == "cooperative":
            base += adaptation
        elif tt_type == "defecting":
            base -= adaptation

        if prev_return_proportion is not None:
            base += reciprocity * (prev_return_proportion - 0.3)

        base = max(0.0, min(1.0, base))
        amount_prop = max(0.0, min(1.0, float(np_rng.normal(base, 0.15))))
        amount_sent = round(amount_prop * endowment)
        amount_prop = amount_sent / endowment

        tripled = amount_sent * multiplier
        return_rate = ret_min + rng.random() * (ret_max - ret_min)
        amount_returned = round(tripled * return_rate)
        amount_returned = max(0, min(tripled, amount_returned))
        return_prop = amount_returned / tripled if tripled > 0 else 0

        timed_out = rng.random() < timeout_rate
        rt = max(500, float(np_rng.normal(4000, 1200))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "round": i + 1,
            "trustee_id": i,
            "trustee_type": tt_type,
            "endowment": endowment,
            "amount_sent": amount_sent if not timed_out else 0,
            "amount_sent_proportion": amount_prop if not timed_out else 0.0,
            "sent_nonzero": amount_sent > 0 if not timed_out else False,
            "tripled_amount": tripled if not timed_out else 0,
            "amount_returned": amount_returned if not timed_out else 0,
            "amount_returned_proportion": return_prop if not timed_out else 0.0,
            "net_payoff": (endowment - amount_sent) + amount_returned if not timed_out else endowment,
            "rt": rt,
            "timed_out": timed_out,
            "response": amount_sent if not timed_out else None,
        }

        if prev_return_proportion is not None:
            trial["prev_return_proportion"] = prev_return_proportion

        trials.append(trial)
        prev_return_proportion = return_prop

    return trials


@pytest.fixture
def trust_config():
    return {
        "task_id": "trust_game",
        "parameters": {
            "n_trials": 15,
            "n_rounds": 15,
            "endowment": 10,
            "multiplier": 3,
            "response_type": "slider",
            "response_field": "amount_sent",
            "slider_range": [0, 10],
        },
    }


@pytest.fixture
def trust_metrics():
    return {
        "task_id": "trust_game",
        "metrics": [
            {"name": "mean_investment_proportion", "type": "mean", "field": "amount_sent_proportion", "human_mean": 0.50, "human_sd": 0.15},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 4000, "human_sd": 1500, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def trust_signatures():
    return {
        "task_id": "trust_game",
        "signatures": [
            {
                "name": "above_zero_trust",
                "test": "proportion_test",
                "filter": {},
                "field": "sent_nonzero",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "trustee_type_adaptation",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"trustee_type": "cooperative"}, "field": "amount_sent_proportion"},
                "group_b": {"filter": {"trustee_type": "defecting"}, "field": "amount_sent_proportion"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_trust_data():
    return _generate_trust_trials(mean_investment=0.5, reciprocity=0.3, adaptation=0.2)


@pytest.fixture
def random_trust_data():
    return _generate_trust_trials(mean_investment=0.5, reciprocity=0.0, adaptation=0.0, seed=99)


# ── N-Back ──────────────────────────────────────────────────

def _generate_nback_trials(
    n_trials=120,
    hit_rate=0.75,
    false_alarm_rate=0.15,
    lure_fa_rate=0.30,
    target_proportion=0.30,
    lure_proportion=0.10,
    post_error_slowing=20,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    letters = ["B", "C", "D", "F", "G", "H", "J", "K", "L", "M"]
    trials = []
    prev_correct = True

    n_targets = round(n_trials * target_proportion)
    n_lures = round(n_trials * lure_proportion)
    n_other = n_trials - n_targets - n_lures

    trial_types = (
        ["target"] * n_targets +
        ["lure"] * n_lures +
        ["nontarget"] * n_other
    )
    rng.shuffle(trial_types)

    for i in range(n_trials):
        tt = trial_types[i]
        is_target = tt == "target"
        is_lure = tt == "lure"
        stimulus = rng.choice(letters)

        base_rt = 550
        if not prev_correct:
            base_rt += post_error_slowing
        rt = max(150, float(np_rng.normal(base_rt, 80)))

        timed_out = rng.random() < timeout_rate

        if timed_out:
            correct = False
            response = None
            rt = None
            hit = False
            miss = is_target
            false_alarm = False
            correct_rejection = not is_target
        elif is_target:
            correct = rng.random() < hit_rate
            hit = correct
            miss = not correct
            false_alarm = False
            correct_rejection = False
            response = "f" if correct else "j"
        elif is_lure:
            fa = rng.random() < lure_fa_rate
            false_alarm = fa
            correct = not fa
            hit = False
            miss = False
            correct_rejection = not fa
            response = "f" if fa else "j"
        else:
            fa = rng.random() < false_alarm_rate
            false_alarm = fa
            correct = not fa
            hit = False
            miss = False
            correct_rejection = not fa
            response = "f" if fa else "j"

        trial = {
            "trial_index": i + 1,
            "block": i // 24 + 1,
            "stimulus": stimulus,
            "n_back_match": is_target,
            "is_lure": is_lure,
            "response": response,
            "rt": rt,
            "correct": correct,
            "hit": hit,
            "miss": miss,
            "false_alarm": false_alarm,
            "correct_rejection": correct_rejection,
            "timed_out": timed_out,
        }
        trials.append(trial)
        prev_correct = correct

    return trials


@pytest.fixture
def nback_config():
    return {
        "task_id": "n_back",
        "parameters": {
            "n_trials": 120,
            "n_blocks": 5,
            "trials_per_block": 24,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def nback_metrics():
    return {
        "task_id": "n_back",
        "metrics": [
            {"name": "d_prime", "type": "d_prime", "field": "correct", "human_mean": 2.5, "human_sd": 0.8},
            {"name": "hit_rate", "type": "proportion_correct", "field": "hit", "filter": {"n_back_match": True}, "human_mean": 0.75, "human_sd": 0.12},
            {"name": "false_alarm_rate", "type": "proportion_correct", "field": "false_alarm", "filter": {"n_back_match": False}, "human_mean": 0.15, "human_sd": 0.08, "direction": "lower_is_better"},
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.82, "human_sd": 0.08},
            {"name": "mean_correct_rt", "type": "mean", "field": "rt", "filter": {"correct": True}, "human_mean": 550, "human_sd": 120, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def nback_signatures():
    return {
        "task_id": "n_back",
        "signatures": [
            {
                "name": "above_chance_discrimination",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"n_back_match": True}, "field": "correct"},
                "group_b": {"filter": {"n_back_match": False}, "field": "false_alarm"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "post_error_slowing",
                "test": "sequential_regression",
                "predictor": {"field": "correct", "lag": 1, "invert": True},
                "outcome": {"field": "rt"},
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.5,
            },
        ],
    }


@pytest.fixture
def human_like_nback_data():
    return _generate_nback_trials(hit_rate=0.75, false_alarm_rate=0.15, lure_fa_rate=0.30, post_error_slowing=20)


@pytest.fixture
def random_nback_data():
    return _generate_nback_trials(hit_rate=0.50, false_alarm_rate=0.50, lure_fa_rate=0.50, post_error_slowing=0, seed=99)


# ── Go/No-Go ──────────────────────────────────────────────

def _generate_gonogo_trials(
    n_trials=100,
    go_proportion=0.75,
    go_accuracy=0.95,
    nogo_accuracy=0.85,
    mean_go_rt=350,
    post_error_slowing=20,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    prev_correct = True

    for i in range(n_trials):
        stimulus_type = "go" if rng.random() < go_proportion else "nogo"
        block = i // 20 + 1

        base_rt = mean_go_rt
        if not prev_correct:
            base_rt += post_error_slowing

        timed_out = rng.random() < timeout_rate

        if stimulus_type == "go":
            responded = rng.random() < go_accuracy and not timed_out
            correct = responded
            hit = responded
            miss = not responded
            false_alarm = False
            correct_rejection = False
            rt = max(150, float(np_rng.normal(base_rt, 60))) if responded else None
            response = "f" if responded else None
        else:
            fa = rng.random() < (1 - nogo_accuracy) and not timed_out
            responded = fa
            correct = not fa
            hit = False
            miss = False
            false_alarm = fa
            correct_rejection = not fa
            rt = max(150, float(np_rng.normal(base_rt - 50, 80))) if responded else None
            response = "f" if responded else None

        trial = {
            "trial_index": i + 1,
            "block": block,
            "stimulus_type": stimulus_type,
            "response": response,
            "rt": rt,
            "correct": correct,
            "hit": hit,
            "miss": miss,
            "false_alarm": false_alarm,
            "correct_rejection": correct_rejection,
            "timed_out": timed_out,
        }

        if i > 0:
            trial["prev_correct"] = prev_correct

        trials.append(trial)
        prev_correct = correct

    return trials


@pytest.fixture
def gonogo_config():
    return {
        "task_id": "go_nogo",
        "parameters": {
            "n_trials": 100,
            "response_keys": ["f"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def gonogo_metrics():
    return {
        "task_id": "go_nogo",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.93, "human_sd": 0.05},
            {"name": "go_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"stimulus_type": "go"}, "human_mean": 0.95, "human_sd": 0.04},
            {"name": "nogo_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"stimulus_type": "nogo"}, "human_mean": 0.85, "human_sd": 0.10},
            {"name": "d_prime", "type": "d_prime", "hit_field": "hit", "fa_field": "false_alarm", "human_mean": 3.0, "human_sd": 0.8},
            {"name": "mean_go_rt", "type": "mean", "field": "rt", "filter": {"stimulus_type": "go", "correct": True}, "human_mean": 350, "human_sd": 60, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def gonogo_signatures():
    return {
        "task_id": "go_nogo",
        "signatures": [
            {
                "name": "above_chance_discrimination",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"stimulus_type": "go"}, "field": "correct"},
                "group_b": {"filter": {"stimulus_type": "nogo"}, "field": "false_alarm"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "commission_over_omission",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"stimulus_type": "nogo"}, "field": "false_alarm"},
                "group_b": {"filter": {"stimulus_type": "go"}, "field": "miss"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
            {
                "name": "post_error_slowing",
                "test": "sequential_regression",
                "predictor": {"field": "correct", "lag": 1, "invert": True},
                "outcome": {"field": "rt"},
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.5,
            },
        ],
    }


@pytest.fixture
def human_like_gonogo_data():
    return _generate_gonogo_trials(go_accuracy=0.95, nogo_accuracy=0.85, post_error_slowing=20)


@pytest.fixture
def random_gonogo_data():
    return _generate_gonogo_trials(go_accuracy=0.50, nogo_accuracy=0.50, post_error_slowing=0, seed=99)


# ── Flanker ──────────────────────────────────────────────

def _generate_flanker_trials(
    n_trials=96,
    accuracy=0.95,
    mean_rt_congruent=400,
    flanker_effect=50,
    post_error_slowing=25,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    prev_correct = True
    prev_condition = "congruent"

    conditions = ["congruent", "incongruent"]
    directions = ["left", "right"]
    key_map = {"left": "f", "right": "j"}

    for i in range(n_trials):
        condition = conditions[i % 2]
        target_dir = directions[i % 2]
        flanker_dir = target_dir if condition == "congruent" else ("right" if target_dir == "left" else "left")
        correct_key = key_map[target_dir]

        base_rt = mean_rt_congruent
        if condition == "incongruent":
            base_rt += flanker_effect
        if not prev_correct:
            base_rt += post_error_slowing

        rt = max(150, float(np_rng.normal(base_rt, 80)))
        timed_out = rng.random() < timeout_rate

        if timed_out:
            is_correct = False
            response = None
            rt = None
        else:
            # Congruent slightly more accurate than incongruent
            trial_acc = accuracy if condition == "congruent" else accuracy - 0.06
            is_correct = rng.random() < trial_acc
            response = correct_key if is_correct else key_map[flanker_dir]

        trial = {
            "trial_index": i + 1,
            "block": i // 24 + 1,
            "condition": condition,
            "target_direction": target_dir,
            "flanker_direction": flanker_dir,
            "correct_key": correct_key,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "timed_out": timed_out,
        }

        if i > 0:
            trial["prev_condition"] = prev_condition
            trial["prev_correct"] = prev_correct

        trials.append(trial)
        prev_correct = is_correct
        prev_condition = condition

    return trials


@pytest.fixture
def flanker_config():
    return {
        "task_id": "flanker",
        "parameters": {
            "n_trials": 96,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def flanker_metrics():
    return {
        "task_id": "flanker",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.95, "human_sd": 0.04},
            {"name": "congruent_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"condition": "congruent"}, "human_mean": 0.98, "human_sd": 0.02},
            {"name": "incongruent_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"condition": "incongruent"}, "human_mean": 0.92, "human_sd": 0.05},
            {"name": "mean_correct_rt", "type": "mean", "field": "rt", "filter": {"correct": True}, "human_mean": 450, "human_sd": 80, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def flanker_signatures():
    return {
        "task_id": "flanker",
        "signatures": [
            {
                "name": "flanker_interference_rt",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"condition": "incongruent"}, "field": "rt"},
                "group_b": {"filter": {"condition": "congruent"}, "field": "rt"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "flanker_interference_accuracy",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"condition": "congruent"}, "field": "correct"},
                "group_b": {"filter": {"condition": "incongruent"}, "field": "correct"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
            {
                "name": "post_error_slowing",
                "test": "sequential_regression",
                "predictor": {"field": "correct", "lag": 1, "invert": True},
                "outcome": {"field": "rt"},
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.5,
            },
        ],
    }


@pytest.fixture
def human_like_flanker_data():
    return _generate_flanker_trials(accuracy=0.95, flanker_effect=50, post_error_slowing=25)


@pytest.fixture
def random_flanker_data():
    return _generate_flanker_trials(accuracy=0.50, flanker_effect=0, post_error_slowing=0, seed=99)


# ── Dictator Game ──────────────────────────────────────────

def _generate_dictator_trials(
    n_rounds=20,
    mean_giving=0.28,
    giving_sd=0.15,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    endowment = 10
    trials = []

    for i in range(n_rounds):
        timed_out = rng.random() < timeout_rate
        rt = max(500, float(np_rng.normal(5000, 2000))) if not timed_out else None

        give_prop = max(0.0, min(1.0, float(np_rng.normal(mean_giving, giving_sd))))
        amount_given = round(give_prop * endowment)
        amount_given = max(0, min(endowment, amount_given))
        give_prop = amount_given / endowment

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "round": i + 1,
            "endowment": endowment,
            "response": amount_given if not timed_out else None,
            "amount_given": amount_given if not timed_out else 0,
            "amount_given_proportion": give_prop if not timed_out else 0.0,
            "gave_nonzero": amount_given > 0 if not timed_out else False,
            "gave_half": amount_given >= endowment / 2 if not timed_out else False,
            "amount_kept": endowment - amount_given if not timed_out else endowment,
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def dictator_config():
    return {
        "task_id": "dictator_game",
        "parameters": {
            "n_trials": 20,
            "response_type": "slider",
            "response_field": "response",
            "slider_range": [0, 10],
        },
    }


@pytest.fixture
def dictator_metrics():
    return {
        "task_id": "dictator_game",
        "metrics": [
            {"name": "mean_giving_proportion", "type": "mean", "field": "amount_given_proportion", "human_mean": 0.28, "human_sd": 0.15},
            {"name": "proportion_gave_nonzero", "type": "proportion_correct", "field": "gave_nonzero", "human_mean": 0.64, "human_sd": 0.15},
            {"name": "proportion_gave_half", "type": "proportion_correct", "field": "gave_half", "human_mean": 0.17, "human_sd": 0.12},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 5000, "human_sd": 2000, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def dictator_signatures():
    return {
        "task_id": "dictator_game",
        "signatures": [
            {
                "name": "nonzero_giving",
                "test": "proportion_test",
                "filter": {},
                "field": "gave_nonzero",
                "chance_level": 0.50,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
        ],
    }


@pytest.fixture
def human_like_dictator_data():
    return _generate_dictator_trials(mean_giving=0.30, giving_sd=0.12)


@pytest.fixture
def random_dictator_data():
    return _generate_dictator_trials(mean_giving=0.50, giving_sd=0.30, seed=99)


# ── Iowa Gambling Task ──────────────────────────────────────

def _generate_igt_trials(
    n_trials=100,
    learning_rate=0.15,
    initial_advantageous=0.40,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    deck_rewards = {"A": 100, "B": 100, "C": 50, "D": 50}
    deck_loss_prob = {"A": 0.50, "B": 0.10, "C": 0.50, "D": 0.10}
    deck_loss_range = {
        "A": (150, 350), "B": (1150, 1350),
        "C": (25, 75), "D": (200, 300),
    }
    decks = ["A", "B", "C", "D"]
    key_map = {"A": "d", "B": "f", "C": "j", "D": "k"}

    total_score = 2000

    for i in range(n_trials):
        block = i // 20 + 1
        # Probability of choosing advantageous increases with trial
        adv_prob = initial_advantageous + learning_rate * (i / n_trials)
        adv_prob = min(0.80, adv_prob)

        timed_out = rng.random() < timeout_rate

        if rng.random() < adv_prob:
            deck = rng.choice(["C", "D"])
        else:
            deck = rng.choice(["A", "B"])

        win = deck_rewards[deck]
        if rng.random() < deck_loss_prob[deck]:
            loss_min, loss_max = deck_loss_range[deck]
            loss = rng.randint(loss_min, loss_max)
        else:
            loss = 0

        net = win - loss
        total_score += net

        rt = max(300, float(np_rng.normal(1500, 400))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "block": block,
            "deck_chosen": deck,
            "deck_type": "advantageous" if deck in ["C", "D"] else "disadvantageous",
            "win": win,
            "loss": loss,
            "net_outcome": net,
            "total_score": total_score,
            "chose_advantageous": deck in ["C", "D"],
            "correct": deck in ["C", "D"],
            "response": key_map[deck] if not timed_out else None,
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def igt_config():
    return {
        "task_id": "iowa_gambling",
        "parameters": {
            "n_trials": 100,
            "response_keys": ["d", "f", "j", "k"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def igt_metrics():
    return {
        "task_id": "iowa_gambling",
        "metrics": [
            {"name": "proportion_advantageous", "type": "proportion_correct", "field": "correct", "human_mean": 0.55, "human_sd": 0.12},
            {"name": "proportion_advantageous_last40", "type": "proportion_correct", "field": "correct", "filter": {"block": 4}, "human_mean": 0.62, "human_sd": 0.15},
            {"name": "proportion_advantageous_last20", "type": "proportion_correct", "field": "correct", "filter": {"block": 5}, "human_mean": 0.65, "human_sd": 0.15},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 1500, "human_sd": 500, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def igt_signatures():
    return {
        "task_id": "iowa_gambling",
        "signatures": [
            {
                "name": "learning_effect",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"block": 5}, "field": "correct"},
                "group_b": {"filter": {"block": 1}, "field": "correct"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "above_chance_advantageous",
                "test": "proportion_test",
                "filter": {},
                "field": "correct",
                "chance_level": 0.50,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_igt_data():
    return _generate_igt_trials(learning_rate=0.20, initial_advantageous=0.40)


@pytest.fixture
def random_igt_data():
    return _generate_igt_trials(learning_rate=0.0, initial_advantageous=0.50, seed=99)


# ── Reversal Learning ──────────────────────────────────────

def _generate_reversal_trials(
    n_trials=120,
    pre_reversal_accuracy=0.85,
    post_reversal_accuracy=0.45,
    recovery_rate=0.08,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    # Generate reversal schedule
    correct_stim = "left"
    trial_since_rev = 0
    rev_count = 0
    next_reversal = rng.randint(15, 25)

    for i in range(n_trials):
        if trial_since_rev >= next_reversal:
            correct_stim = "right" if correct_stim == "left" else "left"
            trial_since_rev = 0
            rev_count += 1
            next_reversal = rng.randint(15, 25)

        phase = "post_reversal" if trial_since_rev < 5 else "pre_reversal"

        if phase == "post_reversal":
            acc = post_reversal_accuracy + recovery_rate * trial_since_rev
        else:
            acc = pre_reversal_accuracy

        acc = min(0.95, acc)
        timed_out = rng.random() < timeout_rate
        is_correct = rng.random() < acc and not timed_out

        if is_correct:
            chosen = correct_stim
        else:
            chosen = "right" if correct_stim == "left" else "left"

        # Probabilistic reward
        if is_correct:
            rewarded = rng.random() < 0.80
        else:
            rewarded = rng.random() < 0.20

        rt = max(200, float(np_rng.normal(600, 150))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
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
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)
        trial_since_rev += 1

    return trials


@pytest.fixture
def reversal_config():
    return {
        "task_id": "reversal_learning",
        "parameters": {
            "n_trials": 120,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def reversal_metrics():
    return {
        "task_id": "reversal_learning",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.72, "human_sd": 0.10},
            {"name": "pre_reversal_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"phase": "pre_reversal"}, "human_mean": 0.85, "human_sd": 0.08},
            {"name": "post_reversal_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"phase": "post_reversal"}, "human_mean": 0.45, "human_sd": 0.15},
            {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"correct": True}, "human_mean": 600, "human_sd": 150, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def reversal_signatures():
    return {
        "task_id": "reversal_learning",
        "signatures": [
            {
                "name": "above_chance_pre_reversal",
                "test": "proportion_test",
                "filter": {"phase": "pre_reversal"},
                "field": "correct",
                "chance_level": 0.50,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "perseveration_effect",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"phase": "pre_reversal"}, "field": "correct"},
                "group_b": {"filter": {"phase": "post_reversal"}, "field": "correct"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
            {
                "name": "post_reversal_learning",
                "test": "correlation_test",
                "x_field": "trials_since_reversal",
                "y_field": "correct",
                "filter": {"phase": "post_reversal"},
                "threshold_p": 0.05,
                "expected_direction": "positive",
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_reversal_data():
    return _generate_reversal_trials(pre_reversal_accuracy=0.85, post_reversal_accuracy=0.40, recovery_rate=0.08)


@pytest.fixture
def random_reversal_data():
    return _generate_reversal_trials(pre_reversal_accuracy=0.50, post_reversal_accuracy=0.50, recovery_rate=0.0, seed=99)


# ── Contingency Judgment ──────────────────────────────────

def _generate_contingency_judgment_trials(
    n_blocks=4,
    sensitivity=0.70,
    noise_sd=0.10,
    overestimation_bias=0.05,
    timeout_rate=0.0,
    seed=42,
):
    """Generate contingency judgment rating trials.

    Each block has a different delta-P value. After observing co-occurrences,
    participants rate causal strength on a 0-100 slider.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    # Block delta-P values: strong positive, moderate, zero, negative
    block_delta_ps = [0.75, 0.40, 0.00, -0.30]
    trials = []

    for block_idx in range(n_blocks):
        delta_p = block_delta_ps[block_idx]

        # Ideal rating: map delta_p [-1, 1] to [0, 100]
        ideal_normalized = (delta_p + 1.0) / 2.0

        # Human-like: sensitive but biased and noisy
        base_rating = ideal_normalized * sensitivity + (1 - sensitivity) * 0.5
        base_rating += overestimation_bias  # slight upward bias

        timed_out = rng.random() < timeout_rate
        rt = max(500, float(np_rng.normal(4000, 1500))) if not timed_out else None

        if timed_out:
            rating_normalized = 0.5
        else:
            rating_normalized = max(0.0, min(1.0, float(np_rng.normal(base_rating, noise_sd))))

        rating_raw = round(rating_normalized * 100)
        rating_normalized = rating_raw / 100.0

        rating_accuracy = max(0.0, 1.0 - abs(rating_normalized - ideal_normalized))
        overestimated = rating_normalized > 0.50
        high_rating = rating_normalized > 0.50

        trial = {
            "trial_index": block_idx + 1,
            "trial_part": "stimulus",
            "block": block_idx + 1,
            "block_delta_p": delta_p,
            "rating": rating_raw,
            "rating_normalized": rating_normalized,
            "rating_accuracy": rating_accuracy,
            "overestimated": overestimated,
            "high_rating": high_rating,
            "response": rating_raw,
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def contingency_config():
    return {
        "task_id": "contingency_judgment",
        "parameters": {
            "n_trials": 4,
            "n_observations": 80,
            "n_blocks": 4,
            "observations_per_block": 20,
            "response_type": "slider",
            "slider_range": [0, 100],
            "response_deadline_ms": 15000,
            "required_fields": ["trial_index", "block", "block_delta_p", "rating", "rating_normalized", "rt"],
        },
    }


@pytest.fixture
def contingency_metrics():
    return {
        "task_id": "contingency_judgment",
        "metrics": [
            {"name": "mean_rating_accuracy", "type": "mean", "field": "rating_accuracy", "human_mean": 0.65, "human_sd": 0.15},
            {"name": "strong_cause_rating", "type": "mean", "field": "rating_normalized", "filter": {"block": 1}, "human_mean": 0.75, "human_sd": 0.15},
            {"name": "no_cause_rating", "type": "mean", "field": "rating_normalized", "filter": {"block": 3}, "human_mean": 0.50, "human_sd": 0.18},
        ],
    }


@pytest.fixture
def contingency_signatures():
    return {
        "task_id": "contingency_judgment",
        "signatures": [
            {
                "name": "delta_p_sensitivity",
                "test": "correlation_test",
                "field_x": "block_delta_p",
                "field_y": "rating_normalized",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "cause_discrimination",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"block": 1}, "field": "high_rating"},
                "group_b": {"filter": {"block": 3}, "field": "high_rating"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "outcome_density_bias",
                "test": "proportion_test",
                "filter": {"block": 3},
                "field": "overestimated",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.10,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_contingency_data():
    return _generate_contingency_judgment_trials(sensitivity=0.70, noise_sd=0.08, overestimation_bias=0.05)


@pytest.fixture
def random_contingency_data():
    return _generate_contingency_judgment_trials(sensitivity=0.0, noise_sd=0.25, overestimation_bias=0.0, seed=99)


# ── Simple & Choice RT ──────────────────────────────────

def _generate_simple_choice_rt_trials(
    n_trials=80,
    simple_rt_mean=220,
    choice2_rt_mean=340,
    choice4_rt_mean=450,
    accuracy=0.95,
    timeout_rate=0.0,
    seed=42,
):
    """Generate simple and choice reaction time trials.

    Tests Hick's Law: RT increases with log2(N alternatives).
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    key_map_simple = [" "]
    key_map_choice2 = ["f", "j"]
    key_map_choice4 = ["d", "f", "j", "k"]

    # Distribute: 20 simple, 30 choice2, 30 choice4
    conditions = ["simple"] * 20 + ["choice2"] * 30 + ["choice4"] * 30
    rng.shuffle(conditions)

    trials = []
    for i in range(n_trials):
        condition = conditions[i]

        if condition == "simple":
            n_alternatives = 1
            correct_key = " "
            keys = key_map_simple
            base_rt = simple_rt_mean
            trial_acc = min(1.0, accuracy + 0.03)
        elif condition == "choice2":
            n_alternatives = 2
            correct_key = rng.choice(key_map_choice2)
            keys = key_map_choice2
            base_rt = choice2_rt_mean
            trial_acc = accuracy
        else:
            n_alternatives = 4
            correct_key = rng.choice(key_map_choice4)
            keys = key_map_choice4
            base_rt = choice4_rt_mean
            trial_acc = accuracy - 0.03

        timed_out = rng.random() < timeout_rate
        rt = max(100, float(np_rng.normal(base_rt, base_rt * 0.15))) if not timed_out else None

        if timed_out:
            is_correct = False
            response = None
        else:
            is_correct = rng.random() < trial_acc
            if is_correct:
                response = correct_key
            else:
                others = [k for k in keys if k != correct_key]
                response = rng.choice(others) if others else correct_key

        log_n = math.log2(max(1, n_alternatives))

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "condition": condition,
            "n_alternatives": n_alternatives,
            "log_n_alternatives": log_n,
            "correct_key": correct_key,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def simple_choice_rt_config():
    return {
        "task_id": "simple_choice_rt",
        "parameters": {
            "n_trials": 80,
            "response_keys": [" ", "d", "f", "j", "k"],
            "response_keys_simple": [" "],
            "response_keys_choice2": ["f", "j"],
            "response_keys_choice4": ["d", "f", "j", "k"],
            "response_type": "keypress",
            "response_deadline_ms": 2000,
            "required_fields": ["trial_index", "condition", "n_alternatives", "correct", "rt"],
        },
    }


@pytest.fixture
def simple_choice_rt_metrics():
    return {
        "task_id": "simple_choice_rt",
        "metrics": [
            {"name": "simple_rt_mean", "type": "mean", "field": "rt", "filter": {"condition": "simple"}, "human_mean": 220, "human_sd": 30, "direction": "lower_is_better"},
            {"name": "choice2_rt_mean", "type": "mean", "field": "rt", "filter": {"condition": "choice2"}, "human_mean": 340, "human_sd": 40, "direction": "lower_is_better"},
            {"name": "choice4_rt_mean", "type": "mean", "field": "rt", "filter": {"condition": "choice4"}, "human_mean": 450, "human_sd": 50, "direction": "lower_is_better"},
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.95, "human_sd": 0.04},
        ],
    }


@pytest.fixture
def simple_choice_rt_signatures():
    return {
        "task_id": "simple_choice_rt",
        "signatures": [
            {
                "name": "hicks_law",
                "test": "correlation_test",
                "field_x": "log_n_alternatives",
                "field_y": "rt",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "choice2_slower_than_simple",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"condition": "choice2"}, "field": "rt"},
                "group_b": {"filter": {"condition": "simple"}, "field": "rt"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "above_chance_accuracy",
                "test": "proportion_test",
                "field": "correct",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_simple_choice_rt_data():
    return _generate_simple_choice_rt_trials(simple_rt_mean=220, choice2_rt_mean=340, choice4_rt_mean=450, accuracy=0.95)


@pytest.fixture
def random_simple_choice_rt_data():
    return _generate_simple_choice_rt_trials(simple_rt_mean=350, choice2_rt_mean=350, choice4_rt_mean=350, accuracy=0.50, seed=99)


# ── BART ──────────────────────────────────────────────────

def _generate_bart_trials(
    n_balloons=30,
    mean_pumps=25,
    pump_sd=10,
    timeout_rate=0.0,
    seed=42,
):
    """Generate BART balloon-level summary trials.

    Each trial is a balloon: n_pumps, popped, cashed_out, balloon_earnings, etc.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    total_earnings = 0.0
    trials = []
    median_pumps = mean_pumps

    for b in range(n_balloons):
        pop_threshold = rng.randint(8, 64)
        timed_out = rng.random() < timeout_rate

        if timed_out:
            n_pumps = 0
            popped = False
            cashed_out = False
            balloon_earnings = 0.0
            rt = None
        else:
            target_pumps = max(1, round(float(np_rng.normal(mean_pumps, pump_sd))))

            if target_pumps >= pop_threshold:
                n_pumps = pop_threshold
                popped = True
                cashed_out = False
                balloon_earnings = 0.0
            else:
                n_pumps = target_pumps
                popped = False
                cashed_out = True
                balloon_earnings = round(n_pumps * 0.05, 2)

            rt = max(200, float(np_rng.normal(800, 300)))

        total_earnings += balloon_earnings
        adjusted_pumps = n_pumps if not popped else None
        above_floor_pumps = n_pumps > 5
        high_pumps = n_pumps > median_pumps
        previous_popped = trials[-1]["popped"] if len(trials) > 0 else False

        trial = {
            "trial_index": b + 1,
            "trial_part": "stimulus",
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
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def bart_config():
    return {
        "task_id": "bart",
        "parameters": {
            "n_trials": 30,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "response_deadline_ms": 5000,
            "feedback_duration_ms": 1500,
            "required_fields": [
                "trial_index", "balloon_number", "n_pumps", "popped",
                "cashed_out", "balloon_earnings", "total_earnings",
            ],
        },
    }


@pytest.fixture
def bart_metrics():
    return {
        "task_id": "bart",
        "metrics": [
            {"name": "mean_adjusted_pumps", "type": "mean", "field": "adjusted_pumps", "human_mean": 25, "human_sd": 12},
            {"name": "total_earnings", "type": "mean", "field": "balloon_earnings", "human_mean": 0.80, "human_sd": 0.40},
            {"name": "pop_rate", "type": "proportion_correct", "field": "popped", "human_mean": 0.35, "human_sd": 0.15},
        ],
    }


@pytest.fixture
def bart_signatures():
    return {
        "task_id": "bart",
        "signatures": [
            {
                "name": "risk_taking",
                "test": "proportion_test",
                "field": "above_floor_pumps",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "post_pop_adjustment",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"previous_popped": False}, "field": "high_pumps"},
                "group_b": {"filter": {"previous_popped": True}, "field": "high_pumps"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "earnings_above_zero",
                "test": "proportion_test",
                "field": "cashed_out",
                "chance_level": 0.3,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_bart_data():
    return _generate_bart_trials(mean_pumps=25, pump_sd=10)


@pytest.fixture
def random_bart_data():
    return _generate_bart_trials(mean_pumps=32, pump_sd=20, seed=99)


# ── Navon ──────────────────────────────────────────────────

def _generate_navon_trials(
    n_trials=80,
    global_accuracy=0.95,
    local_accuracy=0.89,
    global_rt_mean=500,
    local_rt_mean=580,
    congruency_effect_rt=40,
    congruency_effect_acc=0.05,
    timeout_rate=0.0,
    seed=42,
):
    """Generate Navon global/local letter identification trials.

    Shows global precedence (global faster/more accurate than local) and
    congruency effects (congruent faster than incongruent), with an interaction
    (global interferes with local more than local interferes with global).
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    letters = ["H", "S"]
    key_map = {"H": "f", "S": "j"}
    target_levels = ["global", "local"]
    trials = []

    for i in range(n_trials):
        target_level = target_levels[i % 2]
        block = i // 20 + 1

        global_letter = rng.choice(letters)
        if rng.random() < 0.5:
            local_letter = global_letter
        else:
            local_letter = [l for l in letters if l != global_letter][0]

        congruency = "congruent" if global_letter == local_letter else "incongruent"

        target_letter = global_letter if target_level == "global" else local_letter
        correct_key = key_map[target_letter]

        timed_out = rng.random() < timeout_rate

        # RT with global precedence + congruency + interaction
        if target_level == "global":
            base_rt = global_rt_mean
            base_acc = global_accuracy
            cong_rt_effect = congruency_effect_rt * 0.5  # smaller effect for global
            cong_acc_effect = congruency_effect_acc * 0.3
        else:
            base_rt = local_rt_mean
            base_acc = local_accuracy
            cong_rt_effect = congruency_effect_rt * 1.5  # larger effect for local (interaction)
            cong_acc_effect = congruency_effect_acc * 1.5

        if congruency == "incongruent":
            base_rt += cong_rt_effect
            base_acc -= cong_acc_effect

        rt = max(200, float(np_rng.normal(base_rt, 70))) if not timed_out else None

        if timed_out:
            is_correct = False
            response = None
        else:
            is_correct = rng.random() < base_acc
            if is_correct:
                response = correct_key
            else:
                other_key = [v for v in key_map.values() if v != correct_key][0]
                response = other_key

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "block": block,
            "target_level": target_level,
            "global_letter": global_letter,
            "local_letter": local_letter,
            "congruency": congruency,
            "correct_key": correct_key,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def navon_config():
    return {
        "task_id": "navon",
        "parameters": {
            "n_trials": 80,
            "n_blocks": 4,
            "trials_per_block": 20,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "letter_key_mapping": {"H": "f", "S": "j"},
            "required_fields": [
                "trial_index", "block", "target_level", "global_letter",
                "local_letter", "congruency", "correct", "rt",
            ],
        },
    }


@pytest.fixture
def navon_metrics():
    return {
        "task_id": "navon",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.92, "human_sd": 0.05},
            {"name": "global_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"target_level": "global"}, "human_mean": 0.95, "human_sd": 0.04},
            {"name": "local_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"target_level": "local"}, "human_mean": 0.89, "human_sd": 0.06},
            {"name": "mean_correct_rt", "type": "mean", "field": "rt", "filter": {"correct": True}, "human_mean": 550, "human_sd": 100, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def navon_signatures():
    return {
        "task_id": "navon",
        "signatures": [
            {
                "name": "global_precedence_rt",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"target_level": "local", "correct": True}, "field": "rt"},
                "group_b": {"filter": {"target_level": "global", "correct": True}, "field": "rt"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "global_to_local_interference",
                "test": "interaction_test",
                "outcome_field": "rt",
                "factor_a_field": "target_level",
                "factor_b_field": "congruency",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "congruency_effect",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {"congruency": "incongruent", "correct": True}, "field": "rt"},
                "group_b": {"filter": {"congruency": "congruent", "correct": True}, "field": "rt"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_navon_data():
    return _generate_navon_trials(
        global_accuracy=0.95, local_accuracy=0.89,
        global_rt_mean=500, local_rt_mean=580,
        congruency_effect_rt=40, congruency_effect_acc=0.05,
    )


@pytest.fixture
def random_navon_data():
    return _generate_navon_trials(
        global_accuracy=0.50, local_accuracy=0.50,
        global_rt_mean=500, local_rt_mean=500,
        congruency_effect_rt=0, congruency_effect_acc=0.0,
        seed=99,
    )


# ── Category Learning ──────────────────────────────────────────

def _generate_category_learning_trials(
    n_training=96,
    n_transfer=24,
    early_accuracy=0.60,
    late_accuracy=0.92,
    transfer_accuracy=0.88,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    n_total = n_training + n_transfer
    trials = []

    features = [(f1, f2, f3) for f1 in [0, 1] for f2 in [0, 1] for f3 in [0, 1]]
    categories = {f: ("A" if f[0] == 0 else "B") for f in features}
    key_map = {"A": "f", "B": "j"}

    for i in range(n_total):
        if i < n_training:
            phase = "training"
            block = i // 12 + 1
            # Linear interpolation from early to late accuracy
            frac = (block - 1) / 7.0
            acc = early_accuracy + frac * (late_accuracy - early_accuracy)
        else:
            phase = "transfer"
            block = 9
            acc = transfer_accuracy

        stim_feat = features[i % len(features)]
        correct_cat = categories[stim_feat]
        correct_key = key_map[correct_cat]

        timed_out = rng.random() < timeout_rate
        if timed_out:
            is_correct = False
            response = None
            rt = None
        else:
            is_correct = rng.random() < acc
            response = correct_key if is_correct else ("j" if correct_key == "f" else "f")
            base_rt = 1400 - 40 * block if phase == "training" else 1100
            rt = max(250, float(np_rng.normal(base_rt, 200)))

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "block": block,
            "phase": phase,
            "stimulus_features": list(stim_feat),
            "correct_category": correct_cat,
            "correct_key": correct_key,
            "response": response,
            "rt": rt,
            "correct": is_correct,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def category_learning_config():
    return {
        "task_id": "category_learning",
        "parameters": {
            "n_trials": 120,
            "n_training": 96,
            "n_transfer": 24,
            "n_blocks": 8,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def category_learning_metrics():
    return {
        "task_id": "category_learning",
        "metrics": [
            {"name": "overall_training_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"phase": "training"}, "human_mean": 0.80, "human_sd": 0.12},
            {"name": "final_block_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"block": 8}, "human_mean": 0.92, "human_sd": 0.10},
            {"name": "transfer_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"phase": "transfer"}, "human_mean": 0.88, "human_sd": 0.14},
            {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"phase": "training"}, "human_mean": 1200, "human_sd": 400, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def category_learning_signatures():
    return {
        "task_id": "category_learning",
        "signatures": [
            {
                "name": "learning_curve",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"block": 8}, "field": "correct"},
                "group_b": {"filter": {"block": 1}, "field": "correct"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "above_chance_learning",
                "test": "proportion_test",
                "field": "correct",
                "filter": {"block": 8},
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "transfer_generalization",
                "test": "proportion_test",
                "field": "correct",
                "filter": {"phase": "transfer"},
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_category_learning_data():
    return _generate_category_learning_trials(early_accuracy=0.60, late_accuracy=0.92, transfer_accuracy=0.88)


@pytest.fixture
def random_category_learning_data():
    return _generate_category_learning_trials(early_accuracy=0.50, late_accuracy=0.50, transfer_accuracy=0.50, seed=99)


# ── Restless Bandit ──────────────────────────────────────────

def _generate_restless_bandit_trials(
    n_trials=100,
    win_stay_rate=0.70,
    lose_shift_rate=0.55,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    mu = [50.0, 50.0]
    drift_sd = 2.5
    reward_sd = 8.0
    prev_reward = None
    prev_arm = None
    median_reward = 50.0
    rewards_so_far = []

    for i in range(n_trials):
        mu[0] += float(np_rng.normal(0, drift_sd))
        mu[1] += float(np_rng.normal(0, drift_sd))
        mu[0] = max(20, min(80, mu[0]))
        mu[1] = max(20, min(80, mu[1]))

        optimal_arm = 0 if mu[0] >= mu[1] else 1

        timed_out = rng.random() < timeout_rate
        if timed_out:
            chose_arm = rng.choice([0, 1])
            reward = 0.0
            rt = None
        else:
            if prev_reward is not None and prev_arm is not None:
                if prev_reward > median_reward:
                    chose_arm = prev_arm if rng.random() < win_stay_rate else (1 - prev_arm)
                else:
                    chose_arm = (1 - prev_arm) if rng.random() < lose_shift_rate else prev_arm
            else:
                chose_arm = rng.choice([0, 1])

            reward = round(max(0, float(np_rng.normal(mu[chose_arm], reward_sd))), 1)
            rt = max(200, float(np_rng.normal(800, 200)))

        rewards_so_far.append(reward)
        median_reward = sorted(rewards_so_far)[len(rewards_so_far) // 2]

        chose_optimal = chose_arm == optimal_arm
        stayed = chose_arm == prev_arm if prev_arm is not None else None

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "chosen_arm": chose_arm,
            "reward": reward,
            "arm_0_mean": round(mu[0], 2),
            "arm_1_mean": round(mu[1], 2),
            "chose_optimal": chose_optimal,
            "response": "f" if chose_arm == 0 else "j",
            "rt": rt,
            "timed_out": timed_out,
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


@pytest.fixture
def restless_bandit_config():
    return {
        "task_id": "restless_bandit",
        "parameters": {
            "n_trials": 100,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def restless_bandit_metrics():
    return {
        "task_id": "restless_bandit",
        "metrics": [
            {"name": "overall_optimal_rate", "type": "proportion_correct", "field": "chose_optimal", "human_mean": 0.65, "human_sd": 0.10},
            {"name": "mean_reward", "type": "mean", "field": "reward", "human_mean": 60, "human_sd": 10},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 800, "human_sd": 300, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def restless_bandit_signatures():
    return {
        "task_id": "restless_bandit",
        "signatures": [
            {
                "name": "above_chance_tracking",
                "test": "proportion_test",
                "field": "chose_optimal",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "win_stay_lose_shift",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"previous_reward_above_median": True}, "field": "stayed"},
                "group_b": {"filter": {"previous_reward_above_median": False}, "field": "stayed"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "recency_weighting",
                "test": "sequential_regression",
                "outcome_field": "stayed_num",
                "predictor_field": "previous_reward",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_restless_bandit_data():
    return _generate_restless_bandit_trials(win_stay_rate=0.70, lose_shift_rate=0.55)


@pytest.fixture
def random_restless_bandit_data():
    return _generate_restless_bandit_trials(win_stay_rate=0.50, lose_shift_rate=0.50, seed=99)


# ── Serial Recall ──────────────────────────────────────────

def _generate_serial_recall_trials(
    n_lists=10,
    list_length=12,
    primacy_boost=0.30,
    recency_boost=0.25,
    base_recall=0.45,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    words = [f"WORD_{w}" for w in range(100)]
    trials = []

    for li in range(n_lists):
        study_list = rng.sample(words, list_length)

        recall_probs = []
        for pos in range(list_length):
            if pos < 3:
                p = base_recall + primacy_boost - 0.05 * pos
            elif pos >= list_length - 3:
                p = base_recall + recency_boost + 0.05 * (pos - (list_length - 3))
            else:
                p = base_recall
            recall_probs.append(min(0.95, max(0.15, p + float(np_rng.normal(0, 0.05)))))

        recalled_items = []
        recalled_positions = []
        for pos in range(list_length):
            if rng.random() < recall_probs[pos]:
                recalled_items.append(study_list[pos])
                recalled_positions.append(pos)

        n_recalled = len(recalled_items)

        n_correct_position = 0
        for idx, pos in enumerate(recalled_positions):
            if recalled_positions[idx] == idx:
                n_correct_position += 1
        n_correct_position = min(n_correct_position, n_recalled)

        primacy_positions = set(range(3))
        recency_positions = set(range(list_length - 3, list_length))
        middle_positions = set(range(3, list_length - 3))

        primacy_recalled = sum(1 for p in recalled_positions if p in primacy_positions) / len(primacy_positions)
        recency_recalled = sum(1 for p in recalled_positions if p in recency_positions) / len(recency_positions)
        middle_recalled = sum(1 for p in recalled_positions if p in middle_positions) / len(middle_positions)

        above_chance = n_recalled / list_length

        rt = max(2000, float(np_rng.normal(15000, 5000)))

        trials.append({
            "trial_index": li + 1,
            "trial_part": "stimulus",
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
            "rt": rt,
        })

    return trials


@pytest.fixture
def serial_recall_config():
    return {
        "task_id": "serial_recall",
        "parameters": {
            "n_trials": 10,
            "list_length": 12,
            "response_type": "button",
        },
    }


@pytest.fixture
def serial_recall_metrics():
    return {
        "task_id": "serial_recall",
        "metrics": [
            {"name": "mean_items_recalled", "type": "mean", "field": "n_recalled", "human_mean": 7.0, "human_sd": 2.0},
            {"name": "mean_correct_position", "type": "mean", "field": "n_correct_position", "human_mean": 4.5, "human_sd": 1.5},
            {"name": "primacy_recall_rate", "type": "mean", "field": "primacy_recalled", "human_mean": 0.70, "human_sd": 0.15},
            {"name": "recency_recall_rate", "type": "mean", "field": "recency_recalled", "human_mean": 0.75, "human_sd": 0.15},
        ],
    }


@pytest.fixture
def serial_recall_signatures():
    return {
        "task_id": "serial_recall",
        "signatures": [
            {
                "name": "primacy_effect",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {}, "field": "primacy_recalled"},
                "group_b": {"filter": {}, "field": "middle_recalled"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "recency_effect",
                "test": "paired_ttest_greater",
                "group_a": {"filter": {}, "field": "recency_recalled"},
                "group_b": {"filter": {}, "field": "middle_recalled"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "above_chance_recall",
                "test": "proportion_test",
                "field": "above_chance_recall",
                "chance_level": 0.083,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_serial_recall_data():
    return _generate_serial_recall_trials(primacy_boost=0.30, recency_boost=0.25, base_recall=0.45)


@pytest.fixture
def random_serial_recall_data():
    return _generate_serial_recall_trials(primacy_boost=0.0, recency_boost=0.0, base_recall=0.25, seed=99)


# ── Ultimatum Game ──────────────────────────────────────────

def _generate_ultimatum_trials(
    n_rounds=20,
    mean_offer_proportion=0.42,
    offer_sd=0.15,
    fair_accept_rate=0.90,
    low_accept_rate=0.15,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    endowment = 10
    trials = []

    for i in range(n_rounds):
        role = "proposer" if i % 2 == 0 else "responder"
        round_number = i + 1

        timed_out = rng.random() < timeout_rate

        if role == "proposer":
            offer_amount = max(0, min(endowment, round(float(np_rng.normal(mean_offer_proportion * endowment, offer_sd * endowment)))))
            offer_proportion = offer_amount / endowment
            fair_offer = offer_proportion >= 0.3
            low_offer = offer_proportion < 0.2

            accepted = rng.random() < (0.3 + 0.7 * offer_proportion)
            player_payoff = (endowment - offer_amount) if accepted else 0
            rt = max(500, float(np_rng.normal(4000, 1500))) if not timed_out else None

            trial = {
                "trial_index": i + 1,
                "trial_part": "stimulus",
                "round_number": round_number,
                "role": role,
                "offer_amount": offer_amount,
                "offer_proportion": offer_proportion,
                "fair_offer": fair_offer,
                "low_offer": low_offer,
                "accepted": accepted,
                "player_payoff": player_payoff,
                "timed_out": timed_out,
                "rt": rt,
                "response": offer_amount,
            }
        else:
            if i % 4 == 1:
                offer_amount = rng.randint(0, 2)
            elif i % 4 == 3:
                offer_amount = rng.randint(3, 5)
            else:
                offer_amount = rng.randint(2, 4)

            offer_proportion = offer_amount / endowment
            fair_offer = offer_proportion >= 0.3
            low_offer = offer_proportion < 0.2

            if offer_proportion >= 0.4:
                accepted = rng.random() < fair_accept_rate
            elif offer_proportion >= 0.2:
                accepted = rng.random() < 0.60
            else:
                accepted = rng.random() < low_accept_rate

            accepted_num = 1 if accepted else 0
            player_payoff = offer_amount if accepted else 0
            rt = max(400, float(np_rng.normal(3000, 1200))) if not timed_out else None

            trial = {
                "trial_index": i + 1,
                "trial_part": "stimulus",
                "round_number": round_number,
                "role": role,
                "offer_amount": offer_amount,
                "offer_proportion": offer_proportion,
                "fair_offer": fair_offer,
                "low_offer": low_offer,
                "accepted": accepted,
                "accepted_num": accepted_num,
                "player_payoff": player_payoff,
                "timed_out": timed_out,
                "rt": rt,
                "response": "f" if accepted else "j",
            }

        trials.append(trial)

    return trials


@pytest.fixture
def ultimatum_config():
    return {
        "task_id": "ultimatum_game",
        "parameters": {
            "n_trials": 20,
            "endowment": 10,
            "response_keys": ["f", "j"],
            "response_type": "mixed",
        },
    }


@pytest.fixture
def ultimatum_metrics():
    return {
        "task_id": "ultimatum_game",
        "metrics": [
            {"name": "mean_offer_as_proposer", "type": "mean", "field": "offer_proportion", "filter": {"role": "proposer"}, "human_mean": 0.42, "human_sd": 0.12},
            {"name": "acceptance_rate_as_responder", "type": "proportion_correct", "field": "accepted", "filter": {"role": "responder"}, "human_mean": 0.65, "human_sd": 0.20},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 4000, "human_sd": 2000, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def ultimatum_signatures():
    return {
        "task_id": "ultimatum_game",
        "signatures": [
            {
                "name": "fair_offers",
                "test": "proportion_test",
                "filter": {"role": "proposer"},
                "field": "fair_offer",
                "chance_level": 0.3,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "rejection_of_low_offers",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"role": "responder", "low_offer": False}, "field": "accepted"},
                "group_b": {"filter": {"role": "responder", "low_offer": True}, "field": "accepted"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "offer_sensitivity",
                "test": "correlation_test",
                "filter": {"role": "responder"},
                "field_x": "offer_proportion",
                "field_y": "accepted_num",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_ultimatum_data():
    return _generate_ultimatum_trials(mean_offer_proportion=0.42, fair_accept_rate=0.90, low_accept_rate=0.15)


@pytest.fixture
def random_ultimatum_data():
    return _generate_ultimatum_trials(mean_offer_proportion=0.30, fair_accept_rate=0.50, low_accept_rate=0.50, seed=99)


# ── Public Goods ──────────────────────────────────────────

def _generate_public_goods_trials(
    n_rounds=10,
    initial_contribution=12.0,
    decline_rate=0.8,
    contribution_noise=2.5,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    endowment = 20
    multiplier = 1.6
    n_players = 4
    trials = []
    prev_other_mean = None

    for i in range(n_rounds):
        round_number = i + 1

        timed_out = rng.random() < timeout_rate

        base_contribution = max(0, initial_contribution - decline_rate * i + float(np_rng.normal(0, contribution_noise)))
        player_contribution = max(0, min(endowment, round(base_contribution)))
        player_contribution_proportion = player_contribution / endowment
        positive_contribution = player_contribution > 0

        other_contributions = [max(0, min(endowment, round(float(np_rng.normal(8, 3))))) for _ in range(n_players - 1)]
        other_mean_contribution = round(sum(other_contributions) / len(other_contributions), 2)

        total_pot = player_contribution + sum(other_contributions)
        public_return = round((total_pot * multiplier) / n_players, 2)
        player_payoff = round((endowment - player_contribution) + public_return, 2)

        rt = max(500, float(np_rng.normal(5000, 2000))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
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
            "timed_out": timed_out,
            "rt": rt,
            "response": player_contribution,
        }

        if prev_other_mean is not None:
            trial["previous_other_mean"] = prev_other_mean

        trials.append(trial)
        prev_other_mean = other_mean_contribution

    return trials


@pytest.fixture
def public_goods_config():
    return {
        "task_id": "public_goods",
        "parameters": {
            "n_trials": 10,
            "endowment": 20,
            "multiplier": 1.6,
            "n_players": 4,
            "response_type": "slider",
            "slider_range": [0, 20],
        },
    }


@pytest.fixture
def public_goods_metrics():
    return {
        "task_id": "public_goods",
        "metrics": [
            {"name": "mean_contribution_proportion", "type": "mean", "field": "player_contribution_proportion", "human_mean": 0.40, "human_sd": 0.20},
            {"name": "first_round_contribution", "type": "mean", "field": "player_contribution_proportion", "filter": {"round_number": 1}, "human_mean": 0.50, "human_sd": 0.22},
            {"name": "mean_payoff", "type": "mean", "field": "player_payoff", "human_mean": 22, "human_sd": 4},
        ],
    }


@pytest.fixture
def public_goods_signatures():
    return {
        "task_id": "public_goods",
        "signatures": [
            {
                "name": "conditional_cooperation",
                "test": "proportion_test",
                "field": "positive_contribution",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "declining_contributions",
                "test": "correlation_test",
                "field_x": "round_number",
                "field_y": "player_contribution_proportion",
                "expected_direction": "negative",
                "threshold_p": 0.10,
                "weight": 1.0,
            },
            {
                "name": "group_sensitivity",
                "test": "correlation_test",
                "field_x": "previous_other_mean",
                "field_y": "player_contribution",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_public_goods_data():
    return _generate_public_goods_trials(initial_contribution=12.0, decline_rate=0.8, contribution_noise=2.5)


@pytest.fixture
def random_public_goods_data():
    return _generate_public_goods_trials(initial_contribution=10.0, decline_rate=0.0, contribution_noise=6.0, seed=99)


# ── Intertemporal Choice ──────────────────────────────────

def _generate_intertemporal_choice_trials(
    n_trials=60,
    sooner_rate_short=0.55,
    sooner_rate_long=0.35,
    magnitude_effect=0.10,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    delay_categories = ["short", "long"]
    smaller_amounts = [10, 20, 30, 40, 50]
    larger_amounts = [20, 40, 60, 80, 100]
    short_delays = [1, 7, 14]
    long_delays = [30, 90, 180, 365]

    for i in range(n_trials):
        delay_cat = delay_categories[i % 2]
        smaller_amount = smaller_amounts[i % len(smaller_amounts)]
        larger_amount = larger_amounts[i % len(larger_amounts)]
        if larger_amount <= smaller_amount:
            larger_amount = smaller_amount + 20
        delay_sooner = 0
        delay_later = rng.choice(short_delays) if delay_cat == "short" else rng.choice(long_delays)

        timed_out = rng.random() < timeout_rate

        # Base sooner rate depends on delay category
        base_rate = sooner_rate_short if delay_cat == "short" else sooner_rate_long

        # Magnitude effect: less impatience for larger amounts
        if larger_amount >= 80:
            base_rate -= magnitude_effect

        base_rate = max(0.05, min(0.95, base_rate))
        chose_sooner = rng.random() < base_rate and not timed_out
        chose_larger = not chose_sooner and not timed_out

        rt = max(300, float(np_rng.normal(3000, 800))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "smaller_amount": smaller_amount,
            "larger_amount": larger_amount,
            "delay_sooner": delay_sooner,
            "delay_later": delay_later,
            "delay_category": delay_cat,
            "chose_smaller": chose_sooner,
            "chose_larger": chose_larger,
            "chose_sooner": chose_sooner,
            "chose_larger_num": 1 if chose_larger else 0,
            "response": "f" if chose_sooner else ("j" if chose_larger else None),
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def intertemporal_choice_config():
    return {
        "task_id": "intertemporal_choice",
        "parameters": {
            "n_trials": 60,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def intertemporal_choice_metrics():
    return {
        "task_id": "intertemporal_choice",
        "metrics": [
            {"name": "overall_sooner_rate", "type": "proportion_correct", "field": "chose_sooner", "human_mean": 0.45, "human_sd": 0.20},
            {"name": "short_delay_sooner_rate", "type": "proportion_correct", "field": "chose_sooner", "filter": {"delay_category": "short"}, "human_mean": 0.55, "human_sd": 0.22},
            {"name": "long_delay_sooner_rate", "type": "proportion_correct", "field": "chose_sooner", "filter": {"delay_category": "long"}, "human_mean": 0.35, "human_sd": 0.22},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 3000, "human_sd": 1200, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def intertemporal_choice_signatures():
    return {
        "task_id": "intertemporal_choice",
        "signatures": [
            {
                "name": "present_bias",
                "test": "proportion_test",
                "field": "chose_sooner",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "delay_sensitivity",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"delay_category": "short"}, "field": "chose_sooner"},
                "group_b": {"filter": {"delay_category": "long"}, "field": "chose_sooner"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "magnitude_effect",
                "test": "correlation_test",
                "field_x": "larger_amount",
                "field_y": "chose_larger_num",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_intertemporal_choice_data():
    return _generate_intertemporal_choice_trials(sooner_rate_short=0.58, sooner_rate_long=0.32, magnitude_effect=0.12)


@pytest.fixture
def random_intertemporal_choice_data():
    return _generate_intertemporal_choice_trials(sooner_rate_short=0.50, sooner_rate_long=0.50, magnitude_effect=0.0, seed=99)


# ── Two-Step ──────────────────────────────────────────────

def _generate_two_step_trials(
    n_trials=100,
    reward_rate=0.55,
    stay_common_rewarded=0.80,
    stay_rare_rewarded=0.55,
    stay_common_unrewarded=0.40,
    stay_rare_unrewarded=0.65,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    prev_rewarded = None
    prev_transition = None

    for i in range(n_trials):
        stage1_choice = rng.choice(["left", "right"])
        stage1_rt = max(200, float(np_rng.normal(600, 150)))
        transition_type = "common" if rng.random() < 0.70 else "rare"
        stage2_choice = rng.choice(["left", "right"])
        stage2_rt = max(200, float(np_rng.normal(500, 120)))

        timed_out = rng.random() < timeout_rate
        rewarded = rng.random() < reward_rate and not timed_out

        if prev_rewarded is not None and prev_transition is not None:
            if prev_rewarded and prev_transition == "common":
                stayed = rng.random() < stay_common_rewarded
            elif prev_rewarded and prev_transition == "rare":
                stayed = rng.random() < stay_rare_rewarded
            elif not prev_rewarded and prev_transition == "common":
                stayed = rng.random() < stay_common_unrewarded
            else:
                stayed = rng.random() < stay_rare_unrewarded
        else:
            stayed = rng.random() < 0.60

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
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
            "timed_out": timed_out,
        }
        trials.append(trial)
        prev_rewarded = rewarded
        prev_transition = transition_type

    return trials


@pytest.fixture
def two_step_config():
    return {
        "task_id": "two_step",
        "parameters": {
            "n_trials": 100,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def two_step_metrics():
    return {
        "task_id": "two_step",
        "metrics": [
            {"name": "overall_reward_rate", "type": "proportion_correct", "field": "rewarded", "human_mean": 0.55, "human_sd": 0.10},
            {"name": "mean_stage1_rt", "type": "mean", "field": "stage1_rt", "human_mean": 600, "human_sd": 200, "direction": "lower_is_better"},
            {"name": "stay_rate", "type": "proportion_correct", "field": "stayed", "human_mean": 0.65, "human_sd": 0.15},
        ],
    }


@pytest.fixture
def two_step_signatures():
    return {
        "task_id": "two_step",
        "signatures": [
            {
                "name": "model_based_index",
                "test": "interaction_test",
                "outcome_field": "stayed_num",
                "factor_a_field": "previous_rewarded_str",
                "factor_b_field": "previous_transition",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "above_chance_reward",
                "test": "proportion_test",
                "field": "rewarded",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
            {
                "name": "win_stay",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"previous_rewarded": True}, "field": "stayed"},
                "group_b": {"filter": {"previous_rewarded": False}, "field": "stayed"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_two_step_data():
    return _generate_two_step_trials(
        reward_rate=0.55,
        stay_common_rewarded=0.80, stay_rare_rewarded=0.55,
        stay_common_unrewarded=0.40, stay_rare_unrewarded=0.65,
    )


@pytest.fixture
def random_two_step_data():
    return _generate_two_step_trials(
        reward_rate=0.50,
        stay_common_rewarded=0.50, stay_rare_rewarded=0.50,
        stay_common_unrewarded=0.50, stay_rare_unrewarded=0.50,
        seed=99,
    )


# ── Decisions from Experience ─────────────────────────────

def _generate_dfe_trials(
    n_trials=20,
    accuracy_no_rare=0.70,
    accuracy_rare=0.48,
    mean_samples=10,
    recency_strength=0.65,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    for i in range(n_trials):
        rare_event = rng.random() < 0.50
        total_samples = max(2, round(float(np_rng.normal(mean_samples, 4))))
        frugal = total_samples < 15

        timed_out = rng.random() < timeout_rate
        acc = accuracy_rare if rare_event else accuracy_no_rare
        chose_higher_ev = rng.random() < acc and not timed_out

        # Recency: last sample matches choice
        if chose_higher_ev:
            last_sample_match = 1 if rng.random() < recency_strength else 0
        else:
            last_sample_match = 0 if rng.random() < recency_strength else 1

        rt = max(500, float(np_rng.normal(3000, 1000))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "problem_number": i + 1,
            "total_samples": total_samples,
            "chose_higher_ev": chose_higher_ev,
            "chose_higher_ev_num": 1 if chose_higher_ev else 0,
            "rare_event_present": rare_event,
            "frugal_sampling": frugal,
            "last_sample_match": last_sample_match,
            "response": "f" if chose_higher_ev else ("j" if not timed_out else None),
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def dfe_config():
    return {
        "task_id": "decisions_from_experience",
        "parameters": {
            "n_trials": 20,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def dfe_metrics():
    return {
        "task_id": "decisions_from_experience",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "chose_higher_ev", "human_mean": 0.60, "human_sd": 0.15},
            {"name": "mean_total_samples", "type": "mean", "field": "total_samples", "human_mean": 11, "human_sd": 8},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 3000, "human_sd": 1500, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def dfe_signatures():
    return {
        "task_id": "decisions_from_experience",
        "signatures": [
            {
                "name": "description_experience_gap",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"rare_event_present": False}, "field": "chose_higher_ev"},
                "group_b": {"filter": {"rare_event_present": True}, "field": "chose_higher_ev"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "sampling_frugality",
                "test": "proportion_test",
                "field": "frugal_sampling",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
            {
                "name": "recency_in_sampling",
                "test": "correlation_test",
                "field_x": "last_sample_match",
                "field_y": "chose_higher_ev_num",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_dfe_data():
    return _generate_dfe_trials(accuracy_no_rare=0.72, accuracy_rare=0.48, mean_samples=10, recency_strength=0.65)


@pytest.fixture
def random_dfe_data():
    return _generate_dfe_trials(accuracy_no_rare=0.50, accuracy_rare=0.50, mean_samples=15, recency_strength=0.50, seed=99)


# ── Prisoner's Dilemma ────────────────────────────────────

def _generate_prisoners_dilemma_trials(
    n_trials=50,
    coop_after_coop=0.70,
    coop_after_defect=0.35,
    initial_coop=0.60,
    forgiveness_rate=0.45,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    prev_player_coop = None
    prev_partner_coop = None
    prev_mutual_defection = False

    for i in range(n_trials):
        # Tit-for-tat partner
        if prev_player_coop is not None:
            partner_cooperated = prev_player_coop
        else:
            partner_cooperated = True

        timed_out = rng.random() < timeout_rate

        # Player decision
        if prev_partner_coop is not None:
            if prev_partner_coop:
                player_cooperated = rng.random() < coop_after_coop and not timed_out
            else:
                player_cooperated = rng.random() < coop_after_defect and not timed_out
        else:
            player_cooperated = rng.random() < initial_coop and not timed_out

        # Forgiveness after mutual defection
        if prev_mutual_defection and not timed_out:
            player_cooperated = rng.random() < forgiveness_rate

        # Match to partner's previous choice
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

        rt = max(300, float(np_rng.normal(2000, 600))) if not timed_out else None

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "round_number": i + 1,
            "player_choice": "cooperate" if player_cooperated else "defect",
            "partner_choice": "cooperate" if partner_cooperated else "defect",
            "player_cooperated": player_cooperated,
            "partner_cooperated": partner_cooperated,
            "player_payoff": payoff,
            "matched_partner": matched,
            "previous_mutual_defection": prev_mutual_defection,
            "response": "f" if player_cooperated else ("j" if not timed_out else None),
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

        prev_mutual_defection = (not player_cooperated and not partner_cooperated)
        prev_player_coop = player_cooperated
        prev_partner_coop = partner_cooperated

    return trials


@pytest.fixture
def prisoners_dilemma_config():
    return {
        "task_id": "prisoners_dilemma",
        "parameters": {
            "n_trials": 50,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def prisoners_dilemma_metrics():
    return {
        "task_id": "prisoners_dilemma",
        "metrics": [
            {"name": "cooperation_rate", "type": "proportion_correct", "field": "player_cooperated", "human_mean": 0.50, "human_sd": 0.20},
            {"name": "mean_payoff", "type": "mean", "field": "player_payoff", "human_mean": 2.5, "human_sd": 0.8},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 2000, "human_sd": 800, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def prisoners_dilemma_signatures():
    return {
        "task_id": "prisoners_dilemma",
        "signatures": [
            {
                "name": "above_chance_cooperation",
                "test": "proportion_test",
                "field": "player_cooperated",
                "chance_level": 0.25,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "tit_for_tat",
                "test": "proportion_test",
                "field": "matched_partner",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "forgiveness",
                "test": "proportion_test",
                "filter": {"previous_mutual_defection": True},
                "field": "player_cooperated",
                "chance_level": 0.25,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_prisoners_dilemma_data():
    return _generate_prisoners_dilemma_trials(coop_after_coop=0.70, coop_after_defect=0.35, forgiveness_rate=0.45)


@pytest.fixture
def random_prisoners_dilemma_data():
    return _generate_prisoners_dilemma_trials(coop_after_coop=0.50, coop_after_defect=0.50, forgiveness_rate=0.50, seed=99)


# ── Probabilistic Classification ──────────────────────────

def _generate_probclass_trials(
    n_trials=100,
    initial_accuracy=0.50,
    learning_rate=0.05,
    strong_cue_bonus=0.08,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    for i in range(n_trials):
        block = i // 20 + 1

        cue1 = rng.random() < 0.50
        cue2 = rng.random() < 0.50
        cue3 = rng.random() < 0.50
        cue4 = rng.random() < 0.50
        if not any((cue1, cue2, cue3, cue4)):
            cue1 = True

        strong_cue_present = cue1 or cue2

        # True outcome
        score = (0.80 if cue1 else 0.20) + (0.60 if cue2 else 0.40) + \
                (0.40 if cue3 else 0.60) + (0.20 if cue4 else 0.80)
        true_outcome = "sun" if score > 2.0 else "rain"

        # Learning curve
        base_acc = initial_accuracy + learning_rate * block
        if strong_cue_present:
            base_acc += strong_cue_bonus
        base_acc = min(0.90, base_acc)

        timed_out = rng.random() < timeout_rate
        is_correct = rng.random() < base_acc and not timed_out

        rt = max(300, float(np_rng.normal(2000, 500))) if not timed_out else None

        if timed_out:
            response_key = None
            predicted = None
        elif is_correct:
            response_key = "f" if true_outcome == "sun" else "j"
            predicted = true_outcome
        else:
            response_key = "j" if true_outcome == "sun" else "f"
            predicted = "rain" if true_outcome == "sun" else "sun"

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
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
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def probclass_config():
    return {
        "task_id": "probabilistic_classification",
        "parameters": {
            "n_trials": 100,
            "n_blocks": 5,
            "trials_per_block": 20,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def probclass_metrics():
    return {
        "task_id": "probabilistic_classification",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "human_mean": 0.65, "human_sd": 0.10},
            {"name": "final_block_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"block": 5}, "human_mean": 0.72, "human_sd": 0.12},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 2000, "human_sd": 600, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def probclass_signatures():
    return {
        "task_id": "probabilistic_classification",
        "signatures": [
            {
                "name": "learning_curve",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"block": 5}, "field": "correct"},
                "group_b": {"filter": {"block": 1}, "field": "correct"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 1.0,
            },
            {
                "name": "above_chance_accuracy",
                "test": "proportion_test",
                "field": "correct",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
            {
                "name": "cue_utilization",
                "test": "paired_proportion_test",
                "group_a": {"filter": {"strong_cue_present": True}, "field": "correct"},
                "group_b": {"filter": {"strong_cue_present": False}, "field": "correct"},
                "threshold_p": 0.05,
                "expected_direction": "a > b",
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_probclass_data():
    return _generate_probclass_trials(initial_accuracy=0.50, learning_rate=0.05, strong_cue_bonus=0.10)


@pytest.fixture
def random_probclass_data():
    return _generate_probclass_trials(initial_accuracy=0.50, learning_rate=0.0, strong_cue_bonus=0.0, seed=99)


# ── Loss Aversion ───────────────────────────────────────────────────────

def _generate_loss_aversion_trials(
    n_trials=60,
    lambda_loss=2.0,
    noise=0.15,
    timeout_rate=0.0,
    seed=42,
):
    """Generate synthetic mixed-gamble loss aversion data.

    lambda_loss: loss aversion coefficient. >1 means losses loom larger.
    Human-like ~2.0, random ~1.0.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    gains = [5, 10, 15, 20, 25, 30, 35, 40]
    losses = [5, 10, 15, 20, 25, 30, 35, 40]

    all_pairs = [(g, l) for g in gains for l in losses]
    rng.shuffle(all_pairs)
    selected = all_pairs[:n_trials]

    for i in range(n_trials):
        gain, loss = selected[i]
        ev_gamble = (gain - loss) / 2.0
        ev_positive = ev_gamble > 0
        loss_gain_ratio = loss / gain
        ev_abs = abs(ev_gamble)

        # Decision based on subjective utility: accept if gain > lambda * loss
        subjective_value = gain - lambda_loss * loss
        accept_prob = 1.0 / (1.0 + np.exp(-subjective_value / (10.0 + noise * 50)))
        accept_prob = max(0.05, min(0.95, accept_prob))

        timed_out = rng.random() < timeout_rate

        if timed_out:
            accept = False
            reject = False
            rt = None
        else:
            accept = rng.random() < accept_prob
            reject = not accept
            base_rt = 1500 - ev_abs * 20
            rt = round(max(300, float(np_rng.normal(base_rt, 400))), 1)

        trial = {
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "gain": gain,
            "loss": loss,
            "ev_gamble": ev_gamble,
            "ev_positive": ev_positive,
            "loss_gain_ratio": round(loss_gain_ratio, 3),
            "ev_abs": ev_abs,
            "accept": accept,
            "reject": reject,
            "accept_num": 1 if accept else 0,
            "response": "f" if accept else "j",
            "rt": rt,
            "timed_out": timed_out,
        }
        trials.append(trial)

    return trials


@pytest.fixture
def loss_aversion_config():
    return {
        "task_id": "loss_aversion",
        "parameters": {
            "n_trials": 60,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def loss_aversion_metrics():
    return {
        "task_id": "loss_aversion",
        "metrics": [
            {"name": "overall_accept_rate", "type": "proportion_correct", "field": "accept", "human_mean": 0.45, "human_sd": 0.15},
            {"name": "accept_rate_positive_ev", "type": "proportion_correct", "field": "accept", "filter": {"ev_positive": True}, "human_mean": 0.60, "human_sd": 0.15},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 1500, "human_sd": 500, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def loss_aversion_signatures():
    return {
        "task_id": "loss_aversion",
        "signatures": [
            {
                "name": "loss_aversion_effect",
                "test": "correlation_test",
                "field_x": "loss_gain_ratio",
                "field_y": "accept_num",
                "expected_direction": "negative",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "status_quo_bias",
                "test": "proportion_test",
                "field": "reject",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
            {
                "name": "rt_conflict_effect",
                "test": "correlation_test",
                "field_x": "ev_abs",
                "field_y": "rt",
                "expected_direction": "negative",
                "threshold_p": 0.05,
                "weight": 0.5,
            },
        ],
    }


@pytest.fixture
def human_like_loss_aversion_data():
    return _generate_loss_aversion_trials(lambda_loss=2.0, noise=0.15)


@pytest.fixture
def random_loss_aversion_data():
    return _generate_loss_aversion_trials(lambda_loss=1.0, noise=0.5, seed=99)


# ── Context Effects ─────────────────────────────────────────────────────

def _generate_context_effects_trials(
    n_trials=90,
    n_training=30,
    target_bias=0.15,
    learning_rate=0.3,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    target_mean = 70
    competitor_mean = 65

    # Training phase (2-option)
    for i in range(n_training):
        t_reward = round(target_mean + (rng.random() - 0.5) * 20)
        c_reward = round(competitor_mean + (rng.random() - 0.5) * 20)

        # Learning: prefer better option more over time
        prob_target = 0.5 + learning_rate * (i / n_training) * 0.3
        chose_target = rng.random() < prob_target

        trials.append({
            "trial_index": i + 1,
            "trial_part": "stimulus",
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
            "rt": round(max(300, float(np_rng.normal(1500, 400))), 1),
            "timed_out": False,
        })

    # Test phase (3-option with decoy)
    n_test = n_trials - n_training
    effects = ["attraction", "compromise"]
    trial_idx = n_training

    for i in range(n_test):
        effect = effects[i % 2]
        t_reward = round(target_mean + (rng.random() - 0.5) * 20)
        c_reward = round(competitor_mean + (rng.random() - 0.5) * 20)

        if effect == "attraction":
            d_reward = round(t_reward * 0.75 + (rng.random() - 0.5) * 5)
            # Attraction effect: target chosen more than 1/3
            prob_target = 0.333 + target_bias + 0.1
        else:
            d_reward = round(target_mean * 1.3 + (rng.random() - 0.5) * 10)
            prob_target = 0.333 + target_bias

        prob_target = max(0.1, min(0.8, prob_target))
        timed_out = rng.random() < timeout_rate
        trial_idx += 1

        if timed_out:
            option_chosen = None
            reward_chosen = 0
            is_target = False
        else:
            r = rng.random()
            if r < prob_target:
                option_chosen = 0
            elif r < prob_target + (1 - prob_target) * 0.6:
                option_chosen = 1
            else:
                option_chosen = 2
            rewards = [t_reward, c_reward, d_reward]
            reward_chosen = rewards[option_chosen]
            is_target = option_chosen == 0

        block = 2 if effect == "attraction" else 3
        trials.append({
            "trial_index": trial_idx,
            "trial_part": "stimulus",
            "phase": "test",
            "effect_type": effect,
            "block": block,
            "n_options": 3,
            "reward_0": t_reward,
            "reward_1": c_reward,
            "reward_2": d_reward,
            "target_idx": 0,
            "option_chosen": option_chosen,
            "reward_chosen": reward_chosen,
            "is_target": is_target,
            "trial_in_block": i + 1,
            "response": ["d", "f", "j"][option_chosen] if option_chosen is not None else None,
            "rt": round(max(300, float(np_rng.normal(1500, 400))), 1) if not timed_out else None,
            "timed_out": timed_out,
        })

    return trials


@pytest.fixture
def context_effects_config():
    return {
        "task_id": "context_effects",
        "parameters": {
            "n_trials": 90,
            "response_keys": ["d", "f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def context_effects_metrics():
    return {
        "task_id": "context_effects",
        "metrics": [
            {"name": "overall_reward", "type": "mean", "field": "reward_chosen", "human_mean": 65, "human_sd": 15},
            {"name": "target_choice_rate", "type": "proportion_correct", "field": "is_target", "filter": {"phase": "test"}, "human_mean": 0.45, "human_sd": 0.12},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 1500, "human_sd": 500, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def context_effects_signatures():
    return {
        "task_id": "context_effects",
        "signatures": [
            {
                "name": "attraction_effect",
                "test": "proportion_test",
                "filter": {"effect_type": "attraction"},
                "field": "is_target",
                "chance_level": 0.333,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "compromise_effect",
                "test": "proportion_test",
                "filter": {"effect_type": "compromise"},
                "field": "is_target",
                "chance_level": 0.333,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "learning_improvement",
                "test": "correlation_test",
                "field_x": "trial_in_block",
                "field_y": "reward_chosen",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.5,
            },
        ],
    }


@pytest.fixture
def human_like_context_effects_data():
    return _generate_context_effects_trials(target_bias=0.15, learning_rate=0.3)


@pytest.fixture
def random_context_effects_data():
    return _generate_context_effects_trials(target_bias=0.0, learning_rate=0.0, seed=99)


# ── Moral Judgment ──────────────────────────────────────────────────────

def _generate_moral_judgment_trials(
    n_trials=26,
    utilitarian_bias=0.65,
    omission_bias=0.55,
    death_sensitivity=0.1,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    scenario_types = ["quantity", "age", "gender", "status", "species", "intervention"]

    for i in range(n_trials):
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

        # Utilitarian: choose fewer deaths, modulated by death_difference
        p_util = utilitarian_bias + death_sensitivity * death_diff
        p_util = max(0.3, min(0.9, p_util))

        timed_out = rng.random() < timeout_rate

        if timed_out:
            chose_a = False
            chose_fewer = False
            chose_intervention = False
            chose_inaction = False
            rt = None
        else:
            if fewer_deaths_is_a:
                chose_a = rng.random() < p_util
            elif n_b < n_a:
                chose_a = rng.random() > p_util
            else:
                # Equal deaths: slight omission bias
                chose_a = rng.random() < (1 - omission_bias) if action_a == "swerve" else rng.random() < omission_bias

            chose_fewer = (chose_a and fewer_deaths_is_a) or (not chose_a and n_b < n_a)
            if n_a == n_b:
                chose_fewer = True

            chose_intervention = (chose_a and action_a == "swerve") or (not chose_a and action_b == "swerve")
            chose_inaction = not chose_intervention
            rt = round(max(500, float(np_rng.normal(5000, 2000))), 1)

        trials.append({
            "trial_index": i + 1,
            "trial_part": "stimulus",
            "scenario_type": scenario_type,
            "intervention": intervention,
            "n_killed_a": n_a,
            "n_killed_b": n_b,
            "action_a": action_a,
            "action_b": action_b,
            "n_saved_a": n_b if not timed_out else 0,
            "n_saved_b": n_a if not timed_out else 0,
            "chose_fewer_deaths": chose_fewer,
            "chose_fewer_deaths_num": 1 if chose_fewer else 0,
            "death_difference": death_diff,
            "chose_intervention": chose_intervention,
            "chose_inaction": chose_inaction,
            "response": "f" if chose_a else "j" if not timed_out else None,
            "rt": rt,
            "timed_out": timed_out,
        })

    return trials


@pytest.fixture
def moral_judgment_config():
    return {
        "task_id": "moral_judgment",
        "parameters": {
            "n_trials": 26,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def moral_judgment_metrics():
    return {
        "task_id": "moral_judgment",
        "metrics": [
            {"name": "utilitarian_rate", "type": "proportion_correct", "field": "chose_fewer_deaths", "human_mean": 0.63, "human_sd": 0.15},
            {"name": "mean_rt", "type": "mean", "field": "rt", "human_mean": 5000, "human_sd": 3000, "direction": "lower_is_better"},
        ],
    }


@pytest.fixture
def moral_judgment_signatures():
    return {
        "task_id": "moral_judgment",
        "signatures": [
            {
                "name": "utilitarian_preference",
                "test": "proportion_test",
                "field": "chose_fewer_deaths",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 1.0,
            },
            {
                "name": "omission_bias",
                "test": "proportion_test",
                "field": "chose_inaction",
                "chance_level": 0.5,
                "expected_direction": "above_chance",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
            {
                "name": "death_count_sensitivity",
                "test": "correlation_test",
                "field_x": "death_difference",
                "field_y": "chose_fewer_deaths_num",
                "expected_direction": "positive",
                "threshold_p": 0.05,
                "weight": 0.75,
            },
        ],
    }


@pytest.fixture
def human_like_moral_judgment_data():
    return _generate_moral_judgment_trials(utilitarian_bias=0.65, omission_bias=0.55, death_sensitivity=0.1)


@pytest.fixture
def random_moral_judgment_data():
    return _generate_moral_judgment_trials(utilitarian_bias=0.50, omission_bias=0.50, death_sensitivity=0.0, seed=99)


# ── Confirmation Bias RL ──────────────────────────────────────────────


def _generate_confirmation_bias_rl_trials(
    n_per_context=24,
    learning_rate=0.1,
    confirmation_bias_strength=0.3,
    timeout_rate=0.0,
    seed=42,
):
    """Generate synthetic confirmation bias RL data.

    Contexts 0-1: partial feedback (see chosen only)
    Contexts 2-3: complete feedback (see both chosen and unchosen)
    Each context has one arm p=0.75, other p=0.25.
    confirmation_bias_strength: extra win-stay tendency in partial vs complete.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    contexts = [
        {"id": 0, "feedback_type": "partial",  "p_left": 0.75, "p_right": 0.25},
        {"id": 1, "feedback_type": "partial",  "p_left": 0.25, "p_right": 0.75},
        {"id": 2, "feedback_type": "complete", "p_left": 0.75, "p_right": 0.25},
        {"id": 3, "feedback_type": "complete", "p_left": 0.25, "p_right": 0.75},
    ]

    trial_index = 0
    for ctx in contexts:
        q_left = 0.5
        q_right = 0.5
        prev_arm = None
        prev_reward = None

        for t in range(n_per_context):
            timed_out = rng.random() < timeout_rate
            trial_index += 1

            if timed_out:
                trials.append({
                    "trial_index": trial_index,
                    "trial_part": "stimulus",
                    "context": ctx["id"],
                    "feedback_type": ctx["feedback_type"],
                    "arm_chosen": None,
                    "reward": 0,
                    "unchosen_reward": 0,
                    "correct": False,
                    "stayed": False,
                    "prev_reward": None,
                    "response": None,
                    "rt": None,
                    "timed_out": True,
                })
                continue

            # Softmax choice
            diff = q_left - q_right
            p_left = 1.0 / (1.0 + np.exp(-5.0 * diff))
            arm = "left" if rng.random() < p_left else "right"

            p_chosen = ctx["p_left"] if arm == "left" else ctx["p_right"]
            p_unchosen = ctx["p_right"] if arm == "left" else ctx["p_left"]
            reward = 1 if rng.random() < p_chosen else -1
            unchosen_reward = 1 if rng.random() < p_unchosen else -1

            correct = (ctx["p_left"] >= ctx["p_right"] and arm == "left") or \
                      (ctx["p_right"] > ctx["p_left"] and arm == "right")

            # Update Q values
            if arm == "left":
                q_left += learning_rate * (reward - q_left)
                if ctx["feedback_type"] == "complete":
                    q_right += learning_rate * (unchosen_reward - q_right)
            else:
                q_right += learning_rate * (reward - q_right)
                if ctx["feedback_type"] == "complete":
                    q_left += learning_rate * (unchosen_reward - q_left)

            stayed = arm == prev_arm if prev_arm is not None else False
            base_rt = 800
            rt = round(max(200, float(np_rng.normal(base_rt, 150))), 1)

            trials.append({
                "trial_index": trial_index,
                "trial_part": "stimulus",
                "context": ctx["id"],
                "feedback_type": ctx["feedback_type"],
                "arm_chosen": arm,
                "reward": reward,
                "unchosen_reward": unchosen_reward,
                "correct": correct,
                "stayed": stayed,
                "prev_reward": prev_reward,
                "response": "f" if arm == "left" else "j",
                "rt": rt,
                "timed_out": False,
            })
            prev_arm = arm
            prev_reward = reward

    rng.shuffle(trials)
    # Re-index after shuffle
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1
    return trials


@pytest.fixture
def confirmation_bias_rl_config():
    return {
        "task_id": "confirmation_bias_rl",
        "parameters": {
            "n_trials": 96,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def confirmation_bias_rl_metrics():
    return {
        "task_id": "confirmation_bias_rl",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.65, "human_sd": 0.10},
            {"name": "partial_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False, "feedback_type": "partial"}, "human_mean": 0.62, "human_sd": 0.12},
            {"name": "complete_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False, "feedback_type": "complete"}, "human_mean": 0.70, "human_sd": 0.10},
            {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"timed_out": False}, "human_mean": 800, "human_sd": 200},
        ],
    }


@pytest.fixture
def confirmation_bias_rl_signatures():
    return {
        "task_id": "confirmation_bias_rl",
        "signatures": [
            {
                "name": "counterfactual_learning",
                "test": "proportion_test",
                "field": "correct",
                "filter": {"timed_out": False, "feedback_type": "complete"},
                "chance_level": 0.5,
                "threshold_p": 0.05,
                "expected_direction": "above_chance",
                "weight": 1.5,
            },
            {
                "name": "partial_above_chance",
                "test": "proportion_test",
                "field": "correct",
                "filter": {"timed_out": False, "feedback_type": "partial"},
                "chance_level": 0.5,
                "threshold_p": 0.05,
                "expected_direction": "above_chance",
                "weight": 1.0,
            },
            {
                "name": "learning_curve",
                "test": "correlation_test",
                "field_x": "trial_index",
                "field_y": "correct",
                "filter": {"timed_out": False},
                "threshold_p": 0.05,
                "expected_direction": "positive",
                "weight": 1.0,
            },
        ],
    }


@pytest.fixture
def human_like_confirmation_bias_rl_data():
    return _generate_confirmation_bias_rl_trials(learning_rate=0.15, confirmation_bias_strength=0.3)


@pytest.fixture
def random_confirmation_bias_rl_data():
    return _generate_confirmation_bias_rl_trials(learning_rate=0.0, confirmation_bias_strength=0.0, seed=99)


# ── Magnitude RL ──────────────────────────────────────────────────────


def _generate_magnitude_rl_trials(
    trials_per_pair=24,
    n_transfer=24,
    learning_rate=0.1,
    magnitude_bonus=0.15,
    timeout_rate=0.0,
    seed=42,
):
    """Generate synthetic magnitude RL data.

    Pairs 0-1: high magnitude (±10), Pairs 2-3: low magnitude (±1).
    Each pair has one 75%/25% split.
    magnitude_bonus: extra accuracy boost for high magnitude pairs.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    pairs = [
        {"id": 0, "reward_magnitude": "high", "mag_value": 10, "p_left": 0.75, "p_right": 0.25},
        {"id": 1, "reward_magnitude": "high", "mag_value": 10, "p_left": 0.25, "p_right": 0.75},
        {"id": 2, "reward_magnitude": "low",  "mag_value": 1,  "p_left": 0.75, "p_right": 0.25},
        {"id": 3, "reward_magnitude": "low",  "mag_value": 1,  "p_left": 0.25, "p_right": 0.75},
    ]

    trial_index = 0

    # Learning phase
    for pair in pairs:
        q_left = 0.0
        q_right = 0.0
        lr = learning_rate
        if pair["reward_magnitude"] == "high":
            lr += magnitude_bonus

        for t in range(trials_per_pair):
            timed_out = rng.random() < timeout_rate
            trial_index += 1

            if timed_out:
                trials.append({
                    "trial_index": trial_index,
                    "trial_part": "stimulus",
                    "phase": "learning",
                    "context": pair["id"],
                    "reward_magnitude": pair["reward_magnitude"],
                    "mag_value": pair["mag_value"],
                    "arm_chosen": None,
                    "reward": 0,
                    "correct": False,
                    "stayed": False,
                    "prev_reward": None,
                    "response": None,
                    "rt": None,
                    "timed_out": True,
                })
                continue

            diff = q_left - q_right
            p_left = 1.0 / (1.0 + np.exp(-3.0 * diff))
            arm = "left" if rng.random() < p_left else "right"

            p_chosen = pair["p_left"] if arm == "left" else pair["p_right"]
            win = rng.random() < p_chosen
            reward = pair["mag_value"] if win else -pair["mag_value"]
            correct = (pair["p_left"] >= pair["p_right"] and arm == "left") or \
                      (pair["p_right"] > pair["p_left"] and arm == "right")

            if arm == "left":
                q_left += lr * (reward - q_left)
            else:
                q_right += lr * (reward - q_right)

            rt = round(max(200, float(np_rng.normal(700, 150))), 1)

            trials.append({
                "trial_index": trial_index,
                "trial_part": "stimulus",
                "phase": "learning",
                "context": pair["id"],
                "reward_magnitude": pair["reward_magnitude"],
                "mag_value": pair["mag_value"],
                "arm_chosen": arm,
                "reward": reward,
                "correct": correct,
                "stayed": False,
                "prev_reward": None,
                "response": "f" if arm == "left" else "j",
                "rt": rt,
                "timed_out": False,
            })

    # Shuffle learning trials
    rng.shuffle(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1

    # Transfer phase
    high_mag_preference = 0.5 + magnitude_bonus * 2
    for t in range(n_transfer):
        trial_index = len(trials) + 1
        timed_out = rng.random() < timeout_rate

        if timed_out:
            trials.append({
                "trial_index": trial_index,
                "trial_part": "stimulus",
                "phase": "transfer",
                "context": "transfer",
                "reward_magnitude": "mixed",
                "mag_value": 0,
                "arm_chosen": None,
                "reward": 0,
                "correct": False,
                "chose_high_magnitude": False,
                "response": None,
                "rt": None,
                "timed_out": True,
            })
            continue

        chose_high = rng.random() < high_mag_preference
        rt = round(max(200, float(np_rng.normal(800, 200))), 1)

        trials.append({
            "trial_index": trial_index,
            "trial_part": "stimulus",
            "phase": "transfer",
            "context": "transfer",
            "reward_magnitude": "mixed",
            "mag_value": 0,
            "arm_chosen": "left" if rng.random() > 0.5 else "right",
            "reward": 0,
            "correct": True,  # Both have same original p
            "chose_high_magnitude": chose_high,
            "response": "f" if rng.random() > 0.5 else "j",
            "rt": rt,
            "timed_out": False,
        })

    return trials


@pytest.fixture
def magnitude_rl_config():
    return {
        "task_id": "magnitude_rl",
        "parameters": {
            "n_trials": 120,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def magnitude_rl_metrics():
    return {
        "task_id": "magnitude_rl",
        "metrics": [
            {"name": "learning_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False, "phase": "learning"}, "human_mean": 0.68, "human_sd": 0.10},
            {"name": "high_magnitude_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False, "phase": "learning", "reward_magnitude": "high"}, "human_mean": 0.72, "human_sd": 0.10},
            {"name": "transfer_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False, "phase": "transfer"}, "human_mean": 0.65, "human_sd": 0.12},
            {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"timed_out": False, "phase": "learning"}, "human_mean": 700, "human_sd": 200},
        ],
    }


@pytest.fixture
def magnitude_rl_signatures():
    return {
        "task_id": "magnitude_rl",
        "signatures": [
            {
                "name": "magnitude_effect",
                "test": "proportion_test",
                "field": "correct",
                "filter": {"timed_out": False, "phase": "learning", "reward_magnitude": "high"},
                "chance_level": 0.5,
                "threshold_p": 0.05,
                "expected_direction": "above_chance",
                "weight": 1.5,
            },
            {
                "name": "reference_point_adaptation",
                "test": "proportion_test",
                "field": "chose_high_magnitude",
                "filter": {"timed_out": False, "phase": "transfer"},
                "chance_level": 0.5,
                "threshold_p": 0.05,
                "expected_direction": "above_chance",
                "weight": 1.5,
            },
            {
                "name": "learning_improvement",
                "test": "correlation_test",
                "field_x": "trial_index",
                "field_y": "correct",
                "filter": {"timed_out": False, "phase": "learning"},
                "threshold_p": 0.05,
                "expected_direction": "positive",
                "weight": 1.0,
            },
        ],
    }


@pytest.fixture
def human_like_magnitude_rl_data():
    return _generate_magnitude_rl_trials(learning_rate=0.15, magnitude_bonus=0.15)


@pytest.fixture
def random_magnitude_rl_data():
    return _generate_magnitude_rl_trials(learning_rate=0.0, magnitude_bonus=0.0, seed=99)


# ── Probability Learning ─────────────────────────────────────────────


def _generate_probability_learning_trials(
    n_trials=100,
    p_optimal=0.70,
    matching_tendency=0.8,
    win_stay_rate=0.70,
    lose_shift_rate=0.30,
    timeout_rate=0.0,
    seed=42,
):
    """Generate synthetic probability learning data.

    matching_tendency: how closely choice rate matches reward probability.
    1.0 = perfect matching, 0.0 = random, >1 would be maximizing.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []

    optimal_side = "left"
    p_left = p_optimal
    p_right = 1.0 - p_optimal

    prev_choice = None
    prev_reward = None

    for i in range(n_trials):
        timed_out = rng.random() < timeout_rate

        # Pre-determine outcomes
        left_outcome = 1 if rng.random() < p_left else 0
        right_outcome = 1 if rng.random() < p_right else 0

        if timed_out:
            trials.append({
                "trial_index": i + 1,
                "trial_part": "stimulus",
                "choice": None,
                "reward": 0,
                "correct": False,
                "chose_optimal": False,
                "optimal_side": optimal_side,
                "left_outcome": left_outcome,
                "right_outcome": right_outcome,
                "stayed": False,
                "prev_reward": prev_reward,
                "response": None,
                "rt": None,
                "timed_out": True,
            })
            continue

        # Choice model: probability matching with win-stay/lose-shift
        if prev_choice is not None and prev_reward is not None:
            if prev_reward == 1:
                choice = prev_choice if rng.random() < win_stay_rate else ("right" if prev_choice == "left" else "left")
            else:
                choice = ("right" if prev_choice == "left" else "left") if rng.random() < lose_shift_rate else prev_choice
        else:
            # First trial: probability matching
            choice = "left" if rng.random() < (p_optimal * matching_tendency + 0.5 * (1 - matching_tendency)) else "right"

        reward = left_outcome if choice == "left" else right_outcome
        correct = reward == 1
        chose_optimal = choice == optimal_side
        stayed = choice == prev_choice if prev_choice is not None else False

        base_rt = 700 - i * 0.5  # slight speedup over trials
        rt = round(max(200, float(np_rng.normal(base_rt, 150))), 1)

        trials.append({
            "trial_index": i + 1,
            "trial_part": "stimulus",
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
            "rt": rt,
            "timed_out": False,
        })
        prev_choice = choice
        prev_reward = reward

    return trials


@pytest.fixture
def probability_learning_config():
    return {
        "task_id": "probability_learning",
        "parameters": {
            "n_trials": 100,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
        },
    }


@pytest.fixture
def probability_learning_metrics():
    return {
        "task_id": "probability_learning",
        "metrics": [
            {"name": "overall_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.62, "human_sd": 0.08},
            {"name": "optimal_choice_rate", "type": "proportion_correct", "field": "chose_optimal", "filter": {"timed_out": False}, "human_mean": 0.72, "human_sd": 0.12},
            {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"timed_out": False}, "human_mean": 650, "human_sd": 200},
        ],
    }


@pytest.fixture
def probability_learning_signatures():
    return {
        "task_id": "probability_learning",
        "signatures": [
            {
                "name": "probability_matching",
                "test": "proportion_test",
                "field": "chose_optimal",
                "filter": {"timed_out": False},
                "chance_level": 0.5,
                "threshold_p": 0.05,
                "expected_direction": "above_chance",
                "weight": 1.5,
            },
            {
                "name": "win_stay_effect",
                "test": "proportion_test",
                "field": "stayed",
                "filter": {"timed_out": False, "prev_reward": 1},
                "chance_level": 0.5,
                "threshold_p": 0.05,
                "expected_direction": "above_chance",
                "weight": 1.0,
            },
            {
                "name": "learning_curve",
                "test": "correlation_test",
                "field_x": "trial_index",
                "field_y": "chose_optimal",
                "filter": {"timed_out": False},
                "threshold_p": 0.05,
                "expected_direction": "positive",
                "weight": 1.0,
            },
        ],
    }


@pytest.fixture
def human_like_probability_learning_data():
    return _generate_probability_learning_trials(matching_tendency=0.8, win_stay_rate=0.70, lose_shift_rate=0.30)


@pytest.fixture
def random_probability_learning_data():
    return _generate_probability_learning_trials(matching_tendency=0.0, win_stay_rate=0.50, lose_shift_rate=0.50, seed=99)


# ── Novelty Exploration ──────────────────────────────────────────────


def _generate_novelty_exploration_trials(
    n_blocks=10,
    trials_per_block=15,
    novelty_preference=0.55,
    base_reward_prob=0.45,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    trial_idx = 0
    seen = set()

    for b in range(n_blocks):
        for t in range(trials_per_block):
            trial_idx += 1
            timed_out = rng.random() < timeout_rate
            left_id = "opt_%d_%d" % (b, rng.randint(0, 5))
            right_id = "opt_%d_%d" % (b, rng.randint(0, 5))
            while right_id == left_id:
                right_id = "opt_%d_%d" % (b, rng.randint(0, 5))

            left_novel = left_id not in seen
            right_novel = right_id not in seen

            if timed_out:
                trials.append({
                    "trial_index": trial_idx, "trial_part": "stimulus",
                    "block": b, "trial_in_block": t,
                    "chosen_option": None, "chosen_novelty": None,
                    "chose_novel": False, "reward": 0, "correct": False,
                    "response": None, "rt": None, "timed_out": True,
                })
                continue

            # Choose based on novelty preference
            if left_novel and not right_novel:
                choose_left = rng.random() < novelty_preference
            elif right_novel and not left_novel:
                choose_left = rng.random() > novelty_preference
            else:
                choose_left = rng.random() > 0.5

            chosen_id = left_id if choose_left else right_id
            chosen_novel = (left_novel if choose_left else right_novel)
            reward = 1 if rng.random() < base_reward_prob else 0
            seen.add(chosen_id)

            rt = round(max(200, float(np_rng.normal(900, 200))), 1)

            trials.append({
                "trial_index": trial_idx, "trial_part": "stimulus",
                "block": b, "trial_in_block": t,
                "chosen_option": chosen_id,
                "chosen_novelty": "novel" if chosen_novel else "familiar",
                "chose_novel": chosen_novel,
                "reward": reward, "correct": reward == 1,
                "response": "f" if choose_left else "j",
                "rt": rt, "timed_out": False,
            })

    return trials


@pytest.fixture
def novelty_exploration_config():
    return {"task_id": "novelty_exploration", "parameters": {"n_trials": 150, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def novelty_exploration_metrics():
    return {"task_id": "novelty_exploration", "metrics": [
        {"name": "overall_reward_rate", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.55, "human_sd": 0.08},
        {"name": "novel_choice_rate", "type": "proportion_correct", "field": "chose_novel", "filter": {"timed_out": False}, "human_mean": 0.45, "human_sd": 0.12},
        {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"timed_out": False}, "human_mean": 900, "human_sd": 250},
    ]}

@pytest.fixture
def novelty_exploration_signatures():
    return {"task_id": "novelty_exploration", "signatures": [
        {"name": "novelty_bonus", "test": "proportion_test", "field": "chose_novel", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "reward_learning", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
        {"name": "above_chance_reward", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.35, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_novelty_exploration_data():
    return _generate_novelty_exploration_trials(novelty_preference=0.80, base_reward_prob=0.50)

@pytest.fixture
def random_novelty_exploration_data():
    return _generate_novelty_exploration_trials(novelty_preference=0.50, base_reward_prob=0.35, seed=99)


# ── Safe Exploration ─────────────────────────────────────────────────


def _generate_safe_exploration_trials(
    n_blocks=10,
    trials_per_block=10,
    learning_rate=0.15,
    risk_sensitivity=0.2,
    timeout_rate=0.0,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    trial_idx = 0

    for b in range(n_blocks):
        risk_condition = "risky" if b % 2 == 1 else "safe"
        left_mean = 60 + rng.random() * 20 if rng.random() > 0.5 else 20 + rng.random() * 20
        right_mean = 80 - left_mean + 20 + rng.random() * 10
        q_left = 50.0
        q_right = 50.0

        for t in range(trials_per_block):
            trial_idx += 1
            timed_out = rng.random() < timeout_rate

            if timed_out:
                trials.append({
                    "trial_index": trial_idx, "trial_part": "stimulus",
                    "block": b, "trial_in_block": t,
                    "risk_condition": risk_condition,
                    "chosen_option": None, "reward": 0, "correct": False,
                    "kraken_caught": False,
                    "response": None, "rt": None, "timed_out": True,
                })
                continue

            diff = q_left - q_right
            if risk_condition == "risky":
                diff += risk_sensitivity * 10
            p_left = 1.0 / (1.0 + np.exp(-0.05 * diff))
            choose_left = rng.random() < p_left

            side = "left" if choose_left else "right"
            mean = left_mean if choose_left else right_mean
            reward = round(max(0, mean + (rng.random() - 0.5) * 20))
            correct = (left_mean >= right_mean and choose_left) or (right_mean > left_mean and not choose_left)

            kraken = False
            if risk_condition == "risky" and reward < 40 and rng.random() < 0.5:
                kraken = True

            if choose_left:
                q_left += learning_rate * (reward - q_left)
            else:
                q_right += learning_rate * (reward - q_right)

            rt = round(max(200, float(np_rng.normal(800, 200))), 1)

            trials.append({
                "trial_index": trial_idx, "trial_part": "stimulus",
                "block": b, "trial_in_block": t,
                "risk_condition": risk_condition,
                "chosen_option": side, "reward": reward, "correct": correct,
                "kraken_caught": kraken,
                "response": "f" if choose_left else "j",
                "rt": rt, "timed_out": False,
            })

    return trials


@pytest.fixture
def safe_exploration_config():
    return {"task_id": "safe_exploration", "parameters": {"n_trials": 100, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def safe_exploration_metrics():
    return {"task_id": "safe_exploration", "metrics": [
        {"name": "overall_reward", "type": "mean", "field": "reward", "filter": {"timed_out": False}, "human_mean": 50, "human_sd": 15},
        {"name": "optimal_choice_rate", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.65, "human_sd": 0.10},
        {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"timed_out": False}, "human_mean": 800, "human_sd": 250},
    ]}

@pytest.fixture
def safe_exploration_signatures():
    return {"task_id": "safe_exploration", "signatures": [
        {"name": "risk_sensitivity", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False, "risk_condition": "risky"}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "exploration_learning", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
        {"name": "above_chance_performance", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_safe_exploration_data():
    return _generate_safe_exploration_trials(learning_rate=0.2, risk_sensitivity=0.3)

@pytest.fixture
def random_safe_exploration_data():
    return _generate_safe_exploration_trials(learning_rate=0.0, risk_sensitivity=0.0, seed=99)


# ── Observe or Bet ───────────────────────────────────────────────────


def _generate_observe_or_bet_trials(
    n_blocks=3,
    trials_per_block=None,
    observation_rate=0.30,
    learning_speed=0.02,
    timeout_rate=0.0,
    seed=42,
):
    if trials_per_block is None:
        trials_per_block = [25, 50, 50]
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    trial_idx = 0
    block_probs = [0.70, 0.30, 0.80]

    for b in range(n_blocks):
        p_blue = block_probs[b]
        obs_rate = observation_rate

        for t in range(trials_per_block[b]):
            trial_idx += 1
            timed_out = rng.random() < timeout_rate
            light_color = "blue" if rng.random() < p_blue else "red"
            is_practice = b == 0

            if timed_out:
                trials.append({
                    "trial_index": trial_idx, "trial_part": "stimulus",
                    "block": b, "trial_in_block": t, "is_practice": is_practice,
                    "action": "timeout", "light_color": light_color,
                    "reward": 0, "correct": False,
                    "is_observe": False, "is_observe_num": 0, "is_bet": False,
                    "response": None, "rt": None, "timed_out": True,
                })
                continue

            # Decrease observation over trials
            current_obs = max(0.05, obs_rate - learning_speed * t)

            if rng.random() < current_obs:
                action = "observe"
                reward = 0
                correct = False
                is_observe = True
                is_bet = False
            else:
                # Bet on majority color (learned from observations)
                if p_blue > 0.5:
                    guess_blue = rng.random() < (0.5 + 0.3 * min(1, t / 20))
                else:
                    guess_blue = rng.random() < (0.5 - 0.3 * min(1, t / 20))

                if guess_blue:
                    action = "guess_blue"
                    correct = light_color == "blue"
                else:
                    action = "guess_red"
                    correct = light_color == "red"
                reward = 1 if correct else -1
                is_observe = False
                is_bet = True

            rt = round(max(200, float(np_rng.normal(1200, 300))), 1)

            trials.append({
                "trial_index": trial_idx, "trial_part": "stimulus",
                "block": b, "trial_in_block": t, "is_practice": is_practice,
                "action": action, "light_color": light_color,
                "reward": reward, "correct": correct,
                "is_observe": is_observe, "is_observe_num": 1 if is_observe else 0,
                "is_bet": is_bet,
                "response": "k" if is_observe else ("f" if action == "guess_blue" else "j"),
                "rt": rt, "timed_out": False,
            })

    return trials


@pytest.fixture
def observe_or_bet_config():
    return {"task_id": "observe_or_bet", "parameters": {"n_trials": 125, "response_keys": ["f", "j", "k"], "response_type": "keypress"}}

@pytest.fixture
def observe_or_bet_metrics():
    return {"task_id": "observe_or_bet", "metrics": [
        {"name": "observation_rate", "type": "proportion_correct", "field": "is_observe", "filter": {"timed_out": False}, "human_mean": 0.30, "human_sd": 0.12},
        {"name": "bet_accuracy", "type": "proportion_correct", "field": "correct", "filter": {"timed_out": False, "is_bet": True}, "human_mean": 0.70, "human_sd": 0.10},
        {"name": "mean_rt", "type": "mean", "field": "rt", "filter": {"timed_out": False}, "human_mean": 1200, "human_sd": 400},
    ]}

@pytest.fixture
def observe_or_bet_signatures():
    return {"task_id": "observe_or_bet", "signatures": [
        {"name": "adaptive_observation", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "is_observe_num", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "negative", "weight": 1.5},
        {"name": "bet_above_chance", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False, "is_bet": True}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
        {"name": "information_use", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "correct", "filter": {"timed_out": False, "is_bet": True}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_observe_or_bet_data():
    return _generate_observe_or_bet_trials(observation_rate=0.35, learning_speed=0.03)

@pytest.fixture
def random_observe_or_bet_data():
    return _generate_observe_or_bet_trials(observation_rate=0.33, learning_speed=0.0, seed=99)


# ---------- Random Dot Motion ----------

def _generate_random_dot_motion_trials(
    n_trials=120,
    accuracy_easy=0.90,
    accuracy_hard=0.60,
    mean_rt=850,
    rt_ratio_effect=-200,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    conditions = ["easy", "medium", "hard"]
    ratios = {"easy": [1.8, 2.0], "medium": [1.4, 1.5], "hard": [1.1, 1.2]}
    accuracy_map = {"easy": accuracy_easy, "medium": (accuracy_easy + accuracy_hard) / 2, "hard": accuracy_hard}

    trials = []
    for i in range(n_trials):
        condition = conditions[i % 3]
        ratio = rng.choice(ratios[condition])
        base_dots = rng.randint(10, 30)
        n_left = base_dots
        n_right = round(base_dots * ratio)
        correct_side = "right"
        correct_key = "j"

        if rng.random() < 0.5:
            n_left, n_right = n_right, n_left
            correct_side = "left"
            correct_key = "f"

        acc = accuracy_map[condition]
        is_correct = rng.random() < acc
        response = correct_key if is_correct else ("f" if correct_key == "j" else "j")

        base_rt = mean_rt + rt_ratio_effect * (ratio - 1.0)
        rt = max(200, float(np_rng.normal(base_rt, 150)))

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "condition": condition,
            "n_left": n_left,
            "n_right": n_right,
            "ratio": ratio,
            "correct_side": correct_side,
            "correct": is_correct,
            "response": response,
            "rt": round(rt, 1),
            "timed_out": False,
        })

    return trials


@pytest.fixture
def random_dot_motion_config():
    return {"task_id": "random_dot_motion", "parameters": {"n_trials": 120, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def random_dot_motion_metrics():
    return {"task_id": "random_dot_motion", "metrics": [
        {"name": "overall_accuracy", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.78, "human_sd": 0.08},
        {"name": "easy_accuracy", "field": "correct", "filter": {"timed_out": False, "condition": "easy"}, "human_mean": 0.92, "human_sd": 0.05},
        {"name": "hard_accuracy", "field": "correct", "filter": {"timed_out": False, "condition": "hard"}, "human_mean": 0.62, "human_sd": 0.10},
        {"name": "mean_rt", "field": "rt", "filter": {"timed_out": False, "correct": True}, "human_mean": 850, "human_sd": 180},
    ]}

@pytest.fixture
def random_dot_motion_signatures():
    return {"task_id": "random_dot_motion", "signatures": [
        {"name": "ratio_accuracy_effect", "test": "correlation_test", "field_x": "ratio", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.5},
        {"name": "above_chance_accuracy", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
        {"name": "speed_accuracy_tradeoff", "test": "correlation_test", "field_x": "ratio", "field_y": "rt", "filter": {"timed_out": False, "correct": True}, "threshold_p": 0.05, "expected_direction": "negative", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_random_dot_motion_data():
    return _generate_random_dot_motion_trials(accuracy_easy=0.90, accuracy_hard=0.60, rt_ratio_effect=-200)

@pytest.fixture
def random_random_dot_motion_data():
    return _generate_random_dot_motion_trials(accuracy_easy=0.50, accuracy_hard=0.50, rt_ratio_effect=0, seed=99)


# ---------- Lexical Decision ----------

def _generate_lexical_decision_trials(
    n_trials=120,
    word_accuracy=0.95,
    nonword_accuracy=0.92,
    high_freq_rt=550,
    low_freq_rt=650,
    nonword_rt=700,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    high_words = ["table", "house", "water", "money", "light", "world", "place", "think"]
    low_words = ["plumb", "glyph", "trove", "fjord", "knoll", "qualm", "girth", "demur"]
    nonwords = ["flirp", "glomb", "snarp", "brive", "clunt", "drafe", "spalk", "trund"]

    trials = []
    half = n_trials // 2
    word_trials = half // 2

    for i in range(n_trials):
        if i < word_trials:
            stimulus = high_words[i % len(high_words)]
            stimulus_type = "word"
            word_frequency = "high"
            acc = word_accuracy
            base_rt = high_freq_rt
        elif i < half:
            stimulus = low_words[(i - word_trials) % len(low_words)]
            stimulus_type = "word"
            word_frequency = "low"
            acc = word_accuracy * 0.95
            base_rt = low_freq_rt
        else:
            stimulus = nonwords[(i - half) % len(nonwords)]
            stimulus_type = "nonword"
            word_frequency = "none"
            acc = nonword_accuracy
            base_rt = nonword_rt

        is_correct = rng.random() < acc
        if stimulus_type == "word":
            correct_key = "f"
        else:
            correct_key = "j"
        response = correct_key if is_correct else ("f" if correct_key == "j" else "j")
        rt = max(200, float(np_rng.normal(base_rt, 100)))

        trials.append({
            "trial_part": "stimulus",
            "trial_index": i + 1,
            "stimulus": stimulus,
            "stimulus_type": stimulus_type,
            "word_frequency": word_frequency,
            "correct": is_correct,
            "response": response,
            "rt": round(rt, 1),
            "timed_out": False,
        })

    rng2 = random.Random(seed + 1)
    for m in range(len(trials) - 1, 0, -1):
        n = rng2.randint(0, m)
        trials[m], trials[n] = trials[n], trials[m]

    return trials


@pytest.fixture
def lexical_decision_config():
    return {"task_id": "lexical_decision", "parameters": {"n_trials": 120, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def lexical_decision_metrics():
    return {"task_id": "lexical_decision", "metrics": [
        {"name": "overall_accuracy", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.95, "human_sd": 0.03},
        {"name": "word_accuracy", "field": "correct", "filter": {"timed_out": False, "stimulus_type": "word"}, "human_mean": 0.96, "human_sd": 0.03},
        {"name": "nonword_accuracy", "field": "correct", "filter": {"timed_out": False, "stimulus_type": "nonword"}, "human_mean": 0.94, "human_sd": 0.04},
        {"name": "mean_rt", "field": "rt", "filter": {"timed_out": False, "correct": True}, "human_mean": 620, "human_sd": 90},
    ]}

@pytest.fixture
def lexical_decision_signatures():
    return {"task_id": "lexical_decision", "signatures": [
        {"name": "word_frequency_effect", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False, "word_frequency": "high"}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "lexicality_effect", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
        {"name": "nonword_rejection", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False, "stimulus_type": "nonword"}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_lexical_decision_data():
    return _generate_lexical_decision_trials(word_accuracy=0.95, nonword_accuracy=0.92)

@pytest.fixture
def random_lexical_decision_data():
    return _generate_lexical_decision_trials(word_accuracy=0.50, nonword_accuracy=0.50, high_freq_rt=600, low_freq_rt=600, nonword_rt=600, seed=99)


# ---------- Heuristics & Biases ----------

def _generate_heuristics_biases_trials(
    n_trials=40,
    n_tasks=10,
    learning_rate=0.3,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    trials_per_task = n_trials // n_tasks
    trials = []

    for t in range(n_tasks):
        # Generate random weights for this block
        weights = [rng.random() * 2 - 1 for _ in range(4)]
        best_cue = max(range(4), key=lambda c: abs(weights[c]))

        for s in range(trials_per_task):
            cues_a = [rng.randint(10, 90) for _ in range(4)]
            cues_b = [rng.randint(10, 90) for _ in range(4)]

            score_a = sum(w * c for w, c in zip(weights, cues_a)) + rng.gauss(0, 5)
            score_b = sum(w * c for w, c in zip(weights, cues_b)) + rng.gauss(0, 5)
            correct_answer = "f" if score_a > score_b else "j"

            ttb_choice = "f" if (weights[best_cue] > 0) == (cues_a[best_cue] > cues_b[best_cue]) else "j"
            ttb_correct = ttb_choice == correct_answer

            # Accuracy improves within block
            accuracy = 0.5 + learning_rate * (s / max(1, trials_per_task - 1))
            is_correct = rng.random() < accuracy
            response = correct_answer if is_correct else ("f" if correct_answer == "j" else "j")
            used_ttb = (response == correct_answer) == ttb_correct

            cue_diff = [cues_a[i] - cues_b[i] for i in range(4)]
            rt = max(500, float(np_rng.normal(3200, 800)))

            trials.append({
                "trial_part": "stimulus",
                "trial_index": len(trials) + 1,
                "block": t,
                "trial_in_block": s,
                "cue_values": json.dumps(cue_diff),
                "correct_answer": correct_answer,
                "dominant_cue": best_cue,
                "ttb_correct": ttb_correct,
                "correct": is_correct,
                "used_ttb": used_ttb,
                "response": response,
                "rt": round(rt, 1),
                "timed_out": False,
            })

    return trials


@pytest.fixture
def heuristics_biases_config():
    return {"task_id": "heuristics_biases", "parameters": {"n_trials": 40, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def heuristics_biases_metrics():
    return {"task_id": "heuristics_biases", "metrics": [
        {"name": "overall_accuracy", "field": "correct", "filter": {"timed_out": False}, "human_mean": 0.68, "human_sd": 0.10},
        {"name": "late_block_accuracy", "field": "correct", "filter": {"timed_out": False, "trial_in_block": [2, 3]}, "human_mean": 0.75, "human_sd": 0.12},
        {"name": "ttb_usage", "field": "used_ttb", "filter": {"timed_out": False}, "human_mean": 0.55, "human_sd": 0.15},
        {"name": "mean_rt", "field": "rt", "filter": {"timed_out": False}, "human_mean": 3200, "human_sd": 800},
    ]}

@pytest.fixture
def heuristics_biases_signatures():
    return {"task_id": "heuristics_biases", "signatures": [
        {"name": "above_chance_accuracy", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "within_block_learning", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
        {"name": "overall_learning", "test": "correlation_test", "field_x": "block", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_heuristics_biases_data():
    return _generate_heuristics_biases_trials(learning_rate=0.3)

@pytest.fixture
def random_heuristics_biases_data():
    return _generate_heuristics_biases_trials(learning_rate=0.0, seed=99)


# ---------- Phishing Detection ----------

def _generate_phishing_detection_trials(
    n_trials=60,
    phishing_rate=0.3,
    pre_accuracy=0.65,
    train_accuracy=0.80,
    post_accuracy=0.82,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    phases = [("pre", 10), ("train", 40), ("post", 10)]
    acc_map = {"pre": pre_accuracy, "train": train_accuracy, "post": post_accuracy}
    trials = []
    trial_idx = 0

    for phase_name, phase_count in phases:
        for i in range(phase_count):
            trial_idx += 1
            email_type = "phishing" if rng.random() < phishing_rate else "ham"
            acc = acc_map[phase_name]
            # Slight improvement within training
            if phase_name == "train":
                acc = acc + 0.1 * (i / max(1, phase_count - 1))
            is_correct = rng.random() < acc
            if email_type == "phishing":
                correct_key = "j"
            else:
                correct_key = "f"
            response = correct_key if is_correct else ("f" if correct_key == "j" else "j")
            rt = max(500, float(np_rng.normal(5000, 1500)))

            trials.append({
                "trial_part": "stimulus",
                "trial_index": trial_idx,
                "phase": phase_name,
                "email_type": email_type,
                "show_feedback": phase_name == "train",
                "correct": is_correct,
                "response": response,
                "rt": round(rt, 1),
                "timed_out": False,
            })

    return trials


@pytest.fixture
def phishing_detection_config():
    return {"task_id": "phishing_detection", "parameters": {"n_trials": 60, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def phishing_detection_signatures():
    return {"task_id": "phishing_detection", "signatures": [
        {"name": "learning_from_feedback", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False, "phase": "post"}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "above_chance_classification", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
        {"name": "training_improvement", "test": "correlation_test", "field_x": "trial_index", "field_y": "correct", "filter": {"timed_out": False, "phase": "train"}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_phishing_detection_data():
    return _generate_phishing_detection_trials(pre_accuracy=0.65, train_accuracy=0.75, post_accuracy=0.82)

@pytest.fixture
def random_phishing_detection_data():
    return _generate_phishing_detection_trials(pre_accuracy=0.50, train_accuracy=0.50, post_accuracy=0.50, seed=99)


# ---------- Causal Reasoning ----------

def _generate_causal_reasoning_trials(
    n_trials=150,
    n_blocks=3,
    learning_rate=0.15,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    conditions = ["robber", "millionaire", "sheriff"]
    rng_cond = random.Random(seed + 100)
    rng_cond.shuffle(conditions)

    trials_per_block = n_trials // n_blocks
    mine_probs = [0.7, 0.3]
    trials = []

    for b in range(n_blocks):
        cond = conditions[b]
        # Track learned preference for mine A
        pref_a = 0.5

        for t in range(trials_per_block):
            agent_active = rng.random() < 0.3

            mine_a_gold = rng.random() < mine_probs[0]
            mine_b_gold = rng.random() < mine_probs[1]

            if agent_active:
                if cond == "robber":
                    mine_a_gold = False
                    mine_b_gold = False
                elif cond == "millionaire":
                    mine_a_gold = True
                    mine_b_gold = True
                else:
                    mine_a_gold, mine_b_gold = mine_b_gold, mine_a_gold

            # Learning: increase pref for mine A over trials
            pref_a = 0.5 + learning_rate * (t / max(1, trials_per_block - 1))
            chose_a = rng.random() < pref_a
            choice = "A" if chose_a else "B"
            feedback = mine_a_gold if chose_a else mine_b_gold

            rt = max(300, float(np_rng.normal(1500, 400)))

            trials.append({
                "trial_part": "stimulus",
                "trial_index": len(trials) + 1,
                "block": b,
                "condition": cond,
                "trial_in_block": t,
                "agent_active": agent_active,
                "mine_a_gold": mine_a_gold,
                "mine_b_gold": mine_b_gold,
                "choice": choice,
                "feedback": feedback,
                "correct": feedback,
                "chose_better_mine": chose_a,
                "response": "f" if chose_a else "j",
                "rt": round(rt, 1),
                "timed_out": False,
            })

    return trials


@pytest.fixture
def causal_reasoning_config():
    return {"task_id": "causal_reasoning", "parameters": {"n_trials": 150, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def causal_reasoning_signatures():
    return {"task_id": "causal_reasoning", "signatures": [
        {"name": "mine_preference_learning", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "chose_better_mine", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.5},
        {"name": "above_chance_mine_selection", "test": "proportion_test", "field": "chose_better_mine", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
        {"name": "reward_learning", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_causal_reasoning_data():
    return _generate_causal_reasoning_trials(learning_rate=0.15)

@pytest.fixture
def random_causal_reasoning_data():
    return _generate_causal_reasoning_trials(learning_rate=0.0, seed=99)


# ---------- Insider Attack ----------

def _generate_insider_attack_trials(
    n_trials=100,
    n_rounds=4,
    ev_sensitivity=0.6,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    trials_per_round = n_trials // n_rounds
    trials = []

    for r in range(n_rounds):
        for t in range(trials_per_round):
            # Generate two targets
            left_reward = rng.randint(2, 9)
            left_penalty = -rng.randint(1, 8)
            left_mprob = round(rng.random() * 0.55 + 0.05, 2)
            right_reward = rng.randint(2, 9)
            right_penalty = -rng.randint(1, 8)
            right_mprob = round(rng.random() * 0.55 + 0.05, 2)

            left_ev = left_reward * (1 - left_mprob) + left_penalty * left_mprob
            right_ev = right_reward * (1 - right_mprob) + right_penalty * right_mprob

            # Choose based on EV sensitivity + learning
            ev_pref = ev_sensitivity + 0.1 * (t / max(1, trials_per_round - 1))
            chose_left = (left_ev >= right_ev and rng.random() < ev_pref) or (left_ev < right_ev and rng.random() > ev_pref)
            chose_higher_ev = (chose_left and left_ev >= right_ev) or (not chose_left and right_ev >= left_ev)

            chosen_mprob = left_mprob if chose_left else right_mprob
            chosen_reward = left_reward if chose_left else right_reward
            chosen_penalty = left_penalty if chose_left else right_penalty

            monitored = rng.random() < chosen_mprob
            reward = chosen_penalty if monitored else chosen_reward
            warning = monitored and rng.random() < 0.7

            rt = max(500, float(np_rng.normal(3000, 800)))

            trials.append({
                "trial_part": "stimulus",
                "trial_index": len(trials) + 1,
                "round": r,
                "trial_in_round": t,
                "left_reward": left_reward,
                "right_reward": right_reward,
                "left_penalty": left_penalty,
                "right_penalty": right_penalty,
                "left_mprob": left_mprob,
                "right_mprob": right_mprob,
                "left_ev": round(left_ev, 2),
                "right_ev": round(right_ev, 2),
                "target": 0 if chose_left else 1,
                "monitored": monitored,
                "warning": warning,
                "reward": reward,
                "correct": not monitored,
                "chose_higher_ev": chose_higher_ev,
                "response": "f" if chose_left else "j",
                "rt": round(rt, 1),
                "timed_out": False,
            })

    return trials


@pytest.fixture
def insider_attack_config():
    return {"task_id": "insider_attack", "parameters": {"n_trials": 100, "response_keys": ["f", "j"], "response_type": "keypress"}}

@pytest.fixture
def insider_attack_signatures():
    return {"task_id": "insider_attack", "signatures": [
        {"name": "ev_maximization", "test": "proportion_test", "field": "chose_higher_ev", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "within_round_learning", "test": "correlation_test", "field_x": "trial_in_round", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
        {"name": "risk_sensitivity", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.5, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_insider_attack_data():
    return _generate_insider_attack_trials(ev_sensitivity=0.6)

@pytest.fixture
def random_insider_attack_data():
    return _generate_insider_attack_trials(ev_sensitivity=0.5, seed=99)


# ---------- Function Estimation ----------

def _generate_function_estimation_trials(
    n_trials=40,
    n_blocks=8,
    base_error=0.15,
    seed=42,
):
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    trials_per_block = n_trials // n_blocks
    func_types = ["linear", "quadratic", "sinusoidal", "exponential"]
    trials = []

    for b in range(n_blocks):
        func_type = func_types[b % len(func_types)]
        a = (rng.random() * 1.5 + 0.5) * (1 if rng.random() < 0.5 else -1)
        bcoeff = rng.random() * 0.4 - 0.2

        for t in range(trials_per_block):
            x_value = round(-0.9 + 1.8 * t / max(1, trials_per_block - 1), 2)
            if func_type == "linear":
                correct_y = a * x_value + bcoeff
            elif func_type == "quadratic":
                correct_y = a * x_value * x_value + bcoeff
            elif func_type == "sinusoidal":
                correct_y = a * math.sin(3 * x_value) + bcoeff
            else:
                correct_y = a * (math.exp(x_value) - 1) + bcoeff
            correct_y = max(-1, min(1, correct_y))
            correct_y = round(correct_y, 2)

            # Estimation with noise, improving within block
            error_scale = base_error * (1 - 0.3 * t / max(1, trials_per_block - 1))
            estimation_noise = rng.gauss(0, error_scale)
            response = correct_y + estimation_noise
            response = max(-1, min(1, round(response, 2)))
            estimation_error = round(abs(response - correct_y), 4)
            is_correct = estimation_error < 0.3

            rt = max(1000, float(np_rng.normal(5000, 1500)))

            trials.append({
                "trial_part": "stimulus",
                "trial_index": len(trials) + 1,
                "block": b,
                "trial_in_block": t,
                "x_value": x_value,
                "correct_y": correct_y,
                "func_type": func_type,
                "response": response,
                "estimation_error": estimation_error,
                "correct": is_correct,
                "rt": round(rt, 1),
                "timed_out": False,
            })

    return trials


@pytest.fixture
def function_estimation_config():
    return {"task_id": "function_estimation", "parameters": {"n_trials": 40, "response_keys": [], "response_type": "slider", "response_field": "response", "slider_range": [-100, 100]}}

@pytest.fixture
def function_estimation_signatures():
    return {"task_id": "function_estimation", "signatures": [
        {"name": "above_chance_estimation", "test": "proportion_test", "field": "correct", "filter": {"timed_out": False}, "chance_level": 0.3, "threshold_p": 0.05, "expected_direction": "above_chance", "weight": 1.5},
        {"name": "within_block_improvement", "test": "correlation_test", "field_x": "trial_in_block", "field_y": "estimation_error", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "negative", "weight": 1.0},
        {"name": "across_block_improvement", "test": "correlation_test", "field_x": "block", "field_y": "correct", "filter": {"timed_out": False}, "threshold_p": 0.05, "expected_direction": "positive", "weight": 1.0},
    ]}

@pytest.fixture
def human_like_function_estimation_data():
    return _generate_function_estimation_trials(base_error=0.15)

@pytest.fixture
def random_function_estimation_data():
    return _generate_function_estimation_trials(base_error=0.5, seed=99)


# ---------- Random Dot Motion v2 (direction discrimination) ----------

def _generate_random_dot_motion_v2_trials(
    n_trials=120,
    coherence_levels=(0.05, 0.10, 0.20, 0.40, 0.80),
    direction_accuracy_slope=1.0,   # >0 means accuracy ramps with coherence
    base_accuracy=0.50,             # accuracy at coherence=0
    rt_coherence_slope=-300,        # >0 means RT increases with coherence (we expect <0)
    base_rt=900,
    timeout_rate=0.0,
    seed=42,
):
    """Generate human-like RDM-direction trial data.

    Per-trial accuracy: clipped(base_accuracy + slope*coherence) -- e.g. with
    base=0.5, slope=0.6, coherence=0.8 yields accuracy ≈ 0.98.
    Per-trial mean RT: base_rt + rt_coherence_slope * coherence.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    directions = ["left", "right"]
    key_map = {"left": "f", "right": "j"}
    per_cell = max(1, n_trials // (len(coherence_levels) * len(directions)))

    trials = []
    for c_idx, coh in enumerate(coherence_levels):
        for d_idx, direction in enumerate(directions):
            for k in range(per_cell):
                if len(trials) >= n_trials:
                    break
                # Accuracy ramps with coherence (asymptotes near 1.0).
                acc = max(0.0, min(0.995, base_accuracy + direction_accuracy_slope * coh / 2.0))
                timed_out = rng.random() < timeout_rate
                if timed_out:
                    response = None
                    is_correct = False
                    rt = None
                else:
                    is_correct = rng.random() < acc
                    response = key_map[direction] if is_correct else key_map["right" if direction == "left" else "left"]
                    rt_mean = base_rt + rt_coherence_slope * coh
                    rt = max(150, float(np_rng.normal(rt_mean, 120)))
                trials.append({
                    "trial_part": "stimulus",
                    "trial_index": len(trials) + 1,
                    "block": (c_idx * len(directions) + d_idx) // 2 + 1,
                    "condition": "low" if coh <= 0.10 else "medium" if coh <= 0.20 else "high",
                    "coherence": coh,
                    "direction": direction,
                    "correct_key": key_map[direction],
                    "response": response,
                    "correct": is_correct,
                    "rt": rt,
                    "timed_out": timed_out,
                })

    rng.shuffle(trials)
    # Renumber trial_index after shuffle.
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1
    return trials


@pytest.fixture
def random_dot_motion_v2_config():
    return {
        "task_id": "random_dot_motion_v2",
        "parameters": {
            "n_trials": 120,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "block", "condition", "coherence", "direction",
                "correct_key", "response", "correct", "rt", "timed_out"
            ],
        },
    }


_RDM_V2_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "random_dot_motion_v2" / "scoring"
)


@pytest.fixture
def random_dot_motion_v2_metrics():
    with open(_RDM_V2_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def random_dot_motion_v2_signatures():
    with open(_RDM_V2_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_random_dot_motion_v2_data():
    return _generate_random_dot_motion_v2_trials(
        direction_accuracy_slope=1.0, base_accuracy=0.50, rt_coherence_slope=-400, base_rt=950,
    )


@pytest.fixture
def random_random_dot_motion_v2_data():
    return _generate_random_dot_motion_v2_trials(
        direction_accuracy_slope=0.0, base_accuracy=0.50, rt_coherence_slope=0, base_rt=850, seed=99,
    )


# ---------- Grid Bandit (Witte safe-vs-risky spatial bandit) ----------

def _generate_grid_bandit_trials(
    n_blocks=11,
    clicks_per_block=10,
    n_safe_blocks=6,
    n_risky_blocks=5,
    grid_size=11,
    kraken_threshold=50,
    high_value_pref=0.7,        # P(click on a tile with z_true>50) for "human-like"
    risky_extra_caution=0.15,   # additional P(z>50) in risky blocks
    exploit_pull=0.5,           # 0=random, 1=always close after high reward
    learning_slope=2.0,         # mean z gain per click position within a block
    seed=42,
):
    """Generate human-like grid_bandit trial data.

    Simulates a smoothed-grid bandit where the agent picks high-value tiles with
    probability `high_value_pref` (boosted by `risky_extra_caution` in risky blocks),
    moves a small distance after a high-reward click ("exploit pull"), and observed
    reward drifts up across the 10 within-block clicks ("learning_slope").
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    conditions = ["safe"] * n_safe_blocks + ["risky"] * n_risky_blocks
    rng.shuffle(conditions)
    trials = []
    trial_index = 0

    for block_idx, condition in enumerate(conditions, start=1):
        env_idx = rng.randint(0, 29)
        block_pref = high_value_pref + (risky_extra_caution if condition == "risky" else 0.0)
        block_pref = max(0.0, min(0.99, block_pref))

        last_x, last_y, last_z = None, None, None
        running_reward = 0
        for click_idx in range(1, clicks_per_block + 1):
            picks_high = rng.random() < block_pref
            # z_true: high-value tile yields ~65 +/- 12; low-value ~35 +/- 12.
            if picks_high:
                z_true = max(0, min(100, int(np_rng.normal(70, 10))))
            else:
                z_true = max(0, min(100, int(np_rng.normal(35, 10))))
            # Within-block learning bumps the mean of z up over click_idx.
            z_obs = max(0, min(100, int(z_true + learning_slope * (click_idx - 1) + np_rng.normal(0, 1))))

            # Position: if last reward was high and exploit_pull is on, place closer.
            if last_x is not None and last_z is not None and last_z > 50 and rng.random() < exploit_pull:
                dx = rng.choice([-1, 0, 1])
                dy = rng.choice([-1, 0, 1])
                x = max(0, min(grid_size - 1, last_x + dx))
                y = max(0, min(grid_size - 1, last_y + dy))
            else:
                x = rng.randrange(grid_size)
                y = rng.randrange(grid_size)
            distance = None
            if last_x is not None:
                distance = float(((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5)

            kraken_caught = (condition == "risky" and z_true <= kraken_threshold)
            running_reward = 0 if kraken_caught else running_reward + z_obs

            trial_index += 1
            trials.append({
                "trial_part": "click",
                "trial_index": trial_index,
                "block": block_idx,
                "click_in_block": click_idx,
                "block_condition": condition,
                "env_idx": env_idx,
                "x": x, "y": y,
                "z": z_obs,
                "z_true": z_true,
                "z_above_50": z_obs > 50,
                "previous_z": last_z,
                "distance_from_last": distance,
                "is_repeat_tile": False,
                "kraken_caught": kraken_caught,
                "timed_out": False,
                "rt": float(np_rng.uniform(800, 2000)),
            })
            last_x, last_y, last_z = x, y, z_obs

    return trials


_GRID_BANDIT_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "grid_bandit" / "scoring"
)


@pytest.fixture
def grid_bandit_config():
    return {
        "task_id": "grid_bandit",
        "parameters": {
            "n_trials": 110,
            "response_keys": [],
            "response_type": "button",
            "required_fields": [
                "trial_index", "block", "click_in_block", "block_condition",
                "env_idx", "x", "y", "z", "z_true", "previous_z",
                "distance_from_last", "is_repeat_tile", "kraken_caught", "rt",
            ],
        },
    }


@pytest.fixture
def grid_bandit_metrics():
    with open(_GRID_BANDIT_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def grid_bandit_signatures():
    with open(_GRID_BANDIT_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_grid_bandit_data():
    return _generate_grid_bandit_trials(
        high_value_pref=0.7, risky_extra_caution=0.15, exploit_pull=0.6, learning_slope=2.0,
    )


@pytest.fixture
def random_grid_bandit_data():
    return _generate_grid_bandit_trials(
        high_value_pref=0.5, risky_extra_caution=0.0, exploit_pull=0.0, learning_slope=0.0, seed=99,
    )


# ---------- Repeated Games (PD + BoS, Akata 2023) ----------

_REPEATED_GAMES_PAYOFFS = {
    "pd":  {"FF": (5, 5),  "FJ": (10, 0), "JF": (0, 10), "JJ": (8, 8)},
    "bos": {"FF": (10, 7), "FJ": (0, 0),  "JF": (0, 0),  "JJ": (7, 10)},
}


def _bot_move_repeated(game, player_hist, opp_hist):
    if game == "pd":
        # Tit-for-tat: cooperate (J) first, then mirror.
        return "j" if not player_hist else player_hist[-1]
    if game == "bos":
        # Alternation starting with F.
        return "f" if len(opp_hist) % 2 == 0 else "j"
    return "j"


def _generate_repeated_games_trials(
    rounds_per_game=15,
    coop_prob_pd=0.6,         # P(cooperate) when no reciprocity signal
    reciprocity_strength=0.5, # additive boost to coop_prob when opp cooperated last
    bos_match_prob=0.7,       # P(player picks the action the bot will pick this round)
    timeout_rate=0.0,
    game_order=("pd", "bos"),
    seed=42,
):
    """Simulate human-like repeated-games trials.

    For PD: player cooperates with probability `coop_prob_pd`, boosted by
    `reciprocity_strength` if the bot cooperated last round.
    For BoS: player matches the bot's known alternation pattern with
    probability `bos_match_prob` (perfect coordinator at 1.0).
    """
    rng = random.Random(seed)
    trials = []
    trial_index = 0

    for block_order, game in enumerate(game_order, start=1):
        player_hist = []
        opp_hist = []
        for r in range(1, rounds_per_game + 1):
            timed_out = rng.random() < timeout_rate

            if not timed_out:
                if game == "pd":
                    p_coop = coop_prob_pd
                    if opp_hist and opp_hist[-1] == "j":
                        p_coop = min(0.99, p_coop + reciprocity_strength)
                    elif opp_hist and opp_hist[-1] == "f":
                        p_coop = max(0.0, p_coop - reciprocity_strength)
                    pa = "j" if rng.random() < p_coop else "f"
                else:  # bos
                    bot_next = _bot_move_repeated("bos", player_hist, opp_hist)
                    pa = bot_next if rng.random() < bos_match_prob else ("f" if bot_next == "j" else "j")
            else:
                pa = rng.choice(["f", "j"])

            oa = _bot_move_repeated(game, player_hist, opp_hist)
            po = _REPEATED_GAMES_PAYOFFS[game][pa.upper() + oa.upper()]

            prev_opp_coop_pd = None
            if game == "pd" and opp_hist:
                prev_opp_coop_pd = (opp_hist[-1] == "j")

            trial_index += 1
            trials.append({
                "trial_part": "round",
                "trial_index": trial_index,
                "game": game,
                "block_order": block_order,
                "round": r,
                "player_action": pa,
                "opponent_action": oa,
                "player_cooperate": (pa == "j") if game == "pd" else None,
                "opponent_cooperate": (oa == "j") if game == "pd" else None,
                "prev_opp_coop_pd": prev_opp_coop_pd,
                "coordinated": (pa == oa) if game == "bos" else None,
                "player_payoff": po[0],
                "opponent_payoff": po[1],
                "rt": float(rng.uniform(800, 2500)),
                "timed_out": timed_out,
            })
            player_hist.append(pa)
            opp_hist.append(oa)

    return trials


_REPEATED_GAMES_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "repeated_games" / "scoring"
)


@pytest.fixture
def repeated_games_config():
    return {
        "task_id": "repeated_games",
        "parameters": {
            "n_trials": 30,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "game", "block_order", "round",
                "player_action", "opponent_action",
                "player_cooperate", "opponent_cooperate",
                "prev_opp_coop_pd", "coordinated",
                "player_payoff", "opponent_payoff",
                "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def repeated_games_metrics():
    with open(_REPEATED_GAMES_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def repeated_games_signatures():
    with open(_REPEATED_GAMES_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_repeated_games_data():
    # `coop_prob_pd=0.5, reciprocity_strength=0.3` keeps cooperation around 0.5 with
    # enough swing in both directions for the prev_opp_coop_pd predictor to have
    # meaningful variance across the 9 PD rounds where it's defined (rounds 2-10).
    return _generate_repeated_games_trials(
        coop_prob_pd=0.5, reciprocity_strength=0.3, bos_match_prob=0.75,
    )


@pytest.fixture
def random_repeated_games_data():
    return _generate_repeated_games_trials(
        coop_prob_pd=0.5, reciprocity_strength=0.0, bos_match_prob=0.5, seed=99,
    )


# ---------- Marbles (Risky Choice from Description) ----------

def _generate_marbles_risk_trials(
    n_repetitions=4,
    safe_value=5,
    probabilities=(0.125, 0.25, 0.375, 0.5, 0.675, 0.75),
    gamble_values=(8, 20, 50),
    excluded=((0.25, 8), (0.75, 50)),
    risk_aversion=0.6,
    ev_sensitivity=0.6,
    timeout_rate=0.0,
    seed=42,
):
    """Generate human-like Marbles trial data.

    Choice probability follows a logistic with two terms: an EV-sensitivity term
    (slope on ev_diff) and a risk-aversion penalty (subtracted from the risky
    utility). Position is balanced and randomized.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    combos = []
    for p in probabilities:
        for v in gamble_values:
            if any(abs(ex[0] - p) < 1e-9 and ex[1] == v for ex in excluded):
                continue
            combos.append((p, v))
    trials = []
    trial_idx = 0
    for r in range(n_repetitions):
        for p, v in combos:
            ev_risky = p * v
            ev_diff = ev_risky - safe_value
            safe_position = "left" if rng.random() < 0.5 else "right"
            risky_position = "right" if safe_position == "left" else "left"
            has_clear_better = abs(ev_diff) >= 0.05
            near_neutral_ev = abs(ev_diff) <= 1.0
            correct_key_higher_ev = None
            if has_clear_better:
                winning_position = risky_position if ev_diff > 0 else safe_position
                correct_key_higher_ev = "f" if winning_position == "left" else "j"

            slope = 4.0 * ev_sensitivity
            risk_pen = 1.5 * risk_aversion
            logit = slope * ev_diff - risk_pen
            p_risky = 1.0 / (1.0 + np.exp(-logit))
            timed_out = rng.random() < timeout_rate
            if timed_out:
                response = None
                chose_risky = None
                chose_higher_ev = None
                rt = None
            else:
                chose_risky = rng.random() < p_risky
                picked_position = risky_position if chose_risky else safe_position
                response = "f" if picked_position == "left" else "j"
                chose_higher_ev = (response == correct_key_higher_ev) if correct_key_higher_ev else None
                rt = max(200, float(np_rng.normal(2200, 700)))

            trial_idx += 1
            trials.append({
                "trial_part": "stimulus",
                "trial_index": trial_idx,
                "probability": p,
                "gamble_value": v,
                "safe_value": safe_value,
                "ev_risky": ev_risky,
                "ev_diff": ev_diff,
                "safe_position": safe_position,
                "correct_key_higher_ev": correct_key_higher_ev,
                "has_clear_better": has_clear_better,
                "near_neutral_ev": near_neutral_ev,
                "response": response,
                "chose_risky": chose_risky,
                "chose_higher_ev": chose_higher_ev,
                "rt": rt,
                "timed_out": timed_out,
            })
    rng.shuffle(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1
    return trials


_MARBLES_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "marbles_risk" / "scoring"
)


@pytest.fixture
def marbles_risk_config():
    return {
        "task_id": "marbles_risk",
        "parameters": {
            "n_trials": 64,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "probability", "gamble_value", "safe_value",
                "ev_risky", "ev_diff", "safe_position", "correct_key_higher_ev",
                "has_clear_better", "near_neutral_ev",
                "response", "chose_risky", "chose_higher_ev", "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def marbles_risk_metrics():
    with open(_MARBLES_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def marbles_risk_signatures():
    with open(_MARBLES_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_marbles_risk_data():
    return _generate_marbles_risk_trials(risk_aversion=0.6, ev_sensitivity=0.7)


@pytest.fixture
def random_marbles_risk_data():
    return _generate_marbles_risk_trials(risk_aversion=0.0, ev_sensitivity=0.0, seed=99)


# ---------- Moral Machine (autonomous-vehicle dilemmas) ----------

def _generate_moral_machine_trials(
    trials_per_dim=None,
    p_utilitarian=0.78,
    p_save_young=0.72,
    p_save_human=0.85,
    p_save_legal=0.62,
    p_intervention=0.46,
    timeout_rate=0.0,
    seed=42,
):
    """Generate moral_machine trial data.

    For each dimension, the simulated agent picks the canonical-target option
    (the option that matches the canonical human preference) with the
    dimension-specific probability.
    """
    if trials_per_dim is None:
        trials_per_dim = {"number": 10, "age": 10, "species": 10, "legality": 6, "intervention": 4}
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    p_target = {
        "number": p_utilitarian,
        "age": p_save_young,
        "species": p_save_human,
        "legality": p_save_legal,
        # For intervention, target = no_intervention; chose_intervention=True means swerved.
        # So P(chose_target) = 1 - p_intervention.
        "intervention": 1.0 - p_intervention,
    }
    trials = []
    sid = 1
    for dim, n in trials_per_dim.items():
        for _ in range(n):
            timed_out = rng.random() < timeout_rate
            if timed_out:
                chose_target = False
                response = None
            else:
                chose_target = rng.random() < p_target[dim]
                response = "f" if rng.random() < 0.5 else "j"
            target_on_left = rng.random() < 0.5
            chose_side = None if timed_out else ("left" if response == "f" else "right")
            t = {
                "trial_part": "scenario",
                "trial_index": len(trials) + 1,
                "scenario_id": f"scn_{sid}",
                "dimension": dim,
                "side_left_description": "synthetic",
                "side_right_description": "synthetic",
                "side_left_count": 1,
                "side_right_count": 1,
                "side_left_attributes": "synthetic",
                "side_right_attributes": "synthetic",
                "side_left_is_target": target_on_left,
                "side_right_is_target": not target_on_left,
                "chose_side": chose_side,
                "chose_target": chose_target,
                "chose_utilitarian": chose_target if dim == "number" else None,
                "chose_young": chose_target if dim == "age" else None,
                "chose_human": chose_target if dim == "species" else None,
                "chose_legal": chose_target if dim == "legality" else None,
                # Inverse coding: chose_intervention=True means agent swerved (NOT target).
                "chose_intervention": (not chose_target) if dim == "intervention" else None,
                "rt": float(np_rng.uniform(2000, 8000)) if not timed_out else None,
                "timed_out": timed_out,
            }
            trials.append(t)
            sid += 1
    rng.shuffle(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1
    return trials


_MORAL_MACHINE_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "moral_machine" / "scoring"
)


@pytest.fixture
def moral_machine_config():
    return {
        "task_id": "moral_machine",
        "parameters": {
            "n_trials": 40,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "scenario_id", "dimension",
                "side_left_description", "side_right_description",
                "side_left_count", "side_right_count",
                "side_left_attributes", "side_right_attributes",
                "side_left_is_target", "side_right_is_target",
                "chose_side", "chose_target",
                "chose_utilitarian", "chose_young", "chose_human", "chose_legal", "chose_intervention",
                "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def moral_machine_metrics():
    with open(_MORAL_MACHINE_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def moral_machine_signatures():
    with open(_MORAL_MACHINE_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_moral_machine_data():
    return _generate_moral_machine_trials(
        p_utilitarian=0.80, p_save_young=0.75, p_save_human=0.90,
        p_save_legal=0.65, p_intervention=0.40,
    )


@pytest.fixture
def random_moral_machine_data():
    return _generate_moral_machine_trials(
        p_utilitarian=0.50, p_save_young=0.50, p_save_human=0.50,
        p_save_legal=0.50, p_intervention=0.50, seed=99,
    )



# ---------- Tiny Alchemy ----------

def _generate_tiny_alchemy_trials(
    n_attempts=80,
    n_total_elements=540,
    n_initial_inventory=4,
    base_success_rate=0.40,
    empowerment_strength=1.5,
    novelty_decline_strength=0.5,
    success_indegree_scaling=0.6,   # 0=success rate independent of in-degree (random); >0=human-like
    seed=42,
):
    """Generate human-like Tiny Alchemy attempt data.

    Each attempt: pick a pair of inventory elements with probability proportional
    to their in-degree (n_recipes_in). Success rate scales with mean in-degree.
    Novel discovery rate declines as inventory grows.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    inventory = list(range(n_initial_inventory))
    inventory_set = set(inventory)
    attempts = []
    in_degrees = [50, 50, 50, 50] + list(np_rng.lognormal(1.5, 0.8, n_total_elements - 4).round().astype(int))
    in_degrees = [max(1, int(x)) for x in in_degrees]

    for i in range(n_attempts):
        weights = [in_degrees[idx] ** empowerment_strength for idx in inventory]
        a = rng.choices(inventory, weights=weights, k=1)[0]
        b = rng.choices(inventory, weights=weights, k=1)[0]
        if a == b and len(inventory) > 1:
            choices = [x for x in inventory if x != a]
            b = rng.choices(choices, weights=[in_degrees[x] ** empowerment_strength for x in choices], k=1)[0]

        avg_in = (in_degrees[a] + in_degrees[b]) / 2.0
        if success_indegree_scaling > 0:
            logit = np.log(max(0.5, avg_in)) - 1.5
            p_success_raw = 1.0 / (1.0 + np.exp(-logit))
            p_success = base_success_rate + (p_success_raw - base_success_rate) * success_indegree_scaling
        else:
            p_success = base_success_rate
        is_success = rng.random() < p_success

        result_idx = None
        is_novel = False
        if is_success:
            decline_factor = max(0.0, 1.0 - novelty_decline_strength * (i / n_attempts))
            p_novel = 0.7 * decline_factor + 0.1
            is_novel = rng.random() < p_novel
            if is_novel:
                candidates = [x for x in range(n_total_elements) if x not in inventory_set]
                if candidates:
                    result_idx = rng.choice(candidates)
                else:
                    is_novel = False
                    result_idx = rng.choice(list(inventory_set))
            else:
                others = [x for x in inventory if x != a and x != b]
                result_idx = rng.choice(others) if others else a

        sorted_pair = sorted([a, b])
        attempts.append({
            "trial_part": "attempt",
            "trial_index": i + 1,
            "elapsed_time_ms": (i + 1) * 4500 + rng.randint(-500, 500),
            "element_a": f"element_{sorted_pair[0]}",
            "element_b": f"element_{sorted_pair[1]}",
            "element_a_idx": sorted_pair[0],
            "element_b_idx": sorted_pair[1],
            "result": f"element_{result_idx}" if result_idx is not None else None,
            "result_idx": result_idx,
            "is_success": is_success,
            "is_novel_discovery": is_novel,
            "inventory_size_before": len(inventory),
            "inventory_size_after": len(inventory) + (1 if is_novel else 0),
            "a_is_base": sorted_pair[0] < n_initial_inventory,
            "b_is_base": sorted_pair[1] < n_initial_inventory,
            "a_n_recipes_in": in_degrees[sorted_pair[0]],
            "b_n_recipes_in": in_degrees[sorted_pair[1]],
            "mean_input_recipes_in": (in_degrees[sorted_pair[0]] + in_degrees[sorted_pair[1]]) / 2.0,
            "result_n_recipes_in": in_degrees[result_idx] if result_idx is not None else 0,
            "rt": float(rng.uniform(800, 4000)),
            "timed_out": False,
        })
        if is_novel and result_idx is not None:
            inventory.append(result_idx)
            inventory_set.add(result_idx)

    return attempts


_TINY_ALCHEMY_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "tiny_alchemy" / "scoring"
)


@pytest.fixture
def tiny_alchemy_config():
    return {
        "task_id": "tiny_alchemy",
        "parameters": {
            "n_trials": 80,
            "response_keys": [],
            "response_type": "button",
            "required_fields": [
                "trial_index", "elapsed_time_ms",
                "element_a", "element_b",
                "result", "is_success", "is_novel_discovery",
                "inventory_size_before", "inventory_size_after",
                "a_is_base", "b_is_base",
                "a_n_recipes_in", "b_n_recipes_in",
                "mean_input_recipes_in", "result_n_recipes_in",
                "rt",
            ],
        },
    }


@pytest.fixture
def tiny_alchemy_metrics():
    with open(_TINY_ALCHEMY_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def tiny_alchemy_signatures():
    with open(_TINY_ALCHEMY_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_tiny_alchemy_data():
    return _generate_tiny_alchemy_trials(
        n_attempts=100, base_success_rate=0.40, empowerment_strength=1.5, novelty_decline_strength=0.6,
    )


@pytest.fixture
def random_tiny_alchemy_data():
    return _generate_tiny_alchemy_trials(
        n_attempts=100, base_success_rate=0.005,
        empowerment_strength=0.0, novelty_decline_strength=0.0,
        success_indegree_scaling=0.0,
        seed=99,
    )


# ---------- Serial Recall v2 (Haridi cued paired-associate recall, v1 curated) ----------

def _generate_serial_recall_v2_trials(
    similarity_levels=(0.2, 0.4, 0.6, 0.8),
    pairs_per_level=4,
    base_accuracy=0.5,
    similarity_slope=0.6,
    mean_correct_rt=2500,
    mean_incorrect_rt=4500,
    timeout_rate=0.0,
    seed=42,
):
    """Simulate human-like cued-recall trials.

    Per-trial accuracy: clipped(base_accuracy + similarity_slope * similarity_level / 2).
    Correct trials get a faster RT than incorrect ones.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    fake_targets = ["app", "ban", "car", "den", "elm", "fox", "gum", "hat",
                    "ice", "jam", "key", "log", "map", "nut", "oak", "pig",
                    "qui", "rod", "sun", "tar", "urn", "van", "wax", "yam"]
    trials = []
    target_idx = 0
    for sim in similarity_levels:
        for _ in range(pairs_per_level):
            target3 = fake_targets[target_idx % len(fake_targets)]
            target_idx += 1
            target_word = target3 + "ple"
            cue_word = "cue_" + str(target_idx)
            timed_out = rng.random() < timeout_rate
            if timed_out:
                trials.append({
                    "trial_part": "recall",
                    "trial_index": len(trials) + 1,
                    "study_position": len(trials) + 1,
                    "cue_word": cue_word, "target_word": target_word, "similarity_level": sim,
                    "response": "", "response_truncated": "", "target_truncated": target3,
                    "correct": False, "rt": None, "timed_out": True,
                })
                continue
            acc = max(0.01, min(0.99, base_accuracy + similarity_slope * sim / 2.0))
            is_correct = rng.random() < acc
            if is_correct:
                response = target_word
                rt = max(300, float(np_rng.normal(mean_correct_rt, 800)))
            else:
                while True:
                    cand = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(3))
                    if cand != target3:
                        break
                response = cand
                rt = max(300, float(np_rng.normal(mean_incorrect_rt, 1500)))
            response_truncated = response[:3].lower()
            trials.append({
                "trial_part": "recall",
                "trial_index": len(trials) + 1,
                "study_position": len(trials) + 1,
                "cue_word": cue_word, "target_word": target_word, "similarity_level": sim,
                "response": response.lower(),
                "response_truncated": response_truncated,
                "target_truncated": target3,
                "correct": response_truncated == target3,
                "rt": rt, "timed_out": False,
            })
    rng.shuffle(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1
    return trials


_SERIAL_RECALL_V2_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "serial_recall_v2" / "scoring"
)


@pytest.fixture
def serial_recall_v2_config():
    return {
        "task_id": "serial_recall_v2",
        "parameters": {
            "n_trials": 16,
            "response_keys": [],
            "response_type": "text_input",
            "required_fields": [
                "trial_index", "trial_part", "study_position", "cue_word",
                "target_word", "similarity_level", "response", "response_truncated",
                "target_truncated", "correct", "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def serial_recall_v2_metrics():
    with open(_SERIAL_RECALL_V2_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def serial_recall_v2_signatures():
    with open(_SERIAL_RECALL_V2_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_serial_recall_v2_data():
    # seed=1 produces a clean monotonic similarity gradient on the small (16-trial)
    # design, representative of a typical subject who shows the canonical effect.
    return _generate_serial_recall_v2_trials(base_accuracy=0.5, similarity_slope=0.6, seed=1)


@pytest.fixture
def random_serial_recall_v2_data():
    return _generate_serial_recall_v2_trials(base_accuracy=0.0, similarity_slope=0.0, seed=99,
    )



# ---------- Visual Recognition (Brady-style old/new) ----------

def _generate_visual_recognition_trials(
    n_study=50,
    n_lures=50,
    hit_rate=0.92,
    false_alarm_rate=0.08,
    timeout_rate=0.0,
    seed=42,
):
    """Generate test-phase trials only (study trials don't carry signal for L3 here).

    Each test trial: is_old in {True, False}; agent says OLD with prob hit_rate
    (if is_old) or false_alarm_rate (if not_old).
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    items = ([{"is_old": True} for _ in range(n_study)] +
             [{"is_old": False} for _ in range(n_lures)])
    rng.shuffle(items)
    for i, item in enumerate(items, start=1):
        is_old = item["is_old"]
        timed_out = rng.random() < timeout_rate
        if timed_out:
            response = None
            responded_old = None
            is_hit = False
            is_false_alarm = False
            is_miss = is_old
            is_correct_rejection = not is_old
            correct = False
            rt = None
        else:
            p_old = hit_rate if is_old else false_alarm_rate
            responded_old = rng.random() < p_old
            response = "f" if responded_old else "j"
            is_hit = is_old and responded_old
            is_false_alarm = (not is_old) and responded_old
            is_miss = is_old and (not responded_old)
            is_correct_rejection = (not is_old) and (not responded_old)
            correct = is_hit or is_correct_rejection
            rt = max(150, float(np_rng.normal(1100, 350)))
        trials.append({
            "trial_part": "test",
            "phase": "test",
            "trial_index": i,
            "stimulus_id": f"stim_{i}",
            "is_old": is_old,
            "response": response,
            "responded_old": responded_old,
            "is_hit": is_hit,
            "is_false_alarm": is_false_alarm,
            "is_miss": is_miss,
            "is_correct_rejection": is_correct_rejection,
            "correct": correct,
            "rt": rt,
            "timed_out": timed_out,
        })
    return trials


_VISUAL_RECOGNITION_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "visual_recognition" / "scoring"
)


@pytest.fixture
def visual_recognition_config():
    return {
        "task_id": "visual_recognition",
        "parameters": {
            "n_trials": 100,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "phase", "stimulus_id",
                "is_old", "response", "responded_old",
                "is_hit", "is_false_alarm", "is_miss", "is_correct_rejection",
                "correct", "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def visual_recognition_metrics():
    with open(_VISUAL_RECOGNITION_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def visual_recognition_signatures():
    with open(_VISUAL_RECOGNITION_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_visual_recognition_data():
    return _generate_visual_recognition_trials(hit_rate=0.92, false_alarm_rate=0.08)


@pytest.fixture
def random_visual_recognition_data():
    return _generate_visual_recognition_trials(hit_rate=0.5, false_alarm_rate=0.5, seed=99)


# ---------- Effort Foraging (Bustamante 2023 patch foraging, v1 curated) ----------

def _generate_effort_foraging_trials(
    n_blocks=2,
    trials_per_block=40,
    travel_costs=("low_cost", "high_cost"),
    travel_cost_seconds=(4, 8),
    start_reward_mean=70,
    start_reward_sd=6,
    decay_rate_mean=0.88,
    decay_rate_sd=0.04,
    leave_threshold_low=40,
    leave_threshold_high=20,
    timeout_rate=0.0,
    seed=42,
):
    """Simulate human-like effort-foraging trial data with a threshold policy."""
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)
    trials = []
    trial_index = 0
    block_order = list(travel_costs)
    rng.shuffle(block_order)

    for block_idx, condition in enumerate(block_order, start=1):
        cost_seconds = travel_cost_seconds[travel_costs.index(condition)]
        leave_threshold = leave_threshold_low if condition == "low_cost" else leave_threshold_high
        block_total = 0
        block_decisions = 0
        # Use a single-item list to allow mutation from the inner closure.
        patch_id = [0]
        current_reward = [0.0]
        decay_rate = [0.88]
        harvests_so_far_in_patch = [0]

        def start_new_patch():
            patch_id[0] += 1
            current_reward[0] = max(10, min(120, float(np_rng.normal(start_reward_mean, start_reward_sd))))
            decay_rate[0] = max(0.5, min(0.99, float(np_rng.normal(decay_rate_mean, decay_rate_sd))))
            harvests_so_far_in_patch[0] = 0
        start_new_patch()

        for t in range(trials_per_block):
            timed_out = rng.random() < timeout_rate
            pre_avg = block_total / block_decisions if block_decisions > 0 else 0.0
            pre_current_reward = current_reward[0]
            pre_patch_id = patch_id[0]
            pre_harvest_in_patch = harvests_so_far_in_patch[0]
            mvt_optimal_action = "stay" if pre_current_reward >= pre_avg else "leave"

            if timed_out:
                action = "leave"
            else:
                action = "stay" if pre_current_reward >= leave_threshold else "leave"

            harvests_stayed_in_patch = harvests_so_far_in_patch[0]
            if action == "stay":
                harvest_reward = int(round(pre_current_reward))
                block_total += harvest_reward
                current_reward[0] = pre_current_reward * decay_rate[0]
                harvests_so_far_in_patch[0] += 1
            else:
                harvest_reward = 0
                start_new_patch()
            block_decisions += 1
            trial_index += 1

            trials.append({
                "trial_part": "decision",
                "trial_index": trial_index,
                "block": block_idx,
                "block_condition": condition,
                "travel_cost_seconds": cost_seconds,
                "patch_id": pre_patch_id,
                "harvest_in_patch": pre_harvest_in_patch + 1,
                "current_reward_offered": int(round(pre_current_reward)),
                "running_block_avg_per_decision": round(pre_avg, 2),
                "action": action,
                "is_stay": action == "stay",
                "harvest_reward": harvest_reward,
                "harvest_reward_above_chance": harvest_reward > 25,
                "harvests_stayed_in_patch": harvests_stayed_in_patch if action == "leave" else None,
                "mvt_optimal_action": mvt_optimal_action,
                "mvt_optimal_match": action == mvt_optimal_action,
                "rt": float(np_rng.uniform(800, 2500)) if not timed_out else None,
                "timed_out": timed_out,
            })

    return trials


_EFFORT_FORAGING_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "effort_foraging" / "scoring"
)


@pytest.fixture
def effort_foraging_config():
    return {
        "task_id": "effort_foraging",
        "parameters": {
            "n_trials": 80,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "block", "block_condition", "travel_cost_seconds",
                "patch_id", "harvest_in_patch", "current_reward_offered",
                "running_block_avg_per_decision", "action", "is_stay",
                "harvest_reward", "harvest_reward_above_chance",
                "harvests_stayed_in_patch", "mvt_optimal_action", "mvt_optimal_match",
                "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def effort_foraging_metrics():
    with open(_EFFORT_FORAGING_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def effort_foraging_signatures():
    with open(_EFFORT_FORAGING_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_effort_foraging_data():
    return _generate_effort_foraging_trials(
        leave_threshold_low=40, leave_threshold_high=20,
    )


@pytest.fixture
def random_effort_foraging_data():
    rng = random.Random(99)
    trials = _generate_effort_foraging_trials(
        leave_threshold_low=40, leave_threshold_high=20, seed=99,
    )
    # Overwrite the threshold-policy actions with uniform-random choices to
    # simulate a no-policy agent. Re-derive dependent fields.
    for t in trials:
        t["action"] = rng.choice(["stay", "leave"])
        t["is_stay"] = t["action"] == "stay"
        t["mvt_optimal_match"] = t["action"] == t["mvt_optimal_action"]
        if t["action"] == "stay":
            t["harvest_reward"] = t["current_reward_offered"]
            t["harvest_reward_above_chance"] = t["current_reward_offered"] > 25
            t["harvests_stayed_in_patch"] = None
        else:
            t["harvest_reward"] = 0
            t["harvest_reward_above_chance"] = False
            t["harvests_stayed_in_patch"] = rng.randint(0, 4)
    return trials



# ---------- Phishing Detection v2 (Singh 2019) ----------

def _generate_phishing_detection_v2_trials(
    n_pre=10,
    n_training=40,
    n_post=10,
    pre_accuracy=0.62,
    post_accuracy=0.78,
    training_start_acc=0.62,
    training_end_acc=0.78,
    phishing_rate=0.5,
    timeout_rate=0.0,
    seed=42,
):
    """Generate human-like phishing_detection_v2 trial data.

    Pre/post phases: fixed accuracy (pre_accuracy, post_accuracy).
    Training phase: accuracy ramps linearly from training_start_acc to training_end_acc.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    def _phase_trials(phase, n, acc_curve, trial_offset):
        out = []
        for i in range(n):
            is_phishing = rng.random() < phishing_rate
            acc = acc_curve(i, n) if callable(acc_curve) else acc_curve
            timed_out = rng.random() < timeout_rate
            if timed_out:
                response = None
                responded_phishing = None
                is_hit = False
                is_false_alarm = False
                is_miss = is_phishing
                is_correct_rejection = not is_phishing
                correct = False
                rt = None
            else:
                correct = rng.random() < acc
                if correct:
                    responded_phishing = is_phishing
                else:
                    responded_phishing = not is_phishing
                response = "j" if responded_phishing else "f"
                is_hit = is_phishing and responded_phishing
                is_false_alarm = (not is_phishing) and responded_phishing
                is_miss = is_phishing and (not responded_phishing)
                is_correct_rejection = (not is_phishing) and (not responded_phishing)
                rt = max(800, float(np_rng.normal(8000, 4000)))
            out.append({
                "trial_part": "stimulus",
                "trial_index": trial_offset + i + 1,
                "phase": phase,
                "trial_in_phase": i + 1,
                "email_id": 1000 + trial_offset + i,
                "is_phishing": is_phishing,
                "response": response,
                "responded_phishing": responded_phishing,
                "is_hit": is_hit,
                "is_false_alarm": is_false_alarm,
                "is_miss": is_miss,
                "is_correct_rejection": is_correct_rejection,
                "correct": correct,
                "rt": rt,
                "timed_out": timed_out,
            })
        return out

    trials = []
    trials += _phase_trials("pre", n_pre, pre_accuracy, 0)
    trials += _phase_trials(
        "training", n_training,
        lambda i, n: training_start_acc + (training_end_acc - training_start_acc) * (i / max(1, n - 1)),
        n_pre,
    )
    trials += _phase_trials("post", n_post, post_accuracy, n_pre + n_training)
    return trials


_PHISH_V2_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "tasks" / "phishing_detection_v2" / "scoring"
)


@pytest.fixture
def phishing_detection_v2_config():
    return {
        "task_id": "phishing_detection_v2",
        "parameters": {
            "n_trials": 60,
            "response_keys": ["f", "j"],
            "response_type": "keypress",
            "required_fields": [
                "trial_index", "phase", "trial_in_phase",
                "email_id", "is_phishing",
                "response", "responded_phishing",
                "is_hit", "is_false_alarm", "is_miss", "is_correct_rejection",
                "correct", "rt", "timed_out",
            ],
        },
    }


@pytest.fixture
def phishing_detection_v2_metrics():
    with open(_PHISH_V2_DIR / "level2_metrics.json") as f:
        return json.load(f)


@pytest.fixture
def phishing_detection_v2_signatures():
    with open(_PHISH_V2_DIR / "level3_signatures.json") as f:
        return json.load(f)


@pytest.fixture
def human_like_phishing_detection_v2_data():
    return _generate_phishing_detection_v2_trials(
        pre_accuracy=0.62, post_accuracy=0.80, training_start_acc=0.62, training_end_acc=0.80,
    )


@pytest.fixture
def random_phishing_detection_v2_data():
    return _generate_phishing_detection_v2_trials(
        pre_accuracy=0.5, post_accuracy=0.5, training_start_acc=0.5, training_end_acc=0.5, seed=99,
    )
