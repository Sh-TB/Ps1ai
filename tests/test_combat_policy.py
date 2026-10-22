"""tests/test_combat_policy.py — offline logic tests for CombatPolicy
(Issue #5 focused follow-up session 3: facing / rear-engage / clamp).

Pure-logic: no emulator, no RAM. The scan schema is ps1play-combat-scan/1.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.agent.combat import (                     # noqa: E402
    CombatPolicy, scan_entities, ENGAGE_WINDOW, REAR_ENGAGE)


class FakeMem:
    """Minimal entity-table stand-in: slot-word packing only."""

    def __init__(self, slots, px=1000.0, hp=144):
        # slots: {slot_index: (x_fixed, hp)}
        self.slots = slots
        self.TABLE = 0x0CA268
        self.STRIDE = 0x14C
        self._px = int(px * 65536)
        self._hp = hp

    def u32(self, addr):
        if addr == 0x0CA2E0:
            return self._px
        s, off = divmod(addr - self.TABLE, self.STRIDE)
        if s in self.slots and off == 0x78:
            return self.slots[s][0]
        return 0

    def u16(self, addr):
        s, off = divmod(addr - self.TABLE, self.STRIDE)
        if s in self.slots and off == 0x8E:
            return self.slots[s][1]
        if addr == 0x0CA2F6:
            return self._hp
        return 0


def _scan(slots, px=1000.0):
    m = FakeMem(slots, px=px)
    return scan_entities(m)


# ---------------------------------------------------------------
def test_scan_excludes_player_and_transients():
    slots = {0: (int(1000 * 65536), 144),     # player: excluded
             1: (int(1100 * 65536), 90),      # soldier ahead
             2: (int(900 * 65536), 352),      # armored vehicle behind
             3: (int(950 * 65536), 65505),    # signed-negative transient
             4: (int(1200 * 65536), 700)}     # hp>600: not an enemy
    out = scan_entities(FakeMem(slots))
    # scan_entities reads player px from PLAYER_X (FakeMem._px)
    got = {e["slot"] for e in out}
    assert got == {1, 2}, got
    by = {e["slot"]: e for e in out}
    assert by[1]["dx_px"] == 100.0
    assert by[2]["dx_px"] == -100.0
    # nearest first
    assert out[0]["slot"] in (1, 2)


def test_scan_window():
    slots = {5: (int(1500 * 65536), 50)}      # 500px away: out of window
    assert scan_entities(FakeMem(slots)) == []
    slots2 = {5: (int(1380 * 65536), 50)}     # 380px: inside
    out = scan_entities(FakeMem(slots2))
    assert len(out) == 1 and abs(out[0]["dx_px"] - 380) < 1


def test_rear_enemy_defensive_clear_at_clamp():
    """v5: mid-run the agent does NOT turn back for chasers (the
    instrumented death pattern); at the end-clamp it takes the
    DEFENSIVE stance and fires LEFT at them."""
    pol = CombatPolicy()
    enemies = [{"slot": 2, "x_px": 920.0, "dx_px": -80.0, "hp": 100}]
    pol.decide(60, 1000.0, enemies, grenades=0, hp=100)
    assert pol.mode == "advance"             # mid-run: keep running
    pol.observe(1000.0, 0.5, True)
    pol.observe(1000.5, 0.2, True)           # end-clamp detected
    segs = pol.decide(60, 1000.5, enemies, grenades=0, hp=100)
    btns = set().union(*[s["btns"] for s in segs])
    assert "LEFT" in btns or "UP" in btns    # defensive clear
    assert pol.mode == "clamp_clear"


def test_front_enemy_faces_right():
    pol = CombatPolicy()
    enemies = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90}]
    segs = pol.decide(60, 1000.0, enemies, grenades=0)
    btns = set().union(*[s["btns"] for s in segs])
    assert "RIGHT" in btns and "LEFT" not in btns
    assert "Y" in btns
    assert pol.mode == "engage"


def test_midrange_front_enemy_keeps_running():
    """v4: mid-range front enemies do not stop the run — the forward
    fire bursts kill them during the walk-through."""
    pol = CombatPolicy()
    enemies = [{"slot": 1, "x_px": 1120.0, "dx_px": 120.0, "hp": 90}]
    pol.decide(60, 1000.0, enemies, grenades=0, hp=100)
    assert pol.mode == "advance"


def test_pointblank_front_engaged_chasers_ignored():
    """v5: mid-run only a point-blank FRONT threat stops the run; a
    close rear chaser does NOT turn the agent around (evidence: all
    baseline deaths were at the clamp, never behind mid-run)."""
    pol = CombatPolicy()
    enemies = [{"slot": 1, "x_px": 1030.0, "dx_px": 30.0, "hp": 90},
               {"slot": 2, "x_px": 950.0, "dx_px": -50.0, "hp": 80}]
    segs = pol.decide(30, 1000.0, enemies, grenades=0, hp=100)
    btns = set().union(*[s["btns"] for s in segs])
    assert pol.mode == "engage"
    assert "RIGHT" in btns and "LEFT" not in btns


def test_no_enemy_advances_right():
    pol = CombatPolicy()
    segs = pol.decide(60, 1000.0, [], grenades=3)
    btns = set().union(*[s["btns"] for s in segs])
    assert "RIGHT" in btns
    assert pol.mode == "advance"


def test_clamp_detection_and_clear():
    pol = CombatPolicy()
    # two stalled advance chunks -> clamp detected
    pol.observe(1160.0, 0.5, True)
    pol.observe(1161.0, 1.0, True)
    assert pol.clamp_streak >= 2
    segs = pol.decide(60, 1161.0, [], grenades=0)
    btns = set().union(*[s["btns"] for s in segs])
    assert "LEFT" in btns or "UP" in btns    # clearing the rear
    assert pol.mode == "clamp_clear"


def test_clamp_resets_on_progress():
    pol = CombatPolicy()
    pol.observe(1160.0, 0.5, True)
    pol.observe(1161.0, 1.0, True)
    pol.observe(1200.0, 39.0, True)          # moving again
    assert pol.clamp_streak == 0
    segs = pol.decide(30, 1200.0, [], grenades=0)
    assert pol.mode == "advance"


def test_clamp_escalation_same_wall():
    pol = CombatPolicy()
    pol.observe(1160.0, 0.5, True)
    pol.observe(1161.0, 1.0, True)           # clamp #1: entry, round 0
    assert pol.clamp_entry_px == 1161.0
    for pxa in (1100.0, 1050.0, 1000.0):     # walking back (LEFT intent)
        pol.observe(pxa, 50.0, False)
    pol.observe(1160.5, 0.4, True)           # pushing right again
    pol.observe(1161.0, 0.2, True)           # re-clamped at same wall
    assert pol.clamp_round == 1              # escalated


def test_engage_progress_guard():
    """v2 rear gate: far rear mid-run is released (keep pushing); a
    CLOSE rear threat is always engaged."""
    pol = CombatPolicy()
    far_rear = [{"slot": 3, "x_px": 650.0, "dx_px": -350.0, "hp": 90}]
    segs = pol.decide(30, 1000.0, far_rear, grenades=0, hp=100)
    assert pol.mode == "advance"           # not chased mid-run
    # v5: even a close rear chaser does not turn the agent mid-run —
    # rear clearing happens at the end-clamp (defensive stance)
    close_rear = [{"slot": 3, "x_px": 880.0, "dx_px": -120.0, "hp": 90}]
    pol2 = CombatPolicy()
    pol2.decide(30, 1000.0, close_rear, grenades=0, hp=100)
    assert pol2.mode == "advance"


def test_grenade_cluster():
    pol = CombatPolicy()
    enemies = [{"slot": s, "x_px": 1000.0 + s * 40.0,
                "dx_px": s * 40.0, "hp": 60} for s in range(1, 6)]
    seen_grenade = False
    for _ in range(20):
        segs = pol.decide(60, 1000.0, enemies, grenades=5)
        for s in segs:
            if "A" in s["btns"]:
                seen_grenade = True
        if seen_grenade:
            break
    assert seen_grenade, "cluster grenade never thrown"


def test_segments_cover_chunk():
    pol = CombatPolicy()
    enemies = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90}]
    segs = pol.decide(60, 1000.0, enemies, grenades=0)
    assert sum(s["frames"] for s in segs) == 60


# --------------- v2 behaviours (session 3) -----------------------
def test_damage_dodge_triggers_hop():
    pol = CombatPolicy()
    enemies = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90}]
    pol.decide(60, 1000.0, enemies, grenades=0, hp=100)
    segs = pol.decide(60, 1000.0, enemies, grenades=0, hp=80)   # -20
    btns = set().union(*[s["btns"] for s in segs])
    assert "B" in btns, "damage dodge did not hop"
    assert pol.stats["dodge"] >= 1


def test_engage_budget_walkthrough():
    pol = CombatPolicy()
    enemies = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90}]
    for _ in range(7):                     # 7 chunks on the same slot
        pol.decide(60, 1000.0, enemies, grenades=0, hp=100)
    assert pol.stats["budget_walkthrough"] >= 1
    assert pol.force_advance > 0 or pol.mode == "advance"


def test_rear_gate_midrun_vs_clamp():
    # mid-run: rear enemy at 250px -> ignored (beyond REAR_ENGAGE_RUN)
    pol = CombatPolicy()
    far = [{"slot": 3, "x_px": 750.0, "dx_px": -250.0, "hp": 90}]
    pol.decide(30, 1000.0, far, grenades=0, hp=100)
    assert pol.mode == "advance"
    # clamped: the same rear enemy now meets the DEFENSIVE clear
    pol.observe(1000.0, 0.5, True)
    pol.observe(1000.5, 0.2, True)         # clamp_streak = 2
    pol.decide(30, 1000.5, far, grenades=0, hp=100)
    assert pol.mode == "clamp_clear"
    btns = set().union(*[s["btns"] for s in pol.decide(
        30, 1000.5, far, grenades=0, hp=100)])
    assert "LEFT" in btns or "UP" in btns


def test_far_front_enemy_not_engaged():
    """v3: a far front enemy does not stop the run — advance (forward
    fire bursts deal with it on the way)."""
    pol = CombatPolicy()
    far_front = [{"slot": 1, "x_px": 1350.0, "dx_px": 350.0, "hp": 90}]
    pol.decide(30, 1000.0, far_front, grenades=0, hp=100)
    assert pol.mode == "advance"
    close_front = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90}]
    pol2 = CombatPolicy()
    pol2.decide(30, 1000.0, close_front, grenades=0, hp=100)
    assert pol2.mode == "engage"
