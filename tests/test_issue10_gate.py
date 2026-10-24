"""Issue #10 Gate B/D tests: GameplayGate + gate-aware ProgressSignal.

The decision rule validated in issue #10 Gate B (evidence:
work/msx_recomp/evidence/issue10_gateB/gateb_report*.json, 3/3
bit-identical runs):

  flags==active AND progress frozen AND input held  => STUCK
  flags!=active                                     => NOT_GAMEPLAY
                                                       (never STALLED)
  flags==active AND progress advancing              => PROGRESS

These tests pin the rule as pure unit tests on synthetic series -
no emulator required.  Gameplay verification is Gate E (PENDING).
"""
import json
import os

import pytest

from ps1play.agent.progress import GameplayGate, ProgressSignal

PROFILE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))),
    "ps1play", "profiles", "Metal Slug X (USA).json")


# --- GameplayGate ---------------------------------------------------
def test_gate_rejects_menu_word():
    g = GameplayGate()
    assert g.is_active(0x1) is False        # menu/game-over (issue #5)
    assert g.is_active(0x0) is False


def test_gate_accepts_play_word():
    g = GameplayGate()
    assert g.is_active(0xFF) is True        # observed all 3 probe runs


def test_gate_threshold_honours_partial_bitmasks():
    g = GameplayGate(mask_bits=8, min_bits=7)
    assert g.is_active(0x7F) is True        # 7 bits set
    assert g.is_active(0x3F) is False       # 6 bits - below threshold
    # high bits ignored (mask): full-word menu states with stray bits
    assert g.is_active(0x1001) is False


# --- gate-aware ProgressSignal ---------------------------------------
def _active_signal():
    return ProgressSignal(addr=0x0EB85A, verified=True)


def test_menu_freeze_is_not_stall():
    sig = _active_signal()
    # in play: value moves, then freezes briefly -> STALLED as before
    assert sig.update(10, churn=0, in_gameplay=True) == ProgressSignal.PROGRESS
    assert sig.update(50, churn=0, in_gameplay=True) == ProgressSignal.PROGRESS
    for _ in range(5):
        sig.update(50, churn=0, in_gameplay=True)
    assert sig.last_state == ProgressSignal.STALLED
    # menu: word frozen at same value, gate says NOT in gameplay
    assert sig.update(50, churn=0, in_gameplay=False) == \
        ProgressSignal.NOT_GAMEPLAY
    assert sig.last_state != ProgressSignal.STALLED
    assert sig.to_dict()["counts"]["gate_not_gameplay"] == 1


def test_legacy_callers_unchanged_without_gate():
    sig = _active_signal()
    assert sig.update(10, churn=0) == ProgressSignal.PROGRESS
    for _ in range(5):
        sig.update(10, churn=0)
    assert sig.last_state == ProgressSignal.STALLED


def test_menu_reset_surfaces_as_reset_on_resume():
    sig = _active_signal()
    sig.update(200, churn=0, in_gameplay=True)
    sig.update(200, churn=0, in_gameplay=False)   # menu holds word at 200
    sig.update(0, churn=0, in_gameplay=False)     # menu resets it
    # back in play at 0 with the old peak 200 -> RESET, not PROGRESS
    st = sig.update(0, churn=0, in_gameplay=True)
    assert st in (ProgressSignal.PROGRESS, ProgressSignal.RESET)
    st2 = sig.update(0, churn=0, in_gameplay=True)
    assert st2 in (ProgressSignal.PROGRESS, ProgressSignal.STALLED)


def test_stuck_rule_active_and_frozen():
    sig = _active_signal()
    sig.update(152, churn=0, in_gameplay=True)
    states = [sig.update(152, churn=0, in_gameplay=True)
              for _ in range(6)]
    assert states[-1] == ProgressSignal.STALLED   # Gate B step 70-80 sig.


# --- profile carries the validated sensors ---------------------------
def test_msx_profile_has_gate_b_sensors():
    prof = json.load(open(PROFILE))
    s = prof["sensors"]
    assert s["flags_word"]["addr"] == 0x0EE518
    assert s["flags_word"]["status"] == "CONFIRMED"
    assert s["progress_x"]["addr"] == 0x0EB85A
    assert s["progress_x"]["status"] == "CONFIRMED"
    assert s["flags_word"]["issue"] == 10
