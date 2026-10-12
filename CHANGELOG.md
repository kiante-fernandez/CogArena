# Changelog

Versions are git tags; the Croissant `code-archive` URL pins to the most recent.

## v1.3.0 — 2026-10-12

Level 2 now scores only performance. Camera-ready revision for NeurIPS 2026.

Level 2 maps each metric through a monotonic CDF, so exceeding the human mean
always scores higher. That is right for accuracy and wrong for anything with no
better direction, and three groups of metrics had none:
- `tasks/moral_machine/`: all five Level 2 metrics removed. They were moral
  preferences, so an agent more extreme than people outscored them, and each
  preference was counted twice (here and as its Level 3 signature).
- `tasks/marbles_risk/`: `prop_chose_higher_ev` removed. It treated risk
  neutrality as correct; expected utility leaves risk attitude open.
- `tasks/effort_foraging/`: `prop_stay_overall` and both
  `mean_residence_time_*` removed. Staying is better only up to the MVT optimum,
  so these rewarded over-harvesting: agents stayed on 96% of decisions and
  scored 0.89 on the stay rate while matching the MVT choice less often than
  random play.
The patterns themselves are still tested at Level 3. The source-study rates stay
in `scoring/human_baselines/` as reference values.

A task with no Level 2 metrics now has no Level 2 (`None`), not a Level 2 of 0:
- `scoring/composite_score.py`: such a task's composite splits the L2 weight
  over L1 and L3 in proportion (`effective_weights`), keeping the 0-100 scale.
  Analysis scripts reuse the same rule.
- `harness/db/`: `scores.l2_accuracy` is nullable. `migrate` rebuilds a table
  whose live schema still has NOT NULL on a column the models declare nullable,
  so existing databases (including production) migrate on the next cold start.
- Scorecard, admin list and leaderboard means skip a missing L2; the UI shows a
  dash. CLI scorecards print `n/a`.

Signature labels (`construct_type`), no score change:
- `repeated_games/cooperation_when_opp_cooperated` is a capacity. Against a fixed
  tit-for-tat opponent over a known 15-round horizon, the best response
  cooperates every round but the last.
- `marbles_risk/magnitude_effect_high_payoff` is a capacity (choice rising with
  payoff at matched probability, which expected utility requires);
  `above_chance_ev_optimal` is a bias (risk neutrality).

Effect on the archive, all 578 sessions re-scored, no agent re-runs: L1, L3 and
measurability unchanged in every row. Panel mean L2 over measurable sessions
0.439 -> 0.345 (floor 0.139 -> 0.159); composite 53.0 -> 52.0 (floor 29.05 ->
31.31). Model ranking identical under every convention and weighting.

## v1.2.0 — 2026-07-25

Rebuttal revision for NeurIPS 2026. Full record with per-change measured effects
in the change record kept alongside the manuscript.

Design: 4 models x 10 tasks x **5 repeats** = 200 sessions, replacing the single
session per cell reported at v1.1.1. Scored coverage 45/60 (75%) -> 188/200 (94%).

Instrumentation fixes — agents were penalised for harness behaviour:
- `harness/eval.py`: archive every task the run attempted, not only those that
  scored. Recovered 1,905 discarded trials; 13 of the 15 cells v1.1.1 reports as
  failures hold scorable data, 3 of them at full L1 completion.
- `static/skill.md`: drop the instruction to POST to `/api/evaluate`, which
  browser-driving agents cannot issue (140 `405`s across the archive).
- `agents/browser_use_agent.py`: archive screenshots for LLM runs and record the
  resolved observation mode instead of asserting `"screenshot"`.

Scoring fixes — all re-score archived data, no agent re-runs:
- `scoring/level3_behavioral.py`: exclude untestable signatures from L3 rather
  than scoring them 0.0. **Changes what L3 means**; pre- and post-change numbers
  are not comparable, including the random floor.
- `scoring/analysis_templates/proportion_test.py`: exact binomial, and flag
  signatures no behaviour could pass at the given n.
- `tasks/repeated_games/`: `tit_for_tat_reciprocity_pd` becomes a Fisher exact
  conditional contrast; the Pearson version was undefined against a tit-for-tat
  opponent and returned nan in every session.
- `tasks/grid_bandit/`: `prop_high_value_clicks` declared an unread `compute` key
  and measured truthiness, returning 1.0 for every agent. L2 0.447 -> 0.334.
- Reaction time moves from L2 absolute comparison to six L3 relational
  signatures. L2 0.345 -> 0.380, L3 0.392 -> 0.376.

Headline finding:
- **The v1.1.1 rank reversal does not survive repeats.** `gemini-3-flash-preview`
  is rank 1 under both averaging conventions with bootstrap P(rank 1) = 1.00
  (61.88 vs `kimi-k2.5` 45.24). Section 5's kimi-first ordering was an artifact of
  one session per cell plus selective coverage.
- Mean L3 0.251 -> 0.376, driven by 270 of 736 signature observations (37%) that
  are untestable and were previously scored as behavioural failures.
- Agents pass RT-relational signatures 11/97 times (11%); 0 of 7 canonical RT
  relations reproduce above chance, with within-session RT variability in the
  human range.

## v1.1.1 — 2026-05-05

Pilot coverage expansion. No spec changes from v1.1.0.

- Add 5 more models to `results/pilot_v1.csv`: `kimi-k2.5`, `qwen3-vl-235b-instruct`, `qwen3-vl-30b-instruct`, `gpt-5.4-nano`. Canonical pilot now 6 models × 10 tasks × 1 repeat = 60 rows (was 30 rows / 3 models at v1.1.0).
- New suite YAMLs in `harness/suites/`: `pilot_v1_addons.yaml` (kimi + qwen-235), `pilot_v1_addons2.yaml` (qwen-30 + ui-tars + nano).
- Two models (`glm-4.6v`, `ui-tars-1.5-7b`) excluded from canonical CSV because Browser-Use's pydantic action validator rejected their native action shapes. The suite YAMLs that reference them are kept in the repo so the failure pattern is reproducible from a clean clone.

Headline finding (paper-relevant):
- `kimi-k2.5` takes the top spot at 58.24 mean composite (over 7 completed tasks); `gemini-3-flash-preview` is the most consistent at 55.69 over all 10.

## v1.1.0 — 2026-05-05

L2 / L3 scoring spec audit; per-task before/after is recorded with the manuscript.

- `tasks/tiny_alchemy/scoring/level3_signatures.json`: drop `empowerment_preference` (fired 8/8 random sessions); raise `above_chance_discovery` chance level 0.30 → 0.55; rewrite `non_redundant_attempts` to actually test unique-pair attempts.
- `tasks/tiny_alchemy/scoring/level2_metrics.json`: add `unique_pair_rate` metric.
- `tasks/repeated_games/scoring/level3_signatures.json`: replace `non_zero_cooperation_pd` (random trivially passed 0.10 threshold) with `cooperation_when_opp_cooperated` (conditional reciprocity test against 0.5 chance level).
- `tasks/moral_machine/scoring/level3_signatures.json`: add `legality_preference_save_lawful` and `intervention_aversion` signatures (5-of-5 dimension coverage).
- `tasks/marbles_risk/scoring/level2_metrics.json`: drop non-discriminative `prop_chose_risky` metric.
- `scoring/score_session.py`: add `_augment_derived_fields()` helper computing `is_unique_pair` per trial.
- `harness/suites/random_floor_v1.yaml`: bump `repeats` 2 → 10 for tighter chance-ceiling estimates.
- `scripts/rescore_sweeps.py`: new utility — re-score archived sessions against current specs without re-running agents.
- `scripts/rescore_production.py`: new utility — POST `/api/evaluate/{id}` for every scored session on a remote server.

Random-agent floor changes:
- `tiny_alchemy`: mean L3 0.700 → 0.000.
- `repeated_games`: mean L3 0.440 → 0.250.
- The complete table is recorded with the manuscript.

Pilot composite shifts (gemini-3-flash-preview):
- `tiny_alchemy`: 66.70 → 26.17.
- `moral_machine`: 92.38 → 78.74.
- Mean: 61.64 → 55.69.

## v1.0.0 — 2026-05-05

Initial NeurIPS 2026 E&D Track submission tag.

- 10 v1 tasks: `random_dot_motion_v2`, `grid_bandit`, `marbles_risk`, `repeated_games`, `serial_recall_v2`, `visual_recognition`, `effort_foraging`, `tiny_alchemy`, `moral_machine`, `phishing_detection_v2`.
- 3-level scoring (L1 completion / L2 accuracy / L3 behavioral signatures); composite = 0.15·L1 + 0.35·L2 + 0.50·L3, scaled to 100.
- Reference results: random-agent chance floor (`results/random_floor_v1.csv`) + frontier-model pilot (`results/pilot_v1.csv`, 3 models initially: `gemini-3-flash-preview`, `grok-4.1-fast`, `glm-4.6v`).
- Croissant 1.0 metadata with all 7 RAI fields (3 base + 4 NeurIPS-required).
- 374 tests passing (10 harness unit + 313 scoring + 51 field-alignment).
- Public site at `cog-arena.vercel.app` with leaderboard, /catalog, /try, /submit, /skill.md.
