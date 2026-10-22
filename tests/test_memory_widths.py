#!/usr/bin/env python3
"""Regression test: MemoryView.u16/u32 must reassemble BOTH bytes.

The pre-fix implementation shifted a numpy uint8 by 8 inside uint8
arithmetic, which wraps to 0 — every u16/u32 read silently returned
only the low byte. This corrupted, among others, the telemetry
camera_x (u32 >> 16 was always 0) and every progress-word read whose
true value exceeded 255.
"""
import numpy as np
import pytest

from ps1play.core.memory import MemoryView


@pytest.fixture
def mv():
    ram = np.zeros(64, dtype=np.uint8)
    # 0xCA2E0-style u32: 0x048BFFFF (camera at 1162.999 px)
    ram[0x10:0x14] = [0xFF, 0xFF, 0x8B, 0x04]
    # a u16 with a nonzero high byte: 0x0125 = 293
    ram[0x20:0x22] = [0x25, 0x01]
    # a u16 that FITS in the low byte must read unchanged
    ram[0x30:0x32] = [0xFF, 0x00]
    return MemoryView(ram)


def test_u16_reassembles_high_byte(mv):
    assert mv.u16(0x20) == 0x0125
    assert mv.u16(0x20) == 293


def test_u16_low_byte_only_value_unchanged(mv):
    assert mv.u16(0x30) == 0x00FF


def test_u32_reassembles_all_four_bytes(mv):
    assert mv.u32(0x10) == 0x048BFFFF


def test_camera_fixed_point_value(mv):
    # the camera case that exposed the bug: 0x048BFFFF / 65536 = 1163.0
    assert mv.u32(0x10) / 65536.0 == pytest.approx(1164.0, abs=0.01)


def test_u8_still_exact(mv):
    assert mv.u8(0x13) == 0x04
