# CogArena

A benchmark that tests AI agents on interactive behavioral experiments through a web browser. 24 tasks span 7 cognitive domains — perception & attention, decision-making, exploration-exploitation, reinforcement learning, memory & learning, social & strategic cognition, and causal reasoning.

Agents interact with real jsPsych experiments (the same framework used on Prolific/MTurk), and their behavioral data is scored across three levels: task completion, performance accuracy, and human-like behavioral signatures.

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
pytest scoring/tests/ -v        # Scoring tests
pytest harness/tests/ -v        # API + field alignment tests
```

## Tasks (24)

### Perception & Attention

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| Stroop | 96 | Keypress (d/f/j/k) | Stroop interference, post-error slowing, congruency sequence effect |
| Go/No-Go | 100 | Keypress (f) / Withhold | Response inhibition, commission vs omission errors, post-error slowing |
| Flanker | 96 | Keypress (f/j) | Flanker interference, accuracy cost, congruency sequence effect |
| Simple/Choice RT | 80 | Keypress (space/d/f/j/k) | Hick's Law (RT scales with log₂ alternatives), speed-accuracy tradeoff |
| Navon Global/Local | 80 | Keypress (f/j) | Global precedence, asymmetric interference, congruency effect |

### Decision-Making

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| Risky Choice | 60 | Keypress (f/j) | Risk aversion in gains, loss aversion framing, EV sensitivity |
| Iowa Gambling Task | 100 | Keypress (d/f/j/k) | Learning effect, above-chance advantageous choices, deck avoidance |
| Intertemporal Choice | 60 | Keypress (f/j) | Present bias, hyperbolic discounting, magnitude effect |
| Decisions from Experience | 20 | Keypress (f/j/space) | Description-experience gap, sampling frugality, recency |
| BART | 30 | Keypress (f/j) | Risk-taking above floor, post-pop adjustment, earnings above zero |

### Exploration-Exploitation

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| 2-Armed Bandit | 80 | Keypress (f/j) | Horizon-dependent exploration, win-stay, directed exploration |
| Restless Bandit | 100 | Keypress (f/j) | Above-chance tracking, win-stay/lose-shift, recency-weighted updating |

### Reinforcement Learning

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| Reversal Learning | 120 | Keypress (f/j) | Pre-reversal learning, perseveration, post-reversal recovery |
| Two-Step Task | 100 | Keypress (f/j) | Model-based index (reward × transition interaction), above-chance performance |
| Probabilistic Classification | 100 | Keypress (f/j) | Above-chance accuracy, learning curve, cue utilization |

### Memory & Learning

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| N-Back (2-back) | 120 | Keypress (f/j) | Above-chance discrimination, lure susceptibility, post-error slowing |
| Shepard Category Learning | 144 | Keypress (f/j) | Above-chance learning, rule complexity hierarchy, generalization |
| Serial Recall | 10 lists | Button click | Primacy effect, recency effect, U-shaped serial position curve |

### Social & Strategic

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| Trust Game | 15 | Slider (0-10) | Non-zero trust, reciprocity sensitivity, trustee adaptation |
| Dictator Game | 20 | Slider (0-10) | Non-zero giving, giving consistency, prosocial behavior |
| Prisoner's Dilemma | 50 | Keypress (f/j) | Above-chance cooperation, tit-for-tat, forgiveness |
| Ultimatum Game | 20 | Slider + Keypress | Fair offers (~40-50%), rejection of low offers, minimum acceptable offer |
| Public Goods Game | 10 | Slider (0-20) | Conditional cooperation, declining contributions, group sensitivity |

### Causal Reasoning

| Task | Trials | Response | Key Behaviors |
|------|--------|----------|---------------|
| Contingency Judgment | 80 obs + ratings | Slider (0-100) | ΔP sensitivity, outcome density bias, above-chance discrimination |

## Running Agents

CogArena includes two reference agents: a random baseline and a Browser-Use LLM agent.

### Random Baseline Agent

No dependencies beyond core requirements. Presses random valid keys on each trial.

```bash
python -m agents.random_agent --base-url http://localhost:8000 -v
```

### Browser-Use Agent (LLM-powered)

Requires the [browser-use](https://github.com/browser-use/browser-use) package and an API key for your chosen provider.

```bash
pip install browser-use

# OpenAI (requires OPENAI_API_KEY)
python -m agents.browser_use_agent --base-url http://localhost:8000 --model o3

# Google Gemini (requires GOOGLE_API_KEY)
python -m agents.browser_use_agent --base-url http://localhost:8000 --model gemini-flash-latest

# Anthropic Claude (requires ANTHROPIC_API_KEY)
python -m agents.browser_use_agent --base-url http://localhost:8000 --model claude-sonnet-4-20250514
```

### Scoring

All agents auto-submit data to the API. After tasks complete, scores appear at `/api/results/{session_id}` and on the leaderboard at `/leaderboard`.

## Website

The benchmark site at `http://localhost:8000` includes:

- **Leaderboard** (`/leaderboard`) — ranked agent performance
- **Try It Yourself** (`/try`) — run any experiment in demo mode
- **Submit** (`/submit`) — agent onboarding guide with skill file
- **Task Catalog** (`/catalog`) — browse all tasks with descriptions and parameters
- **Skill File** (`/skill.md`) — agent-readable instructions for completing the benchmark

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

## Scoring

Three-level evaluation with weighted composite (0–100):

| Level | Weight | What it measures |
|-------|--------|-----------------|
| L1 Completion | 0.15 | Did the agent respond to every trial with valid keys? |
| L2 Accuracy | 0.35 | How does performance compare to human baselines? |
| L3 Behavioral | 0.50 | Does the agent exhibit known cognitive signatures? |

L3 signatures are tested with standard statistical analyses (paired t-tests, proportion tests, correlations, interaction tests) against literature-derived effect sizes.

## Project Structure

```
cogarena/
├── agents/                     # Reference agent implementations
│   ├── random_agent.py         # Random baseline (no LLM)
│   └── browser_use_agent.py    # Browser-Use LLM agent (multi-provider)
├── harness/                    # FastAPI server & session management
│   ├── server.py               # API + website routes
│   ├── session_manager.py      # Session lifecycle
│   ├── config.py               # Settings (pydantic-settings)
│   ├── run_benchmark.py        # CLI benchmark runner
│   ├── db/models.py            # SQLAlchemy + Pydantic models
│   └── tests/                  # Integration + field alignment tests
├── scoring/                    # Three-level grading pipeline
│   ├── level1_completion.py    # Task completion checks
│   ├── level2_accuracy.py      # Performance metrics vs human baselines
│   ├── level3_behavioral.py    # Statistical signature detection
│   ├── composite_score.py      # Weighted composite (0-100)
│   ├── score_session.py        # Scoring entry point
│   ├── analysis_templates/     # Statistical test implementations
│   ├── human_baselines/        # Reference stats per task (24 files)
│   └── tests/                  # Scoring tests
├── templates/                  # Jinja2 website templates
├── static/                     # CSS, JS, and skill.md
├── tasks/                      # 24 jsPsych experiments (auto-discovered)
│   ├── stroop/                 # Each task contains:
│   ├── go_nogo/                #   index.html, experiment.js,
│   ├── flanker/                #   task_config.json,
│   ├── simple_choice_rt/       #   scoring/level2_metrics.json,
│   ├── navon/                  #   scoring/level3_signatures.json
│   ├── two_armed_bandit/
│   ├── restless_bandit/
│   ├── risky_choice/
│   ├── iowa_gambling/
│   ├── intertemporal_choice/
│   ├── decisions_from_experience/
│   ├── bart/
│   ├── reversal_learning/
│   ├── two_step/
│   ├── probabilistic_classification/
│   ├── n_back/
│   ├── category_learning/
│   ├── serial_recall/
│   ├── trust_game/
│   ├── dictator_game/
│   ├── prisoners_dilemma/
│   ├── ultimatum_game/
│   ├── public_goods/
│   └── contingency_judgment/
├── paper/                      # NeurIPS paper (LaTeX)
└── jsPsych-8.2.3/             # Vendored jsPsych library
```

## Psych-101/201 Overlap

14 of CogArena's 24 tasks have direct counterparts in the [Psych-101](https://huggingface.co/datasets/marcelbinz/Psych-101) or [Psych-201](https://github.com/marcelbinz/Psych-201) text-based datasets, enabling direct comparison of LLM behavior in text-transcript vs. interactive-browser settings.

| CogArena Task | Psych-101 | Psych-201 |
|---|---|---|
| Stroop | — | `busch2024_stroop` |
| Go/No-Go | `go_nogo` | — |
| 2-Armed Bandit | Multiple | `hartley2024`, `anvari2024` |
| Risky Choice | `risky_choice` | `frey2017`, `thoma2025` |
| Iowa Gambling | `iowa_gambling_task` | — |
| N-Back | `n_back` | — |
| Intertemporal Choice | `intertemporal_choice` | `haines2020` |
| Two-Step Task | `two_step_task` | Multiple |
| Decisions from Experience | `decisions_from_experience` | `frey2017dfe` |
| Prisoner's Dilemma | — | `akata2023` |
| Probabilistic Classification | `weather_prediction_task` | — |
| Shepard Category Learning | `shepard_categorization` | — |
| BART | `balloon_analog_risk_task` | — |
| Navon Global/Local | — | `busch2024_navon` |

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0-1 | Done | Stroop task, scoring pipeline, FastAPI server |
| 2 | Done | 4 new tasks (Bandit, Risky Choice, Trust Game, N-Back) |
| 3 | Done | Harness hardening, benchmark runner, integration tests |
| 4 | Done | Benchmark website, API readiness |
| 5 | Done | 5 new tasks (Go/No-Go, Flanker, IGT, Dictator, Reversal Learning) — 10 total |
| 6 | Done | Agent evaluation framework, reference agents |
| 7 | Done | 14 new tasks — 24 total across 7 domains, multi-provider agent support |
| 8 | Next | Run AI agent evaluations (Browser-Use + OpenAI/Gemini) |
| 9 | Planned | Human baselines via Prolific |

## Citation

```bibtex
@article{cogarena2025,
  title={CogArena: Benchmarking AI Agents on Interactive Cognitive Experiments},
  year={2025}
}
```
