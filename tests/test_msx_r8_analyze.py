#!/usr/bin/env python3
"""Unit tests for the round-8 diff-of-diffs analyzer (synthetic npz)."""
import importlib.util
import os
import sys

import numpy as np
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "msx_m1end_m2side_analyze",
    os.path.join(os.path.dirname(__file__), "..", "scripts",
                 "msx_m1end_m2side_analyze.py"))
ana = importlib.util.module_from_spec(_SPEC)
sys.modules["msx_m1end_m2side_analyze"] = ana
_SPEC.loader.exec_module(ana) if _SPEC.loader else None

RAM = 1 << 21


def _track(changes, final_over=None):
    """changes: {byte_off: (first_f, count)}; final_over: {off: val}."""
    t = {
        "val0": np.zeros(RAM, dtype=np.uint8),
        "first_f": np.full(RAM, -1, dtype=np.int32),
        "last_f": np.full(RAM, -1, dtype=np.int32),
        "count": np.zeros(RAM, dtype=np.int32),
        "final": np.zeros(RAM, dtype=np.uint8),
    }
    for off, (ff, cnt) in changes.items():
        t["first_f"][off] = ff
        t["last_f"][off] = ff + 30
        t["count"][off] = cnt
        t["final"][off] = (final_over or {}).get(off, 0xAA)
    return t


def test_word_groups_min_bytes():
    mask = np.zeros(RAM, dtype=bool)
    mask[0x1000:0x1003] = True          # 3 bytes in one word
    mask[0x2000] = True                 # lone byte
    w = ana.word_groups(mask, min_bytes=2)
    assert 0x1000 in w and 0x2000 not in w
    assert w[0x1000] == [0x1000, 0x1001, 0x1002]


def test_u16_u32_decode():
    v0 = np.zeros(RAM, dtype=np.uint8)
    fin = np.zeros(RAM, dtype=np.uint8)
    for i, b in enumerate(b"\x11\x22\x33\x44"):
        v0[0x40 + i] = b
        fin[0x40 + i] = b + 1
    assert ana.u16_at(v0, fin, 0x40) == (0x2211, 0x2312)
    assert ana.u32_at(v0, fin, 0x40) == (0x44332211, 0x45342312)


def test_near_known_ranks_nearest_global():
    name, dist = ana.near_known(ana.KNOWN["SECTION_FLAGS"] + 4)
    assert name == "SECTION_FLAGS" and dist == 4


def test_small_value_shape_filter():
    """A u16 0->3 transition inside a discriminator word must be caught;
    pointer-sized values must not."""
    v0 = np.zeros(RAM, dtype=np.uint8)
    fin = np.zeros(RAM, dtype=np.uint8)
    a = ana.KNOWN["SECTION_STATE"] + 0x10
    # word at a: bytes 0->3 at low byte, high byte stays 0
    fin[a] = 3
    fam = np.zeros(RAM, dtype=bool)
    fam[a] = True
    # emulate the small-value scan directly (no npz round trip)
    v0w, f1w = ana.u16_at(v0, fin, a & ~1)
    assert v0w == 0 and f1w == 3 and v0w <= 0x3F and f1w <= 0x3F
    # pointer shape must fail the small-value gate
    fin[a] = 0x20
    fin[a + 1] = 0x08
    v0w, f1w = ana.u16_at(v0, fin, a & ~1)
    assert f1w > 0x3F
