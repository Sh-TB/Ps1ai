"""tests/test_r72_msx_hybrid.py — R72 Metal Slug X policy v2.0.0
THE VOLLEY+PHASE HYBRID (offline; no emulator, no boot).

The R72 capsule lever, product track.  The R71 boot-3 one-variable
evidence this hybrid encodes:

  * the idle-hold stream CONNECTS ON GRID (1/3 — the k=2 connect
    landed at freeze + 506 +- 2f ON THE PHASE GRID (178 + 164x2,
    tol 2f));
  * the chip-fire stream does not (0/2 on-grid chip-fire throws vs
    the r69b volley 2/7);
  * THE PHASE LAW IS STREAM-DEPENDENT (the fire input stream
    perturbs the vulnerability phase — the R67 cadence-law
    precedent).

v2.0.0 changes (both evidence-armed):
  1. TRUCK_CHIP_FIRE defaults to False — the idle-hold stream is
     the connect mechanism; the K1 arm stays patchable True (the
     K1 unit suite keeps it covered) as the chip-damage supplement
     AFTER the connect mechanism is solved;
  2. the phase gate widens to the FULL tolerance: the land must
     sit within +-2f of ANY grid point (BOTH sides — the v1.9.0
     gate admitted only the 0..2f-after side); the throw fires at
     every 40f cadence frame whose land is on-grid — the hybrid
     maximizes on-grid landings per window.

Covers:
  * the shipped arm default (False) and the patchable True;
  * the FULL tolerance: the pre-side opens (land 176-177 -> the
    throw at 146-147 for k=0), the post-side still opens;
  * the off-grid holds under the shipped default (the phase-hold
    IDLE — never a chip-fire, never a grenade);
  * the gre40 cadence: one throw per grid window, the connect-hold
    between (the cooldown ticks, the grenade budget untouched);
  * the per-grid-window discipline (the geometry: at most one
    on-grid cadence land per window);
  * the version/identity (2.0.0, r72_volley_phase_hybrid).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import ps1play.adapters.metal_slug_x.policy as _policy_mod  # noqa: E402
from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    Mission1Policy, POLICY_VERSION, TRUCK_CHIP_FIRE, TRUCK_GRENADE_CD,
    TRUCK_PHASE_BASE, TRUCK_PHASE_PERIOD, TRUCK_PHASE_TOL,
)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
GRID_K0 = 148                    # the k=0 throw fight_f (land 178)

TRUCK_L = (-133.5, 7, 64.0)      # the record posture


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


def at_clock(fight_f, probe=True):
    """A policy whose NEXT decision lands at fight_f (the truck
    already seen so the anchor reset does not fire), facing LEFT,
    the C4 probe pre-spent by default (the phase behavior in
    isolation)."""
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    if probe:
        p._width_probed = 1
    p._facing = "L"
    return p


class TestShippedDefault:
    def test_version_and_identity(self):
        assert POLICY_VERSION == "2.0.0"
        ident = Mission1Policy().identity()
        assert ident["truck_rules"] == "r72_volley_phase_hybrid"

    def test_arm_default_false(self):
        # THE R72 RE-SELECTION (the boot-3 one-variable evidence):
        # the idle-hold stream connects ON GRID (1/3), the
        # chip-fire stream does not (0/2) — the shipped default is
        # the connect mechanism, NOT the chip supplement
        assert TRUCK_CHIP_FIRE is False
        assert _policy_mod.TRUCK_CHIP_FIRE is False

    def test_arm_stays_patchable_true(self):
        # the K1 arm survives as the chip-damage supplement (the
        # R72 capsule method line: available AFTER the connect
        # mechanism is solved) — the documented patch mechanism
        mp = pytest.MonkeyPatch()
        mp.setattr(_policy_mod, "TRUCK_CHIP_FIRE", True)
        try:
            p = at_clock(60, gren_cd := 20)
            a, diag = decide(p, ents=[TRUCK_L])
            assert a == "FIRE"
            assert diag["rule"] == "truck_chip_fire"
        finally:
            mp.undo()


class TestFullToleranceGate:
    @pytest.mark.parametrize("ff", [GRID_K0 - 2, GRID_K0 - 1])
    def test_pre_side_opens(self, ff):
        # THE R72 WIDENING: the land 176/177 (2/1f BEFORE the
        # grid point 178) now opens — the v1.9.0 gate held here
        a, diag = decide(at_clock(ff), ents=[TRUCK_L])
        assert a == "GRENADE", (ff, diag)
        assert diag["rule"] == "truck_connect_grenade"
        assert diag["phase_k"] == 0

    @pytest.mark.parametrize("ff", [GRID_K0, GRID_K0 + 1,
                                    GRID_K0 + 2])
    def test_post_side_still_opens(self, ff):
        a, diag = decide(at_clock(ff), ents=[TRUCK_L])
        assert a == "GRENADE", (ff, diag)
        assert diag["phase_k"] == 0

    @pytest.mark.parametrize("ff", [GRID_K0 - 3, GRID_K0 + 3,
                                    60, 200])
    def test_beyond_tolerance_holds(self, ff):
        # the tolerance is EXACTLY +-2f: 3f off either side holds
        a, diag = decide(at_clock(ff), ents=[TRUCK_L])
        assert a != "GRENADE", (ff, diag)
        assert a == "IDLE"
        assert diag["rule"] == "truck_phase_hold"

    def test_pre_side_k1_window(self):
        # the k=1 pre-side: the land at 342-2 -> the throw at 310
        ff = GRID_K0 + int(TRUCK_PHASE_PERIOD) - 2
        a, diag = decide(at_clock(ff), ents=[TRUCK_L])
        assert a == "GRENADE", (ff, diag)
        assert diag["phase_k"] == 1

    def test_signed_diagnostics(self):
        # the phase_off diagnostic is now SIGNED (the pre-side
        # negative) — the boot-3 falsification arm's evidence
        # frame stays representable; a hold frame 4f BEFORE the
        # grid point reports -4.0 (the v1.9.0 code reported 160;
        # the -1/-2 frames are INSIDE the tolerance and throw)
        a, diag = decide(at_clock(GRID_K0 - 4), ents=[TRUCK_L])
        assert a == "IDLE"
        assert diag["rule"] == "truck_phase_hold"
        assert diag["phase_off"] == pytest.approx(-4.0)


class TestCadenceHybrid:
    def test_cadence_gated_throws_and_holds(self):
        # the shipped default: the throw ON the grid, then the
        # 40f cadence of connect-holds, the next grid window
        # restores the lob (the gre40 cadence gated by the phase
        # tolerance — the hybrid)
        p = at_clock(GRID_K0)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        assert diag["phase_k"] == 0
        assert p._gren_cd == TRUCK_GRENADE_CD
        # the cooldown: connect-holds, never a chip-fire, never a
        # grenade (the shipped default); the LAST cooldown frame
        # lands gren_cd exactly 0 -> the phase-hold (the committed
        # decrement-then-hold order)
        for i in range(TRUCK_GRENADE_CD):
            a, diag = decide(p, ents=[TRUCK_L])
            assert a == "IDLE", (i, a, diag)
            if i < TRUCK_GRENADE_CD - 1:
                assert diag["rule"] == "truck_connect_hold", (i, diag)
            else:
                assert diag["rule"] == "truck_phase_hold", (i, diag)
        # the cooldown is over, the clock walked past k=0: the
        # phase-hold (off-grid)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "IDLE"
        assert diag["rule"] == "truck_phase_hold"
        # the k=1 window restores the lob
        p._truck_fight_f = GRID_K0 + int(TRUCK_PHASE_PERIOD) - 1
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        assert diag["phase_k"] == 1
        assert diag["grenades_used"] == 2

    def test_one_throw_per_grid_window(self):
        # the widened gate does NOT double-throw inside one
        # window: the pre-side throw books the k and the post-side
        # frame is held (the geometry would not allow a second
        # on-grid cadence land anyway; the bookkeeping is the
        # belt-and-braces guard)
        p = at_clock(GRID_K0 - 2)
        a, _ = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        p._gren_cd = 0                  # force the next frame open
        p._truck_fight_f = GRID_K0 + 1  # the post-side, same k=0
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "IDLE"
        assert diag["rule"] == "truck_phase_hold"

    def test_no_grenade_budget_leak(self):
        # the hybrid never spends grenades off-grid (the hold is
        # IDLE — no width-probe interplay on the shipped default
        # once the probe is spent)
        p = at_clock(60)
        before = p._truck_grenades_used
        for _ in range(60):
            decide(p, ents=[TRUCK_L])
        assert p._truck_grenades_used == before

    def test_escort_precedence_unchanged(self):
        # the T3 rule outranks everything (the lob AND the holds)
        p = at_clock(GRID_K0)
        a, diag = decide(p, ents=[TRUCK_L, (-60.0, 1, 64.0)])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"

    def test_corridor_guard_unchanged(self):
        # the C2 guard withholds the lob on a dirty corridor even
        # ON the grid (both gate sides)
        thief = (-119.0, 6, 64.0)
        p = at_clock(GRID_K0 - 2)
        a, diag = decide(p, ents=[thief, TRUCK_L])
        assert a != "GRENADE", diag
