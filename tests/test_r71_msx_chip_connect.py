"""tests/test_r71_msx_chip_connect.py — R71 Metal Slug X policy
v1.9.0 K1 THE COOLDOWN CHIP-FIRE (offline; no emulator, no boot).

The R71 capsule lever, product track: the CHIP-CONNECT KILL
SCHEDULE.  The R70 evidence this rule encodes:

  * the chip payments (-10 a4 / +100 score) are a SECOND damage
    path — the C4 width probe landed a wrong-phase chip (300 ->
    290), the R70 best boot ran a4 300 -> 230 on the escort strays
    at ~26f cadence under the walker feed, and the R68 record
    fight netted 1 connect + chips (-40);
  * THE KILL MATH (the R70 report): the chips (-10 each) + TWO
    centered connects (-100 each) reach a4 0 INSIDE the
    scroll-capped window — the kill does NOT need three
    phase-connects;
  * the corridor-feed law (the R70 boot-4 evidence): the walkers
    fill the corridor upstream of the posture — the throw must be
    spent only over a CLEAN corridor, and the aimed chip-fire must
    not waste bullets into the feed.

K1 semantics (v1.9.0):
  * the chip-fire runs ONLY inside the corridor-cleared throw
    branch (the branch guard IS the C2 bullet-line guard; the
    v1.6.1 bullets-eaten failure mode is what the guard removes);
  * the chip-fire requires NO escort (the T3 rule keeps
    precedence);
  * the grenade keeps priority when the phase opens with a ready
    grenade — the chip-fire NEVER delays a grid throw;
  * when the corridor is OCCUPIED the chip-fire is WITHHELD (the
    posture holds — the pre-v1.9.0 semantics) so the corridor is
    clean AT each grid window;
  * the fire cadence is the escort FIRE_COOLDOWN (the verified
    12f wave rhythm — the cadence law).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    FIRE_COOLDOWN, Mission1Policy, POLICY_VERSION,
    TRUCK_CONNECT_MAX, TRUCK_CONNECT_MIN, TRUCK_GRENADE_CD,
    TRUCK_THROW_MAX, TRUCK_THROW_MIN,
)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
GRID_K0 = 178 - 30               # the k=0 throw fight_f (= 148)

TRUCK_L = (-133.5, 7, 64.0)      # the record posture
WALKER_IN_CORRIDOR = (-100.0, 1, 64.0)   # between player and truck
ESCORT_REAR = (-50.0, 1, 64.0)   # a clear-line escort


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


def at_clock(fight_f, probe=True, gren_cd=0, fire_cd=0):
    """A policy whose NEXT decision lands at fight_f (the truck
    already seen so the anchor reset does not fire), facing LEFT
    (the record fight facing), both one-shot arms pre-spent."""
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    p._width_probed = 1 if probe else 0
    p._lead_spent = 2
    p._gren_cd = gren_cd
    p._fire_cd = fire_cd
    p._facing = "L"
    return p


class TestK1ChipFire:
    def test_version_is_1_9_0(self):
        assert POLICY_VERSION == "1.9.0"

    def test_chip_fire_during_cooldown_clear_corridor(self):
        # the grenade on cooldown, the corridor clear: the aimed
        # chip-fire fires at the record posture (the SECOND damage
        # path — the R70 chip evidence)
        p = at_clock(60, gren_cd=20)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "FIRE", diag
        assert diag["rule"] == "truck_chip_fire"
        assert diag["truck_dx"] == pytest.approx(-133.5)
        assert p._fire_cd == FIRE_COOLDOWN
        assert p._gren_cd == 19          # ticked exactly once

    def test_chip_wait_during_fire_cadence(self):
        p = at_clock(60, gren_cd=20, fire_cd=5)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "IDLE", diag
        assert diag["rule"] == "truck_chip_wait"
        assert diag["fire_cd"] == 4      # ticked
        assert p._gren_cd == 19

    def test_chip_turn_when_facing_wrong(self):
        # the default facing R must turn first (the same
        # turn discipline as the lob turn — one BACK frame)
        p = at_clock(60, gren_cd=20)
        p._facing = "R"
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "BACK", diag
        assert diag["rule"] == "truck_chip_turn"
        assert p._facing == "L"
        # the NEXT decision fires (no grenade yet — the cooldown)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "FIRE"
        assert diag["rule"] == "truck_chip_fire"

    def test_chip_fire_off_grid_probe_spent(self):
        # the ready grenade OFF the grid: no lob (the phase gate),
        # the chip-fire instead — the pre-v1.9.0 phase-hold IDLE
        # is replaced ONLY when the corridor is clear
        p = at_clock(60)                 # phase_off = (60+30-178)%164
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "FIRE", diag
        assert diag["rule"] == "truck_chip_fire"
        assert diag["phase_off"] == pytest.approx(
            (60 + 30 - 178) % 164)

    def test_grenade_keeps_priority_on_grid(self):
        # the grid window with a ready grenade: the GRENADE fires
        # even with the fire cadence mid-cycle (the chip-fire
        # NEVER delays a grid throw)
        p = at_clock(GRID_K0, fire_cd=7)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE", diag
        assert diag["rule"] == "truck_connect_grenade"
        assert diag["phase_k"] == 0

    def test_chip_fire_withheld_when_corridor_occupied(self):
        # a walker between the player and the truck: the chip-fire
        # is WITHHELD (no bullets into the feed — the corridor-feed
        # law).  The walker itself is a clear-line ESCORT (the T3
        # rule engages it at the fire cadence); BETWEEN escort
        # shots (fire_cd > 0) the posture falls through to the
        # pre-v1.9.0 hold — that is the observable withholding.
        p = at_clock(60, gren_cd=20, fire_cd=5)
        a, diag = decide(p, ents=[TRUCK_L, WALKER_IN_CORRIDOR])
        assert a == "IDLE", diag
        assert diag["rule"] == "truck_hold"
        # the same withholding off-grid with a ready grenade
        p2 = at_clock(60, fire_cd=5)
        a, diag = decide(p2, ents=[TRUCK_L, WALKER_IN_CORRIDOR])
        assert a == "IDLE", diag
        assert diag["rule"] == "truck_hold"

    def test_corridor_walker_cleaned_by_escort_rule(self):
        # the corridor-feed law in action: the walker IN the
        # corridor is a clear-line escort from the player's side —
        # the T3 rule cleans it (the corridor is clean AT each
        # grid window), the chip-fire never wastes bullets into
        # the feed
        p = at_clock(60, gren_cd=20)
        a, diag = decide(p, ents=[TRUCK_L, WALKER_IN_CORRIDOR])
        assert a == "FIRE", diag
        assert diag["rule"] == "truck_escort_first"
        assert diag["target_dx"] == pytest.approx(-100.0)

    def test_escort_outranks_chip_fire(self):
        # a clear-line escort: the T3 rule keeps precedence —
        # bullets go to the escort first (the D7 recipe)
        p = at_clock(60, gren_cd=20)
        a, diag = decide(p, ents=[TRUCK_L, ESCORT_REAR])
        assert a == "FIRE", diag
        assert diag["rule"] == "truck_escort_first"
        assert diag["target_dx"] == pytest.approx(-50.0)

    def test_width_probe_still_precedes_chip_fire(self):
        # the C4 one-shot probe is spent BEFORE the chip-fire
        # becomes the steady state (the C4 ordering)
        p = at_clock(60, probe=False)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE", diag
        assert diag["rule"] == "truck_width_probe"
        p._gren_cd = 0
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "FIRE"
        assert diag["rule"] == "truck_chip_fire"

    def test_chip_fire_cadence_is_fire_cooldown(self):
        # the 12f rhythm: FIRE, then 11 wait decisions, then FIRE
        p = at_clock(60, gren_cd=200)
        acts = []
        for _ in range(FIRE_COOLDOWN + 1):
            a, _ = decide(p, ents=[TRUCK_L])
            acts.append(a)
        assert acts[0] == "FIRE"
        assert acts[1:-1] == ["IDLE"] * (FIRE_COOLDOWN - 1)
        assert acts[-1] == "FIRE"
        assert all(a != "GRENADE" for a in acts)

    def test_no_grenade_spent_by_chip_fire(self):
        # the chip-fire never touches the grenade budget
        p = at_clock(60, gren_cd=30)
        before = p._truck_grenades_used
        for _ in range(50):
            decide(p, ents=[TRUCK_L])
        assert p._truck_grenades_used == before

    def test_below_band_regime_unchanged(self):
        # inside the connect window but BELOW the throw band
        # (dx -130.5, the measured miss): the pre-v1.9.0 hold
        # semantics are preserved (the chip-fire never runs there
        # — the branch guard requires the throw band)
        p = at_clock(60, gren_cd=20)
        a, diag = decide(p, ents=[(-130.5, 7, 64.0)])
        assert a == "IDLE", diag
        assert diag["rule"] == "truck_recenter_hold"

    def test_retreat_below_window_unchanged(self):
        # below the connect window: the away-retreat (the sub-90
        # back-off generalized; the v1.8.5 hold-below law)
        p = at_clock(60, gren_cd=20)
        a, diag = decide(p, ents=[(-125.0, 7, 64.0)])
        assert a == "WALK", diag       # away from a LEFT truck
        assert diag["rule"] == "truck_connect_retreat"

    def test_kill_math_constants_unchanged(self):
        # the kill math bookkeeping: the connect -100 (the
        # grenade), the chip -10 (the aimed/stray bullets) — the
        # policy constants stay the evidence values
        assert TRUCK_GRENADE_CD == 40
        assert FIRE_COOLDOWN == 12
        assert (TRUCK_THROW_MIN, TRUCK_THROW_MAX) == (131.5, 135.0)
        assert (TRUCK_CONNECT_MIN, TRUCK_CONNECT_MAX) == (130.0,
                                                          135.0)


# ---- the adapter v0.5.2 perception tests (the r71 boot-1 fixes) ----
import struct                                            # noqa: E402

from ps1play.adapters.metal_slug_x.adapter import (      # noqa: E402
    ADAPTER_VERSION, ST_PROJECTILE_AIR, MetalSlugXAdapter)

_A_TABLE = 0x0CA268
_A_STRIDE = 0x14C


def _adapter_with_slots(px, slots):
    """slots: {slot: (st, x_word, h, sx, a4)} — the r71 boot-1
    synthetic tables (the ghost blocker + the invisible thief)."""
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
    mem.ram[0x0CA2E0:0x0CA2E4] = struct.pack("<I", int(px) << 16)
    mem.ram[0x0EE518:0x0EE51C] = struct.pack("<I", 0xFF)
    for s, row in slots.items():
        st, xw, h = row[0], row[1], row[2]
        sx = row[3] if len(row) > 3 else 40
        a4 = row[4] if len(row) > 4 else 0
        base = _A_TABLE + s * _A_STRIDE
        mem.ram[base:base + 2] = struct.pack("<H", st)
        mem.ram[base + 0x78:base + 0x7C] = struct.pack("<I", xw)
        mem.ram[base + 0x7E:base + 0x80] = struct.pack("<H", h)
        mem.ram[base + 0x8E:base + 0x90] = struct.pack("<H", sx)
        mem.ram[base + 0xA4:base + 0xA6] = struct.pack("<H", a4)
    FakeP = type("FakeP", (), {"mem": mem})
    FakeEnv = type("FakeEnv", (), {"p": FakeP()})
    return MetalSlugXAdapter(env=FakeEnv())


class TestAdapterV052A4Aware:
    def test_version(self):
        assert ADAPTER_VERSION == "0.5.2"

    def test_ghost_dead_walk_row_not_packed(self):
        # the r71 boot-1 k=0 ghost: slot23 st 0x6730, x 995.0,
        # h 64, a4 0 — an unknown dead-walk state NOT in CORPSE_ST
        # blocked the window while dead; the a4 == 0 rule drops it
        ad = _adapter_with_slots(1071, {
            14: (0x9E88, (1071 - 133) << 16, 64, 40, 300),
            23: (0x6730, (1071 - 76) << 16, 64, 40, 0),
        })
        out = ad.scan_mortals(1071.0)
        sts = [e["st"] for e in out]
        assert 0x9E88 in sts            # the truck anchor stays
        assert 0x6730 not in sts        # THE GHOST IS GONE

    def test_invisible_thief_now_packed(self):
        # the r71 boot-1 k=1 theft stack: 0xb4e4 (a4 30, h 102),
        # 0xabdc (a4 300, h 205) at x 1062.3 — the h > 64 drop hid
        # the LIVE rows; the a4 > 0 rows are packed now
        ad = _adapter_with_slots(1071, {
            14: (0x9E88, (1071 - 133) << 16, 64, 40, 300),
            9: (0xB4E4, int((1071 - 8.7) * 65536), 102, 40, 30),
            15: (0xABDC, int((1071 - 8.7) * 65536), 205, 40, 300),
        })
        out = ad.scan_mortals(1071.0)
        sts = [e["st"] for e in out]
        assert 0xB4E4 in sts            # the thief is visible
        assert 0xABDC in sts

    def test_dead_airborne_row_still_dropped(self):
        # the a4 <= 0 airborne rows stay dropped (projectiles)
        ad = _adapter_with_slots(1071, {
            14: (0x9E88, (1071 - 133) << 16, 64, 40, 300),
            9: (0xB4E4, int((1071 - 8.7) * 65536), 142, 40, 0),
        })
        out = ad.scan_mortals(1071.0)
        assert all(e["st"] != 0xB4E4 for e in out)

    def test_projectile_air_states_stay_excluded(self):
        # the R66 gate-starvation fix must not regress: the known
        # projectile_air states stay excluded even with live a4
        slots = {14: (0x9E88, (1071 - 133) << 16, 64, 40, 300)}
        for i, pst in enumerate(ST_PROJECTILE_AIR):
            slots[20 + i] = (pst, (1071 - 20 - i) << 16, 90, 40,
                             300)
        ad = _adapter_with_slots(1071, slots)
        out = ad.scan_mortals(1071.0)
        sts = [e["st"] for e in out]
        for pst in ST_PROJECTILE_AIR:
            assert pst not in sts
        assert 0x9E88 in sts

    def test_known_states_keep_committed_semantics(self):
        # the KNOWN live states keep the committed semantics
        # whatever their a4 (the R48-R52 evidence set)
        ad = _adapter_with_slots(1071, {
            14: (0x9E88, (1071 - 133) << 16, 64, 40, 300),
            5: (0x4054, (1071 + 60) << 16, 64, 40, 0),   # soft, a4 0
        })
        out = ad.scan_mortals(1071.0)
        sts = [e["st"] for e in out]
        assert 0x4054 in sts            # the known soft row stays
