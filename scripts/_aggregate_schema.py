"""One canonical shape for the several aggregate CSVs a sweep can produce.

Three writers emit per-run summaries and none of them agree:

* ``harness/sweep.py`` -> ``aggregate.csv``
  ``run_index, repeat_index, model_id, task_id, rc, wall_time, composite, l1, l2, l3``
* ``scripts/rescore_sweeps.py`` -> ``aggregate_audited.csv`` (same shape)
* ``scripts/retry_failed.py`` -> ``aggregate.csv`` in the retry dir, which has
  **no** ``run_index`` and names its outcome columns ``original_rc`` /
  ``retry_rc`` / ``retry_wall_time`` / ``retry_usable``.

Reading a retry sweep with a reader written for the first shape raises
``KeyError: 'run_index'``, which is how this was found. Normalising in one place
means a new writer only has to be taught here.
"""
from __future__ import annotations

from typing import Any

CANONICAL = ["run_index", "repeat_index", "model_id", "task_id",
             "rc", "wall_time", "composite", "l1", "l2", "l3"]


def normalize(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return rows carrying every canonical key, without dropping extras.

    ``run_index`` is positional when absent: it only ever orders rows within one
    sweep, and every consumer matches cells on
    ``(repeat_index, model_id, task_id)``.
    """
    out = []
    for i, row in enumerate(rows):
        r = dict(row)
        r.setdefault("run_index", str(i))
        if not r.get("rc"):
            # retry_rc is the outcome of the attempt this row describes;
            # original_rc records the failure that prompted it and is kept.
            r["rc"] = r.get("retry_rc") or ""
        if not r.get("wall_time"):
            r["wall_time"] = r.get("retry_wall_time") or ""
        for k in CANONICAL:
            r.setdefault(k, "")
        out.append(r)
    return out
