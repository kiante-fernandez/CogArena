"""Build a self-contained replay.html from a session's artifact bundle.

Reads ``meta.json``, ``interactions.jsonl``, ``actions.jsonl``, ``score.json``
and ``screenshots/<task_id>/*.png`` from a session directory and renders them
into a single-page viewer using the Jinja2 template at
``templates/replay.html.j2``.

Two modes:
* default — image tags reference relative ``screenshots/...`` paths. The HTML
  must ship together with the screenshots directory.
* ``--inline`` — base64-inline every screenshot into the HTML so the file is
  fully self-contained (much larger, but a single-file deliverable).
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("harness.replay")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSONL line in %s", path)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _maybe_inline(rec: dict[str, Any], session_dir: Path, inline: bool) -> dict[str, Any]:
    if not inline:
        return rec
    rel = rec.get("screenshot_path")
    if not rel:
        return rec
    img_path = session_dir / rel
    if not img_path.exists():
        return rec
    try:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        rec = {**rec, "screenshot_data_url": f"data:image/png;base64,{b64}"}
    except OSError as e:
        logger.warning("Could not inline %s: %s", img_path, e)
    return rec


def build_replay_for_session(session_dir: Path, out_path: Path, inline: bool = False) -> Path:
    """Render the replay HTML for one session. Returns the output path."""
    session_dir = Path(session_dir)
    meta = _read_json(session_dir / "meta.json")
    interactions = _read_jsonl(session_dir / "interactions.jsonl")
    actions = _read_jsonl(session_dir / "actions.jsonl")
    score = _read_json(session_dir / "score.json")

    interactions = [_maybe_inline(rec, session_dir, inline) for rec in interactions]

    # Group interactions by task for the per-task accordion in the viewer.
    by_task: dict[str, list[dict[str, Any]]] = {}
    for rec in interactions:
        by_task.setdefault(rec.get("task_id", "?"), []).append(rec)
    task_groups = [{"task_id": tid, "steps": steps} for tid, steps in by_task.items()]

    # Per-task summary: (task_id, n_steps, n_actions, last_action).
    action_counts: dict[str, int] = {}
    for a in actions:
        action_counts[a.get("task_id", "?")] = action_counts.get(a.get("task_id", "?"), 0) + 1
    summary = []
    for grp in task_groups:
        tid = grp["task_id"]
        summary.append({
            "task_id": tid,
            "n_steps": len(grp["steps"]),
            "n_actions": action_counts.get(tid, 0),
        })

    template_path = TEMPLATES_DIR / "replay.html.j2"
    if not template_path.exists():
        raise FileNotFoundError(f"Template missing: {template_path}")

    # Jinja2 is a hard dependency declared in pyproject.toml; no fallback path.
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["json"] = lambda v: json.dumps(v, default=str, indent=2)
    env.filters["short_json"] = lambda v: json.dumps(v, default=str)
    template = env.get_template("replay.html.j2")
    html = template.render(
        meta=meta, score=score, summary=summary, task_groups=task_groups,
        inline=inline, total_interactions=len(interactions),
        total_actions=len(actions),
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
