"""Section-walker sensor tests (Ghidra FUN_80021898 deep dive, Issue #9).

scan_section() is a read-only sensor over the scroll/camera section-walker
globals identified in the decompiled walker (0x0EB5F4 state, 0x0EB5D0 flags,
0x0EB5D4 progress). These tests pin the contract: schema tag, complete-latch
semantics, and zero-mutation behavior.
"""
import numpy as np
import pytest

from ps1play.agent.combat import (
    SECTION_FLAGS,
    SECTION_PROGRESS,
    SECTION_SCHEMA,
    SECTION_STATE,
    scan_section,
)


class FakeMem:
    def __init__(self):
        self.ram = np.zeros(0x200000, np.uint8)

    def u16(self, a):
        return int(self.ram[a]) | (int(self.ram[a + 1]) << 8)

    def u32(self, a):
        return int.from_bytes(bytes(self.ram[a:a + 4]), "little")

    def poke_u16(self, a, v):
        self.ram[a] = v & 0xFF
        self.ram[a + 1] = (v >> 8) & 0xFF


def test_scan_section_zero_defaults_incomplete():
    m = FakeMem()
    s = scan_section(m)
    assert s["schema"] == SECTION_SCHEMA
    assert s == {"state": 0, "flags": 0, "progress": 0,
                 "schema": SECTION_SCHEMA, "complete": False}


def test_scan_section_reads_state_flags_progress():
    m = FakeMem()
    m.poke_u16(SECTION_STATE, 9)
    m.poke_u16(SECTION_FLAGS, 0x1)
    m.poke_u16(SECTION_PROGRESS, 0x1234)
    s = scan_section(m)
    assert s["state"] == 9
    assert s["flags"] == 0x1
    assert s["progress"] == 0x1234
    assert s["complete"] is False


@pytest.mark.parametrize("state,flags", [(0xF, 0x0), (0x7, 0x200), (0xF, 0x200)])
def test_scan_section_complete_latch(state, flags):
    m = FakeMem()
    m.poke_u16(SECTION_STATE, state)
    m.poke_u16(SECTION_FLAGS, flags)
    assert scan_section(m)["complete"] is True


def test_scan_section_mid_states_incomplete():
    m = FakeMem()
    for state in (0x1, 0x9, 0xE):
        m.poke_u16(SECTION_STATE, state)
        m.poke_u16(SECTION_FLAGS, 0x0)
        assert scan_section(m)["complete"] is False


def test_scan_section_never_writes():
    m = FakeMem()
    m.poke_u16(SECTION_STATE, 5)
    before = m.ram.copy()
    scan_section(m)
    assert (m.ram == before).all()
