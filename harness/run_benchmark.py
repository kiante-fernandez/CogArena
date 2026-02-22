"""
CogArena Benchmark Runner

Usage:
    # Create session and print task URLs (don't wait)
    python -m harness.run_benchmark --agent-name "My Agent" --no-wait

    # Create session, poll for completion, evaluate, print scorecard
    python -m harness.run_benchmark --agent-name "Claude Sonnet 4" \\
        --scaffold "computer-use" --model "claude-sonnet-4"
"""
import argparse
import sys
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description="CogArena Benchmark Runner")
    parser.add_argument("--agent-name", required=True, help="Name of the agent being evaluated")
    parser.add_argument("--scaffold", default=None, help="Scaffold/framework (e.g. computer-use, browser-use)")
    parser.add_argument("--model", default=None, help="Model name (e.g. claude-sonnet-4, gpt-4o)")
    parser.add_argument("--observation-mode", default=None, help="Observation mode (e.g. screenshot, dom, both)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Server base URL")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between status checks")
    parser.add_argument("--timeout", type=int, default=3600, help="Max seconds to wait for all tasks")
    parser.add_argument("--no-wait", action="store_true", help="Just create session and print URLs")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=30.0)

    # 1. Health check
    try:
        resp = client.get("/api/health")
        resp.raise_for_status()
    except httpx.ConnectError:
        print(f"Error: Cannot connect to {args.base_url}. Is the server running?")
        sys.exit(1)

    # 2. Create session
    resp = client.post("/api/sessions", json={
        "agent_name": args.agent_name,
        "scaffold": args.scaffold,
        "model_name": args.model,
        "observation_mode": args.observation_mode,
    })
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]

    print(f"Session created: {session_id}")
    print(f"\nTasks to complete ({len(session['tasks'])}):")
    for task in session["tasks"]:
        print(f"  {task['task_id']:20s} {args.base_url}{task['url']}")

    if args.no_wait:
        print(f"\nWhen all tasks are done, evaluate with:")
        print(f"  curl -X POST {args.base_url}/api/evaluate/{session_id}")
        print(f"  curl {args.base_url}/api/results/{session_id}")
        return

    # 3. Poll for completion
    total_tasks = len(session["tasks"])
    print(f"\nPolling for task completion (every {args.poll_interval}s, timeout {args.timeout}s)...")

    start = time.time()
    while time.time() - start < args.timeout:
        status = client.get(f"/api/sessions/{session_id}").json()
        completed = sum(1 for t in status["tasks"] if t.get("completed"))
        remaining = [t["task_id"] for t in status["tasks"] if not t.get("completed")]
        print(f"  [{completed}/{total_tasks}] Remaining: {', '.join(remaining) if remaining else 'none'}")
        if completed >= total_tasks:
            break
        time.sleep(args.poll_interval)
    else:
        print(f"\nTimeout after {args.timeout}s. Evaluating submitted tasks...")

    # 4. Evaluate
    print("\nTriggering evaluation...")
    resp = client.post(f"/api/evaluate/{session_id}")
    if resp.status_code == 404:
        print("Error: No task data found. Did the agent complete any tasks?")
        sys.exit(1)
    resp.raise_for_status()
    print("Evaluation complete.")

    # 5. Get and display results
    results = client.get(f"/api/results/{session_id}").json()

    print(f"\n{'=' * 65}")
    print(f"  COGARENA SCORECARD: {args.agent_name}")
    if args.scaffold:
        print(f"  Scaffold: {args.scaffold}")
    if args.model:
        print(f"  Model: {args.model}")
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


if __name__ == "__main__":
    main()
