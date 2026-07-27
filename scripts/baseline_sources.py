"""The human datasets every empirical L2 baseline is computed from.

Eight of the ten v1 tasks score against statistics derived from the original
authors' released participant data rather than from author estimates. This
module is the single place that records WHICH file each number came from, WHERE
to get it, and WHAT it hashes to — so a reviewer, or we in six months, can
re-download the archives and re-derive every value.

    python -m scripts.baseline_sources --fetch     # download to data/baseline_sources/
    python -m scripts.baseline_sources --verify    # check hashes of what is on disk

The files total ~211 MB and live under ``data/``, which is gitignored: they are
third-party archives with their own licences and do not belong in this repo.
Only this manifest and the derivation in ``scripts/derive_baselines.py`` are
version-controlled, which is what makes the numbers checkable without
redistributing anyone's data.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "data" / "baseline_sources"

# task -> (local filename, download URL, sha256, citation, what it supplies)
SOURCES: dict[str, dict] = {
    "grid_bandit": {
        "file": "witte_grid_bandit_master.csv",
        "url": "https://raw.githubusercontent.com/KristinWitte/worried_exploration/main/Study1/data/master.csv",
        "sha256": "ab2ea3cfb390a0c3",
        "citation": "Witte, K., Wise, T., Huys, Q. J. M. & Schulz, E. (2024), 'Exploring the "
                    "Unexplored', PsyArXiv doi:10.31234/osf.io/td8xh, Study 1",
        "scale": "26,565 clicks, n=220",
        "supplies": "mean_reward_per_click, mean_reward_safe, mean_reward_risky, "
                    "prop_high_value_clicks, kraken_caught_rate_risky",
    },
    "repeated_games": {
        "file": "akata_repgames.csv",
        "url": "https://raw.githubusercontent.com/eliaka/repeatedgames/main/human_experiment/analysis/repgames.csv",
        "sha256": "f3c3d46a2e34f85f",
        "citation": "Akata, E. et al. (2025), 'Playing repeated games with large language "
                    "models', Nature Human Behaviour, doi:10.1038/s41562-025-02172-y",
        "scale": "3,900 rounds, n=195",
        "supplies": "coop_rate_pd, mean_payoff_pd, coordination_rate_bos, mean_payoff_bos",
    },
    "marbles_risk": {
        "file": "ciranka_TidyMarbleNew.csv",
        "url": "https://zenodo.org/api/records/16738297/files/DevelopingMarbles_zenodo.zip/content"
               "  (extract A_raw_data/TidyMarbleNew.csv)",
        "sha256": "6e586682af4096a4",
        "citation": "Ciranka, S. & van den Bos, W. (2025), Communications Psychology 3:137, "
                    "doi:10.1038/s44271-025-00314-6; archive doi:10.5281/zenodo.16738297",
        "scale": "23,887 trials, n=166",
        "supplies": "prop_chose_higher_ev",
    },
    "moral_machine": {
        "file": "awad_plotdatamain.rdata",
        "url": "https://osf.io/download/u58en/",
        "sha256": "fab359b7ffecca18",
        "citation": "Awad, E. et al. (2018), Nature 563:59-64, doi:10.1038/s41586-018-0637-6; "
                    "OSF osf.io/3hvt2, Datasets/Moral Machine Effect Sizes/plotdatamain.rdata",
        "scale": "Figure 2a source data, n = 35.2M decisions",
        "supplies": "prop_utilitarian, prop_save_young, prop_save_human, prop_save_legal, "
                    "prop_intervention",
    },
    "serial_recall_v2": {
        "file": "haridi_exp1_w2vsim.csv",
        "url": "https://raw.githubusercontent.com/susanneharidi/memoryscaling/main/"
               "ExperimentDataAndAnalysis/Experiment1/ExperimentDataExp1W2VSim.csv",
        "sha256": "3bd1c3fb58988bcc",
        "citation": "Haridi, S., Schulz, E. & Thalmann, M. (2025), Computational Brain & "
                    "Behavior 9:1-33, doi:10.1007/s42113-025-00255-7",
        "scale": "35,856 trials, n=116 after the preregistered validID exclusion",
        "supplies": "overall_accuracy, accuracy_low_sim, accuracy_high_sim",
    },
    "phishing_detection_v2": {
        "file": "singh_experiment1_outcomefeedback.csv",
        "url": "https://raw.githubusercontent.com/DDM-Lab/PhishingTrainingTask/main/"
               "Data/experiment1-outcomefeedback.csv",
        "sha256": "b5069dd2d4dc0d36",
        "citation": "Singh, K., Aggarwal, P., Rajivan, P. & Gonzalez, C. (2019), Proc. Human "
                    "Factors and Ergonomics Society 63:453-457",
        "scale": "18,349 trials, n=296",
        "supplies": "overall_accuracy, pre_training_accuracy, post_training_accuracy, "
                    "hit_rate, false_alarm_rate",
    },
    "random_dot_motion_v2": {
        "file": "desender_2021_cognit.csv",
        "url": "https://osf.io/download/3t98v/",
        "sha256": "67977a1e027f6e8d",
        "citation": "Desender, K., Donner, T. H. & Verguts, T. (2021), Cognition 207:104522, "
                    "doi:10.1016/j.cognition.2020.104522; via the Confidence Database, "
                    "osf.io/s46pr, data_Desender_2021_Cognit.csv",
        "scale": "22,080 trials, n=30; coherences .05/.1/.2/.4 match this port's",
        "supplies": "overall_accuracy, accuracy_low_coherence, accuracy_medium_coherence, "
                    "accuracy_high_coherence",
    },
    "effort_foraging": {
        "file": "bustamante_choiceData_exp1.csv",
        "url": "https://osf.io/download/prf8h/",
        "sha256": "af712b5ef8a30b03",
        "citation": "Bustamante, L. A. et al. (2023), PNAS 120(50):e2221510120; data at "
                    "osf.io/a4r2e, data/experiment_1/choiceData_experiment_1.csv. Design "
                    "ancestor: Constantino, S. M. & Daw, N. D. (2015), Cogn Affect Behav "
                    "Neurosci 15(4):837-853",
        "scale": "350,608 decisions, n=537",
        "supplies": "prop_stay_overall (direct); mean_residence_time_low/high (calibrated "
                    "to this port's MVT optimum, see the baseline note)",
    },
}

# Tasks with no usable public archive, recorded so the gap is explicit.
NO_ARCHIVE = {
    "visual_recognition": "Brady et al. (2008) predates data sharing. All 28 Memory datasets "
                          "in the Confidence Database were checked; none is old/new "
                          "recognition with lures drawn from the studied items' own feature "
                          "space, which is what sets this port's difficulty.",
    "tiny_alchemy": "Brandle et al. (2023) store the 29,493-player dataset outside the repo "
                    "and share it on request. The repo's only behavioural file is a "
                    "15-participant rating study.",
}


def _sha256_prefix(path: Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def verify() -> int:
    """Check every recorded file is present and unchanged."""
    bad = 0
    for task, s in SOURCES.items():
        p = SOURCE_DIR / s["file"]
        if not p.exists():
            print(f"  MISSING  {task:24s} {s['file']}")
            bad += 1
            continue
        got = _sha256_prefix(p)
        ok = got == s["sha256"]
        print(f"  {'ok     ' if ok else 'CHANGED'}  {task:24s} {s['file']:44s} {got}")
        bad += 0 if ok else 1
    for task, why in NO_ARCHIVE.items():
        print(f"  n/a      {task:24s} no public archive")
    return bad


def fetch() -> int:
    """Download every archive that is missing or altered."""
    import urllib.request
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for task, s in SOURCES.items():
        p = SOURCE_DIR / s["file"]
        if p.exists() and _sha256_prefix(p) == s["sha256"]:
            print(f"  have    {task}")
            continue
        url = s["url"].split("  ")[0]
        if url.endswith("/content"):
            print(f"  MANUAL  {task}: {s['url']}")
            failed += 1
            continue
        print(f"  fetch   {task} <- {url}")
        try:
            urllib.request.urlretrieve(url, p)
        except Exception as e:  # noqa: BLE001
            print(f"          FAILED: {e}")
            failed += 1
    return failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch", action="store_true", help="Download missing archives.")
    ap.add_argument("--verify", action="store_true", help="Check hashes on disk.")
    args = ap.parse_args(argv)
    if args.fetch:
        return 1 if fetch() else 0
    if args.verify or True:
        print(f"Baseline source archives in {SOURCE_DIR}:")
        return 1 if verify() else 0


if __name__ == "__main__":
    sys.exit(main())
