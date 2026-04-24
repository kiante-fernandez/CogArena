"""Per-step trace logging for agent runs.

Each agent (random or browser-use) optionally takes a ``trace_dir`` argument.
If provided, agent loops construct a ``TraceWriter`` for the trace_dir and
call ``writer.log_step(...)`` after every state-detection-and-action cycle.

The on-disk format is two JSONL files:

* ``interactions.jsonl`` — one line per (state-detection, action-decision) cycle:
  ``{step, ts, task_id, state, action_proposed, action_valid, validity_reason,
     screenshot_path, prompt_chars, response_chars}``
* ``actions.jsonl`` — one line per low-level browser action emitted:
  ``{step, ts, task_id, action_kind, target, key, ok, error}``

Plus optional ``screenshots/<task_id>/<step:06d>.png`` files. Capturing
screenshots is async (Playwright); the writer accepts an already-encoded PNG
or skips on failure rather than blocking the agent loop.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("harness.trace")


@dataclass
class TraceWriter:
    trace_dir: Path
    capture_screenshots: bool = True
    _step: int = 0
    _interactions_fh: Any = field(default=None, init=False, repr=False)
    _actions_fh: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.trace_dir = Path(self.trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        (self.trace_dir / "screenshots").mkdir(exist_ok=True)
        self._interactions_fh = open(self.trace_dir / "interactions.jsonl", "a", buffering=1)
        self._actions_fh = open(self.trace_dir / "actions.jsonl", "a", buffering=1)

    def close(self) -> None:
        for fh in (self._interactions_fh, self._actions_fh):
            try:
                if fh and not fh.closed:
                    fh.close()
            except Exception:
                pass

    def __enter__(self) -> "TraceWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def step(self) -> int:
        return self._step

    def log_interaction(
        self,
        *,
        task_id: str,
        state: str,
        action_proposed: str | dict | None = None,
        action_valid: bool | None = None,
        validity_reason: str | None = None,
        screenshot_path: str | None = None,
        prompt_chars: int | None = None,
        response_chars: int | None = None,
        extra: dict | None = None,
    ) -> int:
        """Log one (observation, decision) cycle. Returns the assigned step number."""
        self._step += 1
        rec = {
            "step": self._step,
            "ts": time.time(),
            "task_id": task_id,
            "state": state,
            "action_proposed": action_proposed,
            "action_valid": action_valid,
            "validity_reason": validity_reason,
            "screenshot_path": screenshot_path,
            "prompt_chars": prompt_chars,
            "response_chars": response_chars,
        }
        if extra:
            rec["extra"] = extra
        self._interactions_fh.write(json.dumps(rec) + "\n")
        return self._step

    def log_action(
        self,
        *,
        task_id: str,
        action_kind: str,
        target: str | None = None,
        key: str | None = None,
        ok: bool = True,
        error: str | None = None,
    ) -> None:
        rec = {
            "step": self._step,
            "ts": time.time(),
            "task_id": task_id,
            "action_kind": action_kind,
            "target": target,
            "key": key,
            "ok": ok,
            "error": error,
        }
        self._actions_fh.write(json.dumps(rec) + "\n")

    async def capture_screenshot(self, page, task_id: str) -> str | None:
        """Capture a screenshot of the current page; return the relative path
        suitable for embedding in interactions.jsonl. Best-effort: returns None
        on any failure rather than killing the agent loop."""
        if not self.capture_screenshots:
            return None
        try:
            sub = self.trace_dir / "screenshots" / task_id
            sub.mkdir(parents=True, exist_ok=True)
            rel = f"screenshots/{task_id}/step_{self._step + 1:06d}.png"
            full = self.trace_dir / rel
            await page.screenshot(path=str(full), full_page=False)
            return rel
        except Exception as e:
            logger.debug("Screenshot capture failed: %s", e)
            return None
