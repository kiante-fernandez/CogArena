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

100 sessions (10 v1 tasks × 10 repeats), ~60 min wall time, $0 API cost. Some sessions may drop to transient Playwright `Page.goto` timeouts (~15% in our run); the per-task chance-ceiling estimates use whatever sessions complete. Output goes to `data/sweeps/random_floor_v1_<timestamp>/aggregate.csv`.

Reference: [`results/random_floor_v1.csv`](results/random_floor_v1.csv).

---

## 4. Reproduce the frontier-model results

Frontier-model evaluation requires `OPENROUTER_API_KEY` in `.env` (or your shell env). All paper models route through OpenRouter, so a single key is sufficient. Estimated cost per (model × 10-task) run, based on observed token usage at v1.1.1:

| Model | $/M in | $/M out | ≈ $ per 10 tasks | OK / 10 in our run |
|---|---:|---:|---:|---:|
| `gemini-3-flash-preview` | $0.50 | $3.00 | ~$5  | 10 |
| `kimi-k2.5`               | $0.44 | $2.00 | ~$4  | 7  |
| `qwen3-vl-235b-instruct`  | $0.20 | $0.88 | ~$2  | 7  |
| `qwen3-vl-30b-instruct`   | $0.13 | $0.52 | ~$1.50 | 7  |
| `grok-4.1-fast`           | $0.20 | $0.50 | ~$2  | 6  |
| `gpt-5.4-nano`            | $0.20 | $1.25 | ~$2.50 | 8  |

The paper reports the canonical v1 pilot as 6 models × 10 tasks × 1 repeat = 60 sessions. The full set of suite YAMLs that produced it:

```bash
# Three frontier proprietary models (gemini, gpt-5.2-tier, claude-sonnet-4.6).
# Note: only gemini was actually run in the v1 pilot — gpt-5.2 and Sonnet
# are listed but skipped because their per-session cost was outside the
# pilot budget. To rerun gemini alone:
python -m harness sweep --suite harness/suites/pilot_v1.yaml \
    --models gemini-3-flash-preview --max-parallel 4

# Cheap-frontier additions (grok, glm — glm fails Browser-Use schema):
python -m harness sweep --suite harness/suites/pilot_v1_cheap.yaml \
    --max-parallel 4

# Open + cheap-frontier expansion (kimi, qwen-235):
python -m harness sweep --suite harness/suites/pilot_v1_addons.yaml \
    --max-parallel 4

# Smaller open + OpenAI nano (qwen-30, ui-tars [also fails], gpt-5.4-nano):
python -m harness sweep --suite harness/suites/pilot_v1_addons2.yaml \
    --max-parallel 4
```

Aggregate cost across all four sweeps in our run: ~$15-20 OpenRouter credit. ~75-90 min wall time per sweep at `--max-parallel 4`.

To reproduce a single model cheaply (e.g. `gemini-3-flash-preview` for ~$5):

```bash
python -m harness sweep --suite harness/suites/pilot_v1.yaml \
    --models gemini-3-flash-preview --max-parallel 4 --verbose
```

Reference results: [`results/pilot_v1.csv`](results/pilot_v1.csv) (60 rows, 6 models).

Two models were excluded from the canonical results — `glm-4.6v` and `ui-tars-1.5-7b` both produced 0/10 successful sessions because Browser-Use's strict pydantic action validator rejected their native action shapes (`{"key": " "}` and `{"input": ...}` respectively, where the validator requires `{"send_keys": {"keys": " "}}`). The suite YAMLs that reference them are kept in the repo for reproducibility but the failure pattern is a scaffold-compatibility note, not a model-capability claim.

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

- **`results/random_floor_v1.csv`** — 100-row chance floor: `(run_index, repeat_index, model_id, task_id, rc, wall_time, composite, l1, l2, l3)`. `model_id="random"` for all rows. Some rows have `rc=1` (transient Playwright timeouts) and empty score columns; the chance-ceiling analysis in `results/AUDIT.md` uses only `rc=0` rows.
- **`results/pilot_v1.csv`** — 60-row frontier-model pilot, same schema. 6 models × 10 tasks × 1 repeat. Composite = 100 × (0.15·L1 + 0.35·L2 + 0.50·L3).
- **`results/AUDIT.md`** — record of the v1.0.0 → v1.1.0 spec audit (what changed in L2/L3 and why, with per-task before/after chance ceilings).
- **`results/example_replay.html`** — self-contained HTML scrub of one agent run (gemini × moral_machine).
- **Per-session `score.json`** (under `data/sweeps/<run>/runs/<r##>/artifacts/`) — full signature-level detail: every L3 effect's measured statistic, expected direction, score, and weight.

---

## Troubleshooting

- **`playwright._impl._errors.Error: Executable doesn't exist`** — run `playwright install chromium`.
- **`openai.AuthenticationError` or `httpx 401`** — set `OPENROUTER_API_KEY` in `.env`. The harness uses pydantic-settings to auto-load `.env` at import time.
- **All sessions FAIL in 1–3 seconds** — check `data/sweeps/<run>/runs/r00_*/run.log` for a Python traceback. Server log is at `artifacts/server.log` in the same directory.
- **Site-related issues (`/`, `/catalog` 500)** — these are surfaced by the dev server (`uvicorn harness.server:app`). The benchmark itself doesn't depend on the website; it's a presentation layer over `/api/*` endpoints.

For all other questions: see [`CLAUDE.md`](CLAUDE.md) for the developer-oriented architecture overview, or the inline docstrings in `harness/`, `scoring/`, and `agents/`.
