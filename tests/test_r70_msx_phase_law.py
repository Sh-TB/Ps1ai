"""tests/test_r70_msx_phase_law.py — R70 Metal Slug X policy v1.8.0
THE PHASE LAW + the drive-in arm (offline; no emulator, no boot).

The R70 capsule lever, product track.  The r69b connect-probe
evidence this law encodes:

  * the freeze at f811 (st 0x9E88 first seen; x 937.5, a4 300,
    sx 65 frozen thereafter);
  * the two CONFIRMED connects landed at f989 and f1153 — the
    PERIOD 164f apart, both = freeze + 14 (mod 164);
  * the flight EXACTLY 30f twice (f959 -> f989, f1123 -> f1153);
  * the f877 lob landed f907 (82f from both grid points) and
    MISSED — the window width is < 82f, the center-hits connect.

P1 the fight clock + the phase gate; P2 the drive-in posture (the
adapter v0.5.0 SC_TRUCK_IN = 8 mapping of 0x9C14/0x9E08); P3 the
k=0 lead throw (the falsifiable arm: land = freeze + 14, thrown
during the drive-in at freeze - 16).

Covers:
  * the clock anchor (the first SC_TRUCK frame = fight_f 0) and
    the natural accrual;
  * the grid: the throw at fight_f 148..150 (k=0) and 312..314
    (k=1), the phase hold elsewhere, one throw per k;
  * the lead: the approach/hold/retreat on the PREDICTED dx, the
    velocity gate (static history >= 2), the ftf window, the cap;
  * the drive-in escort precedence (the T3 mirror);
  * the adapter v0.5.0 state mapping (0x9C14/0x9E08 -> 8, the
    soldier states untouched, 0x9E88 -> 7 unchanged).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.adapter import (  # noqa: E402
    ADAPTER_VERSION, SC_TRUCK_IN, SC_TRUCK, SC_OTHER, state_code,
)
from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    FIRE_COOLDOWN, Mission1Policy, POLICY_VERSION, TRUCK_CONNECT_MAX,
    TRUCK_CONNECT_MIN, TRUCK_LEAD_CAP, TRUCK_LOB_FLIGHT,
    TRUCK_PHASE_BASE, TRUCK_PHASE_PERIOD, TRUCK_PHASE_TOL,
    TRUCK_PARK_DX, TRUCK_PARK_X,
)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
GRID_K0 = 148                    # fight_f of the k=0 throw


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


TRUCK_L = (-133.5, 7, 64.0)


def at_clock(fight_f, probe=True):
    """A policy whose NEXT decision lands at fight_f (the truck
    already seen so the anchor reset does not fire).  By default
    the C4 width probe is pre-spent so the phase-hold behavior is
    observable in isolation; the probe tests pass probe=False."""
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    if probe:
        p._width_probed = 1
    p._facing = "L"
    return p


class TestPhaseGate:
    def test_constants_match_evidence(self):
        # the r69b law: period 164, the first grid land freeze+178,
        # the flight 30 => the k=0 throw at fight_f 148
        assert TRUCK_PHASE_PERIOD == 164.0
        assert TRUCK_PHASE_BASE == 178.0
        assert TRUCK_LOB_FLIGHT == 30.0
        assert GRID_K0 == TRUCK_PHASE_BASE - TRUCK_LOB_FLIGHT
        assert TRUCK_PARK_X == 937.5 and TRUCK_PARK_DX == -133.5

    @pytest.mark.parametrize("ff", [GRID_K0, GRID_K0 + 1,
                                    GRID_K0 + 2])
    def test_grid_open_k0(self, ff):
        a, diag = decide(at_clock(ff), ents=[TRUCK_L])
        assert a == "GRENADE", (ff, diag)
        assert diag["rule"] == "truck_connect_grenade"
        assert diag["phase_k"] == 0

    @pytest.mark.parametrize("ff", [GRID_K0 + int(TRUCK_PHASE_PERIOD),
                                    GRID_K0 + int(TRUCK_PHASE_PERIOD) + 1,
                                    GRID_K0 + int(TRUCK_PHASE_PERIOD) + 2])
    def test_grid_open_k1(self, ff):
        a, diag = decide(at_clock(ff), ents=[TRUCK_L])
        assert a == "GRENADE", (ff, diag)
        assert diag["phase_k"] == 1

    @pytest.mark.parametrize("ff", [0, 1, 60, 147, 151, 200, 311, 315])
    def test_phase_hold_off_grid(self, ff):
        # re-anchored on v1.9.0 (R71 K1): off-grid NEVER lobs (the
        # phase gate is untouched); between escort shots (fire_cd
        # > 0) with the corridor occupied the posture holds exactly
        # as pre-v1.9.0 — the phase-gate isolation
        p = at_clock(ff)
        p._fire_cd = 5
        a, diag = decide(p, ents=[TRUCK_L, (-60.0, 1, 64.0)])
        assert a == "IDLE", (ff, diag)
        assert diag["rule"] == "truck_hold"
        assert a != "GRENADE"

    def test_one_throw_per_k(self):
        # the tolerance spans 3 frames; the k bookkeeping allows
        # exactly ONE throw per grid point even with the cooldown
        # artificially cleared (the C4 probe pre-spent; v1.9.0: the
        # off-grid posture is the K1 chip-fire — still never a
        # second lob)
        p = at_clock(GRID_K0)
        p._width_probed = 1
        a, _ = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        p._gren_cd = 0
        p._truck_fight_f = GRID_K0 + 1      # still inside the tol span
        a, diag = decide(p, ents=[TRUCK_L])
        assert a != "GRENADE", diag
        assert diag["rule"].startswith("truck_chip")

    def test_clock_natural_accrual_and_anchor(self):
        # the fresh policy anchors fight_f=0 at the first sighting
        # and accrues one per decision; the k=0 throw lands at
        # decision 148-150 (the turn costs one frame inside tol;
        # the C4 probe pre-spent; v1.9.0: the anchor frame opens
        # with the K1 chip-fire turn, facing R default)
        p = Mission1Policy()
        p._width_probed = 1
        acts = []
        for _ in range(GRID_K0 + 5):
            a, _ = decide(p, ents=[TRUCK_L])
            acts.append(a)
        assert acts[0] == "BACK"            # the chip-fire turn
        assert "FIRE" in acts[:10]          # then the aimed fire
        assert "GRENADE" in acts[:GRID_K0 + 3]
        assert acts.index("GRENADE") >= GRID_K0 - 1

    def test_clock_freezes_while_truck_absent(self):
        # the W8 flicker: the truck absent a few frames must NOT
        # shift the grid (the clock only accrues on sighting)
        p = at_clock(GRID_K0)
        a, _ = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        ff_before = p._truck_fight_f
        for _ in range(5):
            decide(p, ents=[])              # the W8 hold frames
        assert p._truck_fight_f == ff_before


TRUCKIN_FAR = (-303.5, 8, 64.0)  # the drive-in start (r69b f733)


class TestDriveInArm:
    def test_approach_on_predicted_dx(self):
        # the player right of the record posture: walk LEFT (BACK)
        p = Mission1Policy()
        a, diag = decide(p, px=1146.0, ents=[TRUCKIN_FAR])
        assert a == "BACK"
        assert diag["rule"] == "truckin_approach"
        assert diag["pred_dx"] == pytest.approx(
            TRUCK_PARK_X - 1146.0)

    def test_hold_on_record_posture(self):
        # the first hold at the posture: no static history yet ->
        # neither the lead nor the probe (the C4 ordering) -> IDLE
        p = Mission1Policy()
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        assert a == "IDLE"
        assert diag["rule"] == "truckin_hold"
        assert diag["pred_dx"] == pytest.approx(-133.5)
        # with BOTH one-shot arms spent the hold is the steady state
        p._width_probed = 1
        p._lead_spent = TRUCK_LEAD_CAP
        p._truckin_static = 2
        p._truckin_dx = -153.5
        p._truckin_px = 1071.0
        a, diag = decide(p, px=1071.0, ents=[(-152.25, 8, 64.0)])
        assert a == "IDLE"
        assert diag["rule"] == "truckin_hold"

    def test_hold_when_past_posture(self):
        # the player walked PAST the posture band (v1.8.5: the
        # re-center walk withdrawn) — the arm holds
        p = Mission1Policy()
        a, diag = decide(p, px=1050.0, ents=[(-183.5, 8, 64.0)])
        assert a == "IDLE"
        assert diag["rule"] == "truckin_hold"

    def test_lead_throw_on_ftf_window(self):
        # the truck closing +1.25 px/f on a static player: the ftf
        # reaches 16 exactly at dx -153.5 => the lead throw
        p = Mission1Policy()
        p._facing = "L"
        for dx in (-156.0, -154.75, -153.5):
            a, diag = decide(p, px=1071.0, ents=[(dx, 8, 64.0)])
        assert a == "GRENADE"
        assert diag["rule"] == "truck_lead_throw"
        assert diag["ftf"] == pytest.approx(16.0)
        assert diag["lead_spent"] == 1

    def test_lead_turn_first_when_facing_wrong(self):
        p = Mission1Policy()                # the default facing R
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        # frame 1: static=0 (no history) -> no lead; the hold arms
        assert a == "IDLE"
        a, _ = decide(p, px=1071.0, ents=[(-152.25, 8, 64.0)])
        a, diag = decide(p, px=1071.0, ents=[(-151.0, 8, 64.0)])
        # ftf = ( -133.5 + 151 ) / 1.25 = 14 -> inside [14, 18]:
        # the lead opens but the facing is R -> the turn first
        assert a == "BACK"
        assert diag["rule"] == "truck_lead_turn"

    def test_lead_no_velocity_history_no_throw(self):
        # a single static frame is NOT enough (the disclosed
        # precision limit): the arm holds instead of throwing
        p = Mission1Policy()
        p._facing = "L"
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        assert a == "IDLE"
        assert diag["rule"] == "truckin_hold"

    def test_lead_cap(self):
        # the lead capped AND the probe spent: no grenade at all
        p = Mission1Policy()
        p._facing = "L"
        p._lead_spent = TRUCK_LEAD_CAP
        p._width_probed = 1
        p._truckin_static = 2
        p._truckin_dx = -154.75
        p._truckin_px = 1071.0
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        assert a != "GRENADE"

    def test_lead_capped_probe_takes_the_shot(self):
        # the C4 fallback: the lead spent, the ftf window passing —
        # the ONE width-probe shot takes the throw
        p = Mission1Policy()
        p._facing = "L"
        p._lead_spent = TRUCK_LEAD_CAP
        p._truckin_static = 2
        p._truckin_dx = -154.75
        p._truckin_px = 1071.0
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        assert a == "GRENADE"
        assert diag["rule"] == "truck_width_probe"

    def test_escort_outranks_drive_in(self):
        # the T3 mirror: a clear-line soldier outranks the arm
        p = Mission1Policy()
        a, diag = decide(p, px=1146.0,
                         ents=[(-303.5, 8, 64.0), (-60.0, 1, 64.0)])
        assert a == "BACK"                  # the escort turn first
        assert diag["rule"] == "truckin_escort_turn"

    def test_truck_freeze_hands_over_to_p1(self):
        # the drive-in ends: the first SC_TRUCK frame anchors the
        # clock at 0 (v1.9.0: the K1 chip-fire opens the fight —
        # the corridor is clean on the record timeline), the grid
        # opens at 148 (the width probe pre-spent)
        p = Mission1Policy()
        p._facing = "L"
        p._width_probed = 1
        decide(p, px=1071.0, ents=[TRUCKIN_FAR])
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "FIRE"
        assert diag["rule"] == "truck_chip_fire"
        assert diag["fight_f"] == 0

    def test_post_freeze_width_probe_fires(self):
        # the C4 post-freeze arm: the first clean in-window hold
        # off-grid with a ready grenade = the one width-probe shot
        p = at_clock(30, probe=False)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"
        assert diag["rule"] == "truck_width_probe"
        assert diag["fight_f"] == 30


class TestAdapterV050:
    def test_version(self):
        # v0.5.2 (R71): the a4-aware liveness filter ships on top of
        # the v0.5.1 truck packing priority
        assert ADAPTER_VERSION == "0.5.2"

    def test_drive_in_state_mapping(self):
        assert state_code(0x9C14) == SC_TRUCK_IN == 8
        assert state_code(0x9E08) == SC_TRUCK_IN
        # the neighbors unchanged
        assert state_code(0x9E88) == SC_TRUCK == 7
        assert state_code(0x1234) == SC_OTHER == 6

    def test_no_soldier_collision(self):
        # the documented soldier walk/throw family stays SC_OTHER
        for st in (0x1594, 0x1BE0, 0x1E38, 0x340C, 0x727C, 0x74C8,
                   0xB570):
            assert state_code(st) == SC_OTHER, hex(st)

    def test_v051_truck_packing_priority(self):
        # the r70 boot-3 evidence: five chasers NEARER than the
        # parked truck must NOT drop the truck row from the
        # observation — the fight anchor displaces the farthest
        import struct
        TABLE = 0x0CA268
        STRIDE = 0x14C

        class FakeMem:
            def __init__(self):
                self.ram = bytearray(0x200000)

            def u16(self, a):
                return int.from_bytes(self.ram[a:a + 2], "little")

            def u32(self, a):
                return int.from_bytes(self.ram[a:a + 4], "little")

            def u8(self, a):
                return self.ram[a]

        mem = FakeMem()
        mem.ram[0x0CA2E0:0x0CA2E4] = struct.pack("<I", 1000 << 16)
        mem.ram[0x0EE518:0x0EE51C] = struct.pack("<I", 0xFF)
        slots = {i: (0x1BE0, (1000 - 50 - i * 5) << 16, 64, 40)
                 for i in range(5)}          # 5 walkers: -50..-70
        slots[14] = (0x9E88, (1000 - 133) << 16, 64, 40)  # the truck
        for s, (st, xw, h, sx) in slots.items():
            base = TABLE + s * STRIDE
            mem.ram[base:base + 2] = struct.pack("<H", st)
            mem.ram[base + 0x78:base + 0x7C] = \
                struct.pack("<I", xw)
            mem.ram[base + 0x7E:base + 0x80] = struct.pack("<H", h)
            mem.ram[base + 0x8E:base + 0x90] = \
                struct.pack("<H", sx)
            # v0.5.2 (R71): the walkers are LIVE rows (a4 = the HP
            # word) — the a4-aware liveness filter drops the dead
            mem.ram[base + 0xA4:base + 0xA6] = \
                struct.pack("<H", 300)
        FakeP = type("FakeP", (), {"mem": mem})
        FakeEnv = type("FakeEnv", (), {"p": FakeP()})
        from ps1play.adapters.metal_slug_x.adapter import \
            MetalSlugXAdapter
        ad = MetalSlugXAdapter(env=FakeEnv())
        out = ad.scan_mortals(1000.0)
        sts = [e["st"] for e in out]
        assert 0x9E88 in sts, sts          # THE ANCHOR SURVIVES
        assert len(out) == 5


class TestV181Corrections:
    """The r70 boot-1 corrections: C2 the corridor guard, C3 the
    drive-in hygiene, C4 the one-shot width probe."""

    def test_c2_corridor_guard_blocks_lob(self):
        # the r70 theft pinned: a mortal between the player and the
        # truck (dx -119 vs the truck -133.5) must WITHHOLD the lob
        # even ON the grid (the descent is eaten otherwise)
        thief = (-119.0, 6, 64.0)
        p = at_clock(GRID_K0)
        a, diag = decide(p, ents=[thief, TRUCK_L])
        assert a != "GRENADE", diag
        # the same grid with a CLEAN corridor lobs
        p2 = at_clock(GRID_K0)
        a2, diag2 = decide(p2, ents=[TRUCK_L])
        assert a2 == "GRENADE"

    def test_c3_occluded_soldier_outranks_drive_in(self):
        # the C3 hygiene: a soldier BEHIND another (no clear line)
        # still outranks the posture walk (the front one falls
        # first — the R49 steal model)
        p = Mission1Policy()
        a, diag = decide(p, px=1146.0,
                         ents=[TRUCKIN_FAR, (-60.0, 1, 64.0),
                               (-40.0, 1, 64.0)])
        assert a == "BACK"              # the escort turn first
        assert diag["rule"] == "truckin_escort_turn"

    def test_c4_width_probe_fires_once_on_clean_hold(self):
        # the truck closing but PAST the lead window (ftf < 12 at
        # dx -143.5): the one-shot probe takes the throw
        p = Mission1Policy()
        p._facing = "L"
        for dx in (-146.0, -144.75, -143.5):
            a, diag = decide(p, px=1071.0, ents=[(dx, 8, 64.0)])
        assert a == "GRENADE"
        assert diag["rule"] == "truck_width_probe"
        assert diag["width_probed"] == 1
        # the cap: never again (the cooldown clears first)
        p._gren_cd = 0
        a, diag = decide(p, px=1071.0, ents=[(-142.25, 8, 64.0)])
        assert a != "GRENADE" or diag["rule"] != "truck_width_probe"

    def test_c4_width_probe_dirty_corridor_holds(self):
        # the C2-only path: a mortal INSIDE the 8px escort floor
        # (point-blank, un-engageable by the escort rules) still
        # blocks the descent corridor -> the probe withholds
        p = Mission1Policy()
        p._facing = "L"
        p._truckin_static = 2
        p._truckin_dx = -154.75
        p._truckin_px = 1071.0
        a, diag = decide(p, px=1071.0,
                         ents=[(-5.0, 6, 64.0), (-153.5, 8, 64.0)])
        assert a == "IDLE"
        assert diag["rule"] == "truckin_hold"
        assert diag["corridor"] is False

    def test_c4_lead_has_priority_over_probe(self):
        # the lead window (ftf ~16) opens BEFORE the probe spends
        p = Mission1Policy()
        p._facing = "L"
        p._truckin_static = 2
        p._truckin_dx = -154.75
        p._truckin_px = 1071.0
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        assert a == "GRENADE"
        assert diag["rule"] == "truck_lead_throw"

    def test_version_bump(self):
        assert POLICY_VERSION == "1.9.0"

    def test_c5_sc6_walker_outranks_lob(self):
        # C5 (the r70 boot-2 evidence): a chaser in a WALK state
        # (sc=6, the R67 probe correction) between the player and
        # the truck is ENGAGED (the T3 fire) — it used to be
        # invisible to the escort rules and it filled the corridor
        p = at_clock(GRID_K0)
        a, diag = decide(p, ents=[(-48.9, 6, 64.0), TRUCK_L])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"
        assert diag["target_sc"] == 6
