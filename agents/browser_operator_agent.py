"""
CogArena BrowserOperator Agent

Uses the BrowserOperator framework (https://github.com/BrowserOperator/browser-operator-core)
to control a browser with an LLM. BrowserOperator uses a multi-agent architecture
with a REST API for task management.

Prerequisites:
    1. BrowserOperator desktop app running (macOS/Windows)
    2. Agent-server running on port 8081
    3. At least one browser agent connected via WebSocket on port 8080
    4. Model configured in BrowserOperator Settings (OpenRouter, OpenAI, Groq, etc.)

Usage:
    python -m agents.browser_operator_agent --base-url http://localhost:8000
    python -m agents.browser_operator_agent --base-url http://localhost:8000 --tasks stroop n_back
"""
import asyncio
import json
import logging
import os
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

AGENT_SERVER_URL = os.environ.get("BROWSER_OPERATOR_URL", "http://localhost:8081")


def _check_agent_server() -> bool:
    """Check if the BrowserOperator agent-server is running and has connected clients."""
    try:
        resp = httpx.get(f"{AGENT_SERVER_URL}/status", timeout=5.0)
        if resp.status_code == 200:
            status = resp.json()
            logger.info("Agent server status: %s", status)
            return True
    except httpx.ConnectError:
        pass
    return False


def _get_clients() -> list[dict]:
    """Get list of connected browser agent clients."""
    try:
        resp = httpx.get(f"{AGENT_SERVER_URL}/clients", timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
    except httpx.ConnectError:
        pass
    return []


def run_task_with_browser_operator(
    task_url: str,
    task_id: str,
    model_name: str,
    timeout: float = 600.0,
) -> bool:
    """Run a single CogArena task via BrowserOperator's agent-server API."""
    task_description = (
        f"Navigate to {task_url} and complete the behavioral experiment. "
        f"Read the on-screen instructions carefully. Respond to each trial "
        f"by pressing the correct keyboard keys or clicking buttons as instructed. "
        f"Complete ALL trials until the experiment shows a completion message. "
        f"The experiment auto-submits data when complete.\n\n"
        f"Reference instructions:\n{_SKILL_INSTRUCTIONS}"
    )

    logger.info("Starting BrowserOperator agent for task: %s", task_id)
    start = time.time()

    try:
        resp = httpx.post(
            f"{AGENT_SERVER_URL}/v1/responses",
            json={
                "input": task_description,
                "model": model_name,
            },
            timeout=timeout,
        )

        elapsed = time.time() - start

        if resp.status_code == 200:
            result = resp.json()
            logger.info("Task %s completed in %.1fs", task_id, elapsed)
            logger.debug("Response: %s", json.dumps(result)[:500])
            return True
        else:
            logger.warning(
                "Task %s returned status %d in %.1fs: %s",
                task_id, resp.status_code, elapsed, resp.text[:200],
            )
            return False

    except httpx.TimeoutException:
        logger.warning("Task %s timed out after %.0fs", task_id, timeout)
        return False
    except httpx.ConnectError:
        logger.error(
            "Cannot connect to BrowserOperator agent-server at %s. "
            "Is it running?", AGENT_SERVER_URL,
        )
        return False
    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e, exc_info=True)
        return False


async def run_all_tasks(
    base_url: str = "http://localhost:8000",
    agent_name: str = "BrowserOperatorAgent",
    model_name: str = "openai/o3",
    no_deadline: bool = True,
    task_timeout: float = 600.0,
    tasks_filter: list[str] | None = None,
):
    """Run the BrowserOperator agent through CogArena tasks."""
    # Check agent-server connectivity
    if not _check_agent_server():
        logger.error(
            "BrowserOperator agent-server not available at %s. "
            "Start the BrowserOperator desktop app and agent-server first.",
            AGENT_SERVER_URL,
        )
        return None

    clients = _get_clients()
    if not clients:
        logger.error("No browser agents connected to the agent-server.")
        return None
    logger.info("Connected browser agents: %d", len(clients))

    client = httpx.Client(base_url=base_url, timeout=30.0)

    resp = client.get("/api/health")
    resp.raise_for_status()

    resp = client.post("/api/sessions", json={
        "agent_name": agent_name,
        "scaffold": "browser-operator",
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

    completed = []
    failed = []

    for task_info in tasks:
        task_id = task_info["task_id"]
        url = f"{base_url}{task_info['url']}"
        if no_deadline:
            url += "&no_deadline=true"

        success = run_task_with_browser_operator(
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
    print(f"  Model: {model_name} | Framework: BrowserOperator")
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
    parser = argparse.ArgumentParser(description="CogArena BrowserOperator Agent")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--agent-name", default="BrowserOperatorAgent")
    parser.add_argument("--model", default="openai/o3",
                        help="Model name (configured in BrowserOperator settings)")
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
