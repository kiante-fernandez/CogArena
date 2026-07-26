"""Single-run evaluation: one model × one or more tasks → one session bundle.

This module wraps the existing ``agents.random_agent.run_all_tasks`` and
``agents.browser_use_agent.run_all_tasks`` functions, adding:

* A predictable on-disk artifact bundle at ``data/sessions/<session_id>/``
  containing meta.json, trial_data.json, score.json, plus (when the agent
  emits them) interactions.jsonl, actions.jsonl, and screenshots/.
* A unified CLI entry point (`python -m harness eval`).
* Optional immediate replay-HTML build via ``--replay``.

The function ``run_eval(args)`` is the entry point called by ``cli.main``.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

logger = logging.getLogger("harness.eval")


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSIONS_ROOT = REPO_ROOT / "data" / "sessions"
MODELS_YAML = Path(__file__).resolve().parent / "models.yaml"


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelEntry:
    id: str                 # short id used in CLI / suite YAML
    api: str                # what we pass to browser-use (e.g. "openrouter/google/gemini-2.5-flash")
    scaffold: str = "browser-use"
    enable_memory: bool = False
    notes: str = ""


def load_model_registry(path: Path = MODELS_YAML) -> dict[str, ModelEntry]:
    """Load the optional ``models.yaml``. Returns an empty dict if absent."""
    if not path.exists():
        return {}
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    out: dict[str, ModelEntry] = {}
    for entry in raw.get("models", []):
        out[entry["id"]] = ModelEntry(
            id=entry["id"],
            api=entry["api"],
            scaffold=entry.get("scaffold", "browser-use"),
            enable_memory=bool(entry.get("enable_memory", False)),
            notes=entry.get("notes", ""),
        )
    return out


def resolve_model(name: str) -> ModelEntry:
    """Resolve a CLI model string to a ModelEntry.

    * "random" → the random-agent baseline (no model API).
    * Any id present in models.yaml → that entry.
    * Anything else → assumed to be a literal model API string passed straight
      through to Browser-Use (provider/model form, e.g. ``openrouter/google/gemini-2.5-flash``).
    """
    if name == "random":
        return ModelEntry(id="random", api="random", scaffold="random")
    registry = load_model_registry()
    if name in registry:
        return registry[name]
    # Fallback: treat as a literal API id.
    return ModelEntry(id=name, api=name, scaffold="browser-use")


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def _wait_for_server(base_url: str, timeout: float = 30.0) -> bool:
    client = httpx.Client(timeout=5.0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = client.get(f"{base_url}/api/health")
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def _start_server_subprocess(base_url: str, server_log: Path | None = None) -> subprocess.Popen:
    port = str(urlparse(base_url).port or 8000)
    logger.info("Starting CogArena server on port %s …", port)
    # Capture server stdout/stderr (uvicorn access logs include /api/data
    # POST/PATCH and /api/evaluate calls — invaluable for debugging agent
    # runs). Without this redirect we cannot see what the browser hit.
    log_fh = None
    if server_log is not None:
        server_log.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(server_log, "w")
        stdout_target = log_fh
        stderr_target = subprocess.STDOUT
    else:
        stdout_target = subprocess.DEVNULL
        stderr_target = subprocess.DEVNULL
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "harness.server:app",
             "--host", "0.0.0.0", "--port", port],
            stdout=stdout_target,
            stderr=stderr_target,
            cwd=str(REPO_ROOT),
        )
        if not _wait_for_server(base_url):
            proc.terminate()
            raise RuntimeError(f"Server failed to start at {base_url}")
    except Exception:
        if log_fh is not None:
            log_fh.close()
        raise
    return proc


# ---------------------------------------------------------------------------
# Artifact bundle
# ---------------------------------------------------------------------------

def session_dir(session_id: str, root: Path | None = None) -> Path:
    base = root or DEFAULT_SESSIONS_ROOT
    out = base / session_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def resolve_session_dir(session_or_path: str) -> Path:
    """Accept either a bare session_id or a path to a session dir."""
    p = Path(session_or_path)
    if p.is_dir():
        return p
    return session_dir(session_or_path)


def _git_sha() -> tuple[str, bool]:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
        ).strip())
        return sha, dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", False


def _resolve_observation_mode(model: "ModelEntry", args) -> str | None:
    """What the model will actually be shown, resolved before the run starts.

    The random agent sees no model input at all. For browser-use, --no-vision
    forces DOM-text-only; otherwise it depends on whether the model accepts
    images. Recording the resolved value means the archive states the modality
    rather than assuming it.
    """
    if model.scaffold == "random":
        return None
    if getattr(args, "no_vision", False):
        return "dom"
    try:
        from agents.browser_use_agent import _model_supports_vision
        return "screenshot" if _model_supports_vision(model.api) else "dom"
    except ImportError:
        return None


def write_meta(
    sdir: Path,
    *,
    session_id: str,
    model: ModelEntry,
    agent_name: str,
    base_url: str,
    tasks: list[str],
    n_trials: int | None,
    use_deadline: bool,
    task_timeout: float,
    observation_mode: str | None = None,
) -> dict[str, Any]:
    git_sha, git_dirty = _git_sha()
    meta = {
        "session_id": session_id,
        "started_at_utc": _dt.datetime.utcnow().isoformat() + "Z",
        "model": {
            "id": model.id,
            "api": model.api,
            "scaffold": model.scaffold,
            "enable_memory": model.enable_memory,
            # Resolved, not assumed: reviewers asked which modality each run
            # actually received, and the answer belongs in the archive.
            "observation_mode": observation_mode,
        },
        "agent_name": agent_name,
        "base_url": base_url,
        "tasks": tasks,
        "n_trials_override": n_trials,
        "use_deadline": use_deadline,
        "task_timeout_seconds": task_timeout,
        "env": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_sha": git_sha,
            "git_dirty": git_dirty,
        },
    }
    with open(sdir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def fetch_trial_data(base_url: str, session_id: str) -> dict[str, Any] | None:
    """Pull the per-task trial JSON from the API after evaluation completes."""
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{base_url}/api/results/{session_id}")
            if r.status_code == 200:
                return r.json()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch results for %s: %s", session_id, e)
    return None


def _attempted_task_ids(
    base_url: str, session_id: str, tasks_filter: list[str] | None
) -> list[str]:
    """Task ids this run tried, whether or not they ended up scoreable.

    Used so partial runs still get their raw data archived. Falls back to an
    empty list on any error: archiving is best-effort and must never take down
    a run that has otherwise finished.
    """
    if tasks_filter:
        return list(tasks_filter)
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{base_url}/api/sessions/{session_id}")
            r.raise_for_status()
            return [t["task_id"] for t in r.json().get("tasks", []) if "task_id" in t]
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        logger.warning("Could not list attempted tasks for %s: %s", session_id, e)
        return []


def fetch_and_save_raw_trial_data(
    base_url: str, session_id: str, task_ids: list[str], out_dir: Path
) -> list[str]:
    """Pull raw jsPsych trial-data for each task and write trial_data/<task_id>.json.

    Returns the list of task_ids successfully saved. The saved files are exactly
    what scoring.score_session expects via --trial-data, so any future scoring
    update can be re-applied without rerunning the agent.
    """
    saved: list[str] = []
    raw_dir = out_dir / "trial_data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60.0) as client:
        for tid in task_ids:
            try:
                r = client.get(f"{base_url}/api/data/{session_id}/{tid}")
                if r.status_code != 200:
                    logger.warning("No raw trial data for %s/%s (HTTP %d)",
                                   session_id, tid, r.status_code)
                    continue
                payload = r.json()
                with open(raw_dir / f"{tid}.json", "w") as f:
                    json.dump(payload["trial_data"], f, indent=2)
                saved.append(tid)
            except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
                logger.warning("Failed to archive raw trial data for %s/%s: %s",
                               session_id, tid, e)
    return saved


# ---------------------------------------------------------------------------
# Eval driver
# ---------------------------------------------------------------------------

def _create_session(base_url: str, agent_name: str, model: ModelEntry) -> str:
    with httpx.Client(timeout=30.0, base_url=base_url) as client:
        r = client.post("/api/sessions", json={
            "agent_name": agent_name,
            "scaffold": model.scaffold,
            "model_name": model.api if model.scaffold != "random" else "none",
            "observation_mode": "dom",
        })
        r.raise_for_status()
        return r.json()["session_id"]


def run_eval(args) -> int:
    """Entry point invoked by ``harness.cli.main`` for the ``eval`` subcommand."""
    model = resolve_model(args.model)
    scaffold = args.scaffold or model.scaffold
    agent_name = args.agent_name or _default_agent_name(model)

    # Decide artifact dir up-front so we can route the server log there too.
    pre_session_log = Path(args.trace_dir) / "server.log" if args.trace_dir else None

    server_proc: subprocess.Popen | None = None
    if args.start_server:
        server_proc = _start_server_subprocess(args.base_url, server_log=pre_session_log)
    elif not _wait_for_server(args.base_url, timeout=5.0):
        logger.error("No server at %s — pass --start-server to launch one.", args.base_url)
        return 1

    try:
        # Create the session up-front so we have a stable ID for the artifact dir.
        session_id = _create_session(args.base_url, agent_name, model)
        logger.info("Session %s | model=%s | scaffold=%s | tasks=%s",
                    session_id, model.id, scaffold, args.tasks)
        sdir = session_dir(session_id) if args.trace_dir is None else Path(args.trace_dir)
        sdir.mkdir(parents=True, exist_ok=True)
        write_meta(
            sdir, session_id=session_id, model=model, agent_name=agent_name,
            base_url=args.base_url, tasks=args.tasks, n_trials=args.n_trials,
            use_deadline=args.use_deadline, task_timeout=args.task_timeout,
            observation_mode=_resolve_observation_mode(model, args),
        )

        # Now hand off to the existing agent driver, but pass the pre-created
        # session_id and the trace_dir.
        #
        # The agent loop is allowed to fail without taking the archive with it.
        # It raises on its own errors (e.g. RuntimeError("No task data found for
        # evaluation")), and until now that propagated out of run_eval before the
        # archiving step, discarding trial data that was already sitting on the
        # server: 26 runs and 2,108 trials in one 200-run sweep. Whatever the
        # agent managed to produce is evidence and must be saved either way.
        agent_error: Exception | None = None
        no_deadline = not args.use_deadline
        try:
            if scaffold == "random":
                from agents.random_agent import run_all_tasks
                asyncio.run(run_all_tasks(
                    base_url=args.base_url,
                    agent_name=agent_name,
                    no_deadline=no_deadline,
                    task_timeout=args.task_timeout,
                    tasks_filter=args.tasks,
                    n_trials=args.n_trials,
                    session_id=session_id,
                    trace_dir=str(sdir),
                ))
            elif scaffold == "browser-use":
                try:
                    from agents.browser_use_agent import run_all_tasks
                except ImportError:
                    logger.error("browser-use not installed. `pip install browser-use`.")
                    return 1
                asyncio.run(run_all_tasks(
                    base_url=args.base_url,
                    agent_name=agent_name,
                    model_name=model.api,
                    no_deadline=no_deadline,
                    task_timeout=args.task_timeout,
                    tasks_filter=args.tasks,
                    n_trials=args.n_trials,
                    session_id=session_id,
                    trace_dir=str(sdir),
                    force_no_vision=getattr(args, "no_vision", False),
                ))
            else:
                logger.error("Unknown scaffold: %s", scaffold)
                return 1
        except Exception as e:  # noqa: BLE001 — archive first, then re-raise
            agent_error = e
            logger.error("Agent loop failed (%s: %s); archiving whatever reached "
                         "the server before giving up", type(e).__name__, e)

        # Trigger evaluation (idempotent; agent loop usually triggers this too).
        with httpx.Client(timeout=120.0, base_url=args.base_url) as client:
            try:
                client.post(f"/api/evaluate/{session_id}")
            except httpx.HTTPError as e:
                logger.warning("Evaluate POST failed (may already be complete): %s", e)

        # Pull and save final results + trial data.
        results = fetch_trial_data(args.base_url, session_id)
        if results is not None:
            with open(sdir / "score.json", "w") as f:
                json.dump(results, f, indent=2)
            _print_scorecard(agent_name, results)
            # Archive raw jsPsych trial data per task so scoring is rerunnable
            # without replaying the agent (e.g. after scoring rule changes).
            #
            # Archive every task the run ATTEMPTED, not just the ones that scored.
            # Keying off task_scores silently discarded all partial runs: an agent
            # that produced hundreds of trials but never reached a scoreable state
            # left nothing behind, even though incremental_save.js had been PATCHing
            # that data to the server throughout. Those cells then read as "the agent
            # produced no behaviour" rather than "the agent produced incomplete
            # behaviour" — a different and much stronger claim than the data supports.
            scored_ids = [ts["task_id"] for ts in results.get("task_scores", [])]
            attempted = _attempted_task_ids(args.base_url, session_id, args.tasks)
            task_ids = sorted(set(scored_ids) | set(attempted))
            saved = fetch_and_save_raw_trial_data(args.base_url, session_id, task_ids, sdir)
            if saved:
                unscored = sorted(set(saved) - set(scored_ids))
                logger.info("Archived raw trial data for %d task(s) under %s/trial_data/",
                            len(saved), sdir)
                if unscored:
                    logger.info("  (%d of these are partial/unscored: %s)",
                                len(unscored), ", ".join(unscored))
        else:
            logger.warning("No results JSON available for session %s", session_id)

        if args.replay:
            from harness.replay import build_replay_for_session
            out = sdir / "replay.html"
            build_replay_for_session(sdir, out, inline=args.replay_inline)
            print(f"Replay built at {out}")

        if agent_error is not None:
            # The archive is written, but the run still failed. Returning
            # non-zero keeps the sweep's rc honest, so a rescued cell is not
            # mistaken for a clean one.
            logger.error("Run archived despite agent failure: %s", agent_error)
            return 1

        return 0

    finally:
        if server_proc:
            logger.info("Stopping server …")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()


def _default_agent_name(model: ModelEntry) -> str:
    if model.scaffold == "random":
        return "RandomAgent"
    return f"BrowserUseAgent-{model.id}"


def _print_scorecard(agent_name: str, results: dict[str, Any]) -> None:
    """Pretty-print the scorecard returned by GET /api/results/{session_id}.

    The API shape is::

        {session_id, task_scores: [...], composite_score, l1_overall,
         l2_overall, l3_overall}

    where each entry in ``task_scores`` is
    ``{task_id, l1_completion, l2_accuracy, l3_behavioral, composite, details}``.
    """
    print("=" * 65)
    print(f"  COGARENA SCORECARD: {agent_name}")
    print("=" * 65)
    print(f"  Composite Score:    {results.get('composite_score', 0):.2f} / 100")
    print(f"  L1 Completion:      {results.get('l1_overall', 0):.4f}")
    print(f"  L2 Accuracy:        {results.get('l2_overall', 0):.4f}")
    print(f"  L3 Behavioral:      {results.get('l3_overall', 0):.4f}")
    task_scores = results.get("task_scores") or []
    if task_scores:
        print("-" * 65)
        print(f"  {'Task':<24} {'Composite':>9} {'L1':>6} {'L2':>6} {'L3':>6}")
        print(f"  {'-'*22:<24} {'---------':>9} {'------':>6} {'------':>6} {'------':>6}")
        for t in sorted(task_scores, key=lambda x: x.get("task_id", "")):
            tid = t.get("task_id", "?")
            print(f"  {tid:<24} {t.get('composite', 0):>9.2f}"
                  f" {t.get('l1_completion', 0):>6.2f}"
                  f" {t.get('l2_accuracy', 0):>6.2f}"
                  f" {t.get('l3_behavioral', 0):>6.2f}")
    print("=" * 65)
