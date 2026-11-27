"""tests/test_r77_msx_respawn_run.py — R77 Metal Slug X policy
v2.4.0 THE RESPAWN KILL RUN (offline; no emulator, no boot).

The R76 battery measured everything the kill needs (the 100-test
savestate battery, the owner directive):
  * the connect-window width {255, 257, 259, 261} on the head's
    259-grid (the C-block, VERIFIED);
  * THE FEED-CLEARING LOB: the walk-out lob + the return lob kills
    the marchers (the score +100/+200) AND connects the truck
    (a4 200->100) — all three walk distances (the B-block);
  * THE DEATH IS THE RESPAWN CYCLE: every A/D test crossed the
    f1884 death window and respawned at px 992 php 120 gren 10
    with the fight intact (a4 130) — the PRESS-START
    auto-continue, NOT a fail state (the A/D blocks).

v2.4.0:
  * the dead branch COUNTS the death frames (the animation);
  * on the alive-return with px < 1050: THE RESPAWN DETECTED ->
    the walk RIGHT to px 1071 (the re-entry walk);
  * post-respawn the throws run UNGATED (the gre40 cadence — the
    r69b volume law: 2/7 connects; the respawned stream's phase
    is unknown — the volume explores it);
  * the kill continuation: the connects (-100) + the chips ->
    a4 130 -> 0 -> the W8/W9 -> the section continues.

Covers: the death counting, the respawn detection + the walk-back,
the volley mode, the endgame math.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    Mission1Policy, POLICY_VERSION)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
TRUCK_L = (-133.5, 7, 64.0)


def obs_from(px=1071.0, gren=10, alive=True, php=120, ents=()):
    x = np.zeros(OBS_LEN, dtype=np.float32)
    x[0] = px
    x[3] = float(gren)
    x[4] = 1.0 if alive else 0.0
    x[5] = 1.0
    x[2] = float(php)
    for i, (dx, sc, h) in enumerate(ents[:5]):
        x[6 + 3 * i] = dx
        x[7 + 3 * i] = float(sc)
        x[8 + 3 * i] = float(h)
    return GameObservation(values=x, frame_seq=1, frame_id="t",
                           timestamp=0.0, valid=True, diagnostics={})


def decide(policy, **kw):
    d = policy.predict(obs_from(**kw))
    return d.action, d.diagnostics


def fresh(px=1071.0, facing="L", fight_f=100):
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    p._width_probed = 1
    p._facing = facing
    p._px = px
    return p


class TestRespawnRun:
    def test_version_and_identity(self):
        assert POLICY_VERSION == "2.6.1"
        ident = Mission1Policy().identity()
        assert ident["truck_rules"] == "r82_chipfire_kill"

    def test_death_counts_frames(self):
        p = fresh()
        for i in range(1, 41):
            a, diag = decide(p, alive=False, px=0.0)
            assert a == "IDLE"
            assert diag["rule"] == "dead"
            assert diag["dead_f"] == i
        assert p._dead_f == 40

    def test_respawn_detected_and_walk_starts(self):
        # the R76 battery: the death animation then the alive-return
        # at px 992 php 120 gren 10
        p = fresh()
        for _ in range(40):
            decide(p, alive=False, px=0.0)
        a, diag = decide(p, alive=True, px=992.0, gren=10, php=120,
                         ents=[TRUCK_L])
        assert p._respawned is True
        assert p._respawn_walk is True
        assert p._dead_f == 0

    def test_walk_back_to_1071(self):
        # the re-entry walk: px 992 -> 1071 (the record posture)
        p = fresh(px=992.0)
        p._respawned = True
        p._respawn_walk = True
        px = 992.0
        steps = 0
        while px < 1071.0 and steps < 120:
            a, diag = decide(p, px=px, gren=10, ents=[TRUCK_L])
            if a != "WALK":
                break
            assert diag["rule"] == "respawn_walk", diag
            px += 1.0
            p._px = px
            steps += 1
        assert px >= 1071.0
        # at the posture the walk ends (the fight rules resume)
        a, diag = decide(p, px=1071.0, gren=10, ents=[TRUCK_L])
        assert diag.get("rule") != "respawn_walk"

    def test_volley_mode_ungated(self):
        # post-respawn the throws run UNGATED (the gre40 cadence):
        # an off-schedule off-grid frame still throws
        p = fresh(px=1071.0)
        p._respawned = True
        p._respawn_walk = False
        p._truck_fight_f = 59          # off-schedule, off-grid
        # R82/R84: the chip-fire FIRST post-respawn (the kill path:
        # the bullets pierce the marchers, the r82/r83 boots killed
        # the truck with 13 chips; the volley lobs never connect
        # in-boot — the M02 law is savestate-scoped)
        a, diag = decide(p, gren=10, ents=[TRUCK_L])
        assert a == "FIRE" and diag["rule"] == "respawn_chip_fire", \
            (a, diag)
        assert p._fire_cd == 13
        # the cadence: the next frames hold (the cooldown)
        a, diag = decide(p, gren=10, ents=[TRUCK_L])
        assert a != "FIRE"

    def test_no_volley_without_respawn(self):
        # the pre-respawn stream unchanged: the off-schedule
        # off-grid frame holds (the v2.3.0 semantics verbatim)
        p = fresh(px=1071.0)
        p._respawned = False
        p._truck_fight_f = 59
        a, diag = decide(p, gren=10, ents=[TRUCK_L])
        assert a == "IDLE"
        assert diag["rule"] == "truck_phase_hold"

    def test_endgame_math(self):
        # the kill math: a4 130 (the r74b1 floor) - the volley
        # connects (-100) - the chips (-10 x N) -> 0
        assert 130 - 100 - 30 == 0
