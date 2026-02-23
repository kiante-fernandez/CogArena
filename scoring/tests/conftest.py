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
