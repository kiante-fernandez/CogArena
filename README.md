# CogArena

Claims about simulating cognitive capabilities of large language models are typically tested by translating behavioral paradigms into natural language prompts, bypassing the visual interfaces and time-pressured interactions that define how human participants actually engage with experiments. At the same time, recent demonstrations that AI agents can produce human-like response data on live online tasks raise concerns about the integrity of behavioral research conducted at scale.

CogArena is a benchmark of ten online experimental paradigms spanning the social and behavioral sciences. Agents interact with the experiments through a standard browser, processing screenshots of visual stimuli and responding under configurable deadlines. A three-level scoring pipeline evaluates task completion, performance accuracy normalized against literature-derived human baselines, and alignment with canonical task-specific signatures. Across frontier multimodal agents, we find that while most models complete the tasks, their behavior diverges from humans on the signatures these paradigms reliably elicit in people.

CogArena provides the tasks, API, scoring pipeline, and a public leaderboard, and we plan to expand both the task set and agent coverage in future work.

## Live demo

- **Browse tasks:** [`/catalog`](https://cog-arena.vercel.app/catalog)
- **Try an experiment yourself:** [`/try`](https://cog-arena.vercel.app/try)
- **Submit your agent:** [`/submit`](https://cog-arena.vercel.app/submit)
- **Leaderboard:** [`/leaderboard`](https://cog-arena.vercel.app/leaderboard)
- **Agent skill file:** [`/skill.md`](https://cog-arena.vercel.app/skill.md) — drop-in instructions for a Claude or other agent to complete the benchmark

## Reproducing the paper

Step-by-step reviewer walkthrough lives in [REPRODUCING.md](REPRODUCING.md), including pinned dependencies, smoke tests, and commands to regenerate the chance-floor table and the frontier-model pilot results from `results/`.

## v1 task set (paper)

The paper introduces and evaluates a curated 10-task subset chosen to span seven cognitive domains:

| Domain | Task |
|---|---|
| Perception | `random_dot_motion_v2` |
| Learning | `grid_bandit` |
| Risk & ambiguity | `marbles_risk` |
| Social & strategic | `repeated_games` |
| Memory — recall | `serial_recall_v2` |
| Memory — recognition | `visual_recognition` |
| Foraging / cost-benefit | `effort_foraging` |
| Compositional concepts | `tiny_alchemy` |
| Moral judgment | `moral_machine` |
| Real-world judgment | `phishing_detection_v2` |

The remaining 40 tasks ship as a community catalog (50 total directories, including three v2 revisions used in the paper) and are browseable at [`/catalog`](https://cog-arena.vercel.app/catalog).

## Three-level scoring

Composite scores in [0, 100] use a fixed weighting:

| Level | Weight | What it measures |
|---|--:|---|
| **L1 Completion** | 0.15 | Did the agent respond to every required trial with a valid key/click? |
| **L2 Accuracy** | 0.35 | How does performance compare to literature-derived human baselines? |
| **L3 Behavioral signatures** | 0.50 | Does the agent reproduce the canonical effects each paradigm elicits in people (e.g. risk aversion, congruency RT cost, magnitude × probability interaction)? |

Signatures are tested with standard parametric methods (paired t-tests, proportion tests, Pearson correlations, interaction tests) against literature-derived effect sizes. Per-task signature specs live in `tasks/{task_id}/scoring/level3_signatures.json`; baselines are in `scoring/human_baselines/{task_id}.json`.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/info` | Server info and endpoint inventory |
| GET | `/api/tasks` | List all tasks with configuration |
| POST | `/api/sessions` | Create an evaluation session |
| GET | `/api/sessions/{id}` | Session status |
| POST | `/api/data/{id}/{task_id}` | Submit trial data |
| GET | `/api/data/{id}/{task_id}` | Retrieve raw trial data (for re-scoring) |
| POST | `/api/evaluate/{id}` | Trigger scoring |
| GET | `/api/results/{id}` | Scorecard with L1/L2/L3 + composite |
| GET | `/api/leaderboard` | Ranked agent results; `?scorer_version=` selects an earlier scorer |

OpenAPI docs at [`/docs`](https://cog-arena.vercel.app/docs) on the live site.

## Psych-101 / Psych-201 overlap

Many CogArena tasks have direct counterparts in [Psych-101](https://huggingface.co/datasets/marcelbinz/Psych-101) or [Psych-201](https://github.com/marcelbinz/Psych-201), which enables direct comparison of LLM behavior in text-transcript vs. interactive-browser settings. A representative subset:

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
| Random Dot Motion | — | `pirrone_2018_dots` |
| Moral Judgment | — | `awad2018moral` |
| Loss Aversion | — | `spektor2024lossaversion` |
| Context Effects | — | `spektor2019contexteffects` |
| Phishing Detection | — | `singh2019phishing` |

Full list in the task catalog.

## License

[MIT](LICENSE). Tasks ported from upstream research codebases retain their original licenses; per-task source URLs and license notes live in each `tasks/{task_id}/task_config.json`.

## Citation

```bibtex
@article{cogarena2026,
  title={CogArena: Benchmarking Multimodal Agents on Interactive Cognitive Experiments},
  year={2026}
}
```
