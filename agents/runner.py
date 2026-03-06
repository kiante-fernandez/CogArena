"""
CogArena Agent Runner

Orchestrates the full evaluation pipeline:
1. Start CogArena server (or connect to existing)
2. Create session via API
3. Run agent on each task
4. Trigger evaluation
5. Print scorecard

Usage:
    # Run with random agent (default)
    python -m agents.runner --agent random

    # Run with browser-use agent
    python -m agents.runner --agent browser-use --model claude-sonnet-4-20250514
"""
import argparse
import asyncio
import logging
import subprocess
import sys
import time

import httpx


def wait_for_server(base_url: str, timeout: float = 30.0) -> bool:
    """Wait for the CogArena server to be ready."""
    client = httpx.Client(timeout=5.0)
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = client.get(f"{base_url}/api/health")
            if resp.status_code == 200:
                return True
        except httpx.ConnectError:
            pass
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser(description="CogArena Agent Runner")
    parser.add_argument("--agent", choices=["random", "browser-use", "openhands", "browser-operator"],
                        default="random", help="Agent type to run")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="CogArena server URL")
    parser.add_argument("--start-server", action="store_true",
                        help="Start the CogArena server automatically")
    parser.add_argument("--agent-name", default=None,
                        help="Agent name for the session")
    parser.add_argument("--model", default="claude-sonnet-4-20250514",
                        help="Model name for LLM agents")
    parser.add_argument("--no-deadline", action="store_true", default=True,
                        help="Remove response deadlines (default: True)")
    parser.add_argument("--use-deadline", action="store_true",
                        help="Keep original response deadlines")
    parser.add_argument("--task-timeout", type=float, default=1200.0,
                        help="Max seconds per task")
    parser.add_argument("--tasks", nargs="*", default=None,
                        help="Only run specific tasks (e.g., --tasks stroop n_back)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("agents.runner")

    # Start server if requested
    server_proc = None
    if args.start_server:
        logger.info("Starting CogArena server...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "harness.server:app",
             "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not wait_for_server(args.base_url):
            logger.error("Server failed to start within 30s")
            server_proc.terminate()
            sys.exit(1)
        logger.info("Server started")

    try:
        # Check server is running
        if not wait_for_server(args.base_url, timeout=5.0):
            logger.error("Cannot connect to %s. Is the server running?", args.base_url)
            sys.exit(1)

        no_deadline = not args.use_deadline
        agent_name = args.agent_name

        if args.agent == "random":
            from agents.random_agent import run_all_tasks
            agent_name = agent_name or "RandomAgent"
            asyncio.run(run_all_tasks(
                base_url=args.base_url,
                agent_name=agent_name,
                no_deadline=no_deadline,
                task_timeout=args.task_timeout,
                tasks_filter=args.tasks,
            ))

        elif args.agent == "browser-use":
            try:
                from agents.browser_use_agent import run_all_tasks
            except ImportError:
                logger.error("browser-use not installed. Run: pip install browser-use")
                sys.exit(1)
            agent_name = agent_name or f"BrowserUseAgent-{args.model}"
            asyncio.run(run_all_tasks(
                base_url=args.base_url,
                agent_name=agent_name,
                model_name=args.model,
                no_deadline=no_deadline,
                task_timeout=args.task_timeout,
                tasks_filter=args.tasks,
            ))

        elif args.agent == "openhands":
            from agents.openhands_agent import run_all_tasks
            agent_name = agent_name or f"OpenHands-{args.model}"
            asyncio.run(run_all_tasks(
                base_url=args.base_url,
                agent_name=agent_name,
                model_name=args.model,
                no_deadline=no_deadline,
                task_timeout=args.task_timeout,
                tasks_filter=args.tasks,
            ))

        elif args.agent == "browser-operator":
            from agents.browser_operator_agent import run_all_tasks
            agent_name = agent_name or f"BrowserOperator-{args.model}"
            asyncio.run(run_all_tasks(
                base_url=args.base_url,
                agent_name=agent_name,
                model_name=args.model,
                no_deadline=no_deadline,
                task_timeout=args.task_timeout,
                tasks_filter=args.tasks,
            ))

    finally:
        if server_proc:
            logger.info("Stopping server...")
            server_proc.terminate()
            server_proc.wait(timeout=10)


if __name__ == "__main__":
    main()
