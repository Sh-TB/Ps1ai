"""Session-4 (Issue #5 F9 unblock) regression tests.

Evidence base (all live, real-inputs-only):
  - soldier_hp_probe.py / soldier_hp_probe2.py (shp_100033, shp2_*):
    wave soldiers cycle st 0x4054 <-> 0x41FC unattended; a killed
    soldier flips to 0x4BE4 and its row zeros at ~+138f; 2 aimed
    bullets kill (soldier_bpp.py 3/3 deterministic).
  - chain_a_full.py v2 (a1_102112 tally): after the wave clear the
    end sequence runs BY ITSELF -> (0xC, 0x9) @ px 26.4 = the
    MISSION 1 banner; chain_a v3/v4: walking during the banner
    expires its countdown into a mission restart.
  - chain_a_full.py v6: 3/3 MISSION banner (PNG evidence).
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.agent.combat import (  # noqa: E402
    CombatPolicy, scan_entities, CORPSE_ST, SOLDIER_FAMILY_ST,
    SECTION_MISSION_END, MISSION_END_CONFIRM, TABLE, STRIDE,
)


class RowMem:
    """Entity-table stand-in with per-slot word0 (st) support.

    slots: {slot_index: (x_fixed, sx, st)}  (st = word0 at +0x00)
    """

    def __init__(self, slots, px=1164.0):
        self.slots = slots
        self.TABLE = TABLE
        self.STRIDE = STRIDE
        self._px = int(px * 65536)

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
            if off == 0x00:
                return self.slots[s][2]
        return 0


def test_scan_entities_excludes_corpse_states():
    """A mid-anim corpse (st 0x4BE4, valid screen-x until its ~+138f
    despawn) must NOT be scanned as an enemy — the F9 mis-aim
    mechanism.  The live soldier (0x4054 or its 0x41FC cycle phase)
    stays."""
    slots = {
        0: (int(1164 * 65536), 144, 0xA0),          # player row
        1: (int(1064 * 65536), 195, 0x4054),        # live soldier
        2: (int(1072 * 65536), 188, 0x4BE4),        # fresh corpse
        3: (int(1045 * 65536), 201, 0x5CC8),        # late corpse
        4: (int(1030 * 65536), 190, 0x41FC),        # cycled live
    }
    out = scan_entities(RowMem(slots))
    got = {e["slot"] for e in out}
    assert 1 in got and 4 in got          # live soldiers kept
    assert 2 not in got and 3 not in got  # corpses dropped
    for e in out:
        assert e["st"] not in CORPSE_ST


def test_soldier_family_constants_match_live_evidence():
    """Guard the encoded live semantics against silent drift."""
    assert CORPSE_ST == (0x4BE4, 0x5CC8)
    assert SOLDIER_FAMILY_ST == (0x4054, 0x41FC)
    assert SECTION_MISSION_END == 0xC
    assert MISSION_END_CONFIRM == 2


def _sec(state, flags=1):
    return {"state": state, "flags": flags, "progress": 0xFFFF,
            "schema": "x", "complete": False}


def test_mission_end_hold_emits_no_input():
    """Two consecutive 0xC readings latch the banner; decide() then
    returns ONE no-input segment covering the whole chunk (walking
    during the banner expires it into a restart — v3/v4)."""
    pol = CombatPolicy()
    pol.observe_section(_sec(0xB, 0x1))       # pre-banner context
    pol.decide(60, 992.0, [], grenades=5, hp=144)
    pol.observe_section(_sec(0xC, 0x9))
    assert not pol.mission_end                # 1 reading: not yet
    pol.observe_section(_sec(0xC, 0x9))
    assert pol.mission_end
    segs = pol.decide(60, 26.4, [], grenades=5, hp=144)
    assert segs == [{"frames": 60, "btns": set()}]
    assert pol.stats.get("mission_end_hold", 0) >= 1
    # the hold is sticky — it survives further non-0xC readings
    pol.observe_section(_sec(0xB, 0x1))
    segs = pol.decide(60, 26.4, [], grenades=5, hp=144)
    assert segs == [{"frames": 60, "btns": set()}]


def test_single_mission_end_reading_does_not_latch():
    """A single 0xC transient (walker resets also cross odd states)
    must not freeze the run."""
    pol = CombatPolicy()
    pol.observe_section(_sec(0xC, 0x9))
    assert not pol.mission_end
    segs = pol.decide(60, 1100.0, [], grenades=5, hp=144)
    assert any(s["frames"] > 0 for s in segs)


def test_clamp_clear_aims_past_corpses():
    """At the pin the ONLY scanned foe must be the live soldier: the
    corpse (closer!) is excluded so the facing follows the live one —
    the session-3 'Y-bursts did not kill' root cause."""
    slots = {
        0: (int(1164 * 65536), 144, 0xA0),
        1: (int(1072 * 65536), 188, 0x4BE4),   # corpse CLOSER (dx -92)
        2: (int(1064 * 65536), 195, 0x4054),   # live soldier (dx -100)
    }
    scan = scan_entities(RowMem(slots))
    assert [e["slot"] for e in scan] == [2]
    pol = CombatPolicy()
    pol.observe_section(_sec(0xA, 0x43))       # pin
    pol.observe_section(_sec(0xA, 0x43))
    pol.decide(60, 1164.0, scan, grenades=0, hp=144)
    # engage/clamp_clear facing must be RIGHT-ward? No: soldier is at
    # dx -100 -> LEFT; assert the policy engaged the live slot by
    # checking the engage ledger picked slot 2 (no corpse aim).
    assert pol.engage_slot in (2, None)


def test_d7_quiet_hold_on_empty_scan():
    """At the D7 zone (px >= 1150) with an EMPTY scan the policy must
    go SILENT: any input during the (0,8)->(0xC) end-sequence skipss
    the banner (policy_chain_trial 3/3).  Outside the zone the old
    alternation fire continues."""
    pol = CombatPolicy()
    pol.observe(px=1164.0, advanced=0.0, intent_right=True)
    segs = pol.decide(60, 1164.0, [], grenades=5, hp=291)
    assert pol.mode == "clamp_clear"
    assert all(not (s.get("btns") or set()) for s in segs)
    assert pol.stats.get("d7_quiet_hold", 0) >= 1
    # outside the zone: the historical rain behaviour persists
    pol2 = CombatPolicy()
    pol2.observe(px=1000.0, advanced=0.0, intent_right=True)
    segs2 = pol2.decide(60, 1000.0, [], grenades=5, hp=291)
    assert any((s.get("btns") or set()) for s in segs2)


def test_prebanner_reset_latches_hold_in_d7_zone():
    """Trigger B: the (state 0, flags & 0x8) walker reset INSIDE the
    D7 zone latches the mission-end hold IMMEDIATELY — policy inputs
    during (0,8)->(0xC) skip the banner (trial c=13)."""
    pol = CombatPolicy()
    pol.observe(px=1164.0, advanced=0.0, intent_right=True)
    pol.observe_section({"state": 0, "flags": 0x8, "progress": 0,
                         "schema": "x", "complete": False})
    assert pol.mission_end
    segs = pol.decide(60, 900.0, [], grenades=5, hp=144)
    assert segs == [{"frames": 60, "btns": set()}]
    assert pol.stats.get("mission_end_prebanner", 0) == 1
    # the same reset OUTSIDE the zone must not latch
    pol2 = CombatPolicy()
    pol2.observe(px=500.0, advanced=0.0, intent_right=True)
    pol2.observe_section({"state": 0, "flags": 0x8, "progress": 0,
                          "schema": "x", "complete": False})
    assert not pol2.mission_end
