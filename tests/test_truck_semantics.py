#!/usr/bin/env python3
"""Regression tests for the corrected entity-field semantics and the
live-verified armored-truck kill routine (Issue #5, uplob2..uplob12).

Covers:
  * scan_entities new keys (sx == hp legacy, hp_a4, st) with a fake mem
  * find_truck identity rules (0x9E88 + ground + hp_a4 band; the
    0x4054 soldier mislock is rejected; bombs/air never match)
  * truck_kill_segments state machine: approach band, hit+escape,
    spam alternation, ammo-out and death termination
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ps1play.agent.combat as combat                          # noqa: E402
from ps1play.agent.combat import (                             # noqa: E402
    find_truck, scan_entities, truck_kill_segments,
    ENTITY_HP_A4, TRUCK_DEATH_ST, FALLER_ST,
)


class FakeMem:
    """Minimal mem stand-in: dict-backed u16/u32 readers."""

    def __init__(self, slots):
        # slots: {slot: {"x": px, "st": word0, "h": h, "hp8e": v,
        #                "hp_a4": v}}
        self.slots = slots

    def _rec(self, base):
        s = (base - combat.TABLE) // combat.STRIDE
        return self.slots.get(s, {})

    def u32(self, addr):
        if addr == combat.PLAYER_X:
            return 1000 * 65536
        base = addr - 0x78
        r = self._rec(base)
        return int(r.get("x", 0.0) * 65536) & 0xFFFFFFFF

    def u16(self, addr):
        base = (addr // combat.STRIDE) * combat.STRIDE \
            if addr >= combat.TABLE else 0
        off = addr - base if base else addr
        r = self._rec(base or addr)
        if off == 0x8E:
            return r.get("hp8e", 0)
        if off == ENTITY_HP_A4:
            return r.get("hp_a4", 0)
        if off == 0x7E:
            return r.get("h", 0)
        if off == 0:
            return r.get("st", 0)
        return 0

    def u8(self, addr):
        return 0


def test_scan_entities_new_keys():
    mem = FakeMem({3: {"x": 1100.0, "st": 0x9E88, "h": 64,
                       "hp8e": 267, "hp_a4": 300}})
    ents = scan_entities(mem, px=1000.0)
    assert len(ents) == 1
    e = ents[0]
    assert e["slot"] == 3
    assert e["sx"] == 267              # screen-x integer
    assert e["hp"] == 267              # legacy alias, same raw value
    assert e["hp_a4"] == 300           # the REAL armored HP
    assert e["st"] == 0x9E88
    assert e["kind"] == "enemy"


def test_find_truck_identity():
    truck = {"slot": 14, "x_px": 937.5, "dx_px": -62.0, "hp": 65,
             "sx": 65, "h": 64, "st": 0x9E88, "hp_a4": 300,
             "kind": "enemy"}
    soldier = dict(truck, slot=10, st=0x4054, hp_a4=0)   # the mislock
    bomb = dict(truck, slot=4, st=FALLER_ST, h=130, hp_a4=30,
                kind="projectile_air")
    air = dict(truck, slot=7, h=90, kind="projectile_air")
    lowhp = dict(truck, slot=14, st=0x9E88, hp_a4=0)     # dead/dying
    assert find_truck([soldier, bomb, air, lowhp, truck]) is truck
    assert find_truck([soldier, bomb, air, lowhp]) is None
    assert find_truck([]) is None


def test_kill_segments_approach_and_hit():
    truck = {"slot": 14, "x_px": 937.5, "dx_px": -150.0, "h": 64,
             "st": 0x9E88, "hp_a4": 300, "kind": "enemy"}
    segs, phase, done = truck_kill_segments(1088.0, truck, 10, None)
    assert not done and segs == [{"frames": 30, "btns": {"LEFT"}}]
    assert phase["mode"] == "approach"
    # in-band: the proven face-left flat lob + 110f escape
    segs, phase, done = truck_kill_segments(990.0, truck, 10, phase)
    btns = [s["btns"] for s in segs]
    assert {"A"} in btns and {"RIGHT"} in btns
    assert phase["mode"] == "spam"          # hp 300-100=200 -> spam next


def test_kill_segments_spam_and_death():
    truck = {"slot": 14, "x_px": 937.5, "dx_px": -150.0, "h": 64,
             "st": 0x9E88, "hp_a4": 200, "kind": "enemy"}
    segs, phase, done = truck_kill_segments(1164.0, truck, 9, None)
    # spam: face-left, alternate UP-lob / flat, watch window
    btns = [s["btns"] for s in segs]
    assert {"LEFT", "UP", "A"} in btns
    assert phase["mode"] == "spam" and phase["n"] == 1
    segs, phase, done = truck_kill_segments(1164.0, truck, 8, phase)
    assert {"LEFT", "A"} in [s["btns"] for s in segs]
    # death: hp_a4 == 0 terminates
    dead = dict(truck, hp_a4=0, st=TRUCK_DEATH_ST)
    segs, phase, done = truck_kill_segments(1164.0, dead, 8, phase)
    assert done and segs == []
    # ammo-out terminates too
    segs, phase, done = truck_kill_segments(1164.0, truck, 0, None)
    assert done


def test_semantics_constants_documented():
    # the corrected offsets are committed evidence, not guesses
    assert ENTITY_HP_A4 == 0xA4
    assert TRUCK_DEATH_ST == 0xA304
    assert FALLER_ST == 0xB4E4
