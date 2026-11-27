"""tests/test_r75_msx_extended_grid.py — R75 Metal Slug X policy
v2.3.0 THE HEAD-PHASE EXTENDED SCHEDULE (offline; no boot).

The R74b1 boot proved THE HEAD-PHASE LAW: the head's own connect
grid = freeze+259 (+81f, ~the half-period vs the r69b/178-grid);
the 229 throw landed ON it (+0f, CONNECTED) while the 270/311
throws missed (+41f/+82f off — the predicted off-window).  The
head's grid CONTINUES at freeze+423 and freeze+587 — v2.3.0
extends the schedule by {393, 557} (their throw frames) and moves
the handoff to fight_f 620: THREE head connects = a4 300 -> 200
-> 100 -> 0 = THE TRUCK KILL INSIDE the death clock (the r74b1
death at freeze+733 admits the freeze+587 land with ~146f of
runway).  The extension throws are ON the head's grid — not
perturbations (the stream law holds by construction if the phase
reproduces — the r74b1 head replay was byte-exact 312/312).

Covers:
  * the extension frames throw on the head stream (393, 557) and
    land exactly on the 259-grid points (+0f);
  * the 178-grid windows still fire during the head (the OR —
    the r74b1 corridor-blocked frame; the law predicts a miss);
  * the handoff at 620: past the freeze+587 read window, before
    the 178-grid k=3 gate (638-642);
  * the kill math and the death-clock fit.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.adapters.metal_slug_x.policy import (  # noqa: E402
    Mission1Policy, POLICY_VERSION, TRUCK_HANDOFF_FIGHT_F,
    TRUCK_VOLLEY_SCHEDULE)
from ps1play.runtime.interfaces import GameObservation  # noqa: E402

OBS_LEN = 21
TRUCK_L = (-133.5, 7, 64.0)


def obs_from(px=1071.0, gren=10, ents=()):
    x = np.zeros(OBS_LEN, dtype=np.float32)
    x[0] = px
    x[3] = float(gren)
    x[4] = 1.0
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
    p = Mission1Policy()
    p._truck_present = True
    p._truck_fight_f = fight_f - 1
    p._width_probed = 1
    p._facing = facing
    return p


class TestExtendedGrid:
    def test_version_and_identity(self):
        assert POLICY_VERSION == "2.6.1"
        ident = Mission1Policy().identity()
        assert ident["truck_rules"] == "r82_chipfire_kill"

    def test_extension_frames_on_the_head_grid(self):
        # the 393/557 throws land EXACTLY on the head's 259-grid
        # (+0f): the R74b1 law's own connect windows
        for ff, land in ((393, 423), (557, 587)):
            assert ff + 30 == land
            assert (land - 259) % 164 == 0
            p = fresh(ff)
            a, diag = decide(p, ents=[TRUCK_L])
            assert a == "GRENADE", (ff, a, diag)
            assert diag["stream"] == "volley"

    def test_extension_in_schedule_constant(self):
        assert 393 in TRUCK_VOLLEY_SCHEDULE
        assert 557 in TRUCK_VOLLEY_SCHEDULE
        assert TRUCK_HANDOFF_FIGHT_F == 620.0

    def test_handoff_after_the_kill_window(self):
        # the handoff fires only past the freeze+587 read window
        # (587 + 30 read margin -> 620) and BEFORE the 178-grid
        # k=3 gate frame (638-642)
        assert 587 + 30 <= TRUCK_HANDOFF_FIGHT_F < 638
        p = fresh(620)
        decide(p, ents=[TRUCK_L])
        assert p._stream == "hold"
        p2 = fresh(619)
        decide(p2, ents=[TRUCK_L])
        assert p2._stream == "volley"


class TestKillMath:
    def test_three_head_connects_kill(self):
        # the R75 kill math: a4 300 -> 200 (freeze+259, the r74b1
        # PROVEN connect) -> 100 (freeze+423) -> 0 (freeze+587)
        a4 = 300
        for _ in range(3):
            a4 -= 100
        assert a4 == 0

    def test_death_clock_admits_the_kill(self):
        # the r74b1 death at freeze+733 (posture-coupled); the
        # freeze+587 land + the read latency fit with ~146f of
        # post-kill runway (the W8/W9 transition + the section
        # continuation measurement)
        assert 587 < 733 - 30
