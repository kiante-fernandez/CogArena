"""What produced a score: the scorer version.

A CogArena score is a function of three things that move independently:

* the scoring **code** (``scoring/*.py``, ``scoring/analysis_templates/*.py``),
* the task **specs** (``tasks/{id}/scoring/level{2,3}_*.json``),
* the human **baselines** (``scoring/human_baselines/{id}.json``).

Versioning only the code would be wrong, and not hypothetically: the July 2026
baseline audit replaced every Level 2 human_mean from the source authors' raw
data without touching a line of scoring code. Runs before and after that audit
produce different numbers from identical behaviour, and a code-only version
string would label them the same — which is precisely the mistake the
leaderboard's version filter exists to prevent.

So the version is ``<series>-<digest>``, e.g. ``1.2-a1b2c3d4e5f6``:

* ``SCORER_SERIES`` is the human-readable part, bumped by hand for headline
  releases. It is what a reader recognises in a dropdown.
* the digest is a content hash over all three inputs, so a spec or baseline edit
  changes the version whether or not anyone remembered to bump the series.

The two together mean a forgotten bump degrades to an ugly-but-correct version
string rather than to two incomparable score sets sharing one label.

JSON inputs are canonicalised (sorted keys, no whitespace) before hashing, so
reformatting a spec does not mint a new version; Python inputs are hashed as raw
bytes, so a docstring edit does. That asymmetry is deliberate: over-splitting
produces a redundant dropdown entry, which is recoverable, while under-splitting
silently blends score sets, which is not.

SCOPE: the digest covers EVERY task carrying a ``scoring/`` directory, not just
the v1 ten. Scoping it to v1 would under-specify the other thirty: they are
scored by the same pipeline, ``scripts/rescore_production.py`` re-scores every
approved session regardless of task, and editing one of their specs would leave
two incomparable score sets sharing a version string — the unrecoverable
direction. Over-splitting merely adds a dropdown entry.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORING_DIR = REPO_ROOT / "scoring"
TASKS_DIR = REPO_ROOT / "tasks"
BASELINES_DIR = SCORING_DIR / "human_baselines"

# Human-readable series. Bump for headline scoring releases; the digest catches
# everything else. Keep this in step with pyproject.toml, croissant.json and
# harness/server.py:APP_VERSION — those four have historically disagreed.
SCORER_SERIES = "1.2.1"

# Rows written before versioning existed. Not a version: it asserts only "we do
# not know what produced this", and must never be compared against a real one.
LEGACY_VERSION = "legacy"


def _canonical_json(path: Path) -> bytes:
    """Stable bytes for a JSON file, insensitive to formatting."""
    raw = path.read_bytes()
    try:
        return json.dumps(json.loads(raw), sort_keys=True,
                          separators=(",", ":")).encode()
    except ValueError:
        # Malformed JSON or bad encoding: hash the raw bytes so the digest still
        # moves rather than silently ignoring the file.
        return raw


def _spec_paths(task_id: str) -> list[Path]:
    return [
        TASKS_DIR / task_id / "scoring" / "level2_metrics.json",
        TASKS_DIR / task_id / "scoring" / "level3_signatures.json",
        BASELINES_DIR / f"{task_id}.json",
    ]


@lru_cache(maxsize=None)
def scorable_tasks() -> tuple[str, ...]:
    """Every task directory carrying a scoring spec, in a stable order."""
    return tuple(sorted(
        d.name for d in TASKS_DIR.iterdir()
        if d.is_dir() and (d / "scoring" / "level3_signatures.json").exists()
    ))


@lru_cache(maxsize=None)
def spec_digest(task_id: str) -> str:
    """12-hex digest of one task's specs and baseline."""
    h = hashlib.sha256()
    for path in _spec_paths(task_id):
        h.update(path.name.encode())
        h.update(_canonical_json(path) if path.exists() else b"<missing>")
    return h.hexdigest()[:12]


@lru_cache(maxsize=None)
def scorer_version() -> str:
    """The version string stamped onto every score this process writes."""
    h = hashlib.sha256()

    # Scoring code, in a stable order.
    code = sorted(
        list(SCORING_DIR.glob("*.py")) + list((SCORING_DIR / "analysis_templates").glob("*.py")),
        key=lambda p: p.relative_to(REPO_ROOT).as_posix(),
    )
    for path in code:
        h.update(path.relative_to(REPO_ROOT).as_posix().encode())
        h.update(path.read_bytes())

    # Specs and baselines for every task the pipeline can score.
    for task_id in scorable_tasks():
        h.update(task_id.encode())
        h.update(spec_digest(task_id).encode())

    return f"{SCORER_SERIES}-{h.hexdigest()[:12]}"


def clear_caches() -> None:
    """Reset both caches together.

    They must be cleared as a pair: ``scorer_version`` folds ``spec_digest``'s
    results in, so clearing only the former rebuilds a version from fresh code
    bytes and stale per-task digests — a wrong answer rather than an error.
    """
    spec_digest.cache_clear()
    scorer_version.cache_clear()
