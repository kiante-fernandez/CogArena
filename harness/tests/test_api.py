"""Integration tests for CogArena API endpoints."""
import json
import random

import pytest
from httpx import AsyncClient, ASGITransport

from harness.server import app, engine
from harness.db.models import Base


@pytest.fixture(autouse=True)
async def reset_db():
    """Create fresh tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_stroop_trials(n=20):
    """Minimal synthetic Stroop data for testing."""
    rng = random.Random(42)
    colors = ["red", "blue", "green", "yellow"]
    key_map = {"red": "d", "blue": "f", "green": "j", "yellow": "k"}
    conditions = ["congruent", "incongruent", "neutral"]
    trials = []
    for i in range(n):
        cond = conditions[i % 3]
        color = colors[i % 4]
        correct_key = key_map[color]
        is_correct = rng.random() < 0.9
        rt = rng.gauss(650 if cond == "congruent" else 730, 100)
        trials.append({
            "trial_index": i + 1, "trial_part": "stimulus", "block": i // 6,
            "condition": cond, "stimulus_word": color.upper(),
            "stimulus_color": color, "correct_key": correct_key,
            "response": correct_key if is_correct else "d", "rt": max(150, rt),
            "correct": is_correct, "timed_out": False,
        })
    return trials


def _make_bandit_trials(n=20):
    rng = random.Random(42)
    trials = []
    for i in range(n):
        horizon = 6 if i < 10 else 1
        arm = rng.choice(["left", "right"])
        correct = arm == "left"
        trials.append({
            "trial_index": i + 1, "trial_part": "stimulus", "game_index": i // 2,
            "horizon": horizon, "trial_in_game": 5, "trial_type": "free",
            "arm_chosen": arm, "reward": rng.gauss(50, 8), "response": "f" if arm == "left" else "j",
            "arm_left_mean": 55, "arm_right_mean": 45, "info_condition": "unequal",
            "more_info_arm": "left", "rt": rng.gauss(800, 200),
            "correct": correct, "timed_out": False,
            "explore_choice": not correct, "chose_less_sampled": arm == "right",
        })
        if i > 0:
            trials[-1]["prev_win"] = trials[-2]["correct"]
            trials[-1]["stayed"] = trials[-1]["arm_chosen"] == trials[-2]["arm_chosen"]
    return trials


def _make_risky_trials(n=20):
    rng = random.Random(42)
    domains = ["gain", "loss", "mixed"]
    trials = []
    for i in range(n):
        domain = domains[i % 3]
        chose_risky = rng.random() < 0.4
        trials.append({
            "trial_index": i + 1, "trial_part": "stimulus", "domain": domain,
            "probability": 0.5, "risky_outcome": 40, "risky_loss": 0,
            "safe_outcome": 18, "ev_risky": 20, "ev_safe": 18,
            "ev_difference": 2, "risky_on_left": True,
            "response": "f" if chose_risky else "j",
            "chose_risky": chose_risky, "chose_safe": not chose_risky,
            "chose_risky_num": 1 if chose_risky else 0,
            "rt": rng.gauss(2500, 500), "timed_out": False,
        })
    return trials


def _make_trust_trials(n=15):
    rng = random.Random(42)
    types = ["cooperative"] * 5 + ["neutral"] * 5 + ["defecting"] * 5
    rng.shuffle(types)
    trials = []
    for i in range(n):
        sent = max(0, min(10, round(rng.gauss(5, 2))))
        tripled = sent * 3
        returned = round(tripled * rng.uniform(0.2, 0.5))
        trials.append({
            "trial_index": i + 1, "trial_part": "stimulus", "round": i + 1,
            "trustee_id": i, "trustee_type": types[i], "endowment": 10,
            "amount_sent": sent, "amount_sent_proportion": sent / 10,
            "sent_nonzero": sent > 0, "tripled_amount": tripled,
            "amount_returned": returned,
            "amount_returned_proportion": returned / tripled if tripled > 0 else 0,
            "net_payoff": (10 - sent) + returned, "response": sent,
            "rt": rng.gauss(4000, 1000), "timed_out": False,
        })
        if i > 0:
            trials[-1]["prev_return_proportion"] = trials[-2]["amount_returned_proportion"]
    return trials


def _make_nback_trials(n=24):
    rng = random.Random(42)
    letters = list("BCDFGHJKLM")
    trials = []
    seq = [rng.choice(letters) for _ in range(n)]
    # Make some targets
    for i in range(2, n):
        if rng.random() < 0.3:
            seq[i] = seq[i - 2]
    for i in range(n):
        stim = seq[i]
        is_target = i >= 2 and stim == seq[i - 2]
        correct = rng.random() < 0.85
        response = "f" if (is_target == correct) else "j" if (is_target and not correct) else ("f" if not correct else "j")
        hit = is_target and response == "f"
        miss = is_target and response == "j"
        fa = not is_target and response == "f"
        cr = not is_target and response == "j"
        trials.append({
            "trial_index": i + 1, "trial_part": "stimulus", "block": 0,
            "stimulus": stim, "n_back_match": is_target, "is_lure": False,
            "response": response, "rt": rng.gauss(550, 100),
            "correct": (is_target and response == "f") or (not is_target and response == "j"),
            "hit": hit, "miss": miss, "false_alarm": fa, "correct_rejection": cr,
            "timed_out": False,
        })
    return trials


TASK_GENERATORS = {
    "stroop": _make_stroop_trials,
    "two_armed_bandit": _make_bandit_trials,
    "risky_choice": _make_risky_trials,
    "trust_game": _make_trust_trials,
    "n_back": _make_nback_trials,
}


# --- Tests ---


async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


async def test_root_html(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_api_info(client: AsyncClient):
    resp = await client.get("/api/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "CogArena"
    assert "stroop" in data["tasks"]
    assert len(data["tasks"]) >= 24


async def test_create_session(client: AsyncClient):
    resp = await client.post("/api/sessions", json={"agent_name": "test-agent", "model_name": "test-model"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "created"
    assert len(data["tasks"]) >= 24
    task_ids = {t["task_id"] for t in data["tasks"]}
    # Core tasks that must always be present
    core_tasks = {
        "stroop", "two_armed_bandit", "risky_choice", "trust_game", "n_back",
        "go_nogo", "flanker", "dictator_game", "iowa_gambling", "reversal_learning",
        "intertemporal_choice", "two_step", "decisions_from_experience",
        "prisoners_dilemma", "probabilistic_classification", "category_learning",
        "restless_bandit", "serial_recall", "ultimatum_game", "public_goods",
        "contingency_judgment", "simple_choice_rt", "bart", "navon",
    }
    assert core_tasks.issubset(task_ids)


async def test_get_session_status(client: AsyncClient):
    # Create session
    resp = await client.post("/api/sessions", json={"agent_name": "test", "model_name": "test-model"})
    session_id = resp.json()["session_id"]

    # Check status — nothing completed
    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert all(not t["completed"] for t in data["tasks"])

    # Submit one task
    trials = _make_stroop_trials()
    resp = await client.post(
        f"/api/data/{session_id}/stroop",
        json={"trial_data": trials, "metadata": {"task_id": "stroop"}},
    )
    assert resp.status_code == 200

    # Check status — stroop completed
    resp = await client.get(f"/api/sessions/{session_id}")
    data = resp.json()
    stroop_task = next(t for t in data["tasks"] if t["task_id"] == "stroop")
    assert stroop_task["completed"] is True
    assert data["status"] == "in_progress"

    non_stroop = [t for t in data["tasks"] if t["task_id"] != "stroop"]
    assert all(not t["completed"] for t in non_stroop)


async def test_submit_data(client: AsyncClient):
    resp = await client.post("/api/sessions", json={"agent_name": "test", "model_name": "test-model"})
    session_id = resp.json()["session_id"]

    trials = _make_stroop_trials()
    resp = await client.post(
        f"/api/data/{session_id}/stroop",
        json={"trial_data": trials},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_duplicate_submission_upserts(client: AsyncClient):
    resp = await client.post("/api/sessions", json={"agent_name": "test", "model_name": "test-model"})
    session_id = resp.json()["session_id"]

    trials = _make_stroop_trials()
    resp1 = await client.post(f"/api/data/{session_id}/stroop", json={"trial_data": trials})
    assert resp1.status_code == 200

    # Second submission succeeds (UPSERT overwrites)
    resp2 = await client.post(f"/api/data/{session_id}/stroop", json={"trial_data": trials})
    assert resp2.status_code == 200


async def test_incremental_save(client: AsyncClient):
    resp = await client.post("/api/sessions", json={"agent_name": "test", "model_name": "test-model"})
    session_id = resp.json()["session_id"]

    # Partial save via PATCH
    partial = _make_stroop_trials()[:5]
    resp = await client.patch(
        f"/api/data/{session_id}/stroop",
        json={"trial_data": partial, "is_complete": False},
    )
    assert resp.status_code == 200
    assert resp.json()["n_trials"] == len(partial)
    assert resp.json()["is_complete"] is False

    # Final save via POST overwrites partial
    full = _make_stroop_trials()
    resp = await client.post(f"/api/data/{session_id}/stroop", json={"trial_data": full})
    assert resp.status_code == 200


async def test_invalid_session(client: AsyncClient):
    resp = await client.get("/api/sessions/nonexistent-id")
    assert resp.status_code == 404

    resp = await client.post(
        "/api/data/nonexistent-id/stroop",
        json={"trial_data": []},
    )
    assert resp.status_code == 400


async def test_full_evaluation_flow(client: AsyncClient):
    # Create session
    resp = await client.post("/api/sessions", json={
        "agent_name": "integration-test",
        "scaffold": "test-scaffold",
        "model_name": "test-model",
    })
    session_id = resp.json()["session_id"]

    # Submit data for all 5 tasks
    for task_id, gen_fn in TASK_GENERATORS.items():
        trials = gen_fn()
        resp = await client.post(
            f"/api/data/{session_id}/{task_id}",
            json={"trial_data": trials, "metadata": {"task_id": task_id}},
        )
        assert resp.status_code == 200, f"Failed to submit {task_id}: {resp.text}"

    # Evaluate
    resp = await client.post(f"/api/evaluate/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "scored"

    # Get results
    resp = await client.get(f"/api/results/{session_id}")
    assert resp.status_code == 200
    results = resp.json()

    assert results["session_id"] == session_id
    assert len(results["task_scores"]) == 5
    assert 0 <= results["composite_score"] <= 100
    assert 0 <= results["l1_overall"] <= 1
    assert 0 <= results["l2_overall"] <= 1
    assert 0 <= results["l3_overall"] <= 1

    scored_task_ids = {ts["task_id"] for ts in results["task_scores"]}
    assert scored_task_ids == {"stroop", "two_armed_bandit", "risky_choice", "trust_game", "n_back"}


async def test_leaderboard_populated(client: AsyncClient):
    # Initially empty
    resp = await client.get("/api/leaderboard")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 0

    # Create and score a session
    resp = await client.post("/api/sessions", json={"agent_name": "lb-test", "model_name": "test-model"})
    session_id = resp.json()["session_id"]

    for task_id, gen_fn in TASK_GENERATORS.items():
        await client.post(
            f"/api/data/{session_id}/{task_id}",
            json={"trial_data": gen_fn()},
        )

    await client.post(f"/api/evaluate/{session_id}")

    # Leaderboard should still be empty (not approved yet)
    resp = await client.get("/api/leaderboard")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 0

    # Approve the session
    await client.post(
        f"/api/admin/submissions/{session_id}/approve",
        headers={"X-Admin-Key": "test-key"},
    )

    # Leaderboard should have one entry now
    resp = await client.get("/api/leaderboard")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["agent_name"] == "lb-test"
    assert entries[0]["tasks_completed"] == 5
    assert 0 <= entries[0]["composite_score"] <= 100
