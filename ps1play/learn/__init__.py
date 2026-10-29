"""ps1play.learn — the learning-to-play foundation (R53 mission).

Stages (the mission's A-F) map onto five EXPLICIT modes (see modes.py):

  explore_assisted      Stage A  — boot the real game, hunt RAM anchors,
                                   verify what is visible vs hidden
  collect_teacher_data  Stage B  — episodes with frames + legal actions +
                                   RAM-derived labels (roles enforced)
  train_student         Stage C  — learned perception + learned control
                                   from pixels (+/- teacher labels)
  evaluate_visual_only  Stage D/E — the saved artifact plays; the decision
                                   path is frame-only by construction
  play_visual_only      Stage E   — same boundary, interactive long runs

THE BOUNDARY (non-negotiable): the final decision function
(ps1play/learn/visual_only.py) imports ONLY numpy + the artifact file.
It never imports ps1play, never receives a host/ram/provider object, and
is checked by tests/test_learning_boundary.py (AST scan + canary +
subprocess brain). RAM-derived values may label data for training and may
score episodes for evaluation, but they cannot reach the decision path.
"""
from ps1play.learn.modes import Mode, MODE_NAMES
from ps1play.learn.observations import (POLICY_LEGAL_ROLES, ObsField, Role,
                                        VISUAL_INPUT)
from ps1play.learn.dataset import EpisodeRecord, LearningDataset
from ps1play.learn.policy import TinyMLP

__all__ = [
    "Mode", "MODE_NAMES", "Role", "ObsField", "POLICY_LEGAL_ROLES",
    "VISUAL_INPUT", "EpisodeRecord", "LearningDataset", "TinyMLP",
]
