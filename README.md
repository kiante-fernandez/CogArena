# CogArena

A benchmark that tests whether AI agents can physically take interactive psychological experiments through a browser — combining TurkingBench's web-interaction approach with CogBench's cognitive science content in WebArena's self-hosted infrastructure.

Agents interact with real jsPsych experiments (the same framework used on Prolific/MTurk), and their behavioral data is scored on three levels: task completion, performance accuracy, and human-like behavioral signatures.

## Quick Start

### Prerequisites

- Python 3.11+

### Setup

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Server

```bash
uvicorn harness.server:app --reload --host 0.0.0.0 --port 8000
```

### Try a Task Manually

Open [http://localhost:8000/tasks/stroop/?session_id=debug](http://localhost:8000/tasks/stroop/?session_id=debug) in a browser.

### Run Tests

```bash
pytest scoring/tests/ -v
```

## How Evaluation Works

```
1. POST /api/sessions              → Create session, get task URLs
2. Agent navigates to each task URL → jsPsych experiment runs in browser
3. jsPsych auto-POSTs trial data   → /api/data/{session_id}/{task_id}
4. POST /api/evaluate/{session_id} → Triggers scoring pipeline
5. GET /api/results/{session_id}   → Returns three-level scorecard
```

## Scoring System

| Level | Name | Weight | What It Measures |
|-------|------|--------|------------------|
| L1 | Completion | 0.15 | Did the agent navigate instructions and respond on all trials? |
| L2 | Accuracy | 0.35 | How well did the agent perform? (% correct, d', RT) |
| L3 | Behavioral Signatures | 0.50 | Does behavior exhibit human cognitive patterns? |

**Composite Score** = (0.15 x L1 + 0.35 x L2 + 0.50 x L3) x 100

L3 is the novel contribution: no existing benchmark scores whether an agent's interactive behavior exhibits specific cognitive signatures (Stroop interference, post-error slowing, exploration bonuses, risk aversion, etc.).

## Tasks

| Task | Domain | Trials | Response | Key Signatures |
|------|--------|--------|----------|----------------|
| Stroop | Perception & Attention | 96 | Keypress (d/f/j/k) | Stroop interference, post-error slowing, congruency sequence effect |
| 2-Armed Bandit | Exploration-Exploitation | 80 | Keypress (f/j) | Horizon-dependent exploration, win-stay, directed exploration |
| Risky Choice | Decision-Making | 60 | Keypress (f/j) | Risk aversion in gains, loss aversion framing, EV sensitivity |
| Trust Game | Social & Strategic | 15 | Slider (0-10) | Non-zero trust, reciprocity sensitivity, trustee adaptation |
| N-Back (2-back) | Memory & Learning | 120 | Keypress (f/j) | Above-chance discrimination, lure susceptibility, post-error slowing |

## Project Structure

```
cogarena/
├── harness/                    # FastAPI server & session management
│   ├── server.py               # API endpoints
│   ├── session_manager.py      # Session lifecycle
│   ├── config.py               # Settings (pydantic-settings)
│   ├── run_benchmark.py        # CLI benchmark runner
│   └── db/models.py            # SQLAlchemy + Pydantic models
├── scoring/                    # Three-level grading pipeline
│   ├── level1_completion.py    # L1: task completion checks
│   ├── level2_accuracy.py      # L2: performance metrics vs human baselines
│   ├── level3_behavioral.py    # L3: statistical signature detection
│   ├── composite_score.py      # Weighted composite (0-100)
│   ├── score_session.py        # CLI scoring entry point
│   ├── analysis_templates/     # Statistical test implementations
│   │   ├── paired_ttest.py
│   │   ├── proportion_test.py
│   │   ├── correlation_test.py
│   │   ├── sequential_regression.py
│   │   └── interaction_test.py
│   ├── human_baselines/        # JSON reference stats per task
│   └── tests/                  # 49 tests with synthetic data generators
├── tasks/                      # jsPsych experiments (auto-discovered)
│   ├── stroop/
│   ├── two_armed_bandit/
│   ├── risky_choice/
│   ├── trust_game/
│   └── n_back/
└── jsPsych-8.2.3/             # Vendored jsPsych library
```

Each task follows a standard structure:
```
task_name/
├── index.html              # Entry point loading jsPsych
├── experiment.js           # Full experiment logic
├── task_config.json        # Parameters, response type, required fields
└── scoring/
    ├── level2_metrics.json # Accuracy metrics with human baselines
    └── level3_signatures.json # Behavioral signature test specs
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/sessions` | Create evaluation session |
| GET | `/api/sessions/{session_id}` | Check session status and task completion |
| POST | `/api/data/{session_id}/{task_id}` | Submit jsPsych trial data |
| POST | `/api/evaluate/{session_id}` | Trigger scoring pipeline |
| GET | `/api/results/{session_id}` | Retrieve scorecard |
| GET | `/api/leaderboard` | Ranked agent results |

### Create Session

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "Claude Sonnet 4", "scaffold": "computer-use", "model_name": "claude-sonnet-4"}'
```

Returns:
```json
{
  "session_id": "abc-123",
  "tasks": [
    {"task_id": "stroop", "url": "/tasks/stroop/?session_id=abc-123", "completed": false},
    ...
  ],
  "status": "created"
}
```

## Benchmark Runner

```bash
# Create session and print task URLs (manual mode)
python -m harness.run_benchmark --agent-name "My Agent" --no-wait

# Create session, poll for completion, evaluate, print scorecard
python -m harness.run_benchmark --agent-name "My Agent" --scaffold "browser-use" --model "gpt-4o"
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0-1 | Done | Stroop task, scoring pipeline, FastAPI server, 15 tests |
| 2 | Done | 4 new tasks (Bandit, Risky Choice, Trust Game, N-Back), 49 tests |
| 3 | Done | README, harness hardening, benchmark runner, integration tests |
| 4 | Next | Test with AI agents (Claude computer use, Browser-Use + GPT-4o) |
| 5 | Planned | Human baselines via Prolific (N=100/task) |
| 6 | Planned | Expand to ~24 tasks across 6 cognitive domains |
| 7 | Planned | Website, leaderboard, public deployment |
