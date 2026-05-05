# CogArena

A benchmark that tests AI agents on interactive behavioral experiments through a web browser. 40 tasks span perception, attention, decision-making, reinforcement learning, exploration, memory, social cognition, language, and more.

Agents interact with real jsPsych experiments (the same framework used on Prolific/MTurk), and their behavioral data is scored across three levels: task completion, performance accuracy, and human-like behavioral signatures.

**Paper scope (v1 launch set, 10 tasks):** the accompanying paper introduces and evaluates a curated 10-task subset — `random_dot_motion_v2`, `grid_bandit`, `marbles_risk`, `repeated_games`, `serial_recall_v2`, `visual_recognition`, `effort_foraging`, `tiny_alchemy`, `moral_machine`, `phishing_detection_v2` — chosen to span the seven cognitive domains covered by the full catalog. The remaining 30 tasks are provided as a community catalog and are not evaluated in the paper. To reproduce the paper's tables see [REPRODUCING.md](REPRODUCING.md).

## Quick Start

### Prerequisites

- Python 3.11+

### Setup

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install pinned dependencies (reproducible)
pip install -r requirements-lock.txt

# Optional: agent runtime (browser-use 0.9.5 + playwright)
pip install -e .[agents]
playwright install chromium
```

For loose minimum-version installs use `requirements.txt`. To reproduce the paper's tables exactly, use `requirements-lock.txt` and follow [REPRODUCING.md](REPRODUCING.md).

### Run the Server

```bash
uvicorn harness.server:app --reload --host 0.0.0.0 --port 8000
```

Visit [http://localhost:8000](http://localhost:8000) to see the benchmark site, browse tasks, and try experiments.

### Run Tests

```bash
pytest scoring/tests/ harness/tests/ -v
```

Expected: 374 passed (313 scoring + 10 harness unit + 51 field-alignment).

## Tasks (50)

The catalog includes 50 task directories: 47 unique cognitive paradigms plus three v2 revisions (`phishing_detection_v2`, `random_dot_motion_v2`, `serial_recall_v2`) used in the paper's v1 launch set. The table below lists the 40 originally-documented tasks; the additions (`effort_foraging`, `grid_bandit`, `marbles_risk`, `moral_machine`, `repeated_games`, `tiny_alchemy`, `visual_recognition`, plus the three v2 revisions) extend the catalog and are browseable at [`/catalog`](https://cog-arena.vercel.app/catalog) on the live site.


| Task | Description |
|------|-------------|
| BART | Inflate balloons for rewards with risk of popping |
| Category Learning | Classify stimuli into categories based on binary features |
| Causal Reasoning | Choose between mines and judge hidden agent interventions |
| Confirmation Bias RL | Two-armed bandit with partial vs complete feedback |
| Context Effects | Three-option choice with decoys (attraction/compromise) |
| Contingency Judgment | Judge causal strength from observed co-occurrences |
| Decisions from Experience | Sample from options before making a final choice |
| Dictator Game | Allocate money between yourself and anonymous partners |
| Flanker | Identify central arrow direction while ignoring flankers |
| Function Estimation | Estimate underlying function from scatterplot data via slider |
| Go/No-Go | Respond to go stimuli while withholding to no-go stimuli |
| Heuristics & Biases | Predict outcomes from multiple cue attributes |
| Insider Attack | Select targets to attack while avoiding monitoring |
| Intertemporal Choice | Choose between smaller-sooner and larger-later rewards |
| Iowa Gambling Task | Choose from four decks with different reward/punishment |
| Lexical Decision | Classify letter strings as real words or nonwords |
| Loss Aversion | Accept or reject mixed gambles with gains and losses |
| Magnitude RL | Two-armed bandit with varying reward magnitudes |
| Moral Judgment | Forced-choice moral dilemmas (autonomous vehicle scenarios) |
| N-Back (2-back) | Respond when current letter matches the one 2 back |
| Navon Global/Local | Identify letters at global or local level of hierarchical stimuli |
| Novelty Exploration | Choose between novel and familiar options for rewards |
| Observe or Bet | Choose to observe (free info) or guess to earn/lose points |
| Phishing Detection | Classify emails as legitimate or phishing with feedback |
| Prisoner's Dilemma | Repeated cooperation-defection game against tit-for-tat |
| Probabilistic Classification | Predict outcomes from probabilistic cue combinations |
| Probability Learning | Repeated binary choice with asymmetric reward probabilities |
| Public Goods Game | Contribute to shared pool with simulated co-players |
| Random Dot Motion | Compare dot arrays to identify which has more dots |
| Restless Bandit | Two-armed bandit with drifting reward distributions |
| Reversal Learning | Learn rewarded stimulus, then adapt after reversal |
| Risky Choice | Binary choices between safe and risky options |
| Safe Exploration | Choose between safe and risky options across zones |
| Serial Recall | Study word lists and recall them in order |
| Simple/Choice RT | Respond to stimuli under 1, 2, or 4 alternatives |
| Stroop | Name ink color of color words, ignoring word meaning |
| Trust Game | Investment game with partners of varying trustworthiness |
| Two-Armed Bandit | Explore-exploit tradeoff with horizon manipulation |
| Two-Step Task | Two-stage Markov decision task with common/rare transitions |
| Ultimatum Game | Propose and respond to monetary offers |

## Running Agents

CogArena includes three reference agents: a random baseline, a Browser-Use LLM agent, and an OpenHands Docker-based agent. The recommended entry point is `agents.runner`, which handles server startup, session creation, agent execution, and scoring.

### Agent Runner (recommended)

```bash
# Run browser-use agent on all v1 tasks (starts server automatically)
python -m agents.runner --agent browser-use --model google/gemini-3-flash-preview --start-server

# Run on specific tasks only
python -m agents.runner --agent browser-use --model google/gemini-3-flash-preview --start-server --tasks marbles_risk grid_bandit

# Skip tasks already scored for this (model, scaffold) pair
python -m agents.runner --agent browser-use --model anthropic/claude-sonnet-4.6 --start-server --skip-scored

# Run random baseline (no API key needed)
python -m agents.runner --agent random --start-server
```

Models containing `/` (e.g. `google/gemini-3-flash-preview`, `anthropic/claude-sonnet-4.6`) are routed through [OpenRouter](https://openrouter.ai/) (requires `OPENROUTER_API_KEY`). Direct provider IDs without `/` (e.g. `gpt-5`, `claude-sonnet-4-6`) use native provider SDKs and require the matching provider API key. The registry of vetted models is in [harness/models.yaml](harness/models.yaml).

For sweeps across many (model, task, repeat) cells, use the harness CLI directly:

```bash
python -m harness sweep --suite harness/suites/pilot_v1.yaml --max-parallel 4
```

### Browser-Use Agent (direct)

Requires the [browser-use](https://github.com/browser-use/browser-use) package and an API key for your chosen provider.

```bash
pip install browser-use
python -m agents.browser_use_agent --base-url http://localhost:8000 --model o3
```

### OpenHands Agent

Requires [OpenHands](https://github.com/All-Hands-AI/OpenHands) with Docker for sandboxed browser control.

```bash
python -m agents.openhands_agent --base-url http://localhost:8000 --model anthropic/claude-sonnet-4
```

### Random Baseline Agent

No dependencies beyond core requirements. Presses random valid keys on each trial.

```bash
python -m agents.random_agent --base-url http://localhost:8000 -v
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
| PATCH | `/api/data/{session_id}/{task_id}` | Incrementally save partial trial data |
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
│   ├── runner.py               # Orchestrator CLI (start server, run agent, evaluate)
│   ├── random_agent.py         # Random baseline (no LLM)
│   ├── browser_use_agent.py    # Browser-Use LLM agent (multi-provider)
│   └── openhands_agent.py      # OpenHands Docker-based agent
├── harness/                    # FastAPI server, eval CLI, sweep runner
│   ├── server.py               # API + website routes
│   ├── cli.py                  # `python -m harness {eval,sweep,replay}` entry
│   ├── eval.py                 # Single (model × tasks) run with raw-data archive
│   ├── sweep.py                # Multi-(model, task, repeat) parallel sweep
│   ├── replay.py               # Self-contained HTML replay builder
│   ├── session_manager.py      # Session lifecycle
│   ├── config.py               # Settings (pydantic-settings)
│   ├── suites/                 # Reproducible run definitions (pilot_v1.yaml etc.)
│   ├── db/models.py            # SQLAlchemy + Pydantic models
│   └── tests/                  # Integration + field alignment tests
├── scoring/                    # Three-level grading pipeline
│   ├── level1_completion.py    # Task completion checks
│   ├── level2_accuracy.py      # Performance metrics vs human baselines
│   ├── level3_behavioral.py    # Statistical signature detection
│   ├── composite_score.py      # Weighted composite (0-100)
│   ├── score_session.py        # Scoring entry point
│   ├── analysis_templates/     # Statistical test implementations
│   ├── human_baselines/        # Reference stats per task (40 files)
│   └── tests/                  # Scoring tests
├── templates/                  # Jinja2 website templates
├── static/                     # CSS, JS, and skill.md
├── tasks/                      # 40 jsPsych experiments (auto-discovered)
│   └── {task_id}/              # Each task contains:
│       ├── index.html          #   HTML entry point
│       ├── experiment.js       #   jsPsych experiment
│       ├── task_config.json    #   Metadata and parameters
│       └── scoring/            #   level2_metrics.json,
│                               #   level3_signatures.json
├── run_study.sh                # Full-study runner (all models × tasks × frameworks)
├── results/                    # Tracked reference results: floor + pilot CSVs, example replay
└── jsPsych-8.2.3/              # Vendored jsPsych library
```

## Psych-101/201 Overlap

30 of CogArena's 40 tasks have direct counterparts in [Psych-101](https://huggingface.co/datasets/marcelbinz/Psych-101) or [Psych-201](https://github.com/marcelbinz/Psych-201), enabling direct comparison of LLM behavior in text-transcript vs. interactive-browser settings.

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
| Loss Aversion | — | `spektor2024lossaversion` |
| Context Effects | — | `spektor2019contexteffects` |
| Moral Judgment | — | `awad2018moral` |
| Confirmation Bias RL | — | `palminteri2017confirmation` |
| Magnitude RL | — | `bavard2018magnitude` |
| Probability Learning | — | `thoma2025problearn` |
| Novelty Exploration | — | `nussenbaum2023novelty` |
| Safe Exploration | — | `witte2024safe_exploration` |
| Observe or Bet | — | `anvari2024observe_bet` |
| Random Dot Motion | — | `pirrone_2018_dots` |
| Lexical Decision | — | `guenther2020LDT` |
| Heuristics & Biases | — | `binz2022heuristics` |
| Phishing Detection | — | `singh2019phishing` |
| Causal Reasoning | — | `cohen2020causal` |
| Insider Attack | — | `aggarwal2023iag` |
| Function Estimation | — | `little2024functionestimation` |

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0-1 | Done | Stroop task, scoring pipeline, FastAPI server |
| 2 | Done | 4 new tasks (Bandit, Risky Choice, Trust Game, N-Back) |
| 3 | Done | Harness hardening, benchmark runner, integration tests |
| 4 | Done | Benchmark website, API readiness |
| 5 | Done | 5 new tasks (Go/No-Go, Flanker, IGT, Dictator, Reversal Learning) — 10 total |
| 6 | Done | Agent evaluation framework, reference agents |
| 7 | Done | 14 new tasks — 24 total, multi-provider agent support |
| 8 | Done | 16 new tasks from Psych-201 — 40 total |
| 9 | In Progress | Run AI agent evaluations across models and frameworks |
| 10 | Planned | Human baselines via Prolific |

## Citation

```bibtex
@article{cogarena2025,
  title={CogArena: Benchmarking AI Agents on Interactive Cognitive Experiments},
  year={2026}
}
```
