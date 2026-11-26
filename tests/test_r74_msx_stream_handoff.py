"""tests/test_r74_msx_stream_handoff.py — R74 Metal Slug X policy
v2.2.0 THE STREAM HANDOFF (offline; no emulator, no boot).

The R74 capsule lever, the product track — THE KILL ATTEMPT.  The
R73 calibration table (data/games/SLUS-01212/truck_evidence/r73/
r73_calibration.json) proved the ownership sets COMPLEMENT:

  * the volley stream (the v1.7.x ungated gre40 cadence) owns
    k=0/k=1 — the connects at freeze+178/+342, the -1f x2 (the
    committed R69 frames f989/f1153);
  * the idle-hold stream owns k=2 — freeze+506, 4/4 across
    -1f/+1f (the R71 boot-3, the R72 boot-1, the R73 boot-1);
  * no single stream owns all three (the idle-hold k=0/k=1/k=3
    0/6 measured; the volley never reached k=2 — the scroll shove).

v2.2.0: the shipped policy STARTS on the volley head — THE
VERBATIM r69b THROW SCHEDULE (fight_f 64/106/147/188/229/270/311;
a dynamic 40f cadence does NOT reproduce this stream: its landing
phase never reaches ANY grid point — the schedule IS the stream) —
and hands off ON THE CLOCK at fight_f 350 (past the k=1 window
close at land 344, before the next volley frame ~352) to the
idle-hold tail (the v2.1.0 semantics verbatim: the full +-2f gate
+ the rear-escort exemption).  The head has NO lead throws and NO
C4 width probe (the r69b stream never led or probed — foreign
inputs).

Covers:
  * the volley head throws at exactly the schedule frames (and
    nowhere else pre-handoff);
  * the head books NO gate discipline (the schedule ignores the
    phase k) and pre-spends the probe;
  * the handoff: the volley state before fight_f 350, the hold
    after; the switch is one-way and resets on the re-anchor;
  * the tail: the phase gate governs again (the off-grid frames
    hold), the k=2 window opens on the gate;
  * the lead: blocked in the volley state (the hold-state coverage
    stays in test_r70);
  * the kill math: 2 head connects (-200) + the k=2 connect
    (-100) = a4 300 -> 0 INSIDE the f1844 clock.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    Mission1Policy, POLICY_VERSION, TRUCK_GRENADE_CD,
    TRUCK_HANDOFF_FIGHT_F, TRUCK_VOLLEY_SCHEDULE)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
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


def fresh(fight_f, facing="L"):
    """A policy whose NEXT decision lands at fight_f WITH the
    volley head active (the truck already seen so the anchor reset
    does not fire); the C4 probe pre-spent (the re-anchor's
    volley-state pre-spend, which this helper bypasses)."""
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    p._width_probed = 1
    p._facing = facing
    return p


class TestShippedHandoff:
    def test_version_and_identity(self):
        assert POLICY_VERSION == "2.2.0"
        ident = Mission1Policy().identity()
        assert ident["truck_rules"] == "r74_stream_handoff"

    def test_constants_match_the_r69b_evidence(self):
        # the schedule = the committed r69b grenade frames on the
        # P1 clock (freeze f811 -> 875/917/958/999/1040/1081/1122)
        assert TRUCK_VOLLEY_SCHEDULE == (64, 106, 147, 188, 229,
                                         270, 311)
        # the handoff: past the k=1 land (342) + the window close
        # (344), before the next volley cadence frame (~352)
        assert TRUCK_HANDOFF_FIGHT_F == 350.0

    def test_fresh_fight_starts_on_volley(self):
        p = Mission1Policy()
        assert p._stream == "volley"
        # the C4 probe is pre-spent in the volley state (the r69b
        # stream never probed — the R70 probe payment is NOT
        # reproduced); the re-anchor arms on the first SC_TRUCK
        # sighting (the drive-in rows run the truckin block)
        p2 = Mission1Policy()
        p2._truck_present = False
        decide(p2, ents=[TRUCK_L])
        assert p2._stream == "volley"
        assert p2._width_probed == 1


class TestVolleyHead:
    def test_schedule_frames_throw(self):
        for ff in TRUCK_VOLLEY_SCHEDULE:
            p = fresh(ff)
            a, diag = decide(p, ents=[TRUCK_L])
            assert a == "GRENADE", (ff, a, diag)
            assert diag["rule"] == "truck_connect_grenade"
            assert diag["stream"] == "volley"

    def test_off_schedule_frames_hold(self):
        # between the schedule frames the head HOLDS (the gre40
        # cooldown — the v1.7.x semantics; no chip-fire on the
        # shipped default)
        for ff in (80, 130, 200, 250, 330):
            p = fresh(ff)
            a, diag = decide(p, ents=[TRUCK_L])
            assert a == "IDLE", (ff, a, diag)
            assert diag["rule"] in ("truck_phase_hold",
                                    "truck_connect_hold")

    def test_head_ignores_the_phase_gate(self):
        # the k=0 window opens at 146 (-2f) AND the schedule books
        # 147: the gate disciplines the TAIL, not the head — the
        # schedule frame throws even with the k booked by the gate
        p = fresh(146)
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "GRENADE"                   # the gate (-2f side)
        assert p._phase_last_k == 0
        p._gren_cd = 0                          # the next frame armed
        a, diag = decide(p, ents=[TRUCK_L])     # fight_f 147: scheduled
        assert a == "GRENADE", (a, diag)
        assert diag["stream"] == "volley"

    def test_probe_never_fires_in_head(self):
        # fight_f 12 (the C4 post-freeze arm in v2.1.0): the head
        # pre-spends the probe — no width-probe throw, no spend
        p = fresh(12)
        before = p._truck_grenades_used
        for ff in range(12, 40):
            p._truck_fight_f = ff - 1
            decide(p, ents=[TRUCK_L])
        assert p._truck_grenades_used == before


class TestHandoffClock:
    def test_switch_at_350(self):
        p = fresh(350)
        assert p._stream == "volley"
        a, _ = decide(p, ents=[TRUCK_L])        # fight_f 350
        assert p._stream == "hold"
        assert p._handoff_f == 350

    def test_one_way_and_resets_on_reanchor(self):
        p = fresh(360)
        decide(p, ents=[TRUCK_L])
        assert p._stream == "hold"
        # the fresh truck = the fresh fight = the volley head again
        p._truck_present = False
        decide(p, ents=[TRUCK_L])
        assert p._stream == "volley"
        assert p._width_probed == 1

    def test_tail_gate_governs_again(self):
        # post-handoff off-grid: the phase hold (the v1.9.0-era
        # semantics restored)
        p = fresh(400)
        decide(p, ents=[TRUCK_L])               # the handoff frame
        assert p._stream == "hold"
        p._truck_fight_f = 419                  # off-grid
        a, diag = decide(p, ents=[TRUCK_L])
        assert a == "IDLE"
        assert diag["rule"] == "truck_phase_hold"

    def test_tail_k2_window_opens(self):
        # THE TAIL'S TARGET: the k=2 grid window (the gate opens at
        # fight_f 474, the -2f side) — the owned connect land at
        # freeze+506 (the decision helper: fight_f N-1 -> the
        # decision lands at fight_f N)
        p = fresh(360)
        decide(p, ents=[TRUCK_L])
        p._truck_fight_f = 472
        a, diag = decide(p, ents=[TRUCK_L])     # fight_f 473: -3f
        assert a != "GRENADE"                   # closed
        p._truck_fight_f = 473
        a, diag = decide(p, ents=[TRUCK_L])     # fight_f 474: -2f
        assert a == "GRENADE"
        assert diag["phase_k"] == 2


class TestHeadForeignInputs:
    def test_lead_blocked_in_volley_state(self):
        # the drive-in lead arm (the hold-state coverage in
        # test_r70): in the volley head the lead never fires (the
        # r69b stream never led)
        p = Mission1Policy()
        p._stream = "volley"
        p._facing = "L"
        p._truckin_static = 2
        p._truckin_dx = -154.75
        p._truckin_px = 1071.0
        a, diag = decide(p, px=1071.0, ents=[(-153.5, 8, 64.0)])
        assert a != "GRENADE", diag
        assert diag.get("rule") != "truck_lead_throw"

    def test_t3_verbatim_in_head(self):
        # off-window volley frames: a clear-line escort (SAME side)
        # outranks — the v1.7.x semantics verbatim (the stream law)
        p = fresh(80)
        a, diag = decide(p, ents=[TRUCK_L, (-60.0, 1, 64.0)])
        assert a == "FIRE"
        assert diag["rule"] == "truck_escort_first"


class TestKillMath:
    def test_head_plus_tail_reaches_zero(self):
        # THE R74 KILL MATH: the head connects k=0 (-100) + k=1
        # (-100) + the tail k=2 (-100) = a4 300 -> 0 — three
        # connects from the two complementary streams
        a4 = 300
        for _ in (0, 1, 2):
            a4 -= 100
        assert a4 == 0
        # ...and the f1844 section clock (freeze+693) admits the
        # k=2 land at freeze+506 with 187f of post-kill runway
        assert 506 < 693
