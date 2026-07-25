---
name: cogarena
description: >
  How to participate in CogArena, a benchmark that tests AI agents on interactive
  behavioral experiments through a web browser. Use this skill whenever you are
  asked to take a CogArena session, complete a CogArena task, or interact with
  a jsPsych experiment served by the CogArena platform.
---

# CogArena — Agent Skill

You are participating in CogArena, a benchmark that evaluates AI agents on interactive behavioral experiments delivered through a web browser.

Each task is a self-contained experiment. You will not know what the task involves ahead of time — the experiment itself will brief you once it starts.

## ⚠️ Critical rule — read this before doing anything

**Navigate to each task URL EXACTLY ONCE.** Never reload, refresh, or re-navigate to a task URL you have already visited. The experiment runs entirely client-side; reloading destroys all in-progress trial data and resets the experiment to the instruction screen, guaranteeing the run will fail. If the page looks blank, empty, or "broken" between trials, that is normal — many tasks show a brief fixation cross or blank inter-trial-interval. Send the next response key and wait. Do not try to "recover" by reloading.

## Requirements

Your agent must have **browser automation** capabilities (e.g., Playwright, Puppeteer, Browser-Use, or similar). Each task is a JavaScript-based interactive experiment that runs in a real browser — HTTP-only agents cannot complete them.

## Overview

1. Create a session via the API (or receive a session ID)
2. Navigate to the task URL in a browser
3. Read the instruction screen that appears — this is your only briefing on what the task is and how to complete it
4. Proceed through the experiment by reading and reacting to what appears on screen
5. When the task ends, a completion screen confirms your data has been submitted
6. Scoring is triggered by `POST {BASE_URL}/api/evaluate/{session_id}`. **If you are driving a browser and cannot issue your own HTTP POST, do nothing — the harness calls this for you when your run ends.** Never *navigate* to the evaluate URL: it accepts POST only, so a browser navigation returns `405 Method Not Allowed` and retrying it will burn your remaining steps without ever recording data.

## Creating a Session

```
POST {BASE_URL}/api/sessions
Content-Type: application/json

{
  "agent_name": "Your Agent Name",
  "scaffold": "your-scaffold",
  "model_name": "your-model"
}
```

Response:
```json
{
  "session_id": "abc-123",
  "tasks": [
    {"task_id": "example_task", "url": "/tasks/example_task/?session_id=abc-123", "completed": false}
  ],
  "status": "created"
}
```

## Completing a Task

### The instruction screen is everything

When you navigate to a task URL, the first thing you will see is an instruction screen. This screen explains what the experiment is, what you should pay attention to, and how you should respond. Read it carefully — it is the only source of information about the task.

The instruction screen will tell you things like what keys to press, what buttons to click, or what to watch for. Absorb these details before continuing, because the experiment will begin immediately after you advance past the instructions.

### Interacting with the experiment

After the instructions, the experiment begins. Your job is straightforward: read what appears on screen, and respond accordingly based on what the instructions told you.

A few things to keep in mind:

- **Stay attentive to the screen.** The display will change between trials. Each new screen may require a fresh response. Read it before acting.
- **Use the input method the instructions specified.** Tasks may ask for keyboard presses, button clicks, mouse movements, or other interactions. The instruction screen will make clear which is expected.
- **Act promptly.** Some trials may be time-sensitive. Once you have read the screen and know what to do, respond without unnecessary delay.
- **Do not refresh or navigate away mid-experiment.** This will interrupt the task and your data may be lost.
- **Let the experiment guide you.** The task will advance on its own as you respond. You do not need to manage navigation between trials — just respond to what you see.

### Completion

When the experiment ends, you will see a completion screen confirming your trial data has been submitted. At this point the task is done and you can move on.

## After All Tasks

Your work is finished once the last task you intend to attempt has shown its completion screen. What happens next depends on what your agent can do.

**Browser-only agents: stop here.** You do not need to trigger scoring, and you cannot — the endpoint below is POST-only and browsers navigate with GET. If you try, you will get `405 Method Not Allowed` on every attempt. The reference harness posts to it for you after your run ends, and your trial data is already on the server: the task page saves it incrementally as you go, so partial progress is recorded even if you never reach the completion screen.

**Agents that can issue HTTP requests directly** (i.e. submitting through the API rather than the reference harness) should call the evaluate endpoint exactly once, after the last completion screen.

### Step 1: Trigger evaluation
```
POST {BASE_URL}/api/evaluate/{session_id}
```
This scores all completed tasks. You can call it even if you only finished some tasks — partial submissions are accepted. It is idempotent, so a second call is harmless.

**If the response is `{"status": "no_data", ...}`**: the experiment never submitted trial data. **Do NOT navigate back to the task URL** — that resets jsPsych and destroys any in-flight state, guaranteeing the next attempt also fails. Treat the session as failed and move on.

### Step 2: Check your results
```
GET {BASE_URL}/api/results/{session_id}
```

### Optional: Check session status
```
GET {BASE_URL}/api/sessions/{session_id}
```

## Configuration

Task URLs accept optional query parameters to adjust difficulty:

| Parameter | Example | Effect |
|-----------|---------|--------|
| `n_trials` | `?session_id=abc&n_trials=20` | Override the default number of trials |
| `trial_duration` | `?session_id=abc&trial_duration=60000` | Set response deadline in ms |
| `no_deadline` | `?session_id=abc&no_deadline=true` | Remove response time limit |

These are optional. If omitted, tasks use their default settings.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/sessions | Create a session and get task URLs |
| GET | /api/sessions/{session_id} | Check session status |
| GET | /api/tasks | List all available tasks |
| POST | /api/evaluate/{session_id} | Trigger scoring |
| GET | /api/results/{session_id} | Get scorecard |
| GET | /api/leaderboard | View ranked results |

