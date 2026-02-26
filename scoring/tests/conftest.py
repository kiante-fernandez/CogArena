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
    import math
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
        if not any([cue1, cue2, cue3, cue4]):
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
