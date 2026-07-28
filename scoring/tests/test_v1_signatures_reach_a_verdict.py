"""No v1 signature may be unmeasurable across the ENTIRE archive.

The defect this catches is silent and one-directional. ``validate_signatures_spec``
rejects an unknown test name or a missing ``threshold_p``, but nothing rejects a
mistyped ``field`` / ``field_x`` / ``condition_field``. A typo there matches zero
trials, the template reports ``insufficient_data``, the signature drops out of the
L3 denominator, and every score computed against that spec goes UP. A broken spec
looks like a cleaner result.

It cannot be checked while scoring: a truncated session legitimately contains no
trial carrying a field, so a runtime existence check cannot tell a typo from
sparse data. That was tried during v1.2.1 and reverted after firing on 48 real
sessions (see the note in ``analysis_templates/correlation_test.py``).

Nor can it be checked against a single "complete" session, which is the obvious
next idea and does not work either: filters exclude ``timed_out`` trials, so an
agent that timed out on seven of ten moral_machine trials leaves n=3 on a
structurally complete run. That measures the agent, not the spec.

The predicate that does work is over the whole archive:

    a signature whose fields are mistyped can be tested in NO session;
    a signature whose fields are right can be tested in at least one.

So these tests ask, for every v1 signature, whether any archived session anywhere
reached a verdict on it. That is robust to agent behaviour, truncation and
timeouts, and it fails exactly on the defect it is meant to catch.

The archives under ``data/sweeps/`` are gitignored, so this skips on a fresh
clone. It is a guard for the repo where the specs are edited — which is where a
typo would be introduced.

Note ``harness/tests/test_field_alignment.py`` covers this ground for the legacy
tasks with hand-written generators, and covers NONE of the ten v1 tasks.
"""
import glob
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pytest

from harness.task_sets import V1_TASK_IDS
from scoring.analysis_templates import UNDERPOWERED
from scoring.level3_behavioral import score_behavioral
from scoring.score_session import _augment_derived_fields

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP_GLOBS = [
    "data/sweeps/rebuttal_v1_*/runs/*/artifacts/trial_data/{task}.json",
    "data/sweeps/random_floor_v12_*/runs/*/artifacts/trial_data/{task}.json",
]


@lru_cache(maxsize=None)
def _verdicts(task_id):
    """signature name -> set of outcomes seen across every archived session.

    Cached: both tests below need the same answer for the same task, and
    re-scoring the whole archive twice per task was ~19% of the suite's runtime.
    Pure in `task_id` — the result depends only on files on disk.

    Outcomes are "scored", "insufficient_data", "underpowered", or another
    template-declared untestable reason.
    """
    spec = json.loads((REPO_ROOT / "tasks" / task_id / "scoring" /
                       "level3_signatures.json").read_text())
    config = json.loads((REPO_ROOT / "tasks" / task_id / "task_config.json").read_text())

    seen = defaultdict(set)
    n_sessions = 0
    for pattern in SWEEP_GLOBS:
        for path in glob.glob(str(REPO_ROOT / pattern.format(task=task_id))):
            try:
                trials = json.load(open(path))
            except (OSError, ValueError):
                continue
            if isinstance(trials, dict):
                trials = trials.get("trials", [])
            if not trials:
                continue
            n_sessions += 1
            try:
                result = score_behavioral(
                    _augment_derived_fields(list(trials), task_id, config), spec)
            except Exception:  # noqa: BLE001 - a scoring crash is a different test's job
                continue
            for s in result["signatures"]:
                if s.get("testable") is not False:
                    seen[s["name"]].add("scored")
                else:
                    # The template's own reason, not a match on its prose. The
                    # string-matching version of this stopped asserting the
                    # moment anyone reworded a detail message.
                    seen[s["name"]].add(s.get("untestable_reason") or "unknown")
    return seen, n_sessions, tuple(s["name"] for s in spec["signatures"])


@pytest.mark.parametrize("task_id", sorted(V1_TASK_IDS))
def test_every_signature_is_measurable_somewhere(task_id):
    seen, n_sessions, names = _verdicts(task_id)
    if n_sessions == 0:
        pytest.skip(f"no archived sessions for {task_id} under data/sweeps/")

    never = [n for n in names if "scored" not in seen.get(n, set())]
    assert not never, (
        f"{task_id}: {len(never)} signature(s) reached a verdict in NONE of "
        f"{n_sessions} archived sessions: {never}. A mistyped field name looks "
        f"exactly like this, and it silently RAISES L3 by shrinking the "
        f"denominator. Observed outcomes: "
        f"{ {n: sorted(seen.get(n, set())) for n in never} }"
    )


@pytest.mark.parametrize("task_id", sorted(V1_TASK_IDS))
def test_no_signature_is_structurally_unpassable(task_id):
    """The reverse defect: a signature no behaviour could ever pass.

    `moral_machine/intervention_aversion` was exactly this — 4 trials against a
    chance level of 0.5, best attainable exact-binomial p of 0.0625 — and it sat
    in the spec for the whole submitted study, reporting untestable in all 50
    archived sessions. Removed in v1.2.1; this stops another one appearing.

    A signature that is underpowered in SOME sessions is fine: that is a short
    run. One that is underpowered in every session it was ever evaluated on, and
    scored in none, is a design defect.
    """
    seen, n_sessions, names = _verdicts(task_id)
    if n_sessions == 0:
        pytest.skip(f"no archived sessions for {task_id} under data/sweeps/")

    unpassable = [
        n for n in names
        if seen.get(n) and "scored" not in seen[n] and UNDERPOWERED in seen[n]
    ]
    assert not unpassable, (
        f"{task_id}: signature(s) that no behaviour passed in any of {n_sessions} "
        f"archived sessions because the trial allocation cannot reach threshold_p. "
        f"Raise the trial count or remove them: {unpassable}"
    )
