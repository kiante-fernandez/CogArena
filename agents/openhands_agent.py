"""
CogArena OpenHands Agent

Uses the OpenHands framework (https://github.com/All-Hands-AI/OpenHands)
running natively via a separate conda environment (Python 3.12+).
OpenHands spawns Docker sandbox containers with a browser for task execution.

Requirements:
    conda env 'openhands' with openhands-ai installed
    Docker running (for OpenHands sandbox containers)
    OPENHANDS_PYTHON env var pointing to the conda env's python binary

Usage:
    python -m agents.runner --agent openhands --model google/gemini-2.5-flash --start-server --tasks dictator_game
    python -m agents.openhands_agent --base-url http://localhost:8000 --model anthropic/claude-sonnet-4
"""
import logging
import os
import shutil
import subprocess
import tempfile
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


def _resolve_openhands_python() -> str:
    """Find the OpenHands Python binary."""
    explicit = os.environ.get("OPENHANDS_PYTHON")
    if explicit:
        return explicit
    # Try common conda env location
    candidate = shutil.which("python", path=os.path.expanduser(
        "~/anaconda3/envs/openhands/bin"
    ))
    if candidate:
        return candidate
    raise FileNotFoundError(
        "OpenHands Python not found. Set OPENHANDS_PYTHON env var to the "
        "Python binary in your openhands conda env, e.g.:\n"
        "  export OPENHANDS_PYTHON=~/anaconda3/envs/openhands/bin/python"
    )


def _build_config_toml(model_name: str) -> str:
    """Build an OpenHands config.toml for the given model."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = ""

    # Detect OpenRouter models (contain '/')
    if "/" in model_name:
        base_url = "https://openrouter.ai/api/v1"
        # OpenHands uses LiteLLM — OpenRouter models need openrouter/ prefix
        if not model_name.startswith("openrouter/"):
            litellm_model = f"openrouter/{model_name}"
        else:
            litellm_model = model_name
    else:
        litellm_model = model_name
        # Use provider-specific keys
        if model_name.startswith("claude"):
            api_key = os.environ.get("ANTHROPIC_API_KEY", api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", api_key)

    config = f"""[core]
workspace_base = "/tmp/workspace"

[llm]
model = "{litellm_model}"
api_key = "{api_key}"
"""
    if base_url:
        config += f'base_url = "{base_url}"\n'

    # Use pre-built runtime image to avoid build step
    config += """
[sandbox]
runtime_container_image = "ghcr.io/openhands/runtime:oh_v1.4.0_image_nikolaik_s_python-nodejs_tag_python3.12-nodejs22"
"""

    return config


def run_task_with_openhands(
    task_url: str,
    task_id: str,
    config_file_path: str,
    openhands_python: str,
    timeout: float = 600.0,
) -> bool:
    """Run a single CogArena task using OpenHands as a native subprocess."""
    task_description = (
        f"Navigate to {task_url} and complete the experiment you find there.\n\n"
        f"{_SKILL_INSTRUCTIONS}"
    )

    # Write task to temp file (avoid shell escaping issues)
    task_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="openhands_task_", delete=False
    )
    task_file.write(task_description)
    task_file.close()

    logger.info("Starting OpenHands agent for task: %s", task_id)
    start = time.time()

    try:
        cmd = [
            openhands_python, "-m", "openhands.core.main",
            "--config-file", config_file_path,
            "-f", task_file.name,
        ]

        logger.debug("Command: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            logger.info("Task %s completed in %.1fs", task_id, elapsed)
            if result.stdout:
                logger.debug("stdout (last 500): %s", result.stdout[-500:])
            return True
        else:
            logger.warning(
                "Task %s exited with code %d in %.1fs",
                task_id, result.returncode, elapsed,
            )
            if result.stderr:
                logger.warning("stderr (last 1000): %s", result.stderr[-1000:])
            if result.stdout:
                logger.debug("stdout (last 500): %s", result.stdout[-500:])
            return False

    except subprocess.TimeoutExpired:
        logger.warning("Task %s timed out after %.0fs", task_id, timeout)
        return False
    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e, exc_info=True)
        return False
    finally:
        os.unlink(task_file.name)


def run_all_tasks(
    base_url: str = "http://localhost:8000",
    agent_name: str = "OpenHandsAgent",
    model_name: str = "openai/o3",
    no_deadline: bool = True,
    task_timeout: float = 1800.0,
    tasks_filter: list[str] | None = None,
    n_trials: int | None = None,
    skip_tasks: set[str] | None = None,
):
    """Run the OpenHands agent through CogArena tasks."""
    # Resolve OpenHands Python
    try:
        openhands_python = _resolve_openhands_python()
    except FileNotFoundError as e:
        logger.error("%s", e)
        return None

    # Verify OpenHands is importable
    try:
        result = subprocess.run(
            [openhands_python, "-c", "import openhands; print(openhands.__version__)"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.error(
                "OpenHands not importable at %s. "
                "Install with: pip install openhands-ai",
                openhands_python,
            )
            return None
        logger.info("OpenHands version: %s", result.stdout.strip())
    except FileNotFoundError:
        logger.error("OpenHands Python not found at %s", openhands_python)
        return None

    # Verify Docker is available (needed for OpenHands sandbox)
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.error("Docker is not running. Start Docker Desktop first.")
            return None
    except FileNotFoundError:
        logger.error("Docker not found. Install Docker Desktop first.")
        return None

    # Write config once — it's the same for all tasks
    config_toml = _build_config_toml(model_name)
    config_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", prefix="openhands_config_", delete=False
    )
    config_file.write(config_toml)
    config_file.close()
    os.chmod(config_file.name, 0o600)

    try:
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
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

            MAX_CONSECUTIVE_FAILURES = 3

            tasks = session["tasks"]
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

            # OpenHands sandbox runs in Docker — use host.docker.internal so the
            # browser inside the sandbox can reach the CogArena server on the host
            docker_base_url = base_url.replace(
                "localhost", "host.docker.internal"
            ).replace("127.0.0.1", "host.docker.internal")

            completed = []
            failed = []
            consecutive_failures = 0

            for task_info in tasks:
                task_id = task_info["task_id"]
                url = f"{docker_base_url}{task_info['url']}"
                if no_deadline:
                    url += "&no_deadline=true"
                if n_trials is not None:
                    url += f"&n_trials={n_trials}"

                success = run_task_with_openhands(
                    url, task_id, config_file.name, openhands_python,
                    timeout=task_timeout,
                )
                if success:
                    completed.append(task_id)
                    consecutive_failures = 0
                else:
                    failed.append(task_id)
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        raise RuntimeError(
                            f"Aborting: {consecutive_failures} consecutive failures — "
                            "likely a systemic issue (expired credits, wrong API key, etc.)"
                        )

            logger.info("Completed: %d/%d tasks", len(completed), len(tasks))
            if failed:
                logger.warning("Failed: %s", ", ".join(failed))

            if not completed:
                raise RuntimeError("All tasks failed")

            # Trigger evaluation
            status = client.get(f"/api/sessions/{session_id}").json()
            if status["status"] == "scored":
                logger.info("Auto-evaluation completed")
            else:
                logger.info("Triggering manual evaluation...")
                resp = client.post(f"/api/evaluate/{session_id}")
                if resp.status_code == 404:
                    raise RuntimeError("No task data found for evaluation")
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
    finally:
        os.unlink(config_file.name)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CogArena OpenHands Agent")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--agent-name", default="OpenHandsAgent")
    parser.add_argument("--model", default="openai/o3",
                        help="LLM model (LiteLLM format, e.g. openai/o3)")
    parser.add_argument("--use-deadline", action="store_true",
                        help="Enable task deadlines (default: no deadline)")
    parser.add_argument("--task-timeout", type=float, default=1800.0)
    parser.add_argument("--tasks", nargs="*", default=None,
                        help="Only run specific tasks")
    parser.add_argument("--n-trials", type=int, default=None,
                        help="Override trial count per task (e.g., --n-trials 40)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_all_tasks(
        base_url=args.base_url,
        agent_name=args.agent_name,
        model_name=args.model,
        no_deadline=not args.use_deadline,
        task_timeout=args.task_timeout,
        tasks_filter=args.tasks,
        n_trials=args.n_trials,
    )


if __name__ == "__main__":
    main()
