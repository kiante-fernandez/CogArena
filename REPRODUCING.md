# Reproducing CogArena results

This guide accompanies the paper, [CogArena: Benchmarking Multimodal Agents on Interactive Behavioral Experiments](https://arxiv.org/abs/2610.36484) (NeurIPS 2026, Evaluations and Datasets Track). Every number in the paper comes from release `v1.3.0` and the results tables under [`results/`](results/).

CogArena is a benchmark suite, so the main artifact is the evaluation infrastructure rather than a static dataset. You can check the paper's claims in two ways. The first re-derives every analysis from the results tables we released, at no API cost (Section 3). The second re-runs the agents yourself and compares the scorecards (Section 4).

---

## 1. Install

```bash
git clone https://github.com/kiante-fernandez/CogArena.git
cd CogArena
git checkout v1.3.0                    # the release the paper reports
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt   # core (server + harness + scoring)
pip install -e .[agents]               # adds browser-use==0.9.5, playwright
playwright install chromium            # Chromium binary for browser-use
```

System: Python 3.11+, macOS or Linux. The lockfile pins the exact versions of the 42 core packages used to produce the paper's results (FastAPI 0.129.2, Starlette 0.52.1, with jsPsych 8.2.3 vendored in the repo).

---

## 2. Smoke test (no API calls)

Run the random agent on a single task. This validates the harness without any LLM cost.

```bash
python -m harness eval --model random --tasks marbles_risk \
    --start-server --trace-dir /tmp/cogarena_smoke --task-timeout 300
```

Expect about 90 seconds of wall time and a `COGARENA SCORECARD` with Level 1, Level 2, Level 3, and composite scores. `marbles_risk` has no Level 2 metrics as of `v1.3.0`, so its Level 2 prints as `n/a` and the composite splits that weight over Level 1 and Level 3. Scores vary from run to run, because each session draws its own stimulus seed.

Artifacts under `/tmp/cogarena_smoke/`:
- `meta.json` — session metadata (model, git sha, environment, task list)
- `score.json` — the full Level 1/2/3 breakdown with signature-level detail
- `trial_data/marbles_risk.json` — raw jsPsych trial data
- `interactions.jsonl`, `actions.jsonl`, `screenshots/` — the agent's step trail
- `server.log` — uvicorn access log and tracebacks

To re-score the saved trial data without rerunning the agent:

```bash
python -m scoring.score_session \
    --trial-data /tmp/cogarena_smoke/trial_data/marbles_risk.json \
    --task-id marbles_risk
```

This is the mechanism that lets scoring rules evolve without invalidating earlier runs.

---

## 3. Re-derive the paper's analyses (no API cost)

The released tables hold one row per scored session and one row per signature test:

| Directory | Study in the paper |
|---|---|
| `results/rebuttal_v1/` | Main panel: 4 models × 10 tasks × 10 sessions = 400 sessions |
| `results/random_floor/` | Chance floor: Random Agent, 10 tasks × 10 sessions = 100 sessions |
| `results/vision_ablation/` | Vision ablation: 4 models × 4 tasks × 5 sessions, DOM text only |
| `results/flagship/` | Frontier model `gpt-5.6-sol`, one session per task |

Each directory has `runs.csv` (session-level L1, L2, L3, composite, coverage, and observation mode) and `signatures.csv` (signature-level p-value, effect size, direction, and testability).

```bash
# Per-cell means and SDs, bootstrap rank probabilities, signature pass rates
# with Wilson intervals, and Level 3 zero-flip counts. Rewrites
# results/rebuttal_v1/analysis/, and the output matches the committed tables.
python -m scripts.analyze_repeats --results results/rebuttal_v1

# Level 3 under four grading rules (the grading-rule sensitivity table).
python -m scripts.grading_rule_sensitivity

# Recompute every derived human baseline from the source studies' data in
# scoring/human_baselines/sources/, and check those files' hashes.
python -m scripts.derive_baselines
python -m scripts.baseline_sources --verify
```

`results/bootstrap_signatures.csv` holds the moving-block bootstrap regrade of every signature test. Producing it, and the response-time structure analysis, requires the raw per-session trial archives (`scripts.block_bootstrap`, `scripts.analyze_rt_structure`, `scripts.build_results`, `scripts.rescore_sweeps`). We will release those archives separately.

---

## 4. Re-run the studies

The chance floor needs no API key. The model studies need `OPENROUTER_API_KEY` in `.env` (or your shell environment). Every model in the paper routes through OpenRouter, so one key is enough.

```bash
# Chance floor: 100 sessions, about 60 min at --max-parallel 4, no API cost.
python -m harness sweep --suite harness/suites/random_floor_v1.yaml --max-parallel 4

# Main panel: 400 sessions across four models.
python -m harness sweep --suite harness/suites/rebuttal_v1.yaml --max-parallel 4

# Vision ablation: the same four models on four tasks with screenshots removed.
python -m harness sweep --suite harness/suites/vision_ablation.yaml --max-parallel 4

# Frontier model: one session per task.
python -m harness sweep --suite harness/suites/rebuttal_flagship.yaml --max-parallel 4
```

To run part of a study, pass `--models` (e.g. `--models gemini-3-flash-preview`). Each sweep writes per-session artifacts under `data/sweeps/<suite>_<timestamp>/`. To turn a sweep into tables like the released ones and analyze them:

```bash
python -m scripts.build_results --sweep data/sweeps/<your_sweep> --out results/my_run
python -m scripts.analyze_repeats --results results/my_run
```

Approximate OpenRouter cost per model for one session on each of the ten tasks, from observed token usage. A full panel cell is ten such passes.

| Model | $/M in | $/M out | ≈ $ per 10 tasks |
|---|---:|---:|---:|
| `gemini-3-flash-preview` | $0.50 | $3.00 | ~$5 |
| `kimi-k2.5`              | $0.44 | $2.00 | ~$4 |
| `qwen3-vl-235b-instruct` | $0.20 | $0.88 | ~$2 |
| `gpt-5.4-nano`           | $0.20 | $1.25 | ~$2.50 |

Two models attempted for the paper, `glm-4.6v` and `ui-tars-1.5-7b`, produced no valid scorecards. Browser-Use's pydantic action validator rejected their native action shapes (`{"key": " "}` and `{"input": ...}` respectively, where it requires `{"send_keys": {"keys": " "}}`). This is a scaffold-compatibility note, not a model-capability claim.

The submission-era pilot (6 models × 10 tasks × 1 session) is kept for the record in `results/pilot_v1.csv` and the `harness/suites/pilot_v1*.yaml` suites. The paper no longer reports it.

---

## 5. Inspect a recorded agent run

A pre-recorded sample replay is committed at [`results/example_replay.html`](results/example_replay.html). Open it in any browser to scrub through an agent's screenshots and step-by-step actions.

To generate your own from a session you just ran:

```bash
python -m harness replay --session <session_id> --inline
```

The `--inline` flag produces a self-contained HTML file with screenshots embedded, so no server is needed to view it.

---

## 6. Run the test suite

```bash
pytest scoring/tests/ harness/tests/ -v
```

Expected: 456 passed. Among them, `scoring/tests/test_committed_results_reproduce.py` checks that every committed results table reproduces under the current task specifications.

---

## What each result file contains

- **`results/rebuttal_v1/`, `results/random_floor/`, `results/vision_ablation/`, `results/flagship/`** — `runs.csv` and `signatures.csv` for each study, as described in Section 3. A session is measurable (`l3_measurable`) when at least half of its task's signature weight was testable and no test errored. The paper's descriptive Level 3 and composite means are taken over measurable sessions.
- **`results/rebuttal_v1/analysis/`** — the tables `scripts.analyze_repeats` writes: `cell_stability.csv`, `rank_stability.csv`, `signature_pass_rates.csv`, and `l3_zero_flips.csv`.
- **`results/bootstrap_signatures.csv`** — the moving-block bootstrap regrade of every signature test.
- **`results/pilot_v1.csv`**, **`results/random_floor_v1.csv`** — the submission-era pilot and chance floor, superseded by the directories above.
- **`results/example_replay.html`** — a self-contained HTML scrub of one agent run (gemini × moral_machine).
- **Per-session `score.json`** (under `data/sweeps/<run>/runs/<r##>/artifacts/`, after you run a sweep) — full signature-level detail: every Level 3 effect's measured statistic, expected direction, score, and weight.

The composite is 100 × (0.15·L1 + 0.35·L2 + 0.50·L3). A task with no Level 2 metrics splits the Level 2 weight over Level 1 and Level 3 in proportion.

---

## Troubleshooting

- **`playwright._impl._errors.Error: Executable doesn't exist`** — run `playwright install chromium`.
- **`openai.AuthenticationError` or `httpx 401`** — set `OPENROUTER_API_KEY` in `.env`. The harness uses pydantic-settings to load `.env` at import time.
- **All sessions FAIL in 1–3 seconds** — check `data/sweeps/<run>/runs/r00_*/run.log` for a Python traceback. The server log is at `artifacts/server.log` in the same directory.
- **Site-related issues (`/`, `/catalog` 500)** — these come from the dev server (`uvicorn harness.server:app`). The benchmark itself doesn't depend on the website, which is a presentation layer over the `/api/*` endpoints.

For anything else, see [`CLAUDE.md`](CLAUDE.md) for the developer-oriented architecture overview, or the docstrings in `harness/`, `scoring/`, and `agents/`.
