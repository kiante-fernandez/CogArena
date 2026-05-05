# Reproducing CogArena results

This document walks reviewers through (1) installing CogArena, (2) running a single agent end-to-end, (3) regenerating the chance-floor and frontier-model results reported in the paper.

CogArena is a benchmark suite — the artifact under review is the *evaluation infrastructure*, not a static dataset. To inspect what the paper claims, you run the agent yourself and look at the resulting scorecards.

---

## 1. Install

```bash
git clone https://github.com/kiante-fernandez/CogArena.git
cd CogArena
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt   # core (server + harness + scoring)
pip install -e .[agents]               # adds browser-use==0.9.5, playwright
playwright install chromium            # Chromium binary for browser-use
```

System: Python 3.11+, macOS or Linux. The lockfile pins exact versions of the 41 core packages used to produce the paper's results (FastAPI 0.129.2, Starlette 0.52.1, jsPsych 8.2.3 vendored in the repo).

---

## 2. Smoke test (no API calls)

Run the random agent on a single task. This validates the harness without any LLM cost:

```bash
python -m harness eval --model random --tasks marbles_risk \
    --start-server --trace-dir /tmp/cogarena_smoke --task-timeout 300
```

Expected: ~90 seconds wall time. Prints a scorecard like:

```
COGARENA SCORECARD: RandomAgent
  Composite Score:    33.07 / 100
  L1 Completion:      1.0000
  L2 Accuracy:        0.5164
  L3 Behavioral:      0.0000
```

Artifacts under `/tmp/cogarena_smoke/`:
- `meta.json` — session metadata (model, git sha, env, task list)
- `score.json` — full L1/L2/L3 breakdown with signature-level detail
- `trial_data/marbles_risk.json` — raw jsPsych trial data
- `interactions.jsonl`, `actions.jsonl`, `screenshots/` — agent step trail
- `server.log` — uvicorn access + tracebacks

To re-score the saved trial data without rerunning the agent:

```bash
python -m scoring.score_session \
    --trial-data /tmp/cogarena_smoke/trial_data/marbles_risk.json \
    --task-id marbles_risk
```

This is the mechanism that lets scoring rules evolve without invalidating prior runs.

---

## 3. Reproduce the chance-floor table

The paper's chance-floor numbers come from running the random agent across the v1 task set:

```bash
python -m harness sweep --suite harness/suites/random_floor_v1.yaml \
    --max-parallel 4 --verbose
```

20 sessions (10 v1 tasks × 2 repeats), ~12 min wall time, $0 API cost. Output goes to `data/sweeps/random_floor_v1_<timestamp>/aggregate.csv`.

Compare against the committed reference: [`results/random_floor_v1.csv`](results/random_floor_v1.csv).

---

## 4. Reproduce the frontier-model results

Frontier-model evaluation requires `OPENROUTER_API_KEY` in `.env` (or your shell env). All paper models route through OpenRouter so a single key is sufficient. Estimated cost per (model, 10-task) run, based on observed token usage:

| Model | $/M in | $/M out | ≈ $ per 10 tasks |
|---|---:|---:|---:|
| `gemini-3-flash-preview` | $0.50 | $3 | ~$5 |
| `gpt-5.2` | $1.75 | $14 | ~$19 |
| `claude-sonnet-4.6` | $3 | $15 | ~$29 |
| `kimi-k2.5` | $0.44 | $2 | ~$4 |
| `grok-4.1-fast` | $0.20 | $0.50 | ~$2 |
| `glm-4.6v` | $0.30 | $0.90 | ~$3 |

To rerun the paper's pilot study (3 frontier models × 10 tasks × 1 repeat):

```bash
python -m harness sweep --suite harness/suites/pilot_v1.yaml \
    --max-parallel 4 --verbose
```

~75 min wall time at parallel=4, ~$50 OpenRouter spend. Output: `data/sweeps/pilot_v1_<timestamp>/aggregate.csv`.

To reproduce a single model only (cheaper, e.g. `gemini-3-flash-preview` for ~$5):

```bash
python -m harness sweep --suite harness/suites/pilot_v1.yaml \
    --models gemini-3-flash-preview --max-parallel 4 --verbose
```

Reference results: [`results/pilot_v1.csv`](results/pilot_v1.csv).

---

## 5. Inspect a recorded agent run

A pre-recorded sample replay is committed at [`results/example_replay.html`](results/example_replay.html). Open it in any browser to scrub through an agent's screenshots and step-by-step actions.

To generate your own from a session you just ran:

```bash
python -m harness replay --session <session_id> --inline
```

The `--inline` flag produces a self-contained HTML file with screenshots embedded — no server required to view it.

---

## 6. Run the test suite

```bash
pytest scoring/tests/ harness/tests/ -v
```

Expected: 374 passed (313 scoring + 10 harness unit + 51 field-alignment tests). Field-alignment tests verify every task's data layout matches what the L1/L2/L3 scorers expect.

---

## What each result file contains

- **`results/random_floor_v1.csv`** — 20-row chance floor: `(model_id, task_id, repeat_index, rc, wall_time, composite, l1, l2, l3)`. `model_id="random"` for all rows.
- **`results/pilot_v1.csv`** — frontier-model results, same schema. Columns: composite (0–100), L1 (completion 0–1), L2 (accuracy 0–1), L3 (behavioral signature score 0–1). Composite = 0.15·L1 + 0.35·L2 + 0.50·L3, scaled to 100.
- **Per-session `score.json`** (under `data/sweeps/<run>/runs/<r##>/artifacts/`) — full signature-level detail: every L3 effect's measured statistic, expected direction, score, and weight.

---

## Troubleshooting

- **`playwright._impl._errors.Error: Executable doesn't exist`** — run `playwright install chromium`.
- **`openai.AuthenticationError` or `httpx 401`** — set `OPENROUTER_API_KEY` in `.env`. The harness uses pydantic-settings to auto-load `.env` at import time.
- **All sessions FAIL in 1–3 seconds** — check `data/sweeps/<run>/runs/r00_*/run.log` for a Python traceback. Server log is at `artifacts/server.log` in the same directory.
- **Site-related issues (`/`, `/catalog` 500)** — these are surfaced by the dev server (`uvicorn harness.server:app`). The benchmark itself doesn't depend on the website; it's a presentation layer over `/api/*` endpoints.

For all other questions: see [`CLAUDE.md`](CLAUDE.md) for the developer-oriented architecture overview, or the inline docstrings in `harness/`, `scoring/`, and `agents/`.
