# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Run server (dev)
uvicorn harness.server:app --reload --host 0.0.0.0 --port 8000

# Tests
pytest scoring/tests/ harness/tests/ -v
pytest scoring/tests/test_score_session.py::test_stroop_scoring -v   # single test

# Score a saved session locally
python -m scoring.score_session --trial-data path/to/data.json --task-id stroop

# Run an agent end-to-end (starts server, creates session, runs, scores)
python -m agents.runner --agent browser-use --model google/gemini-2.5-flash \
    --start-server --tasks stroop n_back --task-timeout 1200

# Skip tasks already scored for the same model+scaffold
python -m agents.runner --agent browser-use --model <m> --start-server --skip-scored

# Full study (5 models × 40 tasks, parallel ports)
./run_study.sh                          # all
./run_study.sh --model google/gemini-3-flash-preview
./run_study.sh --dry-run

# Reference harness (wraps random + browser-use agents under one CLI;
# captures interactions.jsonl + screenshots + replay.html + server.log per session)
python -m harness eval --model random --tasks stroop --start-server --replay
python -m harness eval --model gpt-5-mini --tasks marbles_risk --start-server --trace-dir /tmp/run1
python -m harness sweep --suite harness/suites/headline.yaml --max-parallel 2 --dry-run
python -m harness replay --session <session_id> --inline   # standalone HTML
```

The harness writes per-session artifacts under `<trace_dir>/` (or `data/sessions/<id>/` by default): `meta.json`, `interactions.jsonl`, `actions.jsonl`, `score.json`, `server.log` (uvicorn access + tracebacks), `conversations/<task_id>/...txt`, `screenshots/`. Use `replay.html` to scrub the run.

`CONDA_PYTHON` overrides which Python `run_study.sh` uses for `browser_use` imports. The `harness` CLI sets `ANONYMIZED_TELEMETRY=false` by default to disable Browser-Use + PostHog telemetry.

### Model registry & suite YAMLs

`harness/models.yaml` is the registered model list (id, api string, scaffold). Use canonical OpenRouter IDs (`google/gemini-2.5-flash`, not `openrouter/google/...` — that prefix is rejected by OpenRouter). Bare IDs without `/` use native provider SDKs (gpt-* → ChatOpenAI, claude-* → ChatAnthropic, gemini-* → ChatGoogle). Models not in `models.yaml` pass through verbatim to the browser-use scaffold.

`harness/suites/headline.yaml` defines the headline study (5 frontier models × 10 v1 tasks × 3 repeats).

### v1 launch task set (10 tasks)

`random_dot_motion_v2`, `grid_bandit`, `marbles_risk`, `repeated_games`, `serial_recall_v2`, `visual_recognition`, `effort_foraging`, `tiny_alchemy`, `moral_machine`, `phishing_detection_v2`. The site `/api/tasks` still returns all 40+ tasks; the v1 set is the foreground for the paper.

### Optional `[agents]` extra

`pip install cogarena[agents]` installs `browser-use==0.9.5` + `playwright>=1.45.0` for the LLM agent path. Without it, `harness eval --model random` still works (random agent uses raw playwright). The `cogarena` console script in `pyproject.toml` is the same as `python -m harness`.

## Architecture

**FastAPI + SQLAlchemy + jsPsych benchmark.** The browser runs real jsPsych experiments; agents drive the browser; the server stores trials and scores them.

### Request flow
1. Client `POST /api/sessions` → `SessionManager` mints a `session_id`.
2. Agent navigates to `/{task_id}?session={id}`. The task's `index.html` loads jsPsych + `static/js/incremental_save.js`, which wraps `initJsPsych` to PATCH `/api/data/{session_id}/{task_id}` every 10 trials. Final POST submits the full dataset.
3. `POST /api/evaluate/{session_id}` triggers `scoring.score_session.score_task` for each completed task.
4. Composite score = `0.15·L1 + 0.35·L2 + 0.50·L3` (see `scoring/composite_score.py`).

### Scoring pipeline (`scoring/`)
Three independent levels read per-task spec files in `tasks/{task_id}/scoring/`:
- **L1 completion** (`level1_completion.py`) — every required trial responded with a valid key.
- **L2 accuracy** (`level2_accuracy.py`) — metrics from `level2_metrics.json` compared to `human_baselines/{task_id}.json`.
- **L3 behavioral** (`level3_behavioral.py`) — runs statistical tests from `level3_signatures.json` via templates in `scoring/analysis_templates/` (paired t-test, proportion, correlation, interaction, sequential regression). Each signature is a literature-derived effect size.

To add a new task you need: `tasks/{id}/{index.html, experiment.js, task_config.json, scoring/level2_metrics.json, scoring/level3_signatures.json}` and `scoring/human_baselines/{id}.json`. Tasks are auto-discovered by iterating `settings.TASKS_DIR`. Every `index.html` must include the `incremental_save.js` script tag.

### Database
- Local dev: `sqlite+aiosqlite:///./data/cogarena.db` (async).
- Vercel deploy: Turso via `sqlite+libsql` (sync driver). `harness/server.py` wraps the sync session in `_SyncSessionAsyncWrapper` to keep the route handlers uniform — when editing DB code, both code paths must work.
- Schema in `harness/db/models.py` (SQLAlchemy + Pydantic side by side).

### Agents (`agents/`)
- `runner.py` is the orchestrator (server lifecycle, session creation, agent dispatch, scoring trigger).
- `browser_use_agent.py` is the primary LLM agent. Model strings containing `/` (e.g. `google/gemini-2.5-flash`) are routed through OpenRouter (needs `OPENROUTER_API_KEY`); plain model IDs use native provider SDKs.
- `openhands_agent.py` uses Docker-sandboxed browser control.
- `random_agent.py` presses random valid keys — no LLM, used as floor.

### Known agent quirks
- Gemini Flash (via OpenRouter) handles slider and keyboard tasks reliably.
- Claude Sonnet 4 via OpenRouter works on slider tasks (e.g. `dictator_game`) but fails keyboard tasks (e.g. `trust_game`) because it emits `{"key": "Space"}` instead of the `{"send_keys": {"keys": "Space"}}` form Browser-Use validates. Worth checking before adding it back to a study.

### jsPsych
The repo vendors `jsPsych-8.2.3/`. Tasks must target this version's API. Do not bump the vendored version without verifying every task's plugins.
