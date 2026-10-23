"""tests/test_msx_regression8.py — the 8 controlled MSX regression
cases from the Coder-2 mission (enemy awareness before map-completion).

Mission case -> test map:
  1 enemy in FRONT                -> test_case1_front_enemy_engaged
  2 enemy BEHIND (mid-run)        -> test_case2_rear_pursuer_turns_bounded
  3 boundary + valid enemy behind -> test_case3_clamp_rear_defensive_clear
  4 no valid enemy in RAM         -> test_case4_no_enemy_keeps_moving
  5 suspected target is scenery/  -> test_case5_unverified_object_never_enemy
    unverified object
  6 target lost / killed          -> test_case6_target_lost_releases_lock
  7 falling projectile (identity  -> test_case7_falling_shell_dodged_not_faced
    + trajectory verified)
  8 death/respawn/segment change  -> test_case8_respawn_invalidates_stale
    invalidates stale observations

Pure-logic: no emulator, no RAM. The scan schema is
ps1play-combat-scan/1 rev 2 (combat.py): entries carry
{"slot","x_px","dx_px","hp","h","kind"} with kind in
{"enemy","projectile_air"} — the RAW height label; the policy
additionally verifies the FALLING trajectory across sightings before
dodging (D8). Evidence sources cited per case.

ABSENT OBSERVATION IS NOT SAFETY: every case asserts the agent keeps
producing movement segments — standing still in the open is the
instrumented death pattern (heli-ladder patterns 1/10; session-3 v3).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.agent.combat import (                     # noqa: E402
    CombatPolicy, scan_entities, GROUND_HEIGHT, REAR_CHECK_PERSIST)


class FakeMem:
    """Entity-table stand-in: slot X (fixed), HP, and HEIGHT words."""

    def __init__(self, slots, px=1000.0, hp=144):
        # slots: {slot_index: (x_fixed, hp, height)}
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
        if s in self.slots:
            if off == 0x8E:
                return self.slots[s][1]
            if off == 0x7E:
                return self.slots[s][2] if len(self.slots[s]) > 2 else 0
        if addr == 0x0CA2F6:
            return self._hp
        return 0


def _btns(segs):
    return set().union(*[s["btns"] for s in segs]) if segs else set()


# ---------------------------------------------------------------
# CASE 1 — enemy in FRONT (verified by the same instrumented probes
# that proved slot0=player / HP window: probe0, session 3).
def test_case1_front_enemy_engaged():
    pol = CombatPolicy()
    front = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90,
              "kind": "enemy"}]
    segs = pol.decide(60, 1000.0, front, grenades=0, hp=100)
    btns = _btns(segs)
    assert pol.mode == "engage"
    assert "RIGHT" in btns and "LEFT" not in btns   # faces the target
    assert "Y" in btns                              # fires at it
    assert sum(s["frames"] for s in segs) == 60     # action is real


# CASE 2 — enemy BEHIND mid-run: the mission requires a DIRECTION
# CORRECTION (turn -> re-engage -> resume), NOT blind advance and NOT
# an infinite turn. Evidence frame: all baseline deaths were
# rear-related (session-3 A/B, dx -54..-93), yet walking INTO the
# pursuit pack (v4) and standing still (v3) are both death patterns —
# so the correction is bounded: one turn+fire chunk per
# REAR_CHECK_PERSIST chunks, never a walk-toward.
def test_case2_rear_pursuer_turns_bounded():
    pol = CombatPolicy()
    rear = [{"slot": 2, "x_px": 920.0, "dx_px": -80.0, "hp": 100,
             "kind": "enemy"}]
    saw_correction = False
    modes = []
    for _ in range(REAR_CHECK_PERSIST + 2):
        segs = pol.decide(60, 1000.0, rear, grenades=0, hp=100)
        modes.append(pol.mode)
        if pol.mode == "rear_check":
            saw_correction = True
            btns = _btns(segs)
            assert "LEFT" in btns                    # turned around
            assert "Y" in btns                       # fired rearward
            # the walk-toward is capped: at most REAR_CHECK_TURN frames
            # of LEFT (the turn tap), the rest stands/fires
            left_frames = sum(s["frames"] for s in segs
                              if "LEFT" in s["btns"])
            assert left_frames <= 8, left_frames
        else:
            assert "RIGHT" in _btns(segs)            # backbone resumes
    assert saw_correction, f"no direction correction: {modes}"
    # bounded: the check repeats, it does not lock the agent in place
    assert modes.count("rear_check") >= 1
    assert modes.count("advance") >= REAR_CHECK_PERSIST
    assert pol.stats["rear_check"] >= 1


# CASE 3 — at the derived boundary (stage-end) with a VALID enemy
# behind: stop advancing, defensive rear-clear (the D3 fix, proven
# live in the session-3 A/B: 62 clamp chunks never turning -> 0, clamp
# rear-clear kills 5901).
def test_case3_clamp_rear_defensive_clear():
    pol = CombatPolicy()
    rear = [{"slot": 2, "x_px": 920.0, "dx_px": -80.0, "hp": 100,
             "kind": "enemy"}]
    pol.observe(1000.0, 0.5, True)
    pol.observe(1000.5, 0.2, True)                   # end-clamp derived
    segs = pol.decide(60, 1000.5, rear, grenades=0, hp=100)
    btns = _btns(segs)
    assert pol.mode == "clamp_clear"
    assert "RIGHT" not in btns                       # no blind advance
    assert "LEFT" in btns or "UP" in btns            # rearward response


# CASE 4 — no valid enemy in RAM: the backbone keeps MOVING (absence
# of observation is not safety; standing still is the death pattern).
def test_case4_no_enemy_keeps_moving():
    pol = CombatPolicy()
    segs = pol.decide(60, 1000.0, [], grenades=0, hp=100)
    btns = _btns(segs)
    assert pol.mode == "advance"
    assert "RIGHT" in btns                           # always progressing
    # never a full stand-still segment while unpressed
    for s in segs:
        assert s["btns"], "stand-still segment with no observation"


# CASE 5 — suspected target is scenery / an UNVERIFIED object: slots
# with out-of-window HP, signed-negative transients, or invalid X are
# dropped by scan_entities and must NEVER become engage targets. The
# policy must neither face nor fire at them, and must not convert
# "unknown" into "enemy" (mission: unknown objects stay unknown).
def test_case5_unverified_object_never_enemy():
    mem = FakeMem({3: (int(1100 * 65536), 700, 64),      # hp > max
                   4: (int(950 * 65536), 65505, 64),     # signed transient
                   5: (int(980 * 65536), 0, 64)})        # dead slot
    out = scan_entities(mem, px=1000.0)
    assert out == [], f"unverified objects leaked: {out}"
    pol = CombatPolicy()
    segs = pol.decide(60, 1000.0, out, grenades=0, hp=100)
    assert pol.mode == "advance"                     # no enemy belief
    assert pol.stats["engage"] == 0
    assert "RIGHT" in _btns(segs)                    # keeps moving


# CASE 6 — target lost / killed: the engage lock releases when the
# slot disappears from the scan (kill evidence = slot removal +
# score, tracked by the runner); the agent re-selects or advances
# instead of facing a corpse position forever.
def test_case6_target_lost_releases_lock():
    pol = CombatPolicy()
    target = [{"slot": 1, "x_px": 1020.0, "dx_px": 20.0, "hp": 90,
               "kind": "enemy"}]
    pol.decide(60, 1000.0, target, grenades=0, hp=100)
    assert pol.engage_slot == 1
    # the target dies: its slot leaves the scan
    segs = pol.decide(60, 1000.0, [], grenades=0, hp=100)
    assert pol.engage_slot is None
    assert pol.mode == "advance"
    assert "RIGHT" in _btns(segs)
    # a NEW target is re-selected normally (re-acquire, not stuck)
    new = [{"slot": 7, "x_px": 1015.0, "dx_px": 15.0, "hp": 60,
            "kind": "enemy"}]
    pol.decide(60, 1000.0, new, grenades=0, hp=100)
    assert pol.engage_slot == 7
    assert pol.mode == "engage"


# CASE 7 — falling projectile (identity + trajectory verified: height
# word @+0x7E > ground contact 64, session-2 decode + heli-ladder
# trace): NEVER an engage target, and within dodge radius it triggers
# an immediate hop. D8 rev: trajectory verification needs TWO
# consecutive sightings of the same slot with the height DECREASING
# (the rain signature at chunk granularity) — a single raw label is
# not enough (live slot 7 false positive). The run-through backbone
# continues (movement is life); no enemy belief is formed from the
# projectile.
def test_case7_falling_shell_dodged_not_faced():
    mem = FakeMem({9: (int(1010 * 65536), 92, 120),      # falling: h=120
                   1: (int(1300 * 65536), 90, 64)})      # far ground foe
    out = scan_entities(mem, px=1000.0)
    kinds = {e["slot"]: e["kind"] for e in out}
    assert kinds[9] == "projectile_air"
    assert kinds[1] == "enemy"
    shell = [e for e in out if e["slot"] == 9]
    pol = CombatPolicy()
    segs = pol.decide(60, 1000.0, shell, grenades=0, hp=100)
    assert pol.mode == "advance"                     # not "engage"
    assert pol.stats["engage"] == 0
    # FIRST sighting: falling not yet verifiable -> no dodge hop
    assert "B" not in _btns(segs)
    assert pol.stats["proj_dodge"] == 0
    assert pol.stats["proj_unverified"] >= 1
    # SECOND sighting, height DECREASED (verified falling): hop fires
    shell2 = [{"slot": 9, "x_px": 1005.0, "dx_px": 5.0, "hp": 60,
               "h": 90, "kind": "projectile_air"}]
    segs2 = pol.decide(60, 1000.0, shell2, grenades=0, hp=100)
    assert pol.mode == "advance"
    assert "B" in _btns(segs2)                       # dodge hop fired
    assert pol.stats["proj_dodge"] >= 1
    # ground enemies are NOT dodged: h==64 stays "enemy"
    assert GROUND_HEIGHT == 64
    ground = [e for e in out if e["slot"] == 1]
    pol2 = CombatPolicy()
    segs2b = pol2.decide(60, 1000.0, ground, grenades=0, hp=100)
    assert pol2.stats["proj_dodge"] == 0


# CASE 7b (D8, live-confirmed in combat_live2) — a STATIC elevated
# object (live: slot 7 at x=264.0, height AND hp constant for 16
# chunks = elevated scenery) carries the raw "projectile_air" label
# but its trajectory never verifies: the policy must NOT burn dodge
# hops on it, must not engage it, and must keep advancing. A RISING
# height is equally unverified. (Unknown objects stay unknown — the
# symmetric half of mission case 5.)
def test_case7b_static_elevated_object_never_dodged():
    pol = CombatPolicy()
    static = [{"slot": 7, "x_px": 264.0, "dx_px": 5.0, "hp": 264,
               "h": 200, "kind": "projectile_air"}]
    for i in range(6):                               # 6 constant sightings
        segs = pol.decide(60, 1000.0, static, grenades=0, hp=100)
        # any B must be the backbone's own cadence hop (stats[jump]),
        # never a projectile dodge (stats[proj_dodge] stays 0)
        if "B" in _btns(segs):
            assert pol.stats["jump"] >= 1, \
                f"unexplained hop on static object, chunk {i}"
        assert pol.stats["proj_dodge"] == 0
        assert pol.mode == "advance"
        assert "RIGHT" in _btns(segs)                # backbone continues
    assert pol.stats["proj_unverified"] >= 6
    assert pol.stats["engage"] == 0                  # never a target
    # rising height: also unverified
    pol2 = CombatPolicy()
    rising = [{"slot": 7, "x_px": 264.0, "dx_px": 5.0, "hp": 264,
               "h": 100, "kind": "projectile_air"}]
    pol2.decide(60, 1000.0, rising, grenades=0, hp=100)
    rising2 = [{"slot": 7, "x_px": 264.0, "dx_px": 5.0, "hp": 264,
                "h": 140, "kind": "projectile_air"}]
    segs3 = pol2.decide(60, 1000.0, rising2, grenades=0, hp=100)
    assert "B" not in _btns(segs3)
    assert pol2.stats["proj_dodge"] == 0
    # respawn invalidation clears the height memory too (case 8 x D8)
    pol.observe(1000.0, 0.0, True)                   # anchor observation
    pol.decide(60, 1000.0,
               [{"slot": 9, "x_px": 1010.0, "dx_px": 10.0, "hp": 92,
                 "h": 120, "kind": "projectile_air"}], grenades=0)
    assert pol.prev_h == {9: 120}
    pol.observe(200.0, -800.0, True)                 # teleport
    assert pol.stats["stale_reset"] == 1
    assert pol.prev_h == {}


# CASE 8 — player death / respawn / segment change invalidates stale
# observations: a large px discontinuity (respawn teleports hundreds
# of px; walking covers <40 px per 60f chunk) resets wall position,
# escalation round, engage lock and pursuer streak BEFORE the next
# decision — the agent must not clear a wall it is no longer at.
def test_case8_respawn_invalidates_stale():
    pol = CombatPolicy()
    pol.observe(1160.0, 0.5, True)
    pol.observe(1161.0, 1.0, True)                   # clamped @1161
    pol.decide(60, 1161.0, [], grenades=0)
    assert pol.mode == "clamp_clear"
    pol.observe(200.0, -961.0, True)                 # respawn far back
    assert pol.stats["stale_reset"] == 1
    assert pol.clamp_entry_px is None
    segs = pol.decide(60, 200.0, [], grenades=0, hp=100)
    assert pol.mode == "advance"                     # stale wall dropped
    assert "RIGHT" in _btns(segs)
    # engage lock is invalidated too
    pol2 = CombatPolicy()
    pol2.decide(60, 1000.0,
                [{"slot": 4, "x_px": 1020.0, "dx_px": 20.0, "hp": 90,
                  "kind": "enemy"}], grenades=0, hp=100)
    assert pol2.engage_slot == 4
    pol2.observe(100.0, -900.0, True)                # teleport
    pol2.decide(60, 100.0, [], grenades=0, hp=100)
    assert pol2.engage_slot is None
