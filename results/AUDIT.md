# L2/L3 Spec Audit (v1.0.0 → v1.1.0)

A close audit of the v1 task suite's L2/L3 scoring specs (with the random-agent floor as evidence) surfaced four signature-design problems. This document records what changed, why, and the resulting per-task chance ceilings.

## Headline result

| Task | Random L3 (v1.0.0, n=2) | Random L3 (v1.1.0, n=8–9) | Δ |
|---|---:|---:|---:|
| tiny_alchemy | **0.700** | **0.000** | −0.700 |
| repeated_games | **0.440** | **0.250** | −0.190 |
| moral_machine | 0.060 | 0.126 | +0.066 (added 2 signatures) |
| marbles_risk | 0.060 | 0.236 | +0.176 (L2 reweighted; L3 unchanged) |
| visual_recognition | 0.440 | 0.271 | −0.169 |
| serial_recall_v2 | 0.000 | 0.000 | 0 |
| random_dot_motion_v2 | 0.300 | 0.211 | −0.089 |
| grid_bandit | 0.150 | 0.172 | +0.022 |
| effort_foraging | 0.220 | 0.208 | −0.012 |
| phishing_detection_v2 | 0.170 | 0.292 | +0.122 |

The two tasks the audit specifically targeted (`tiny_alchemy`, `repeated_games`) saw substantial reductions in their random-agent L3 floors.

## What changed

### `tasks/tiny_alchemy/scoring/level3_signatures.json`

- **`above_chance_discovery`**: `chance_level` 0.30 → 0.55. The original 0.30 threshold underestimated random play; with a growing inventory the four base elements participate in many recipes, so a uniform-random combiner empirically reaches ~0.65–0.70 success.
- **`empowerment_preference`**: **dropped entirely.** It tested whether `mean_input_recipes_in` correlated positively with `is_success`, but the correlation exists *mechanically* — random pair selection from a growing inventory keeps sampling the four base elements (high in-degree) without any cognitive selectivity. The signature fired in 8/8 random sessions in the validation sweep.
- **`non_redundant_attempts`**: rewritten to actually test what the description claims (proportion of unique `(element_a_idx, element_b_idx)` pairs in the session, against a chance ceiling of 0.85). The original implementation duplicated the empowerment_preference fields.

### `tasks/tiny_alchemy/scoring/level2_metrics.json`

- Added **`unique_pair_rate`** metric (re-uses the new `is_unique_pair` derived field). Human baseline 0.95 ± 0.05 from Brändle et al. 2023.

### `tasks/repeated_games/scoring/level3_signatures.json`

- **`non_zero_cooperation_pd`** replaced by **`cooperation_when_opp_cooperated`**. The original tested whether the player cooperated more than 10% of the time; random play (~50%) trivially passed any threshold below 0.5. The new signature is conditional: when the opponent cooperated in the previous round, the player should cooperate above 0.5. Random ~0.5 in any conditional bin lacks statistical power to fire significance; reciprocating humans pass.

### `tasks/moral_machine/scoring/level3_signatures.json`

- Added **`legality_preference_save_lawful`** (proportion `chose_legal` > 0.5, weight 1.0; Awad et al. 2018 ~0.61).
- Added **`intervention_aversion`** (proportion `chose_intervention` < 0.5, weight 0.5; Awad et al. 2018 ~0.46 — humans show mild aversion to swerving). Brings L3 coverage to match the 5 dimensions in L2.

### `tasks/marbles_risk/scoring/level2_metrics.json`

- Dropped **`prop_chose_risky`** (baseline 0.45). Random play (~0.50) landed within one SD of the baseline, so the metric could not discriminate random from risk-averse human play. The remaining `prop_chose_higher_ev` is genuinely directional.

### `scoring/score_session.py`

- Added `_augment_derived_fields()`. For tiny_alchemy, computes `is_unique_pair` per trial in scoring (rather than experiment.js) to keep jsPsych code simple. Pairs are unordered: (a,b) and (b,a) collapse.

### `harness/suites/random_floor_v1.yaml`

- Bumped `repeats` from 2 to 10. The 2-repeat random floor was too noisy to discriminate signature-design issues from small-N variance. 10 repeats give a per-task chance ceiling at the 95th percentile.

## Residual chance ceilings

After the audit, two tasks still have non-trivial random L3 floors:

- **`visual_recognition`** (mean L3 = 0.271, n=9): The headline `above_chance_discrimination` paired test is sound; the auxiliary `above_chance_accuracy` and `low_false_alarm_rate` proportion tests against chance level 0.5 fire on 30-trial small-N noise (~10–15% per session). Not a spec design issue — a sample-size issue inherent to the experiment's 30 test trials.
- **`phishing_detection_v2`** (mean L3 = 0.292, n=8): Similarly, the headline paired-discrimination signature is sound; auxiliary `above_chance_overall` and `learning_effect` tests fire on small-N noise.

For both, the meaningful signature is the paired test; the auxiliaries provide diagnostic info but contribute residual noise. Tightening `threshold_p` globally from 0.05 to 0.01 would reduce the false-positive rate ~5× across all tasks; we deferred this for v1.1 because it would also affect agent-side scoring and warrants its own validation pass. Camera-ready / v2 candidate.

## Validation method

1. `python -m harness sweep --suite harness/suites/random_floor_v1.yaml --max-parallel 4` — 100 random-agent sessions across 10 v1 tasks × 10 repeats. 85 succeeded; 15 dropped due to transient Playwright `Page.goto` networkidle timeouts (concurrency artifact, not signature-related).
2. `python -m scripts.rescore_sweeps --sweep ...` — rescore every archived session against the new specs from raw `trial_data/<task>.json`.
3. Compare per-task L3 distributions to the v1.0.0 baseline (this document).

## Affected pilot results

The audit shifts published pilot composites for the most-touched tasks:

| Model × Task | v1.0.0 composite | v1.1.0+ composite | Δ |
|---|---:|---:|---:|
| gemini-3-flash-preview × tiny_alchemy | 66.70 | **26.17** | −40.53 |
| gemini-3-flash-preview × moral_machine | 92.38 | 78.74 | −13.64 |
| gemini-3-flash-preview × marbles_risk | 87.28 | 81.92 | −5.36 |
| grok-4.1-fast × marbles_risk | 24.63 | 22.92 | −1.71 |

Mean composite for gemini-3-flash-preview across the 10 v1 tasks: **61.64 → 55.69** (−5.95). The drops reflect tightened discrimination, not a new agent capability.

## Pilot expansion at v1.1.1

After the spec audit, the canonical pilot was expanded to 6 models × 10 tasks × 1 repeat = 60 sessions, all scored under the audited specs. Mean composite per model (over completed sessions only):

| Model | Sessions OK | Mean composite |
|---|---:|---:|
| `kimi-k2.5` | 7/10 | **58.24** |
| `gemini-3-flash-preview` | 10/10 | **55.69** |
| `grok-4.1-fast` | 6/10 | 30.36 |
| `qwen3-vl-235b-instruct` | 7/10 | 27.42 |
| `gpt-5.4-nano` | 8/10 | 20.75 |
| `qwen3-vl-30b-instruct` | 7/10 | 19.61 |

Two additional models — `glm-4.6v` and `ui-tars-1.5-7b` — were attempted but produced 0/10 successful sessions because Browser-Use's strict pydantic action validator rejected their native action shapes. The suite YAMLs that reference them are kept in `harness/suites/` for reproducibility, but the failures are scaffold-compatibility data, not model-capability claims, and are excluded from the canonical results.

Notable cross-model deltas worth mentioning in the paper:

- **`repeated_games`**: `kimi-k2.5` 75.8 vs `gemini-3-flash-preview` 36.3. Gemini cooperates 0/15 in the PD block (pure defector); kimi shows reciprocal cooperation. The post-audit `cooperation_when_opp_cooperated` signature captures this directly.
- **`tiny_alchemy`**: `kimi-k2.5` 72.5 vs `gemini-3-flash-preview` 26.2 (post-audit). The audit fix (drop `empowerment_preference`, raise `above_chance_discovery` chance ceiling) means this delta now reflects genuine model selectivity, not inventory mechanics.
- **`visual_recognition`**: every model except gemini scores at or below the random floor; gemini also fails (15.1) but with L1=1.0 (completed task, picked wrong answers). This task is a robust failure mode for all v1 frontier models tested.
