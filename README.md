# CogArena

[![NeurIPS 2026](https://img.shields.io/badge/NeurIPS%202026-Evaluations%20%26%20Datasets%20Track-4b44ce)](#citation)

> **Accepted at NeurIPS 2026.** CogArena will appear in the Evaluations and Datasets Track of the 40th Conference on Neural Information Processing Systems. See [Citation](#citation) below.

Claims about the cognitive capabilities of large language models are typically tested by translating behavioral paradigms into natural language prompts, bypassing the visual interfaces and time-pressured interactions through which human participants actually engage with experiments. In parallel, recent demonstrations that AI agents can produce human-like response data on live behavioral tasks raise concerns that online datasets used across the social and behavioral sciences are increasingly susceptible to contamination. We introduce CogArena, a benchmark of ten experimental paradigms drawn from social and behavioral science. Agents interact with the experiments through a standard browser, processing visual stimuli and responding under configurable deadlines. We designed a three-level scoring pipeline that evaluates task completion, performance accuracy, and alignment with canonical task-specific signatures. Across four economy-tier multimodal agents, each run ten times per task, we find that completing an experiment and reproducing its behavioral signatures are separable. Agents that finish a task reproduce some of the signatures these paradigms reliably elicit in people and not others, and many attempted sessions do not produce complete data at all. CogArena provides the tasks, scoring pipeline, and a public leaderboard for ongoing community submissions.

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
@inproceedings{cogarena2026,
  title     = {{CogArena}: Benchmarking Multimodal Agents on Interactive Behavioral Experiments},
  author    = {Fernandez, Kiant{\'e} and Chen, Caitlin and Zhou, Jialu and Sadowski, Bartek and Miceli, Anthony C. and Krajbich, Ian},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS 2026), Evaluations and Datasets Track},
  year      = {2026}
}
```
