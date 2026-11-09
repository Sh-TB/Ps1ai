"""tests/test_r69_msx_connect_window.py — R69 Metal Slug X policy
v1.7.0 THE CONNECT WINDOW (offline; no emulator, no boot).

The R69 capsule lever, product track: the lob fires ONLY while
|dx| in [TRUCK_CONNECT_MIN, TRUCK_CONNECT_MAX] = [125, 140] (the
measured landing band: the R68 record run's lobs landed at dx -133.5
from the stationary throw posture px 1071), on the gre40 cadence,
facing correct, no clear-line escort, the live grenade counter the
only budget.  Outside the window the player WALKS: approach above
140, RETREAT below 125 (the sub-90 back-off generalized).  During
the grenade cooldown the posture HOLDS (IDLE; the T5 chip-fire is
withdrawn for the window test).

Covers:
  * the in-window lob at the R68 record dx (-133.5) and the window
    edges (125/140 inclusive, 124.9/140.1 exclusive);
  * the cooldown hold (IDLE between lobs, gre40 cadence preserved);
  * the facing turn before the first lob (the default facing is R);
  * the retreat direction symmetry (left truck -> WALK away, right
    truck -> BACK away);
  * the escort override (a clear-line soldier outranks the lob);
  * the no-grenade edge (no GRENADE on an empty counter);
  * the W8/W9 kill chain regression (truck-gone + dead_truck_x ->
    the hazard retreat — unchanged by C1);
  * determinism (the same observation stream -> byte-identical
    actions) and the policy identity (v1.7.0, r69_connect_window).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    FIRE_COOLDOWN, Mission1Policy, POLICY_VERSION, TRUCK_CONNECT_MAX,
    TRUCK_CONNECT_MIN, TRUCK_GRENADE_CD,
)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21


def obs_from(px=1071.0, score=0, php=144, gren=10, alive=True,
             ents=(), diag=None):
    """ents: iterable of (dx, state_code, h)."""
    x = np.zeros(OBS_LEN, dtype=np.float32)
    x[0] = px
    x[1] = float(score)
    x[2] = float(php)
    x[3] = float(gren)
    x[4] = 1.0 if alive else 0.0
    x[5] = 1.0
    for i, (dx, sc, h) in enumerate(ents[:5]):
        x[6 + 3 * i] = dx
        x[7 + 3 * i] = float(sc)
        x[8 + 3 * i] = float(h)
    return GameObservation(values=x, frame_seq=1,
                           frame_id="t", timestamp=0.0, valid=True,
                           diagnostics=diag or {})


def decide(policy, **kw):
    d = policy.predict(obs_from(**kw))
    return d.action, d.diagnostics


TRUCK_L = (-133.5, 7, 64.0)      # the R68 record posture (left side)


class TestConnectWindow:
    def test_version_and_identity(self):
        assert POLICY_VERSION == "1.7.1"
        p = Mission1Policy()
        ident = p.identity()
        assert ident["policy_version"] == "1.7.1"
        assert ident["truck_rules"] == "r69_connect_window"

    def test_lob_at_record_dx(self):
        p = Mission1Policy()
        p._facing = "L"              # already facing the truck
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        assert diag["rule"] == "truck_connect_grenade"
        assert diag["grenades_used"] == 1

    def test_v170_outer_half_falsified(self):
        # THE R69 PROBE RESULT (pinned): the v1.7.0 capsule window
        # [125, 140] threw at -136.5/-139.5 and ALL missed (the a4
        # frozen at 300).  v1.7.1: those dxs are OUTSIDE the window
        # -> the approach (BACK toward a LEFT truck), never a lob.
        for dx in (-136.5, -139.5):
            p = Mission1Policy()
            p._facing = "L"
            a, diag = decide(p, ents=[(dx, 7, 64.0)])
            assert a == "BACK", (dx, a, diag)
            assert diag["rule"] == "truck_approach"

    @pytest.mark.parametrize("dx", [-130.0, -135.0, 130.0, 135.0])
    def test_window_edges_inclusive(self, dx):
        p = Mission1Policy()
        p._facing = "R" if dx > 0 else "L"
        a, diag = decide(p, ents=[(dx, 7, 64.0)])
        assert a == "GRENADE", (dx, diag)

    @pytest.mark.parametrize("dx", [-129.9, -135.1])
    def test_window_edges_exclusive(self, dx):
        p = Mission1Policy()
        p._facing = "L"
        a, diag = decide(p, ents=[(dx, 7, 64.0)])
        assert a != "GRENADE"
        if abs(dx) < TRUCK_CONNECT_MIN:
            assert a == "WALK"       # retreat away from a LEFT truck
            assert diag["rule"] == "truck_connect_retreat"
        else:
            assert a == "BACK"       # approach a LEFT truck
            assert diag["rule"] == "truck_approach"

    def test_retreat_direction_symmetry(self):
        # a RIGHT truck below the window: retreat = BACK (away)
        p = Mission1Policy()
        p._facing = "R"
        a, diag = decide(p, ents=[(120.0, 7, 64.0)])
        assert a == "BACK"
        assert diag["rule"] == "truck_connect_retreat"
        assert p._facing == "L"      # the facing turned away

    def test_inner_edge_125_now_retreats(self):
        # v1.7.0's inner edge (125) is BELOW the v1.7.1 window:
        # dx -125 -> the connect retreat (away from a LEFT truck)
        p = Mission1Policy()
        p._facing = "L"
        a, diag = decide(p, ents=[(-125.0, 7, 64.0)])
        assert a == "WALK"
        assert diag["rule"] == "truck_connect_retreat"

    def test_facing_turn_before_first_lob(self):
        p = Mission1Policy()         # the default facing is R
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "BACK"           # the turn frame
        assert diag["rule"] == "truck_turn"
        assert p._facing == "L"
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"

    def test_cooldown_hold_gre40(self):
        p = Mission1Policy()
        p._facing = "L"
        a, _ = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "IDLE"
        assert diag["rule"] == "truck_connect_hold"
        # the cadence: the grenade repeats after TRUCK_GRENADE_CD
        for _ in range(TRUCK_GRENADE_CD - 1):
            a, _ = decide(p, ents=[TRUCK_L])
            assert a == "IDLE", a
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        assert diag["grenades_used"] == 2

    def test_escort_outranks_lob(self):
        # a clear-line escort soldier between the player and the
        # truck (the T3 rule outranks the lob — unchanged)
        p = Mission1Policy()
        p._facing = "L"
        ents = [(-60.0, 1, 64.0), TRUCK_L]
        a, diag = decide(p, ents=ents)
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"

    def test_no_grenade_on_empty_counter(self):
        p = Mission1Policy()
        p._facing = "L"
        a, diag = decide(p, ents=[TRUCK_L], gren=0)
        assert a != "GRENADE"

    def test_grenade_budget_is_live_counter(self):
        # the v1.6.0 rule stands: the ONLY budget is the live
        # counter — 10 grenades => 10 lob opportunities on cadence
        p = Mission1Policy()
        p._facing = "L"
        thrown = 0
        for _ in range(TRUCK_GRENADE_CD * 10):
            a, _ = decide(p, ents=[TRUCK_L], gren=10)
            if a == "GRENADE":
                thrown += 1
        assert thrown == 10, thrown


class TestKillChainRegression:
    def test_w8_w9_unchanged(self):
        # the truck disappears after an engaged lob + the dead_truck_x
        # diagnostic -> the kill transition arms the W9 hazard retreat
        p = Mission1Policy()
        p._facing = "L"
        a, _ = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        # the truck leaves the observation; the confirmation window
        # holds position for TRUCK_GONE_CONFIRM_F - 1 decisions
        from ps1play.adapters.metal_slug_x.policy import \
            TRUCK_GONE_CONFIRM_F
        for k in range(TRUCK_GONE_CONFIRM_F - 1):
            a, diag = decide(p, ents=[])
            assert a == "IDLE", (k, a, diag)
        # the confirmed kill with the wreck position -> the retreat
        hazard_px = 1071.0 - 133.5          # the wreck world px
        a, diag = decide(p, ents=[], diag={"dead_truck_x": hazard_px})
        assert a == "WALK"                  # away from a LEFT wreck
        assert diag["rule"] == "truck_kill_retreat"

    def test_determinism(self):
        stream = [TRUCK_L, (-120.0, 7, 64.0), (-141.0, 7, 64.0),
                  TRUCK_L, (-60.0, 1, 64.0), TRUCK_L]
        runs = []
        for _ in range(2):
            p = Mission1Policy()
            acts = []
            for e in stream:
                a, _ = decide(p, ents=[e])
                acts.append(a)
            runs.append(tuple(acts))
        assert runs[0] == runs[1]
        assert "GRENADE" in runs[0]
