"""Tests for grid_bandit task scoring (Witte safe-vs-risky spatial bandit)."""
import json
from pathlib import Path

from scoring.level1_completion import score_completion
from scoring.level2_accuracy import score_accuracy
from scoring.level3_behavioral import score_behavioral

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks"


def _load_spec(filename):
    with open(TASKS_DIR / "grid_bandit" / "scoring" / filename) as f:
        return json.load(f)


def test_l1_completion_humanlike(human_like_grid_bandit_data, grid_bandit_config):
    result = score_completion(human_like_grid_bandit_data, grid_bandit_config)
    assert result["score"] == 1.0


def test_l1_completion_random(random_grid_bandit_data, grid_bandit_config):
    result = score_completion(random_grid_bandit_data, grid_bandit_config)
    assert result["score"] == 1.0


def test_l2_humanlike_above_chance_reward(human_like_grid_bandit_data):
    metrics = _load_spec("level2_metrics.json")
    result = score_accuracy(human_like_grid_bandit_data, metrics)
    vals = {m["name"]: m["raw_value"] for m in result["metrics"]}
    # Both safe and risky should yield per-click rewards above the random-grid
    # baseline (~50). The relative ordering of safe vs risky depends on whether
    # the agent's caution-boost in risky blocks outweighs the occasional Kraken,
    # so we don't assert a direction here.
    assert vals["mean_reward_per_click"] > 55
    assert vals["mean_reward_safe"] > 55
    assert vals["mean_reward_risky"] > 55
    # Kraken catches happen but should be below chance (~50%).
    assert vals["kraken_caught_rate_risky"] < 0.5


def test_l3_humanlike_recovers_signatures(human_like_grid_bandit_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(human_like_grid_bandit_data, sigs)
    sig_by_name = {s["name"]: s for s in result["signatures"]}
    # Headline: agents avoid the kraken in risky blocks.
    assert sig_by_name["kraken_avoidance_in_risky"]["direction_correct"]
    # Above-chance reward.
    assert sig_by_name["above_chance_reward"]["direction_correct"]
    # Within-block learning.
    assert sig_by_name["within_block_learning"]["direction_correct"]
    # Composite L3 should be substantially above chance.
    assert result["score"] >= 0.6


def test_l3_random_low_score(random_grid_bandit_data):
    sigs = _load_spec("level3_signatures.json")
    result = score_behavioral(random_grid_bandit_data, sigs)
    # A random agent should not consistently fire the directional signatures.
    assert result["score"] <= 0.55


def test_empty_data_l1_zero(grid_bandit_config):
    result = score_completion([], grid_bandit_config)
    assert result["score"] == 0.0
