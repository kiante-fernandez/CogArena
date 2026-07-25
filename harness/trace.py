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

Plus optional ``screenshots/<task_id>/<step:06d>.<ext>`` files. Two paths exist:
``capture_screenshot`` takes a fresh Playwright shot (async), while
``save_screenshot_b64`` persists the already-encoded frame the scaffold handed
to the model. The extension follows the actual bytes (Browser-Use 0.9.5 emits
JPEG). Both skip on failure rather than blocking the agent loop.
"""
from __future__ import annotations

import base64
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

    def save_screenshot_b64(self, b64_image: str | None, task_id: str) -> str | None:
        """Persist an already-encoded screenshot and return its relative path.

        Unlike ``capture_screenshot``, this takes the frame the scaffold already
        handed to the model, so the archive records what the model actually saw
        rather than a re-capture taken at a slightly different moment. Callers
        run inside synchronous step callbacks, hence no Playwright round-trip.

        The extension is chosen from the decoded bytes rather than assumed:
        Browser-Use 0.9.5 hands over JPEG, but that is an implementation detail
        of the scaffold and has changed before.

        Call this *before* ``log_interaction`` so the step numbering lines up.
        Best-effort: returns None on any failure rather than killing the loop.
        """
        if not self.capture_screenshots or not b64_image:
            return None
        try:
            # Tolerate a data: URI wrapper as well as a bare base64 payload.
            if b64_image.startswith("data:"):
                b64_image = b64_image.split(",", 1)[-1]
            raw = base64.b64decode(b64_image)
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                ext = "png"
            elif raw[:3] == b"\xff\xd8\xff":
                ext = "jpg"
            elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                ext = "webp"
            else:
                logger.debug("Unrecognized screenshot format; skipping")
                return None

            sub = self.trace_dir / "screenshots" / task_id
            sub.mkdir(parents=True, exist_ok=True)
            rel = f"screenshots/{task_id}/step_{self._step + 1:06d}.{ext}"
            (self.trace_dir / rel).write_bytes(raw)
            return rel
        except Exception as e:
            logger.debug("Screenshot persist failed: %s", e)
            return None
