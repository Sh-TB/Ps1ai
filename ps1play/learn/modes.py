"""modes.py — the five EXPLICIT execution modes of the learning mission.

The mode is recorded in every episode record and every log line, so any
result can be traced back to the information sources that were legal in
that mode. evaluate_visual_only / play_visual_only are the ONLY modes
allowed to produce gameplay claims about the final policy, and they are
the only ones whose runner wires the frame-only brain (visual_only.py).
"""
from enum import Enum

EXPLORE_ASSISTED = "explore_assisted"
COLLECT_TEACHER_DATA = "collect_teacher_data"
TRAIN_STUDENT = "train_student"
EVALUATE_VISUAL_ONLY = "evaluate_visual_only"
PLAY_VISUAL_ONLY = "play_visual_only"

MODE_NAMES = (
    EXPLORE_ASSISTED,
    COLLECT_TEACHER_DATA,
    TRAIN_STUDENT,
    EVALUATE_VISUAL_ONLY,
    PLAY_VISUAL_ONLY,
)


class Mode:
    """Namespace-style holder (strings, not Enum, so records stay
    JSON-native). Validation helper only."""

    NAMES = MODE_NAMES

    @staticmethod
    def valid(name):
        return name in MODE_NAMES

    @staticmethod
    def is_visual_only(name):
        return name in (EVALUATE_VISUAL_ONLY, PLAY_VISUAL_ONLY)

    @staticmethod
    def is_assisted(name):
        return name in (EXPLORE_ASSISTED, COLLECT_TEACHER_DATA,
                        TRAIN_STUDENT)
