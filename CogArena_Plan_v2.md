# CogArena: Implementation Plan v2

## 1. Vision

### One-Sentence Pitch

CogArena is a benchmark that tests whether AI agents can physically take interactive psychological experiments through a browser — combining TurkingBench's web-interaction approach with CogBench's cognitive science content in WebArena's self-hosted infrastructure.

### The Landscape and Where CogArena Fits

There are now several benchmarks testing AI on web-based tasks and on cognitive psychology tasks, but none that combine both:

**TurkingBench** (NAACL 2025, JHU): Takes real MTurk HIT pages (HTML) and tests whether AI agents can complete them via web interaction — clicking radio buttons, filling text boxes, etc. 158 tasks, 32.2K instances. Tasks are NLP annotation tasks (paraphrasing, sentiment analysis). The insight: crowdsourcing web pages designed for humans are a natural testbed for AI agents. **CogArena borrows this core insight but applies it to behavioral science experiments instead of NLP annotation tasks.**

**CogBench** (ICML 2024, Schulz group): Tests LLMs on 7 cognitive psychology experiments with 10 behavioral metrics. Bandits, two-step task, risky choice, etc. But it's entirely text-based — sends text prompts to LLMs via API. No browser, no visual stimuli, no real-time interaction. **CogArena takes CogBench's cognitive content but delivers it through interactive web experiments rather than text prompts.**

**WebArena** (NeurIPS 2023, CMU): Self-hosted web environments (Reddit clone, GitLab clone, shopping site, etc.) where agents complete productivity tasks via browser. 812 tasks. Binary pass/fail grading. **CogArena uses WebArena's self-hosted approach — we host our own jsPsych experiments rather than pointing agents at external sites.**

**Mind2Web / Online-Mind2Web** (NeurIPS 2023/COLM 2025, OSU): 2,350+ tasks across 137 live websites. Multi-level evaluation (completion rate + task success + efficiency). **CogArena adapts Mind2Web's multi-level evaluation structure for behavioral science: completion + accuracy + behavioral signatures.**

**Psych-101/201** (Binz, Schulz, et al.): Massive datasets of human behavioral data from psychological experiments, converted into text for LLM evaluation. 160+ experiments. **CogArena uses Psych-101/201 as our human baseline source but rebuilds the experiments as interactive web apps instead of text transcripts.**

| Benchmark | Content Domain | Agent Interface | Task Structure | Grading | Human Comparison |
|-----------|---------------|-----------------|----------------|---------|-----------------|
| **WebArena** | Web productivity (shop, code, forum) | Browser (screenshot + DOM) | Open-ended goals | Binary pass/fail | No |
| **Mind2Web** | Web tasks across 137 sites | Browser (screenshot + DOM) | Natural language instructions | Multi-level (CR + SR + efficiency) | No |
| **TurkingBench** | NLP annotation (MTurk HITs) | Browser (screenshot + HTML) | Structured web forms | Accuracy vs. crowdworker answers | Crowdworker answers as ground truth |
| **CogBench** | Cognitive psychology (7 exps) | Text API prompt | Text-based trial sequences | 10 behavioral metrics | Qualitative comparison |
| **Psych-101/201** | Cognitive psychology (160+ exps) | Text API prompt | Text-based trial sequences | Log-likelihood of human response | Direct via likelihoods |
| **CogArena** | Cognitive psychology (25+ exps) | Browser (screenshot + DOM) | Interactive jsPsych experiments | Multi-level (completion + accuracy + behavioral signatures) | Direct via same analysis pipelines |

### The Core Claim

CogArena is to behavioral science what TurkingBench is to NLP annotation: it takes web-based tasks originally designed for human participants and tests whether AI agents can complete them through the same interface. But because our tasks are controlled psychological experiments (not open-ended annotation), we can go beyond binary pass/fail to measure whether the agent's behavioral data exhibits the same cognitive signatures (Stroop interference, post-error slowing, exploration bonuses) that humans reliably produce.

### What CogArena Is NOT

- Not text-based evaluation (that's CogBench, Psych-101/201)
- Not general web productivity (that's WebArena, Mind2Web)
- Not NLP annotation tasks (that's TurkingBench)
- Not testing whether models "know" the right answer — testing whether they can physically take an experiment and produce human-like behavioral data

### Target Venues

- **Benchmark paper:** NeurIPS 2026 Datasets & Benchmarks Track
- **Behavioral analysis paper:** Psychological Review, Nature Human Behaviour, or Cognition

---

## 2. Architecture

### How It Maps to Existing Benchmarks

Every successful agent benchmark follows the same pattern. Here's how CogArena instantiates each component, with explicit references to how WebArena, TurkingBench, and Mind2Web handle the same component:

### 2.1 Task Environment

**WebArena:** Docker containers hosting self-built website clones (Reddit, GitLab, shopping, wiki, map). Self-hosted → full control, reproducible.

**TurkingBench:** Real HTML pages from MTurk, instantiated with different input values per instance. Each page has instructions + input fields (radio buttons, text boxes, checkboxes). Templates sourced from real crowdsourcing requesters.

**Mind2Web-Live:** Tasks on live external websites. Realistic but uncontrolled — sites change, break, add CAPTCHAs. Requires periodic revalidation.

**CogArena:** Self-hosted jsPsych experiments (like WebArena's Docker approach for control), but using the same technology that real behavioral science experiments use on Prolific/MTurk (like TurkingBench's real-HIT philosophy). Each task is a standalone HTML/JS web app running jsPsych v8.

```
tasks/
├── stroop/
│   ├── index.html              # Entry point, loads jsPsych
│   ├── experiment.js           # Full experiment logic
│   ├── task_config.json        # Parameters (n_trials, timing, conditions)
│   ├── README.md               # Citation, expected human behavior
│   └── scoring/
│       ├── level2_metrics.json # Accuracy metrics to compute
│       └── level3_signatures.json # Behavioral signatures to test
├── two_armed_bandit/
├── risky_choice/
├── trust_game/
├── n_back/
└── ... (25-30 tasks total)
```

**Key difference from TurkingBench:** TurkingBench tasks are one-shot — read instructions, fill in the form, done. Our tasks are multi-trial — the agent must stay on the page and respond to 50-200 sequential stimuli with controlled timing. This tests sustained interaction and sequential decision-making, not just page comprehension.

**Key difference from WebArena:** WebArena tasks require multi-step navigation across different pages and sites. Our tasks are single-page applications — the agent stays on one page and the experiment runs in place. Simpler navigation, but harder perceptual/timing demands.

### 2.2 Agent Interface

**WebArena:** Screenshot (1280×720) + accessibility tree. Actions: click[id], type[id][text], scroll[direction], etc.

**TurkingBench:** Two modes — (1) visual: agent sees rendered page screenshot, produces click/type actions; (2) textual: agent gets raw HTML, produces HTML modifications. Best models use both.

**Mind2Web:** Screenshot + DOM with key attributes. Actions: CLICK, TYPE, SCROLL, SELECT. Action cap (25 steps) to prevent infinite loops.

**CogArena:** Same as WebArena/Mind2Web — agents interact through any browser automation tool. Screenshot + DOM/accessibility tree. Actions are keypresses, mouse clicks, slider adjustments. We record the scaffold and model as separate dimensions, following HAL/Online-Mind2Web's convention (e.g., "Browser-Use + Claude Sonnet 4" vs "SeeAct + GPT-5").

**Observation modes we support and track:**

| Mode | What Agent Sees | Closest Analogy |
|------|----------------|-----------------|
| Screenshot only | Raw pixels of jsPsych experiment | WebArena screenshot mode |
| DOM / Accessibility Tree | Structured HTML elements + text | WebArena a11y tree mode |
| Screenshot + DOM | Both | TurkingBench "full" mode |

### 2.3 Evaluation Harness

**WebArena:** Python harness launches Docker environment → provides goal + initial screenshot → agent takes actions in loop → harness records trajectory → runs eval script checking end state.

**TurkingBench:** Framework that renders HTML page → sends to model (as screenshot or text) → receives model's proposed actions (click, type, etc.) → applies actions to HTML → checks modified HTML against ground truth answers.

**Mind2Web-Live:** WebCanvas framework manages browser sessions → records action sequences → evaluates against "key nodes" (intermediate states that must be reached).

**CogArena:** FastAPI server hosts jsPsych experiments → agent navigates to task URL → jsPsych handles all experimental logic (stimulus presentation, timing, data logging) → on experiment end, jsPsych auto-POSTs trial data to server → server runs scoring pipeline.

The critical simplification: **jsPsych does the heavy lifting.** Unlike WebArena where the harness must parse DOM state or check database rows, jsPsych already captures exactly the data we need (stimulus, response, RT, accuracy) in a structured JSON format. We just need to receive it and score it.

```
harness/
├── server.py           # FastAPI: hosts tasks, manages sessions, receives data
├── session_manager.py  # Tracks evaluation sessions, task assignments
└── db/
    ├── schema.sql      # PostgreSQL schema for sessions, results, leaderboard
    └── models.py       # SQLAlchemy/Pydantic models
```

**Evaluation session flow:**
```
1. Agent developer registers → gets API key + session_id
2. Server assigns task list (full benchmark or subset, each with unique random seed)
3. For each task:
   a. Agent navigates browser to task URL
   b. jsPsych shows instruction screens
   c. Agent reads instructions, clicks "Start"
   d. jsPsych runs trial loop (display stimulus → agent responds → log data → next)
   e. On experiment end, jsPsych POSTs trial data to server
4. POST /api/evaluate/{session_id} → triggers scoring pipeline
5. GET /api/results/{session_id} → returns full scorecard
```

### 2.4 Graders / Scoring

**WebArena:** Binary pass/fail. Programmatic checks — did the URL match? Did the database row change? Single score per task.

**TurkingBench:** Accuracy against crowdworker ground-truth answers. Per-field scoring. Aggregated by task and by field type.

**Mind2Web-Live:** Multi-level — Completion Rate (step-level, partial credit per key node) + Task Success Rate (all key nodes achieved) + Efficiency Score (penalizes redundant actions). This is the model we should follow.

**CogBench:** 10 behavioral metrics from 7 experiments. Metrics include: accuracy, risk aversion, loss aversion sensitivity, model-based index, directed exploration, random exploration, etc. Analyzed via multilevel regression. No formal scoring system — it's a phenotyping toolkit.

**CogArena:** Three-level continuous scoring, inspired by Mind2Web's multi-level approach but with behavioral science content like CogBench:

| Level | What It Measures | Analogous To | Weight |
|-------|-----------------|--------------|--------|
| **L1: Completion** (0-1) | Did the agent navigate instructions and respond on all trials? | Mind2Web Completion Rate | 0.15 |
| **L2: Accuracy** (0-1) | How well did the agent perform? (% correct, reward, d-prime) | WebArena pass/fail (but continuous), TurkingBench accuracy | 0.35 |
| **L3: Behavioral Alignment** (0-1) | Does behavior show human cognitive signatures? | CogBench behavioral metrics (but formalized as scoring) | 0.50 |

**Level 3 is the novel contribution.** No existing benchmark — in CS or psychology — scores whether an agent's interactive behavior exhibits specific cognitive signatures. CogBench measures behavioral metrics but doesn't formalize them into a scoring system. WebArena doesn't look at process at all.

Each task specifies its behavioral signatures in `level3_signatures.json`:

```json
{
  "task_id": "stroop",
  "signatures": [
    {
      "name": "stroop_interference_rt",
      "description": "RT on incongruent > RT on congruent",
      "test": "paired_ttest_greater",
      "group_a": {"filter": {"condition": "incongruent"}, "field": "rt"},
      "group_b": {"filter": {"condition": "congruent"}, "field": "rt"},
      "threshold_p": 0.05,
      "expected_direction": "a > b"
    },
    {
      "name": "post_error_slowing",
      "test": "sequential_regression",
      "predictor": {"field": "correct", "lag": 1, "invert": true},
      "outcome": {"field": "rt"},
      "expected_direction": "positive"
    }
  ]
}
```

Score per signature: 1.0 if detected (p < .05 in expected direction), 0.5 if right direction but not significant, 0.0 if absent or wrong direction.

**Composite CogArena Score = 0.15 × L1 + 0.35 × L2 + 0.50 × L3** (0-100 scale)

Plus domain subscores (Bandits, Decision, RL, Perception, Memory, Social).

### 2.5 Anti-Contamination

**LiveBench:** Releases new questions monthly from recent sources. Keeps 1/6 private.

**WebArena:** Self-hosted clones not in training data.

**TurkingBench:** Instantiates templates with different input values → diverse instances.

**CogArena:**
- Self-hosted (like WebArena) — experiments aren't crawlable external sites
- Stimulus randomization per session — trial orders, reward distributions, condition assignments generated from unique seed per evaluation (like TurkingBench's template instantiation)
- Paradigms are public (Stroop is Stroop) but specific configurations are not memorizable
- Community-contributed tasks expand the pool over time
- Knowing the "right answer" from text-based training (Psych-101/201) doesn't help because the agent must physically interact with the visual experiment

---

## 3. Task Pool

### Domain Taxonomy (6 domains, ~25 tasks)

Tasks drawn from paradigms in Psych-101/201 and CogBench, rebuilt as standalone jsPsych web apps.

#### Domain 1: Multi-Armed Bandits & Exploration-Exploitation
| # | Task | Response Type | Key Metrics | CogBench Overlap |
|---|------|---------------|-------------|------------------|
| 1 | 2-Armed Bandit (Horizon Task) | Keypress (L/R) | % optimal, exploration rate by horizon, directed vs random | Yes (CogBench Exp 1) |
| 2 | Restless Bandit | Click | Tracking accuracy, win-stay/lose-shift | No |
| 3 | Contextual Bandit | Click | Generalization accuracy | No |
| 4 | 3-Armed Bandit | Keypress | Exploration bonus | No |

#### Domain 2: Decision-Making Under Risk
| # | Task | Response Type | Key Metrics | CogBench Overlap |
|---|------|---------------|-------------|------------------|
| 5 | Risky Choice (Gambles) | Keypress (L/R) | Risk aversion, CPT parameters | Partial (CogBench Exp 4) |
| 6 | Intertemporal Choice | Keypress (L/R) | Discount rate, hyperbolic fit | Yes (CogBench Exp 3) |
| 7 | Decisions from Experience | Click + keypress | Sampling count, description-experience gap | No |
| 8 | Multi-Attribute Choice | Click | Attribute weighting, RT-difficulty correlation | No |

#### Domain 3: Reinforcement Learning
| # | Task | Response Type | Key Metrics | CogBench Overlap |
|---|------|---------------|-------------|------------------|
| 9 | Reversal Learning | Keypress | Perseveration errors, post-reversal learning rate | No |
| 10 | Two-Step Task | Keypress | MB/MF index | Yes (CogBench Exp 2) |
| 11 | Probabilistic Classification | Keypress | Learning curve, strategy type | No |

#### Domain 4: Perception & Attention
| # | Task | Response Type | Key Metrics | CogBench Overlap |
|---|------|---------------|-------------|------------------|
| 12 | Stroop Task | Keypress (4 keys) | Stroop effect, congruency sequence | No |
| 13 | Flanker Task | Keypress | Congruency effect | No |
| 14 | Go/No-Go | Keypress / withhold | d-prime, false alarm rate | No |
| 15 | Simple/Choice RT | Keypress | Mean RT, RT variability, Hick's law | No |

#### Domain 5: Memory & Learning
| # | Task | Response Type | Key Metrics | CogBench Overlap |
|---|------|---------------|-------------|------------------|
| 16 | N-Back (2-back) | Keypress | d-prime, hit rate, false alarm rate | No |
| 17 | Free Recall | Typed response | Serial position curve, total recalled | No |
| 18 | Supervised Classification | Keypress | Learning curve, generalization | No |
| 19 | Probability Estimation | Slider | Calibration, Brier score | No |

#### Domain 6: Social & Strategic Games
| # | Task | Response Type | Key Metrics | CogBench Overlap |
|---|------|---------------|-------------|------------------|
| 20 | Trust Game | Slider + click | Amount sent, reciprocity | No |
| 21 | Dictator Game | Slider | Modal split, fairness norm | No |
| 22 | Public Goods Game | Number input | Cooperation rate | No |
| 23 | Repeated Prisoner's Dilemma | Keypress | Cooperation rate, tit-for-tat | Yes (CogBench Exp 6) |
| 24 | Ultimatum Game | Slider + keypress | Minimum acceptable offer | No |

**CogBench overlap:** CogArena shares ~4-5 paradigms with CogBench (bandits, two-step, temporal discounting, risky choice, prisoner's dilemma). This is a feature, not a bug — it allows direct comparison of text-based (CogBench) vs. interactive (CogArena) evaluation of the same phenomena. We can ask: "Does the Stroop effect emerge when an agent physically takes the experiment but not when it reads a text description?"

### Task Implementation Standard

Every task follows this file structure:
```
task_name/
├── index.html                  # Entry point loading jsPsych
├── experiment.js               # Full experiment logic
├── stimuli/                    # Images, audio, etc. (if needed)
├── task_config.json            # Parameterized settings
├── README.md                   # Citation, expected behavior, Psych-201 reference
└── scoring/
    ├── level2_metrics.json     # Accuracy metrics to compute
    └── level3_signatures.json  # Behavioral signatures to test
```

**task_config.json example (Stroop):**
```json
{
  "task_id": "stroop",
  "task_name": "Stroop Color-Word Interference Task",
  "domain": "perception_attention",
  "version": "1.0.0",
  "citation": "Stroop, 1935",
  "psych201_reference": "busch2024_stroop",
  "cogbench_reference": null,
  "parameters": {
    "n_trials": 96,
    "n_blocks": 4,
    "conditions": ["congruent", "incongruent", "neutral"],
    "proportion_congruent": 0.33,
    "stimulus_duration_ms": 2000,
    "fixation_duration_ms": 500,
    "response_deadline_ms": 5000,
    "response_keys": ["d", "f", "j", "k"],
    "color_key_mapping": {"red": "d", "blue": "f", "green": "j", "yellow": "k"}
  },
  "randomization": {
    "seed_from_session": true,
    "randomize_trial_order": true,
    "randomize_color_assignment": true
  },
  "data_logging": {
    "required_fields": [
      "trial_index", "block", "condition", "stimulus_word",
      "stimulus_color", "response", "rt", "correct"
    ]
  }
}
```

**jsPsych trial data output (what gets POSTed to server):**
```json
{
  "trial_index": 42,
  "block": 2,
  "condition": "incongruent",
  "stimulus_word": "RED",
  "stimulus_color": "blue",
  "response": "f",
  "rt": 823,
  "correct": true,
  "timestamp_ms": 1708372800000
}
```

---

## 4. Public/Private Split & Community Contributions

### Inspired by LiveBench + TurkingBench

LiveBench keeps 1/6 of questions private and rotates monthly. TurkingBench instantiates templates with different values for diversity. We combine both ideas:

**Public Demo Tasks (~8 tasks):** Always playable on the website by humans. These double as the "Try It Yourself" feature. Visitors play the same experiments agents take, see their results alongside the AI leaderboard. This generates ongoing human baseline data and makes the benchmark tangible.

Proposed public set: Stroop, 2-Armed Bandit, Risky Choice, Trust Game, N-Back, Go/No-Go, Reversal Learning, Dictator Game (one per domain plus extras).

**Core Evaluation Tasks (all ~24 tasks):** The full scored benchmark. Paradigms and descriptions are public. Specific stimulus parameters are regenerated per evaluation session via random seed (like TurkingBench's template instantiation). Agents can be run on public demo tasks for debugging/development, but official scores come from the full set.

**Community-Contributed Tasks (growing):** Researchers submit new tasks via GitHub PR. Requirements:
- Follow the task implementation standard
- Include task_config.json, level2_metrics.json, level3_signatures.json
- Include README with citation and expected human behavior
- Must collect or provide human baseline data

---

## 5. Website & Leaderboard

### Modeled after HAL (Princeton) + LiveBench

**HAL's Online-Mind2Web leaderboard** is our closest model for UX. It shows: Scaffold × Model combinations, accuracy with confidence intervals, cost, number of runs, downloadable traces, verification badges. Plus visualizations: heatmap of per-task performance, cost-performance Pareto frontier, accuracy over time.

### Tab Structure

**Tab 1: Leaderboard**
Table columns (like HAL):
- Rank
- Scaffold (Browser-Use, SeeAct, Playwright, Claude Computer Use, etc.)
- Model (Claude Sonnet 4, GPT-5, Gemini 2.0, etc.)
- Observation Mode (screenshot, DOM, both)
- CogArena Score (composite, 0-100)
- L1: Completion (0-100)
- L2: Accuracy (0-100)
- L3: Behavioral Alignment (0-100)
- Domain subscores (expandable: Bandits, Decision, RL, Perception, Memory, Social)
- Cost (USD) — total API cost for full benchmark
- Runs
- Traces (downloadable)
- Verified badge (reproduced by CogArena team)

Plus visualizations:
- Radar chart per agent (6 domain scores)
- Behavioral signature heatmap (which signatures each agent exhibits)
- Cost-performance Pareto frontier

**Tab 2: Try It Yourself** ← The killer feature no other benchmark has
8 public tasks playable in browser. After completion:
- "You scored X% on Stroop. Here's how Claude and GPT-4o did."
- "Your Stroop effect was Xms. Claude's was Yms."
- Optional consent to contribute data to human baselines

**Tab 3: Task Catalog**
All tasks documented. For each: name, domain, citation, screenshot, what it measures, human baseline stats, whether it's in the public set.

**Tab 4: Submit a Task**
GitHub PR template + contribution guidelines.

**Tab 5: Evaluate Your Agent**
Two paths:
- Self-serve: register → API key → point agent at task URLs → results appear
- Managed: email us, we run it (for proprietary agents like Operator)

**Tab 6: About / Paper**

### Tech Stack
- **Frontend:** Next.js + Tailwind (for SSR, good for leaderboard tables)
- **jsPsych tasks:** Static HTML/JS served by the same backend or from CDN
- **Backend API:** FastAPI (Python)
- **Database:** PostgreSQL
- **Hosting:** Vercel (frontend) + Fly.io or Railway (API + DB)
- **Domain:** cogarena.ai or cogarena.org

---

## 6. Scoring Pipeline (Detail)

### Level 1: Task Completion (Weight: 0.15)

Binary per-task checks:

| Check | Criterion |
|-------|-----------|
| Task loaded | Agent navigated to task URL |
| Instructions read | Advanced past instruction screens |
| Responded on all trials | Timeout rate < 20% |
| Valid responses | Correct keys pressed > 80% of trials |
| Completed experiment | Reached end screen, data submitted |

Per-task L1 score = proportion of checks passed (0-1)
Overall L1 = average across tasks

Implementation: `scoring/level1_completion.py` — pure Python, reads trial data JSON, runs checks.

### Level 2: Performance Accuracy (Weight: 0.35)

Task-specific metrics defined in each task's `level2_metrics.json`:

```json
{
  "task_id": "stroop",
  "metrics": [
    {
      "name": "overall_accuracy",
      "type": "proportion_correct",
      "field": "correct",
      "human_mean": 0.95,
      "human_sd": 0.04
    },
    {
      "name": "mean_correct_rt",
      "type": "mean",
      "field": "rt",
      "filter": {"correct": true},
      "human_mean": 680,
      "human_sd": 120
    }
  ]
}
```

Scoring: z-score against human baseline → convert to percentile → cap at 1.0.
Per-task L2 = average of normalized metrics.
Overall L2 = average across tasks.

Implementation: `scoring/level2_accuracy.py` — loads trial data + metrics spec + human baselines.

### Level 3: Behavioral Alignment (Weight: 0.50)

Statistical tests for cognitive signatures, defined in `level3_signatures.json` (see Section 2.4 above).

Available test types:
- `paired_ttest_greater` — compare two conditions (e.g., incongruent vs congruent RT)
- `sequential_regression` — regress current trial on lagged predictor (e.g., post-error slowing)
- `interaction_test` — test for interaction between factors (e.g., congruency sequence effect)
- `proportion_test` — test if a proportion differs from chance (e.g., exploration rate)
- `correlation_test` — test for correlation (e.g., RT-difficulty relationship)
- `curve_fit` — fit a parametric model (e.g., learning curve, serial position curve)

Score per signature: 1.0 (detected), 0.5 (right direction, not significant), 0.0 (absent/wrong).
Per-task L3 = average of signature scores.
Overall L3 = average across tasks.

Implementation: `scoring/level3_behavioral.py` — uses scipy.stats, statsmodels. Each test type is a generic function parameterized by the JSON spec.

### Composite

```
CogArena Score = (0.15 × L1 + 0.35 × L2 + 0.50 × L3) × 100
```

---

## 7. Timing

Human experiments measure RT in milliseconds. AI agents have inference latency (500ms-5s).

**Our approach:**
1. jsPsych records wall-clock RT (stimulus onset to keypress). This includes agent inference time.
2. Generous timeouts per task (5-10 seconds per trial).
3. Responses < 100ms flagged (too fast, likely automated without perception).
4. Responses > human p99 flagged but not disqualified.
5. RT-based behavioral signatures (Stroop effect, post-error slowing) are tested on whatever RTs the agent produces — if the effect shows up in the data, that's meaningful regardless of absolute scale.

---

## 8. Full Directory Structure

```
cogarena/
├── tasks/                          # jsPsych experiments
│   ├── stroop/
│   │   ├── index.html
│   │   ├── experiment.js
│   │   ├── task_config.json
│   │   ├── README.md
│   │   └── scoring/
│   │       ├── level2_metrics.json
│   │       └── level3_signatures.json
│   ├── two_armed_bandit/
│   ├── risky_choice/
│   └── ... (24 tasks)
├── harness/                        # Evaluation harness
│   ├── server.py                   # FastAPI server
│   ├── session_manager.py          # Session tracking
│   └── db/
│       ├── schema.sql
│       └── models.py
├── scoring/                        # Grading pipeline
│   ├── level1_completion.py
│   ├── level2_accuracy.py
│   ├── level3_behavioral.py
│   ├── composite_score.py
│   ├── score_session.py            # CLI entry point
│   ├── tests/                      # Unit tests with synthetic data
│   │   ├── test_level1.py
│   │   ├── test_level2.py
│   │   └── test_level3.py
│   ├── human_baselines/            # JSON files with human reference stats
│   │   ├── stroop.json
│   │   ├── two_armed_bandit.json
│   │   └── ...
│   └── analysis_templates/         # Statistical test implementations
│       ├── paired_ttest.py
│       ├── sequential_regression.py
│       ├── interaction_test.py
│       ├── proportion_test.py
│       ├── correlation_test.py
│       └── curve_fit.py
├── website/                        # Public-facing site
│   ├── app/                        # Next.js app
│   ├── components/
│   │   ├── Leaderboard.tsx
│   │   ├── RadarChart.tsx
│   │   ├── SignatureHeatmap.tsx
│   │   └── TryItEmbed.tsx
│   └── public/
│       └── tasks/                  # Static copies of public demo tasks
├── data/                           # Collected data (gitignored)
│   ├── agent_runs/
│   ├── human_runs/
│   └── leaderboard/
└── docs/
    ├── task_spec.md
    ├── agent_spec.md
    ├── scoring_spec.md
    └── contributing.md
```

---

## 9. Implementation Roadmap

### Phase 0: Project Setup (Week 1)

**Goal:** Repository structure, dependencies, dev tooling.

- [ ] Create GitHub repo `cogarena/cogarena`
- [ ] Set up monorepo structure (above)
- [ ] `npm init` + install jsPsych v8 and plugins (html-keyboard-response, survey, etc.)
- [ ] `pip install fastapi uvicorn scipy statsmodels pandas numpy sqlalchemy`
- [ ] Create task template (empty task following the standard)
- [ ] Write JSON schema validators for task_config.json, level2_metrics.json, level3_signatures.json
- [ ] Basic dev server: `python harness/server.py` serves a task, `npm start` opens it in browser
- [ ] Write CONTRIBUTING.md

**Deliverable:** Run `python harness/server.py` → navigate to `localhost:8000/tasks/template/` → see blank jsPsych experiment.

### Phase 1: First Task — Stroop (Weeks 2-3)

**Goal:** One complete task proving the entire pipeline end-to-end.

Why Stroop first: simplest paradigm, clearest behavioral signature (RT interference), keypress-only response, well-understood by any audience, direct comparison to CogBench (which doesn't include perception tasks — this immediately differentiates us).

- [ ] Implement Stroop in jsPsych v8:
  - Instruction screens with key mapping
  - Practice block (8 trials with feedback)
  - 4 experimental blocks × 24 trials = 96 trials
  - Conditions: congruent, incongruent, neutral (balanced)
  - Fixation cross (500ms) → stimulus (until response or 2000ms) → feedback (if practice) → ITI (500-1000ms)
  - Data logging: all required fields per trial
  - End screen with "thank you" message
  - On finish: POST trial data JSON to `/api/data/{session_id}/{task_id}`
- [ ] Write task_config.json for Stroop
- [ ] Write level2_metrics.json (overall accuracy, congruent accuracy, incongruent accuracy, mean RT)
- [ ] Write level3_signatures.json (Stroop interference RT, Stroop interference accuracy, post-error slowing, congruency sequence effect)
- [ ] Write Stroop README.md with citation and expected human behavior
- [ ] Test manually in browser — complete the task yourself, verify data output
- [ ] Implement scoring pipeline for Stroop:
  - level1_completion.py: check trial count, response validity
  - level2_accuracy.py: compute metrics, normalize against placeholder baselines
  - level3_behavioral.py: run statistical tests on trial data
  - composite_score.py: combine with weights
- [ ] Write unit tests for scoring with synthetic data:
  - Perfect data (all correct, fast RT) → high L1, L2
  - Random data (50% correct, no RT difference by condition) → low L2, L3
  - Human-like data (95% correct, 80ms Stroop effect, post-error slowing) → high L1, L2, L3
- [ ] End-to-end test: open task in browser → complete it → data POSTed to server → run `python scoring/score_session.py` → get scorecard JSON

**Deliverable:** Complete Stroop task playable in browser, automated scoring producing a three-level scorecard.

### Phase 2: Four More Tasks (Weeks 3-5)

Build one task per remaining domain:

| Task | Domain | Why | Complexity |
|------|--------|-----|-----------|
| 2-Armed Bandit (Horizon) | Bandits | Core paradigm, CogBench overlap for comparison | Medium |
| Risky Choice (Gambles) | Decision | Standard, fits CPT, keypress only | Low |
| Trust Game | Social | Multi-step, slider input | Medium |
| N-Back (2-back) | Memory | Working memory, clear d-prime | Medium |

For each task, same process as Phase 1:
- [ ] Implement jsPsych experiment
- [ ] Write config + scoring specs
- [ ] Write README
- [ ] Test manually
- [ ] Extend scoring pipeline to handle new metric types and test types as needed
- [ ] Write unit tests

**Deliverable:** 5 fully functional tasks with automated scoring.

### Phase 3: Harness & API (Weeks 5-7)

**Goal:** End-to-end system where an agent can take the benchmark.

- [ ] Build FastAPI endpoints:
  - `POST /api/sessions` → create session, return session_id + task list with URLs
  - `POST /api/data/{session_id}/{task_id}` → receive jsPsych trial data
  - `POST /api/evaluate/{session_id}` → trigger scoring pipeline
  - `GET /api/results/{session_id}` → return scorecard JSON
  - `GET /api/leaderboard` → current standings
- [ ] PostgreSQL schema:
  - sessions (session_id, agent_name, scaffold, model, observation_mode, status, created_at)
  - task_results (session_id, task_id, trial_data_json, submitted_at)
  - scores (session_id, task_id, l1, l2, l3, details_json)
  - leaderboard (agent_id, scaffold, model, composite, l1, l2, l3, domain_scores, cost, evaluated_at)
- [ ] Session manager: track task completion, handle timeouts, enforce ordering
- [ ] Wire up: jsPsych experiment end → POST to server → server stores data → evaluate endpoint runs scoring → results endpoint returns scorecard
- [ ] Test end-to-end manually: complete all 5 tasks in browser → scores computed automatically

**Deliverable:** Running server at localhost:8000 where completing tasks produces automatic scores.

### Phase 4: Test with AI Agents (Weeks 7-9)

**Goal:** First real agent evaluations.

- [ ] Test with Claude computer use (via Claude in Chrome or computer use API)
  - Run all 5 tasks
  - Debug: can it find response keys? Read instructions? Perceive stimuli?
- [ ] Test with at least one other agent (GPT-4o + Browser-Use, or Playwright bot)
- [ ] Analyze agent data:
  - Do agents show Stroop interference?
  - Do they explore in the bandit task?
  - How do RT distributions compare to humans?
- [ ] Iterate on task implementations based on findings
- [ ] Document agent-specific issues and solutions

**Deliverable:** First CogArena scorecards for 2-3 real agents. Initial findings on what works and what breaks.

### Phase 5: Human Baselines (Weeks 8-10, parallel with Phase 4)

- [ ] Deploy 5 tasks to public URL (Netlify or served by FastAPI)
- [ ] Run on Prolific: N=100 per task
- [ ] Process human data through same scoring pipeline
- [ ] Compute baseline distributions (mean, SD, effect sizes)
- [ ] Store in `scoring/human_baselines/` as JSON
- [ ] Update Level 2 and 3 scoring to use real baselines

**Deliverable:** Verified human baselines for all 5 Phase 1 tasks.

### Phase 6: Expand to Full Benchmark (Weeks 10-14)

- [ ] Build remaining ~19 tasks (same process as Phase 1-2)
- [ ] Prioritize by: Psych-201 overlap, response modality diversity, CogBench comparisons
- [ ] Collect human baselines for new tasks
- [ ] Run all agents through full benchmark
- [ ] Validate scoring at scale

### Phase 7: Website & Launch (Weeks 14-18)

- [ ] Build leaderboard page (modeled after HAL)
- [ ] Build "Try It Yourself" page
- [ ] Build task catalog, agent submission, task contribution pages
- [ ] Deploy
- [ ] Write benchmark paper
- [ ] Submit to NeurIPS 2026 Datasets & Benchmarks

### Phase 8: Ongoing

- [ ] Accept community tasks via GitHub
- [ ] Quarterly leaderboard refreshes
- [ ] Expand to mouse tracking / continuous response tasks
- [ ] Cross-species comparison (animal cognition paradigms)

---

## 10. Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Agents can't perceive jsPsych stimuli | Large, high-contrast stimuli. Test with agents early (Phase 4). |
| Agent inference latency exceeds timeout | Generous timeouts (5-10s). Report timeout rate separately. |
| Insufficient power for L3 with few trials | Adequate trial counts (≥50/condition). Partial credit for right-direction trends. |
| Benchmark too easy or too hard | Tasks span difficulty. Iterate after Phase 4 testing. |
| "So what?" — reviewers ask why not just use CogBench | CogBench is text-based. We test whether the same phenomena emerge from actual interaction. The Stroop effect requires perceiving visual stimuli — you can't test that with text. |
| "So what?" — reviewers ask why not just use TurkingBench | TurkingBench tasks are one-shot annotation. Our tasks involve sustained multi-trial interaction with controlled experimental designs, enabling rigorous behavioral analysis. |

---

## 11. Immediate Next Steps

1. **Create GitHub repo** with directory structure from Section 8
2. **Build the Stroop task** in jsPsych v8 (Phase 1)
3. **Build the scoring pipeline** for Stroop with synthetic test data
4. **Test end-to-end** with manual browser completion
5. **Test with Claude computer use** to validate that agents can actually interact with jsPsych experiments

This gives us CogArena v0.1: one task + scoring + one agent = proof of concept.
