"""
CogArena Browser-Use Agent

Uses the Browser-Use framework (https://github.com/browser-use/browser-use)
to control a browser with an LLM. The LLM sees the page, reads instructions,
and decides what keys to press or slider values to set.

The system prompt tells the LLM it's in a cognitive experiment and provides the
action vocabulary, but does NOT teach task rules — the agent must read jsPsych's
instruction screens to learn key mappings, just like a human would.

Requirements:
    pip install browser-use langchain-anthropic

Usage:
    python -m agents.browser_use_agent --base-url http://localhost:8000 --model claude-sonnet-4-20250514
"""
import asyncio
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI agent participating in a cognitive behavioral experiment called CogArena.

You are navigating a web browser to complete interactive psychology experiments built with jsPsych.

## How to interact

Each experiment has:
1. **Instruction screens** — Read them carefully to learn the task rules and key mappings. Click "Next" to advance.
2. **Stimulus trials** — A stimulus appears on screen. Press the correct keyboard key as instructed.
3. **Slider trials** — Drag the slider to your chosen value and click the submit button.
4. **Fixation/feedback screens** — These advance automatically. Wait for them.
5. **Completion screen** — Says "Task Complete" when done.

## Important rules
- Read ALL instruction pages before starting. They tell you which keys to press.
- Respond to every trial — missed responses count as timeouts.
- For keyboard tasks: press the exact key shown in the instructions (e.g., 'd', 'f', 'j', 'k').
- For slider tasks: set a value and click the submit/send button.
- Do NOT refresh the page.
- When you see "Task Complete", the task is done.

## Your goal
Complete each trial as accurately as you can based on the instructions you read.
"""


async def run_task_with_browser_use(task_url: str, task_id: str, model_name: str, timeout: float = 600.0):
    """Run a single CogArena task using Browser-Use."""
    try:
        from browser_use import Agent
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError(
            "browser-use and langchain-anthropic are required. "
            "Install with: pip install browser-use langchain-anthropic"
        )

    llm = ChatAnthropic(model=model_name)

    task_description = (
        f"Navigate to {task_url} and complete the cognitive experiment. "
        f"Read the instruction screens carefully to learn the task rules and key mappings. "
        f"Then respond to each trial according to the instructions. "
        f"When you see 'Task Complete', you are done."
    )

    agent = Agent(
        task=task_description,
        llm=llm,
        system_prompt_class=None,  # We'll provide our own via the task description
    )

    logger.info("Starting Browser-Use agent for task: %s", task_id)
    start = time.time()

    try:
        result = await asyncio.wait_for(agent.run(), timeout=timeout)
        elapsed = time.time() - start
        logger.info("Task %s completed in %.1fs", task_id, elapsed)
        return True
    except asyncio.TimeoutError:
        logger.warning("Task %s timed out after %.0fs", task_id, timeout)
        return False
    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        return False


async def run_all_tasks(
    base_url: str = "http://localhost:8000",
    agent_name: str = "BrowserUseAgent",
    model_name: str = "claude-sonnet-4-20250514",
    no_deadline: bool = True,
    task_timeout: float = 600.0,  # 10 minutes per task
):
    """Run the Browser-Use agent through all CogArena tasks."""
    client = httpx.Client(base_url=base_url, timeout=30.0)

    # Health check
    resp = client.get("/api/health")
    resp.raise_for_status()

    # Create session
    resp = client.post("/api/sessions", json={
        "agent_name": agent_name,
        "scaffold": "browser-use",
        "model_name": model_name,
        "observation_mode": "screenshot",
    })
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]
    logger.info("Session created: %s", session_id)

    tasks = session["tasks"]
    logger.info("Tasks to complete: %d", len(tasks))

    completed = []
    failed = []

    for task_info in tasks:
        task_id = task_info["task_id"]
        url = f"{base_url}{task_info['url']}"
        if no_deadline:
            url += "&no_deadline=true"

        success = await run_task_with_browser_use(url, task_id, model_name, timeout=task_timeout)
        if success:
            completed.append(task_id)
        else:
            failed.append(task_id)

    logger.info("Completed: %d/%d tasks", len(completed), len(tasks))
    if failed:
        logger.warning("Failed: %s", ", ".join(failed))

    # Check if auto-evaluation ran
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
    parser.add_argument("--no-deadline", action="store_true", default=True)
    parser.add_argument("--use-deadline", action="store_true")
    parser.add_argument("--task-timeout", type=float, default=600.0)
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
    ))


if __name__ == "__main__":
    main()
