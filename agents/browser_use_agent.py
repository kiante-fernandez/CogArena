"""
CogArena Browser-Use Agent

Uses the Browser-Use framework (https://github.com/browser-use/browser-use)
to control a browser with an LLM. The agent receives only the task URL and
the public skill.md reference — it must read jsPsych's on-screen instructions
to learn task rules and key mappings, just like a human participant would.

Supported providers (auto-detected from model name):
    - OpenRouter: provider/model  (requires OPENROUTER_API_KEY)
      e.g. openai/o3, anthropic/claude-sonnet-4, google/gemini-2.5-flash
    - OpenAI:    gpt-*, o3, o4-* (requires OPENAI_API_KEY)
    - Google:    gemini-*        (requires GOOGLE_API_KEY)
    - Anthropic: claude-*        (requires ANTHROPIC_API_KEY)

Requirements:
    pip install browser-use

Usage:
    python -m agents.browser_use_agent --base-url http://localhost:8000 --model openai/o3
    python -m agents.browser_use_agent --base-url http://localhost:8000 --model anthropic/claude-sonnet-4
    python -m agents.browser_use_agent --base-url http://localhost:8000 --model google/gemini-2.5-flash
    python -m agents.browser_use_agent --base-url http://localhost:8000 --model o3
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
import httpx

load_dotenv()  # Load .env so API keys are available to LLM providers

logger = logging.getLogger(__name__)

# Load skill instructions from static/skill.md
_SKILL_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "skill.md")
try:
    with open(_SKILL_PATH) as f:
        _SKILL_INSTRUCTIONS = f.read()
except FileNotFoundError:
    _SKILL_INSTRUCTIONS = ""


def _make_llm(model_name: str):
    """Create the appropriate LangChain LLM based on model name prefix.

    If model_name contains '/' (e.g. 'openai/o3'), route through OpenRouter.
    Otherwise, auto-detect provider from model name prefix.
    """
    try:
        from browser_use import Agent  # noqa: F401 — validate browser-use is installed
    except ImportError:
        raise ImportError("browser-use is required. Install with: pip install browser-use")

    # OpenRouter: model names contain '/' (e.g. openai/o3, anthropic/claude-sonnet-4)
    if "/" in model_name:
        from browser_use import ChatOpenAI
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for OpenRouter models. "
                "Set it in .env or environment."
            )
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    name = model_name.lower()
    if name.startswith("gpt-") or name.startswith("o3") or name.startswith("o4"):
        from browser_use import ChatOpenAI
        return ChatOpenAI(model=model_name)
    elif name.startswith("gemini"):
        from browser_use import ChatGoogle
        return ChatGoogle(model=model_name)
    elif name.startswith("claude"):
        from browser_use import ChatAnthropic
        return ChatAnthropic(model=model_name)
    else:
        # Default to OpenAI-compatible
        from browser_use import ChatOpenAI
        return ChatOpenAI(model=model_name)


# Models known to lack vision/image-input support on OpenRouter
_NO_VISION_MODELS = {
    "z-ai/glm-5",
    "minimax/minimax-m2.5",
}


def _model_supports_vision(model_name: str) -> bool:
    """Check if a model supports image input (vision)."""
    return model_name not in _NO_VISION_MODELS


async def run_task_with_browser_use(
    task_url: str, task_id: str, model_name: str,
    timeout: float = 600.0, headless: bool = True,
    trace_writer=None, force_no_vision: bool = False,
):
    """Run a single CogArena task using Browser-Use.

    If ``trace_writer`` is supplied, every model call is logged to its
    interactions.jsonl via Browser-Use's ``register_new_step_callback``,
    and full prompt+response transcripts are written under
    ``<trace_dir>/conversations/<task_id>/`` via ``save_conversation_path``.
    """
    from browser_use import Agent, BrowserSession

    llm = _make_llm(model_name)
    # force_no_vision drives the ablation: same model, same scaffold, DOM text
    # only. Any performance drop is attributable to the loss of pixels.
    use_vision = (not force_no_vision) and _model_supports_vision(model_name)
    # Recorded per step so the archive states what the model was actually given,
    # rather than asserting a modality the run may not have used.
    observation_mode = "screenshot" if use_vision else "dom"

    task_description = (
        f"Navigate to {task_url} and complete the experiment you find there.\n\n"
        f"{_SKILL_INSTRUCTIONS}"
    )

    browser_session = BrowserSession(headless=headless)

    # Per-step callback: log the model's parsed action(s) into our TraceWriter.
    # Browser-Use invokes this after every successful model call (parse failures
    # are surfaced separately via consecutive_failures and don't fire the hook).
    step_cb = None
    if trace_writer is not None:
        seen_task_urls: set[str] = set()

        def step_cb(browser_state, agent_output, n_steps):  # noqa: E306
            try:
                actions = []
                for a in (getattr(agent_output, "action", None) or []):
                    actions.append(a.model_dump(exclude_none=True) if hasattr(a, "model_dump") else str(a))
                current = getattr(agent_output, "current_state", None)
                extra = {}
                if current is not None and hasattr(current, "model_dump"):
                    cs = current.model_dump(exclude_none=True)
                    # Trim verbose fields; keep the model's reasoning and goal.
                    for k in ("evaluation_previous_goal", "memory", "next_goal"):
                        if k in cs:
                            extra[k] = cs[k]

                # Re-navigation watchdog: a second navigate to the same task
                # URL means the agent is restarting the experiment, which
                # destroys jsPsych state and guarantees no data submission.
                # Surface it loudly in the trace so the failure mode is visible.
                renav = False
                for a in actions:
                    nav = isinstance(a, dict) and a.get("navigate")
                    url = nav.get("url") if isinstance(nav, dict) else None
                    if url and "/tasks/" in url:
                        if url in seen_task_urls:
                            renav = True
                            logger.error(
                                "RE-NAVIGATION DETECTED: agent re-navigated to %s "
                                "(this resets jsPsych state and loses trial data)", url)
                        seen_task_urls.add(url)

                # Persist the exact frame the scaffold showed the model. In
                # vision mode Browser-Use hands us a base64 PNG on the state
                # summary; in DOM mode there is none, and the absence is itself
                # the record of what the model had to work with.
                shot = None
                if getattr(trace_writer, "capture_screenshots", False):
                    b64 = getattr(browser_state, "screenshot", None)
                    if b64 is None and hasattr(browser_state, "get_screenshot"):
                        b64 = browser_state.get_screenshot()
                    shot = trace_writer.save_screenshot_b64(b64, task_id)

                try:
                    response_chars = len(json.dumps(
                        agent_output.model_dump(exclude_none=True), default=str))
                except Exception:
                    response_chars = None

                trace_writer.log_interaction(
                    task_id=task_id,
                    state="browser_use_renav" if renav else "browser_use_step",
                    action_proposed=actions if len(actions) != 1 else actions[0],
                    action_valid=not renav,
                    validity_reason="agent re-navigated to a task URL it already visited" if renav else None,
                    screenshot_path=shot,
                    response_chars=response_chars,
                    extra={"step": n_steps, "observation_mode": observation_mode, **extra},
                )
                for a in actions:
                    trace_writer.log_action(
                        task_id=task_id,
                        action_kind=next(iter(a)) if isinstance(a, dict) and a else "unknown",
                        target=None, key=None, ok=not renav,
                    )
            except Exception as e:
                logger.debug("trace callback failed (non-fatal): %s", e)

    agent_kwargs = dict(
        task=task_description,
        llm=llm,
        use_vision=use_vision,
        max_actions_per_step=5,
        max_failures=10,
        loop_detection_enabled=True,
        browser_session=browser_session,
    )
    if step_cb is not None:
        agent_kwargs["register_new_step_callback"] = step_cb
    if trace_writer is not None:
        agent_kwargs["save_conversation_path"] = str(
            Path(trace_writer.trace_dir) / "conversations" / task_id
        )

    agent = Agent(**agent_kwargs)
    if not use_vision:
        logger.info("Vision disabled for %s — using DOM text mode", model_name)

    logger.info("Starting Browser-Use agent for task: %s", task_id)
    start = time.time()

    try:
        await asyncio.wait_for(agent.run(max_steps=500), timeout=timeout)
        elapsed = time.time() - start
        logger.info("Task %s completed in %.1fs", task_id, elapsed)
        return True
    except asyncio.TimeoutError:
        logger.warning("Task %s timed out after %.0fs", task_id, timeout)
        return False
    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e, exc_info=True)
        return False
    finally:
        await browser_session.stop()


async def run_all_tasks(
    base_url: str = "http://localhost:8000",
    agent_name: str = "BrowserUseAgent",
    model_name: str = "claude-sonnet-4-20250514",
    no_deadline: bool = True,
    task_timeout: float = 1800.0,
    tasks_filter: list[str] | None = None,
    n_trials: int | None = None,
    headless: bool = True,
    force_no_vision: bool = False,
    skip_tasks: set[str] | None = None,
    session_id: str | None = None,
    trace_dir: str | None = None,
):
    """Run the Browser-Use agent through all CogArena tasks.

    If ``session_id`` is provided, reuse it. If ``trace_dir`` is provided,
    record per-task wall time and the resolved task URL into a small
    ``interactions.jsonl`` so the harness has *some* per-step trail even though
    Browser-Use's internal step loop is not directly observable from here.
    """
    MAX_CONSECUTIVE_FAILURES = 3

    client = httpx.Client(base_url=base_url, timeout=30.0)
    try:
        return await _run_all_tasks_inner(
            client=client, base_url=base_url, agent_name=agent_name,
            model_name=model_name, no_deadline=no_deadline,
            task_timeout=task_timeout, tasks_filter=tasks_filter,
            n_trials=n_trials, headless=headless, session_id=session_id,
            trace_dir=trace_dir, skip_tasks=skip_tasks,
            max_consecutive_failures=MAX_CONSECUTIVE_FAILURES,
            force_no_vision=force_no_vision,
        )
    finally:
        client.close()


async def _run_all_tasks_inner(
    *, client: "httpx.Client", base_url: str, agent_name: str,
    model_name: str, no_deadline: bool, task_timeout: float,
    tasks_filter: list[str] | None, n_trials: int | None, headless: bool,
    session_id: str | None, trace_dir: str | None,
    skip_tasks: set[str] | None,
    max_consecutive_failures: int,
    force_no_vision: bool = False,
):
    MAX_CONSECUTIVE_FAILURES = max_consecutive_failures

    resp = client.get("/api/health")
    resp.raise_for_status()

    if session_id is None:
        resp = client.post("/api/sessions", json={
            "agent_name": agent_name,
            "scaffold": "browser-use",
            "model_name": model_name,
            "observation_mode": ("dom" if force_no_vision
                                 else ("screenshot" if _model_supports_vision(model_name) else "dom")),
        })
        resp.raise_for_status()
        session = resp.json()
        session_id = session["session_id"]
        logger.info("Session created: %s", session_id)
        tasks = session["tasks"]
    else:
        logger.info("Reusing pre-created session: %s", session_id)
        resp = client.get(f"/api/sessions/{session_id}")
        resp.raise_for_status()
        tasks = resp.json().get("tasks", [])

    trace_writer = None
    if trace_dir:
        from harness.trace import TraceWriter
        trace_writer = TraceWriter(Path(trace_dir), capture_screenshots=True)
    if tasks_filter:
        tasks = [t for t in tasks if t["task_id"] in tasks_filter]
    if skip_tasks:
        before = len(tasks)
        tasks = [t for t in tasks if t["task_id"] not in skip_tasks]
        skipped = before - len(tasks)
        if skipped:
            logger.info("Skipping %d already-scored tasks", skipped)
    if not tasks:
        logger.info("All tasks already scored — nothing to do")
        return session_id
    logger.info("Tasks to complete: %d", len(tasks))

    completed = []
    failed = []
    consecutive_failures = 0

    for task_info in tasks:
        task_id = task_info["task_id"]
        url = f"{base_url}{task_info['url']}"
        if no_deadline:
            url += "&no_deadline=true"
        if n_trials is not None:
            url += f"&n_trials={n_trials}"

        if trace_writer:
            trace_writer.log_interaction(
                task_id=task_id, state="task_start",
                action_proposed={"kind": "navigate", "url": url},
                action_valid=True,
                extra={"model": model_name},
            )
        task_start = time.time()
        success = await run_task_with_browser_use(
            url, task_id, model_name, timeout=task_timeout, headless=headless,
            trace_writer=trace_writer, force_no_vision=force_no_vision,
        )
        if trace_writer:
            trace_writer.log_interaction(
                task_id=task_id,
                state="task_end" if success else "task_failed",
                action_proposed=None,
                action_valid=success,
                extra={"wall_time_seconds": round(time.time() - task_start, 2)},
            )
        if success:
            completed.append(task_id)
            consecutive_failures = 0
        else:
            failed.append(task_id)
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    "Aborting: %d consecutive failures — likely a systemic issue "
                    "(expired credits, wrong API key, etc.)", consecutive_failures,
                )
                raise RuntimeError(
                    f"Aborting: {consecutive_failures} consecutive failures — "
                    "likely a systemic issue (expired credits, wrong API key, etc.)"
                )

    logger.info("Completed: %d/%d tasks", len(completed), len(tasks))
    if failed:
        logger.warning("Failed: %s", ", ".join(failed))
    if trace_writer:
        trace_writer.close()

    if not completed:
        raise RuntimeError("All tasks failed")

    # Check if auto-evaluation ran. The server may be in a degraded state
    # (e.g. after a 500 from a scoring exception), so guard the JSON parse.
    sess_resp = client.get(f"/api/sessions/{session_id}")
    if sess_resp.status_code != 200:
        raise RuntimeError(
            f"Session lookup failed: HTTP {sess_resp.status_code} "
            f"{sess_resp.text[:200]!r}"
        )
    status = sess_resp.json()
    if status["status"] == "scored":
        logger.info("Auto-evaluation completed")
    else:
        logger.info("Triggering manual evaluation...")
        resp = client.post(f"/api/evaluate/{session_id}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"Evaluate failed: HTTP {resp.status_code} {resp.text[:200]!r}"
            )
        body = resp.json()
        if body.get("status") == "no_data":
            raise RuntimeError("No task data found for evaluation")
        # Surface per-task scoring failures so the run is flagged even when
        # /api/evaluate as a whole returned 200.
        for err in body.get("scoring_errors") or []:
            logger.warning("Scoring error for task %s: %s",
                           err.get("task_id"), err.get("error"))

    # Print scorecard — but only if running standalone. When the harness
    # CLI invokes this with trace_dir set, the harness prints its own
    # scorecard after this returns and we'd duplicate it.
    if trace_dir is None:
        results = client.get(f"/api/results/{session_id}").json()
        print(f"\n{'=' * 65}")
        print(f"  COGARENA SCORECARD: {agent_name}")
        print(f"  Model: {model_name}")
        print(f"{'=' * 65}")
        print(f"  Composite Score:    {results['composite_score']:.2f} / 100")
        print(f"  L1 Completion:      {results['l1_overall']:.4f}")
        print(f"  L2 Accuracy:        {results['l2_overall']:.4f}")
        print(f"  L3 Behavioral:      {results['l3_overall']:.4f}")
        print(f"{'-' * 65}")
        print(f"  {'Task':<22s} {'Composite':>9s} {'L1':>6s} {'L2':>6s} {'L3':>6s}")
        print(f"  {'-'*22} {'-'*9} {'-'*6} {'-'*6} {'-'*6}")
        for ts in sorted(results["task_scores"], key=lambda t: t["task_id"]):
            print(f"  {ts['task_id']:<22s} {ts['composite']:>9.2f} "
                  f"{ts['l1_completion']:>6.2f} {ts['l2_accuracy']:>6.2f} "
                  f"{ts['l3_behavioral']:>6.2f}")
        print(f"{'=' * 65}")

    return session_id


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CogArena Browser-Use Agent")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--agent-name", default="BrowserUseAgent")
    parser.add_argument("--model", default="claude-sonnet-4-20250514",
                        help="LLM model name")
    parser.add_argument("--use-deadline", action="store_true",
                        help="Enable task deadlines (default: no deadline)")
    parser.add_argument("--task-timeout", type=float, default=1800.0)
    parser.add_argument("--tasks", nargs="*", default=None,
                        help="Only run specific tasks (e.g., --tasks stroop n_back)")
    parser.add_argument("--n-trials", type=int, default=None,
                        help="Override trial count per task (e.g., --n-trials 40)")
    parser.add_argument("--no-headless", action="store_true",
                        help="Show the browser window (default: headless)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    no_deadline = not args.use_deadline
    asyncio.run(run_all_tasks(
        base_url=args.base_url,
        agent_name=args.agent_name,
        model_name=args.model,
        no_deadline=no_deadline,
        task_timeout=args.task_timeout,
        tasks_filter=args.tasks,
        n_trials=args.n_trials,
        headless=not args.no_headless,
    ))


if __name__ == "__main__":
    main()
