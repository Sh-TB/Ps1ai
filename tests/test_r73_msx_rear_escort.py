"""tests/test_r73_msx_rear_escort.py — R73 Metal Slug X policy v2.1.0
THE REAR-ESCORT EXEMPTION (offline; no emulator, no boot).

The R73 capsule lever, product track.  Two evidence legs, both from
the committed calibration table (data/games/SLUS-01212/truck_evidence/
r73/r73_calibration.json):

  * THE K-OWNERSHIP LAW CONFIRMED ON BOTH SIDES: on the idle-hold
    stream the k=2 window connects 4/4 across BOTH side buckets
    (-1f v2.0.0 boot + +1f v1.9.0 boot) while k=0/k=1 never connect
    (0/4 across -2f and +0f) — the windows are stream-owned, the
    side does not matter;
  * THE BLOCKED WINDOW: the r72 boot-1 death-frame audit — the k=3
    grid window (fight_f 638-642, phase open, 9 grenades live) never
    threw: every frame from f1780 to the death f1844 was held by the
    T3 escort-first cadence on a REAR escort at dx +37.8 (the
    opposite side of the truck at -133.5).  A lob toward the truck
    never passes x>0 (the C2 corridor predicate already guards the
    descent line), so the hold was a pure loss of the owned window.

v2.1.0 change (one rule, minimal perturbation):
  during the PHASE-OPEN frames ONLY, a clear-line escort on the
  OPPOSITE side of the truck no longer holds the grid throw.
  Same-side escorts keep FULL precedence (the D7/R49 law); the
  off-window frames keep byte-identical behavior (the stream law —
  the R67 cadence-law precedent).

Covers:
  * THE R72b1 REPRODUCTION: the exact blocked frame (fight_f 638,
    escort +37.8) now throws (phase k=3);
  * the same-side escort still holds ON the grid (the D7 law);
  * the cross-side escort still holds OFF-window (the stream law);
  * the exemption generalizes across windows (k=0) and both sides;
  * the corridor guard still governs the exempted throw (the C2
    thief on the truck line blocks even with the exemption);
  * the exemption turn frame: the facing resets to the truck side
    and the throw lands inside the +-2f window;
  * the grenade accounting (grenades_used, _phase_last_k booked).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    Mission1Policy, POLICY_VERSION, TRUCK_GRENADE_CD, TRUCK_PHASE_BASE,
    TRUCK_PHASE_PERIOD)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
GRID_K0 = 148                    # the k=0 throw fight_f (land 178)
K3_THROW = 638                   # the r72b1 blocked window (land 668,
                                 # grid point 670 = 178 + 164*3 -> the
                                 # -2f side, INSIDE the +-2f tolerance)

TRUCK_L = (-133.5, 7, 64.0)      # the record posture
REAR_ESCORT = (37.8, 1, 64.0)    # the r72b1 f1780-1844 rear escort
SAME_ESCORT = (-60.0, 1, 64.0)   # the D7 same-side escort


def obs_from(px=1071.0, gren=10, alive=True, ents=()):
    x = np.zeros(OBS_LEN, dtype=np.float32)
    x[0] = px
    x[3] = float(gren)
    x[4] = 1.0 if alive else 0.0
    x[5] = 1.0
    for i, (dx, sc, h) in enumerate(ents[:5]):
        x[6 + 3 * i] = dx
        x[7 + 3 * i] = float(sc)
        x[8 + 3 * i] = float(h)
    return GameObservation(values=x, frame_seq=1, frame_id="t",
                           timestamp=0.0, valid=True, diagnostics={})


def decide(policy, **kw):
    d = policy.predict(obs_from(**kw))
    return d.action, d.diagnostics


def at_clock(fight_f, facing="L", probe=True):
    """A policy whose NEXT decision lands at fight_f (the truck
    already seen so the anchor reset does not fire), the C4 probe
    pre-spent by default (the phase behavior in isolation)."""
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    p._stream = "hold"   # v2.2.0: the exemption lives on the hold stream
    if probe:
        p._width_probed = 1
    p._facing = facing
    return p


class TestShippedRule:
    def test_version_and_identity(self):
        # re-anchored -> v2.3.0 (R75): the extended head grid
        # ships; the exemption itself is unchanged (the tail rule)
        assert POLICY_VERSION == "2.6.1"
        ident = Mission1Policy().identity()
        assert ident["truck_rules"] == "r82_chipfire_kill"

    def test_r72b1_blocked_window_now_throws(self):
        # THE R72b1 REPRODUCTION: fight_f 638 (the k=3 window open,
        # the -2f side inside the tolerance) with the rear escort at
        # +37.8 — the v2.0.0 shipped FIRE here every frame from
        # f1780 to the death; the exemption restores the owned
        # window
        p = at_clock(K3_THROW)
        before = p._truck_grenades_used
        a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert a == "GRENADE", (a, diag)
        assert diag["rule"] == "truck_connect_grenade"
        assert diag["phase_k"] == 3
        assert p._gren_cd == TRUCK_GRENADE_CD
        assert p._phase_last_k == 3
        assert p._truck_grenades_used == before + 1

    def test_cross_side_exemption_both_k0_windows(self):
        # the exemption is not k=3-specific: the k=0 grid window
        # (closed per the ownership law, but the RULE is geometric)
        # with a rear escort also throws
        for ff in (GRID_K0 - 2, GRID_K0 + 1):
            p = at_clock(ff)
            a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
            assert a == "GRENADE", (ff, a, diag)
            assert diag["phase_k"] == 0

    def test_exemption_right_sided_truck(self):
        # the law is symmetric in the truck side: a truck at +133.5
        # with an escort at -37.8 (the rear relative to it) throws
        p = at_clock(K3_THROW)
        p._facing = "R"
        a, diag = decide(p, ents=[(133.5, 7, 64.0), (-37.8, 1, 64.0)])
        assert a == "GRENADE", (a, diag)
        assert diag["phase_k"] == 3


class TestLawsPreserved:
    def test_same_side_escort_still_holds_on_grid(self):
        # the D7/R49 law: a clear-line SAME-side escort holds the
        # lob (the descent line is theirs) — full precedence, even
        # on the grid
        p = at_clock(GRID_K0)
        a, diag = decide(p, ents=[TRUCK_L, SAME_ESCORT])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"

    def test_cross_side_escort_still_holds_offwindow(self):
        # THE STREAM LAW: off the phase-open frames the behavior is
        # byte-identical v2.0.0 — the rear escort keeps the
        # escort-first cadence (the deterministic wave trajectory;
        # the player faces R here exactly like the r72b1 rear-fire
        # state, so the escort rule FIREs without the turn frame)
        p = at_clock(60, facing="R")
        a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"
        # and a phase-HOLD frame (the gate closed by the booked k)
        p = at_clock(K3_THROW, facing="R")
        p._phase_last_k = 3              # the window already spent
        a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"

    def test_corridor_guard_governs_exempted_throw(self):
        # the exemption removes the REAR hold, not the C2 guard: a
        # thief ON the truck line blocks the exempted throw
        thief = (-119.0, 6, 64.0)
        p = at_clock(K3_THROW)
        a, diag = decide(p, ents=[thief, TRUCK_L, REAR_ESCORT])
        assert a != "GRENADE", diag

    def test_turn_frame_inside_window(self):
        # the escort-first cadence left the player facing the REAR
        # side; the exempted branch must turn FIRST and still land
        # the throw inside the +-2f window (the turn eats one frame,
        # the land walks -2f -> -1f)
        p = at_clock(K3_THROW, facing="R")
        a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert a in ("BACK", "WALK")      # the turn frame
        assert diag["rule"] in ("truck_turn", "truck_width_turn")
        a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert a == "GRENADE"
        assert diag["phase_k"] == 3


class TestNoBudgetLeak:
    def test_exemption_never_spends_offgrid(self):
        # the exemption does not loosen the gate: off-window frames
        # with a rear escort spend NOTHING (the hold + the escort
        # cadence are the v2.0.0 semantics verbatim)
        p = at_clock(200)
        before = p._truck_grenades_used
        for _ in range(60):
            decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert p._truck_grenades_used == before

    def test_one_throw_per_window_with_exemption(self):
        # the bookkeeping guard: after the exempted k=3 throw the
        # same window does NOT double-throw (the gate re-closes on
        # the booked k; the rear escort re-holds — the player faces
        # R, the r72b1 rear-fire state, so the escort rule fires
        # without the turn frame)
        p = at_clock(K3_THROW)
        decide(p, ents=[TRUCK_L, REAR_ESCORT])
        p._facing = "R"
        p._gren_cd = 0                    # force the next frame armed
        a, diag = decide(p, ents=[TRUCK_L, REAR_ESCORT])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"
