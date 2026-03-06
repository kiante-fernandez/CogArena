"""
CogArena Random Baseline Agent

A Playwright-based agent that presses random valid keys on each trial.
No LLM call — used for testing the benchmark pipeline end-to-end and
as a chance-level baseline for scoring comparisons.

Usage:
    python -m agents.random_agent --base-url http://localhost:8000
"""
import asyncio
import json
import logging
import random
import time

import httpx
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

# Task-specific valid keys (from task_config.json files)
TASK_KEYS = {
    # Original 10 tasks
    "stroop": ["d", "f", "j", "k"],
    "flanker": ["f", "j"],
    "go_nogo": ["f"],
    "n_back": ["f", "j"],
    "reversal_learning": ["f", "j"],
    "iowa_gambling": ["d", "f", "j", "k"],
    "two_armed_bandit": ["f", "j"],
    "risky_choice": ["f", "j"],
    "trust_game": [],       # Slider task
    "dictator_game": [],    # Slider task
    # New tasks (Phase 7)
    "intertemporal_choice": ["f", "j"],
    "two_step": ["f", "j"],
    "decisions_from_experience": ["f", "j", " "],  # F/J for deck choice, SPACE to stop sampling
    "prisoners_dilemma": ["f", "j"],
    "probabilistic_classification": ["f", "j"],
    "category_learning": ["f", "j"],
    "restless_bandit": ["f", "j"],
    "serial_recall": [],    # Button response task
    "ultimatum_game": ["f", "j"],  # Mixed: slider (proposer) + keypress (responder)
    "public_goods": [],     # Slider task
    "contingency_judgment": [],  # Slider task (ratings)
    "simple_choice_rt": ["d", "f", "j", "k", " "],  # SPACE for simple, D/F/J/K for choice
    "bart": ["f", "j"],
    "navon": ["f", "j"],
    # New tasks (Phase 8)
    "loss_aversion": ["f", "j"],
    "context_effects": ["d", "f", "j"],
    "moral_judgment": ["f", "j"],
    "confirmation_bias_rl": ["f", "j"],
    "magnitude_rl": ["f", "j"],
    "probability_learning": ["f", "j"],
    "novelty_exploration": ["f", "j"],
    "safe_exploration": ["f", "j"],
    "observe_or_bet": ["f", "j", "k"],
    "random_dot_motion": ["f", "j"],
    "lexical_decision": ["f", "j"],
    "heuristics_biases": ["f", "j"],
    "phishing_detection": ["f", "j"],
    "causal_reasoning": ["f", "j"],
    "insider_attack": ["f", "j"],
    "function_estimation": [],  # Slider task
}

SLIDER_TASKS = {
    "trust_game", "dictator_game", "function_estimation",
    "public_goods", "contingency_judgment", "serial_recall",
}


async def wait_for_jspsych_content(page: Page, timeout: float = 30.0):
    """Wait until #jspsych-content has visible content."""
    await page.wait_for_selector("#jspsych-content", state="attached", timeout=timeout * 1000)


async def detect_state(page: Page) -> str:
    """Classify the current jsPsych page state."""
    return await page.evaluate("""() => {
        const content = document.querySelector('#jspsych-content');
        if (!content) return 'loading';
        const text = content.innerText || '';

        // Task complete
        if (text.includes('Task Complete') || text.includes('data has been submitted') ||
            text.includes('You have completed')) return 'complete';

        // Instruction page (has Next button)
        if (document.querySelector('#jspsych-instructions-next') ||
            document.querySelector('.jspsych-instructions-nav')) return 'instruction';

        // Slider trial
        if (document.querySelector('#jspsych-html-slider-response-response')) return 'slider';

        // Fixation cross
        const stimulus = content.querySelector('.jspsych-html-keyboard-response-stimulus');
        if (stimulus) {
            const stimText = stimulus.innerText || '';
            if (stimText.trim() === '+' || stimulus.querySelector('.fixation')) return 'fixation';
        }

        // Forced trial (two-armed bandit) — must detect before generic stimulus
        if (text.includes('Forced Trial') || text.includes('must pick the highlighted')) return 'forced';

        // Feedback or auto-advancing screens (NO_KEYS)
        if (text.includes('Correct') || text.includes('Incorrect') || text.includes('Too slow') ||
            text.includes('No response') || text.includes('arm: +')) return 'feedback';

        // Keyboard trial with choices
        const display = document.querySelector('.jspsych-display-element');
        if (display) {
            const kbStim = document.querySelector('#jspsych-html-keyboard-response-stimulus');
            if (kbStim) return 'stimulus';
        }

        // If there's content but we can't classify it, it might be a stimulus
        if (text.trim().length > 0) return 'stimulus';

        return 'waiting';
    }""")


async def handle_instruction(page: Page):
    """Click Next on instruction pages."""
    btn = page.locator("#jspsych-instructions-next")
    if await btn.count() > 0:
        await btn.click()
        return

    # Some instructions use a generic button
    nav_btn = page.locator(".jspsych-instructions-nav button").last
    if await nav_btn.count() > 0:
        await nav_btn.click()


async def handle_slider(page: Page, task_id: str):
    """Set a random slider value and click submit."""
    slider = page.locator("#jspsych-html-slider-response-response")
    if await slider.count() == 0:
        return

    # Get slider range
    slider_min = await slider.evaluate("el => parseInt(el.min) || 0")
    slider_max = await slider.evaluate("el => parseInt(el.max) || 10")
    value = random.randint(slider_min, slider_max)

    # Set value and dispatch change event (needed for require_movement)
    await page.evaluate(f"""() => {{
        const slider = document.querySelector('#jspsych-html-slider-response-response');
        slider.value = {value};
        slider.dispatchEvent(new Event('input', {{bubbles: true}}));
        slider.dispatchEvent(new Event('change', {{bubbles: true}}));
    }}""")

    # Click submit
    submit = page.locator("#jspsych-html-slider-response-next")
    if await submit.count() > 0:
        await submit.click()


async def handle_forced(page: Page):
    """Handle forced-choice trials (two-armed bandit) by pressing the highlighted arm's key."""
    forced_key = await page.evaluate("""() => {
        const arms = document.querySelectorAll('.bandit-arm');
        for (const arm of arms) {
            const style = arm.getAttribute('style') || '';
            // The forced arm has border-color; the other has opacity:0.4
            if (style.includes('border-color') || !style.includes('opacity')) {
                return arm.classList.contains('left') ? 'f' : 'j';
            }
        }
        return 'f';
    }""")
    await page.keyboard.press(forced_key)


async def handle_stimulus(page: Page, task_id: str):
    """Press a random valid key for the current task."""
    keys = TASK_KEYS.get(task_id, ["f"])
    if not keys:
        # Slider tasks still need key presses for "Press any key" screens
        await page.keyboard.press(" ")
        return
    key = random.choice(keys)
    await page.keyboard.press(key)


async def run_task(page: Page, task_url: str, task_id: str, timeout: float = 600.0):
    """Run a single task to completion."""
    logger.info("Starting task: %s", task_id)
    await page.goto(task_url, wait_until="networkidle")
    await wait_for_jspsych_content(page)

    start = time.time()
    prev_state = None
    stuck_count = 0

    while time.time() - start < timeout:
        state = await detect_state(page)

        if state != prev_state:
            logger.debug("Task %s: state=%s (was %s)", task_id, state, prev_state)

        if state == "complete":
            logger.info("Task %s complete", task_id)
            # Wait for auto-submission
            await asyncio.sleep(2)
            return True

        if state == prev_state:
            stuck_count += 1
            if stuck_count > 50:
                # Try pressing a key to unstick
                keys = TASK_KEYS.get(task_id, ["f"])
                if keys:
                    await page.keyboard.press(random.choice(keys))
                stuck_count = 0
        else:
            stuck_count = 0
        prev_state = state

        if state == "instruction":
            await handle_instruction(page)
            await asyncio.sleep(0.3)
        elif state == "slider":
            await handle_slider(page, task_id)
            await asyncio.sleep(0.3)
        elif state == "forced":
            await handle_forced(page)
            await asyncio.sleep(0.1)
        elif state == "stimulus":
            await handle_stimulus(page, task_id)
            await asyncio.sleep(0.1)
        elif state in ("fixation", "feedback", "waiting"):
            await asyncio.sleep(0.2)
        elif state == "loading":
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(0.2)

    logger.warning("Task %s timed out after %.0fs", task_id, timeout)
    return False


async def run_all_tasks(
    base_url: str = "http://localhost:8000",
    agent_name: str = "RandomAgent",
    no_deadline: bool = True,
    task_timeout: float = 600.0,
    tasks_filter: list[str] | None = None,
):
    """Run the random agent through all CogArena tasks."""
    client = httpx.Client(base_url=base_url, timeout=30.0)

    # Health check
    resp = client.get("/api/health")
    resp.raise_for_status()

    # Create session
    resp = client.post("/api/sessions", json={
        "agent_name": agent_name,
        "scaffold": "random",
        "model_name": "none",
        "observation_mode": "dom",
    })
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]
    logger.info("Session created: %s", session_id)

    tasks = session["tasks"]
    if tasks_filter:
        tasks = [t for t in tasks if t["task_id"] in tasks_filter]
    logger.info("Tasks to complete: %d", len(tasks))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        completed = []
        failed = []

        for task_info in tasks:
            task_id = task_info["task_id"]
            url = f"{base_url}{task_info['url']}"
            if no_deadline:
                url += "&no_deadline=true"

            success = await run_task(page, url, task_id, timeout=task_timeout)
            if success:
                completed.append(task_id)
            else:
                failed.append(task_id)

        await browser.close()

    logger.info("Completed: %d/%d tasks", len(completed), len(tasks))
    if failed:
        logger.warning("Failed: %s", ", ".join(failed))

    # Check if auto-evaluation ran
    status = client.get(f"/api/sessions/{session_id}").json()
    if status["status"] == "scored":
        logger.info("Auto-evaluation completed")
    else:
        # Manually trigger evaluation if not all tasks completed
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
    parser = argparse.ArgumentParser(description="CogArena Random Baseline Agent")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--agent-name", default="RandomAgent")
    parser.add_argument("--no-deadline", action="store_true", default=True,
                        help="Remove response deadlines (default: True)")
    parser.add_argument("--use-deadline", action="store_true",
                        help="Keep original response deadlines")
    parser.add_argument("--task-timeout", type=float, default=600.0,
                        help="Max seconds per task (default: 600)")
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
        no_deadline=no_deadline,
        task_timeout=args.task_timeout,
    ))


if __name__ == "__main__":
    main()
