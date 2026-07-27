# Human baseline source data

The participant-level datasets that eight of the ten v1 L2 baselines are
computed from. Each file is the original authors' released data, renamed to
`author_year_task` so the folder is navigable; nothing has been altered except
one column-subset noted below.

Re-derive every number with:

```bash
python -m scripts.derive_baselines            # recompute and compare to the specs
python -m scripts.baseline_sources --verify   # check the files are unmodified
```

The corresponding `human_mean` / `human_sd` live in
`tasks/{task}/scoring/level2_metrics.json`, and each task's
`scoring/human_baselines/{task}.json` note records exactly how its numbers were
derived from the file listed here.

---

## Files

### `witte_2024_grid_bandit_study1.csv` → `grid_bandit`
**Witte, K., Wise, T., Huys, Q. J. M. & Schulz, E. (2024).** Exploring the
Unexplored: Worry as a Catalyst for Exploratory Behavior in Anxiety and
Depression. *PsyArXiv.* doi:[10.31234/osf.io/td8xh](https://doi.org/10.31234/osf.io/td8xh)

Source: `github.com/KristinWitte/worried_exploration` → `Study1/data/master.csv`
· 26,565 clicks, n=220 · Licence: MIT (repo)

Supplies `mean_reward_per_click`, `mean_reward_safe`, `mean_reward_risky`,
`prop_high_value_clicks`, `kraken_caught_rate_risky`. Our port reuses this
study's reward grids verbatim.

### `akata_2025_repeated_games_human.csv` → `repeated_games`
**Akata, E., Schulz, L., Coda-Forno, J., Oh, S. J., Bethge, M. & Schulz, E.
(2025).** Playing repeated games with large language models. *Nature Human
Behaviour.* doi:[10.1038/s41562-025-02172-y](https://doi.org/10.1038/s41562-025-02172-y)
(preprint arXiv:2305.16867)

Source: `github.com/eliaka/repeatedgames` →
`human_experiment/analysis/repgames.csv` · 3,900 rounds, n=195 Prolific

Supplies `coop_rate_pd`, `mean_payoff_pd`, `coordination_rate_bos`,
`mean_payoff_bos`. **Note:** these humans played GPT-4; our port plays a fixed
tit-for-tat / alternating bot. Payoff matrices match exactly.

### `ciranka_2025_marbles_trials.csv` → `marbles_risk`
**Ciranka, S. & van den Bos, W. (2025).** Internal uncertainty impacts social
information use in risky choice across adolescence. *Communications Psychology*
3:137. doi:[10.1038/s44271-025-00314-6](https://doi.org/10.1038/s44271-025-00314-6)

Source: Zenodo doi:[10.5281/zenodo.16738297](https://doi.org/10.5281/zenodo.16738297)
→ `DevelopingMarbles_zenodo/A_raw_data/TidyMarbleNew.csv` · 23,887 trials, n=166
· Licence: CC-BY (Zenodo record)

Supplies `prop_chose_higher_ev`, computed from `valueGamble × probGamble` against
`valueSure`. Sample is ages 10–26; adults 18+ give 0.725 against the full
sample's 0.728, so the developmental spread does not bias this metric.

### `awad_2018_moral_machine_amce_fig2a.rdata` → `moral_machine`
**Awad, E., Dsouza, S., Kim, R., Schulz, J., Henrich, J., Shariff, A., Bonnefon,
J.-F. & Rahwan, I. (2018).** The Moral Machine experiment. *Nature* 563:59–64.
doi:[10.1038/s41586-018-0637-6](https://doi.org/10.1038/s41586-018-0637-6)

Source: OSF [osf.io/3hvt2](https://osf.io/3hvt2) →
`Datasets/Moral Machine Effect Sizes/plotdatamain.rdata` · Figure 2a source
data, n = 35.2M decisions

Two files: the original `.rdata` as downloaded, and
`awad_2018_moral_machine_amce_fig2a.csv` extracted from it, which is what the
derivation reads. The extraction is exact — the RData carries the `Label` factor
codes `[9,8,4,7,6,5,3,2,1]` alongside the estimates, so each value is tied to its
attribute by the file rather than by inferring an order:

| attribute | ΔP | s.e. |
|---|---|---|
| Species | 0.582736 | 0.000947 |
| No. Characters | 0.508132 | 0.000662 |
| Age | 0.490328 | 0.000788 |
| Law | 0.351348 | 0.000925 |
| Social Status | 0.345112 | 0.001504 |
| Fitness | 0.160909 | 0.000590 |
| Gender | 0.116780 | 0.000667 |
| Relation to AV | 0.096815 | 0.000653 |
| Intervention | 0.060556 | 0.000355 |

Cross-check: the Fig 2 caption states the Age effect as 0.49, against the file's
0.490328. Supplies all five `prop_*` metrics via `p = (1 + ΔP) / 2`. Not raw
trials — this is the published effect-size table, so the standard errors reflect
n = 35.2M and are **not** usable as `human_sd` (between-person variation).

### `haridi_2025_serial_recall_exp1.csv` → `serial_recall_v2`
**Haridi, S., Schulz, E. & Thalmann, M. (2025).** Context Size and Set Size
Effects: The Relevance of Specific Cues When Searching Long-Term Memory.
*Computational Brain & Behavior* 9:1–33.
doi:[10.1007/s42113-025-00255-7](https://doi.org/10.1007/s42113-025-00255-7)

Source: `github.com/susanneharidi/memoryscaling` →
`ExperimentDataAndAnalysis/Experiment1/ExperimentDataExp1W2VSim.csv` · 35,856
trials, n=116 after the preregistered `validID` exclusion

Supplies `overall_accuracy`, `accuracy_low_sim`, `accuracy_high_sim`, restricted
to `ListLength == 16` to match our port's 16 word pairs.

### `singh_2019_phishing_exp1_outcomefeedback.csv` → `phishing_detection_v2`
**Singh, K., Aggarwal, P., Rajivan, P. & Gonzalez, C. (2019).** Training to
Detect Phishing Emails: Effects of the Frequency of Experienced Phishing Emails.
*Proceedings of the Human Factors and Ergonomics Society* 63:453–457.
doi:[10.1177/1071181319631355](https://doi.org/10.1177/1071181319631355)

Source: `github.com/DDM-Lab/PhishingTrainingTask` →
`Data/experiment1-outcomefeedback.csv` · 18,349 trials, n=296 MTurk

Supplies all five metrics, from the `50_OutFeed` arm's training phase — the only
phase at the 50% phishing rate our port uses throughout.

### `desender_2021_random_dot_motion.csv` → `random_dot_motion_v2`
**Desender, K., Donner, T. H. & Verguts, T. (2021).** Dynamic expressions of
confidence within an evidence accumulation framework. *Cognition* 207:104522.
doi:[10.1016/j.cognition.2020.104522](https://doi.org/10.1016/j.cognition.2020.104522)

Source: The Confidence Database, OSF [osf.io/s46pr](https://osf.io/s46pr) →
`data_Desender_2021_Cognit.csv` · 22,080 trials, n=30

Chosen from the Confidence Database's 43 dot-motion datasets because its
coherence levels (.05, .1, .2, .4) are four of our five. Supplies
`overall_accuracy` and the three per-coherence metrics; the .80 level is
extrapolated by a Weibull fit and flagged as such in the task note.

The Confidence Database itself: **Rahnev, D. et al. (2020).** The Confidence
Database. *Nature Human Behaviour* 4:317–325.
doi:[10.1038/s41562-019-0813-1](https://doi.org/10.1038/s41562-019-0813-1)

### `bustamante_2023_effort_foraging_exp1_slim.csv` → `effort_foraging`
**Bustamante, L. A. et al. (2023).** Effort Foraging Task reveals positive
correlation between individual differences in the cost of cognitive and physical
effort. *PNAS* 120(50):e2221510120.
doi:[10.1073/pnas.2221510120](https://doi.org/10.1073/pnas.2221510120)

Design ancestor, and the correct citation for our port's travel-*time*
manipulation: **Constantino, S. M. & Daw, N. D. (2015).** Learning the
opportunity cost of time in a patch-foraging task. *Cognitive, Affective, &
Behavioral Neuroscience* 15(4):837–853.
doi:[10.3758/s13415-015-0350-y](https://doi.org/10.3758/s13415-015-0350-y)

Source: OSF [osf.io/a4r2e](https://osf.io/a4r2e) →
`data/experiment_1/choiceData_experiment_1.csv` · 350,608 decisions, n=537

**This is the one modified file.** The original is 204 MB across 69 columns;
this copy keeps the 10 columns the derivation reads (`subject_id`,
`is_practice`, `decision`, `effort_level`, `patch_n_harvests`,
`travel_duration`, `harvest_duration`, `depletion_rate_mean`,
`start_reward_mean`, `round`) and is 28 MB. Row count and values are unchanged.
Re-fetch the full file from the URL above if you need the other columns.

Supplies `prop_stay_overall` directly. Residence times are *calibrated* rather
than transferred, because their travel duration is fixed at 8.33 s in both
conditions while our port varies travel time 4 s vs 8 s — see the task note.

---

## Tasks with no usable public archive

**`visual_recognition`** — Brady, T. F., Konkle, T., Alvarez, G. A. & Oliva, A.
(2008), *PNAS* 105(38):14325–14329, doi:10.1073/pnas.0803390105, predates data
sharing. All 28 Memory datasets in the Confidence Database were checked:
`Kreis_2019` is continuous-report rather than old/new, `Skora_unpub` is change
detection, and the rest use words, faces, paintings or scenes. Since lure
similarity sets old/new difficulty and our lures come from the studied items'
own 768-combination feature space, none is a better basis than converting
Brady's exemplar-condition 2AFC accuracy through the standard d′ identity.

**`tiny_alchemy`** — Brändle, F., Stocks, L. J., Tenenbaum, J. B., Gershman,
S. J. & Schulz, E. (2023), *Nature Human Behaviour* 7:1481–1489,
doi:10.1038/s41562-023-01661-2. The 29,493-player dataset is held outside the
repo and shared on request; the repository's only behavioural file is a
15-participant rating study. `novelty_rate` is derived from Figure 1c
(mean 158.06 trials, mean final inventory 50.91 from 4 starting elements);
`success_rate` and `unique_pair_rate` remain author estimates.

---

## Licensing

These are third-party research datasets, redistributed here unmodified (except
the documented Bustamante column subset) for reproducibility of the baselines.
Each remains under its original licence and should be cited to its own paper,
not to CogArena. If any author objects to redistribution, delete the file — the
derivation re-downloads it from the URLs above via
`python -m scripts.baseline_sources --fetch`.
