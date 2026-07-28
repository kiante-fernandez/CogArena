"""The scorer version must move when the scores would move.

The regression this guards is concrete: the July 2026 baseline audit replaced
every Level 2 human_mean from the source authors' raw data without touching a
line of scoring code. A code-only version string would have labelled pre- and
post-audit scores identically, and the leaderboard's version selector would then
have offered two incomparable score sets under one name — the exact failure it
exists to prevent.
"""
import json
import re

import pytest

from scoring import version as version_mod
from scoring.version import (SCORER_SERIES, clear_caches, scorable_tasks,
                             scorer_version, spec_digest)


@pytest.fixture(autouse=True)
def _reset_version_caches():
    clear_caches()
    yield
    clear_caches()


def test_version_shape_and_determinism():
    first = scorer_version()
    clear_caches()
    assert first == scorer_version()
    assert re.fullmatch(rf"{re.escape(SCORER_SERIES)}-[0-9a-f]{{12}}", first), first


def test_editing_a_human_baseline_changes_the_version(tmp_path, monkeypatch):
    """The case that a code-only version string would miss."""
    before = scorer_version()

    real = version_mod.TASKS_DIR / "marbles_risk" / "scoring" / "level2_metrics.json"
    spec = json.loads(real.read_text())
    # Perturb whatever the first human_mean is, wherever it lives.
    dumped = json.dumps(spec)
    assert "human_mean" in dumped, "fixture assumption: L2 specs carry human_mean"

    fake_tasks = tmp_path / "tasks"
    (fake_tasks / "marbles_risk" / "scoring").mkdir(parents=True)
    for task_id in version_mod.scorable_tasks():
        src = version_mod.TASKS_DIR / task_id / "scoring"
        dst = fake_tasks / task_id / "scoring"
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("level2_metrics.json", "level3_signatures.json"):
            if (src / name).exists():
                (dst / name).write_text((src / name).read_text())

    mutated = json.loads((fake_tasks / "marbles_risk" / "scoring" / "level2_metrics.json").read_text())
    mutated["_baseline_audit_marker"] = "changed"
    (fake_tasks / "marbles_risk" / "scoring" / "level2_metrics.json").write_text(json.dumps(mutated))

    monkeypatch.setattr(version_mod, "TASKS_DIR", fake_tasks)
    clear_caches()
    scorable_tasks.cache_clear()
    after = scorer_version()

    assert after != before, "a spec/baseline edit must mint a new scorer version"


def test_reformatting_a_spec_does_not_change_the_version(tmp_path, monkeypatch):
    """Whitespace churn must not fill the dropdown with phantom versions."""
    fake_tasks = tmp_path / "tasks"
    for task_id in version_mod.scorable_tasks():
        src = version_mod.TASKS_DIR / task_id / "scoring"
        dst = fake_tasks / task_id / "scoring"
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("level2_metrics.json", "level3_signatures.json"):
            if (src / name).exists():
                (dst / name).write_text((src / name).read_text())

    monkeypatch.setattr(version_mod, "TASKS_DIR", fake_tasks)
    clear_caches(); scorable_tasks.cache_clear()
    before = scorer_version()

    target = fake_tasks / "marbles_risk" / "scoring" / "level2_metrics.json"
    target.write_text(json.dumps(json.loads(target.read_text()), indent=8))

    clear_caches()
    assert scorer_version() == before


def test_spec_digest_is_per_task():
    a = spec_digest("marbles_risk")
    b = spec_digest("grid_bandit")
    assert a != b
    assert re.fullmatch(r"[0-9a-f]{12}", a)


def test_score_task_stamps_provenance():
    from pathlib import Path
    from scoring.score_session import score_task

    trials = [{"trial_part": "stimulus", "timed_out": False} for _ in range(4)]
    result = score_task(trials, "marbles_risk", Path("tasks"))
    assert result["scorer_version"] == scorer_version()
    assert result["spec_digest"] == spec_digest("marbles_risk")
