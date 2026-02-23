# CogArena

A benchmark that tests AI agents on interactive behavioral experiments through a web browser. Tasks are sampled widely across cognitive science — from attention and memory to decision-making, reinforcement learning, and social cognition.

Agents interact with real jsPsych experiments (the same framework used on Prolific/MTurk), and their behavioral data is scored across task completion, performance accuracy, and human-like behavioral signatures.

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

Visit [http://localhost:8000](http://localhost:8000) to see the benchmark site, browse tasks, and try experiments.

### Run Tests

```bash
pytest scoring/tests/ -v        # Scoring tests (49)
pytest harness/tests/ -v        # API integration tests (10)
```

## Tasks

| Task | Domain | Trials | Response | Key Behaviors |
|------|--------|--------|----------|---------------|
| Stroop | Perception & Attention | 96 | Keypress (d/f/j/k) | Stroop interference, post-error slowing, congruency sequence effect |
| 2-Armed Bandit | Exploration-Exploitation | 80 | Keypress (f/j) | Horizon-dependent exploration, win-stay, directed exploration |
| Risky Choice | Decision-Making | 60 | Keypress (f/j) | Risk aversion in gains, loss aversion framing, EV sensitivity |
| Trust Game | Social & Strategic | 15 | Slider (0-10) | Non-zero trust, reciprocity sensitivity, trustee adaptation |
| N-Back (2-back) | Memory & Learning | 120 | Keypress (f/j) | Above-chance discrimination, lure susceptibility, post-error slowing |

## Website

The benchmark site at `http://localhost:8000` includes:

- **Task Catalog** (`/catalog`) — browse all tasks with descriptions and parameters
- **Task Detail** (`/catalog/{task_id}`) — full task info and measured behaviors
- **Leaderboard** (`/leaderboard`) — ranked agent performance
- **Try It Yourself** (`/try`) — run any experiment in demo mode
- **API Docs** (`/docs`) — interactive OpenAPI documentation

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/info` | Server info and available endpoints |
| GET | `/api/health` | Health check |
| GET | `/api/tasks` | List all tasks with configuration |
| POST | `/api/sessions` | Create evaluation session |
| GET | `/api/sessions/{session_id}` | Check session status |
| POST | `/api/data/{session_id}/{task_id}` | Submit trial data |
| POST | `/api/evaluate/{session_id}` | Trigger scoring |
| GET | `/api/results/{session_id}` | Retrieve scorecard |
| GET | `/api/leaderboard` | Ranked agent results |

### Example: Full Evaluation Flow

```bash
# 1. Create session
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "My Agent", "scaffold": "computer-use", "model_name": "claude-sonnet-4"}'

# 2. Agent navigates to each task URL and completes the jsPsych experiment
#    jsPsych auto-submits trial data to /api/data/{session_id}/{task_id}

# 3. Trigger evaluation
curl -X POST http://localhost:8000/api/evaluate/{session_id}

# 4. Get results
curl http://localhost:8000/api/results/{session_id}
```

### Benchmark Runner CLI

```bash
# Create session and print task URLs (manual mode)
python -m harness.run_benchmark --agent-name "My Agent" --no-wait

# Create session, poll for completion, evaluate, print scorecard
python -m harness.run_benchmark --agent-name "My Agent" --scaffold "browser-use" --model "gpt-4o"
```

## Project Structure

```
cogarena/
├── harness/                    # FastAPI server & session management
│   ├── server.py               # API + website routes
│   ├── session_manager.py      # Session lifecycle
│   ├── config.py               # Settings (pydantic-settings)
│   ├── run_benchmark.py        # CLI benchmark runner
│   ├── db/models.py            # SQLAlchemy + Pydantic models
│   └── tests/                  # 10 integration tests
├── scoring/                    # Three-level grading pipeline
│   ├── level1_completion.py    # Task completion checks
│   ├── level2_accuracy.py      # Performance metrics vs human baselines
│   ├── level3_behavioral.py    # Statistical signature detection
│   ├── composite_score.py      # Weighted composite (0-100)
│   ├── score_session.py        # Scoring entry point
│   ├── analysis_templates/     # Statistical test implementations
│   ├── human_baselines/        # Reference stats per task
│   └── tests/                  # 49 scoring tests
├── templates/                  # Jinja2 website templates
│   ├── base.html               # Shared layout (nav, footer)
│   ├── index.html              # Landing page
│   ├── catalog.html            # Task catalog
│   ├── task_detail.html        # Individual task page
│   ├── leaderboard.html        # Leaderboard table
│   └── try.html                # Try It Yourself
├── static/                     # CSS and JS assets
├── tasks/                      # jsPsych experiments (auto-discovered)
│   ├── stroop/
│   ├── two_armed_bandit/
│   ├── risky_choice/
│   ├── trust_game/
│   └── n_back/
└── jsPsych-8.2.3/             # Vendored jsPsych library
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0-1 | Done | Stroop task, scoring pipeline, FastAPI server |
| 2 | Done | 4 new tasks (Bandit, Risky Choice, Trust Game, N-Back) |
| 3 | Done | Harness hardening, benchmark runner, integration tests |
| 4 | Done | Benchmark website, API readiness |
| 5 | Next | Test with AI agents via external services |
| 6 | Planned | Human baselines via Prolific |
| 7 | Planned | Expand to ~24 tasks across 6 cognitive domains |
