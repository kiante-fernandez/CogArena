"""
CogArena OpenHands Agent

Uses the OpenHands framework (https://github.com/All-Hands-AI/OpenHands)
to control a sandboxed Docker environment with browser + code execution.
The agent receives task URLs and must complete jsPsych experiments.

OpenHands runs in headless CLI mode with JSON output for structured logging.
LLM configuration uses LiteLLM format (supports OpenRouter model IDs).

Requirements:
    pip install openhands-ai
    docker (running)

Usage:
    python -m agents.openhands_agent --base-url http://localhost:8000 --model openai/o3
    python -m agents.openhands_agent --base-url http://localhost:8000 --model anthropic/claude-sonnet-4
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import time

from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

_SKILL_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "skill.md")
try:
    with open(_SKILL_PATH) as f:
        _SKILL_INSTRUCTIONS = f.read()
except FileNotFoundError:
    _SKILL_INSTRUCTIONS = ""


def _get_host_url(base_url: str) -> str:
    """Convert localhost URL to host.docker.internal for Docker access."""
    return base_url.replace("localhost", "host.docker.internal").replace(
        "127.0.0.1", "host.docker.internal"
    )


def run_task_with_openhands(
    task_url: str,
    task_id: str,
    model_name: str,
    timeout: float = 600.0,
) -> bool:
    """Run a single CogArena task using OpenHands in headless mode."""
    task_description = (
        f"Navigate to {task_url} in the browser and complete the experiment. "
        f"This is a jsPsych behavioral experiment. Read the on-screen instructions "
        f"carefully, then respond to each trial by pressing the correct keys or "
        f"clicking the correct buttons as instructed.\n\n"
        f"Key guidelines:\n"
        f"- Wait for each trial to appear before responding\n"
        f"- Use keyboard keys or mouse clicks as the experiment instructs\n"
        f"- Complete ALL trials until the experiment shows a completion message\n"
        f"- The experiment auto-submits data when complete\n\n"
        f"Reference instructions:\n{_SKILL_INSTRUCTIONS}"
    )

    env = os.environ.copy()
    # OpenHands uses LiteLLM format for model names
    env["LLM_MODEL"] = model_name
    if os.environ.get("OPENROUTER_API_KEY"):
        env["LLM_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
        env["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"

    cmd = [
        sys.executable, "-m", "openhands.core.main",
        "--headless",
        "--json",
        "-t", task_description,
    ]

    logger.info("Starting OpenHands agent for task: %s (model: %s)", task_id, model_name)
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            logger.info("Task %s completed in %.1fs", task_id, elapsed)
            return True
        else:
            logger.warning(
                "Task %s exited with code %d in %.1fs",
                task_id, result.returncode, elapsed,
            )
            if result.stderr:
                logger.debug("stderr: %s", result.stderr[-500:])
            return False

    except subprocess.TimeoutExpired:
        logger.warning("Task %s timed out after %.0fs", task_id, timeout)
        return False
    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e, exc_info=True)
        return False


async def run_all_tasks(
    base_url: str = "http://localhost:8000",
    agent_name: str = "OpenHandsAgent",
    model_name: str = "openai/o3",
    no_deadline: bool = True,
    task_timeout: float = 600.0,
    tasks_filter: list[str] | None = None,
):
    """Run the OpenHands agent through CogArena tasks."""
    client = httpx.Client(base_url=base_url, timeout=30.0)

    resp = client.get("/api/health")
    resp.raise_for_status()

    resp = client.post("/api/sessions", json={
        "agent_name": agent_name,
        "scaffold": "openhands",
        "model_name": model_name,
        "observation_mode": "screenshot",
    })
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]
    logger.info("Session created: %s", session_id)

    tasks = session["tasks"]
    if tasks_filter:
        tasks = [t for t in tasks if t["task_id"] in tasks_filter]
    logger.info("Tasks to complete: %d", len(tasks))

    # OpenHands runs in Docker — use host.docker.internal
    docker_base_url = _get_host_url(base_url)

    completed = []
    failed = []

    for task_info in tasks:
        task_id = task_info["task_id"]
        url = f"{docker_base_url}{task_info['url']}"
        if no_deadline:
            url += "&no_deadline=true"

        success = run_task_with_openhands(
            url, task_id, model_name, timeout=task_timeout,
        )
        if success:
            completed.append(task_id)
        else:
            failed.append(task_id)

    logger.info("Completed: %d/%d tasks", len(completed), len(tasks))
    if failed:
        logger.warning("Failed: %s", ", ".join(failed))

    # Trigger evaluation
    status = client.get(f"/api/sessions/{session_id}").json()
    if status["status"] == "scored":
        logger.info("Auto-evaluation completed")
    else:
        logger.info("Triggering manual evaluation...")
        resp = client.post(f"/api/evaluate/{session_id}")
        if resp.status_code == 404:
            logger.error("No task data found")
            return session_id
        resp.raise_for_status()

    # Print scorecard
    results = client.get(f"/api/results/{session_id}").json()
    print(f"\n{'=' * 65}")
    print(f"  COGARENA SCORECARD: {agent_name}")
    print(f"  Model: {model_name} | Framework: OpenHands")
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
    parser = argparse.ArgumentParser(description="CogArena OpenHands Agent")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--agent-name", default="OpenHandsAgent")
    parser.add_argument("--model", default="openai/o3",
                        help="LLM model (LiteLLM format, e.g. openai/o3)")
    parser.add_argument("--no-deadline", action="store_true", default=True)
    parser.add_argument("--use-deadline", action="store_true")
    parser.add_argument("--task-timeout", type=float, default=600.0)
    parser.add_argument("--tasks", nargs="*", default=None,
                        help="Only run specific tasks")
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
    ))


if __name__ == "__main__":
    main()
