"""The v1 launch task set.

A leaf module on purpose: ``scoring.version`` hashes these tasks' specs to build
the scorer version, and ``harness.server`` filters the site to them. Keeping the
constant here means neither has to import the other.
"""
from __future__ import annotations

# The ten curated tasks foregrounded on the deployment site for the NeurIPS 2026
# D&B v1 paper. The broader 30+ tasks remain on disk and stay discoverable via
# /api/tasks for direct use.
V1_TASK_IDS: frozenset[str] = frozenset({
    "random_dot_motion_v2",
    "grid_bandit",
    "marbles_risk",
    "repeated_games",
    "moral_machine",
    "tiny_alchemy",
    "visual_recognition",
    "serial_recall_v2",
    "phishing_detection_v2",
    "effort_foraging",
})
