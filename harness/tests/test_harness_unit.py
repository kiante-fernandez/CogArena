"""Unit tests for the harness package — model registry, suite expansion,
trace writer, replay builder. No live server, no live model API.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


# ---------- Model registry ----------

def test_load_default_models_yaml():
    from harness.eval import load_model_registry, MODELS_YAML
    registry = load_model_registry(MODELS_YAML)
    assert "random" in registry
    assert "gemini-2.5-flash" in registry
    assert registry["random"].scaffold == "random"
    assert registry["gemini-2.5-flash"].scaffold == "browser-use"
    # Canonical OpenRouter model IDs are bare "provider/model" — the leading
    # "openrouter/" prefix is rejected by the OpenRouter API.
    assert registry["gemini-2.5-flash"].api == "google/gemini-2.5-flash"


def test_resolve_model_random():
    from harness.eval import resolve_model
    m = resolve_model("random")
    assert m.id == "random"
    assert m.scaffold == "random"


def test_resolve_model_passthrough():
    """Bare provider/model strings not in models.yaml should pass through to browser-use."""
    from harness.eval import resolve_model
    m = resolve_model("someprovider/new-model")
    assert m.api == "someprovider/new-model"
    assert m.scaffold == "browser-use"


# ---------- Suite expansion ----------

def _write_suite(tmp_path: Path, content: dict) -> Path:
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump(content))
    return p


def test_expand_runs_basic(tmp_path):
    from harness.sweep import _load_suite, expand_runs
    suite_path = _write_suite(tmp_path, {
        "suite_name": "test",
        "tasks": ["a", "b"],
        "models": [{"id": "m1"}, {"id": "m2"}],
        "repeats": 2,
    })
    suite = _load_suite(suite_path)
    runs = expand_runs(suite, base_port=8000, results_dir=tmp_path / "out")
    assert len(runs) == 2 * 2 * 2  # 2 models * 2 tasks * 2 repeats
    # Wave structure: first 4 runs all repeat 0, next 4 all repeat 1.
    assert all(r.repeat_index == 0 for r in runs[:4])
    assert all(r.repeat_index == 1 for r in runs[4:])
    # Unique ports.
    ports = [r.base_url.rsplit(":", 1)[-1] for r in runs]
    assert len(set(ports)) == len(runs)


def test_expand_runs_respects_filters(tmp_path):
    from harness.sweep import _load_suite, expand_runs
    suite_path = _write_suite(tmp_path, {
        "suite_name": "test",
        "tasks": ["a", "b", "c"],
        "models": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
        "repeats": 1,
    })
    suite = _load_suite(suite_path)
    runs = expand_runs(
        suite, base_port=8000,
        tasks_filter=["a"], models_filter=["m1", "m3"],
        results_dir=tmp_path / "out",
    )
    assert len(runs) == 2  # 2 models * 1 task
    assert {r.model_id for r in runs} == {"m1", "m3"}
    assert {r.task_id for r in runs} == {"a"}


def test_expand_runs_repeats_override(tmp_path):
    from harness.sweep import _load_suite, expand_runs
    suite_path = _write_suite(tmp_path, {
        "suite_name": "test", "tasks": ["a"],
        "models": [{"id": "m1"}], "repeats": 5,
    })
    suite = _load_suite(suite_path)
    runs = expand_runs(suite, base_port=8000, repeats_override=2,
                       results_dir=tmp_path / "out")
    assert len(runs) == 2


# ---------- Trace writer ----------

def test_trace_writer_emits_jsonl(tmp_path):
    from harness.trace import TraceWriter
    with TraceWriter(tmp_path, capture_screenshots=False) as w:
        w.log_interaction(task_id="stroop", state="stimulus",
                          action_proposed={"kind": "press_key", "key": "f"},
                          action_valid=True)
        w.log_action(task_id="stroop", action_kind="press_key", key="f")
        w.log_interaction(task_id="stroop", state="stimulus",
                          action_proposed={"kind": "press_key", "key": "j"},
                          action_valid=True)
    interactions = (tmp_path / "interactions.jsonl").read_text().strip().split("\n")
    actions = (tmp_path / "actions.jsonl").read_text().strip().split("\n")
    assert len(interactions) == 2
    assert len(actions) == 1
    rec = json.loads(interactions[0])
    assert rec["step"] == 1
    assert rec["state"] == "stimulus"
    assert rec["action_proposed"]["key"] == "f"


def test_trace_writer_step_counter_advances(tmp_path):
    from harness.trace import TraceWriter
    w = TraceWriter(tmp_path, capture_screenshots=False)
    for _ in range(5):
        w.log_interaction(task_id="t", state="s")
    w.close()
    assert w.step == 5


# ---------- Replay builder ----------

# ---------- Browser-Use callback wiring ----------

def test_browser_use_step_callback_logs_to_trace_writer(tmp_path):
    """The closure built inside `run_task_with_browser_use` should accept the
    Browser-Use callback signature (browser_state, agent_output, n_steps) and
    write a sensible interaction record + per-action records to the writer.

    We construct the closure by instantiating a tiny stand-in shaped like the
    real builder so the test doesn't need browser-use installed.
    """
    from harness.trace import TraceWriter

    # Stand-ins for AgentOutput and its action items (Pydantic BaseModel-shaped).
    class _FakeAction:
        def __init__(self, payload): self._p = payload
        def model_dump(self, exclude_none=True): return dict(self._p)

    class _FakeCurrentState:
        def model_dump(self, exclude_none=True):
            return {
                "evaluation_previous_goal": "ok",
                "memory": "pressed F twice",
                "next_goal": "press F again",
                "thinking": "long internal monologue we want to drop",
            }

    class _FakeAgentOutput:
        def __init__(self):
            self.action = [_FakeAction({"send_keys": {"keys": "f"}})]
            self.current_state = _FakeCurrentState()

    writer = TraceWriter(tmp_path, capture_screenshots=False)

    # Recreate the callback exactly as agents/browser_use_agent.py builds it.
    task_id = "stroop"
    def step_cb(browser_state, agent_output, n_steps):
        actions = []
        for a in (getattr(agent_output, "action", None) or []):
            actions.append(a.model_dump(exclude_none=True) if hasattr(a, "model_dump") else str(a))
        current = getattr(agent_output, "current_state", None)
        extra = {}
        if current is not None and hasattr(current, "model_dump"):
            cs = current.model_dump(exclude_none=True)
            for k in ("evaluation_previous_goal", "memory", "next_goal"):
                if k in cs:
                    extra[k] = cs[k]
        writer.log_interaction(
            task_id=task_id, state="browser_use_step",
            action_proposed=actions if len(actions) != 1 else actions[0],
            action_valid=True,
            extra={"step": n_steps, **extra},
        )
        for a in actions:
            writer.log_action(
                task_id=task_id,
                action_kind=next(iter(a)) if isinstance(a, dict) and a else "unknown",
                target=None, key=None, ok=True,
            )

    step_cb(browser_state=None, agent_output=_FakeAgentOutput(), n_steps=7)
    writer.close()

    interactions = (tmp_path / "interactions.jsonl").read_text().strip().split("\n")
    actions = (tmp_path / "actions.jsonl").read_text().strip().split("\n")
    assert len(interactions) == 1
    assert len(actions) == 1

    rec = json.loads(interactions[0])
    assert rec["task_id"] == "stroop"
    assert rec["state"] == "browser_use_step"
    assert rec["action_proposed"] == {"send_keys": {"keys": "f"}}
    assert rec["action_valid"] is True
    # Verbose `thinking` field should NOT have been propagated.
    assert "thinking" not in rec["extra"]
    # The summary fields we DO want should be there.
    assert rec["extra"]["memory"] == "pressed F twice"
    assert rec["extra"]["step"] == 7

    act = json.loads(actions[0])
    assert act["action_kind"] == "send_keys"


def test_replay_builder_writes_html(tmp_path):
    from harness.replay import build_replay_for_session

    sdir = tmp_path / "session_abc"
    sdir.mkdir()
    (sdir / "meta.json").write_text(json.dumps({
        "session_id": "abc", "agent_name": "TestAgent",
        "model": {"id": "random", "api": "random", "scaffold": "random"},
        "tasks": ["stroop"],
        "env": {"git_sha": "deadbeef", "git_dirty": False},
    }))
    (sdir / "interactions.jsonl").write_text(
        json.dumps({"step": 1, "task_id": "stroop", "state": "stimulus",
                    "action_proposed": {"kind": "press_key", "key": "f"},
                    "action_valid": True}) + "\n"
    )
    (sdir / "actions.jsonl").write_text("")
    # Match the real /api/results shape: flat top-level fields, plus task_scores list.
    (sdir / "score.json").write_text(json.dumps({
        "session_id": "abc",
        "composite_score": 47.31,
        "l1_overall": 1.0,
        "l2_overall": 0.28,
        "l3_overall": 0.45,
        "task_scores": [
            {"task_id": "stroop", "l1_completion": 1.0, "l2_accuracy": 0.28,
             "l3_behavioral": 0.45, "composite": 47.31, "details": None},
        ],
    }))

    out = sdir / "replay.html"
    build_replay_for_session(sdir, out, inline=False)
    assert out.exists()
    html = out.read_text()
    assert "session_id" not in html or "abc" in html
    assert "stroop" in html
    assert "47.31" in html
