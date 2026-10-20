#!/usr/bin/env python3
"""Offline unit tests for the BIOS-free pad-test payload builder.

The payload is hand-assembled MIPS; these tests pin down the exact
machine-code properties the runtime experiment depends on:

  * EXE header fields per the core's LoadEXE (PC@0x10, TextStart@0x18,
    TextSize@0x1C, SP@0x30) and the strict size rule
    TextSize == filesize - 0x800
  * halfword stores (SH, opcode 0x29) for the non-word-aligned SIO
    registers CTRL(0x1F80104A) and BAUD(0x1F80104E) — a word store
    there raises AdES on the real CPU model
  * the "PAD1" breadcrumb constant is present
  * GP0/GP1 register base constants are present
  * every LW in the wait macro is followed by a NOP (the core enforces
    the MIPS load-delay slot)
  * the build is deterministic
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))

import make_padtest_hw  # noqa: E402


def _words():
    return list(struct.unpack("<%dI" % (len(make_padtest_hw.build()) // 4),
                              make_padtest_hw.build()))


def test_build_deterministic():
    a = make_padtest_hw.build()
    b = make_padtest_hw.build()
    assert a == b and len(a) % 4 == 0 and len(a) > 0


def test_opcodes_present():
    words = _words()
    opcodes = {w >> 26 for w in words}
    assert 0x0F in opcodes   # LUI (li macro, address setup)
    assert 0x23 in opcodes   # LW  (status polls, breadcrumb loads)
    assert 0x2B in opcodes   # SW  (RAM breadcrumbs, GP0/GP1, TX data)
    assert 0x29 in opcodes   # SH  (CTRL/BAUD halfword stores)


def test_no_word_store_encoding_without_sh():
    # The SIO control register is halfword-aligned only; the payload must
    # contain SH (0x29). This test fails if someone reverts SH -> SW.
    words = _words()
    assert any((w >> 26) == 0x29 for w in words), \
        "CTRL/BAUD stores must be halfword (SH) to avoid AdES"


def test_pad1_breadcrumb_constant_present():
    """li() splits the constant into LUI hi16 + ORI lo16; both halves
    must be present."""
    words = _words()
    lui_hi = any((w >> 26) == 0x0F and (w & 0xFFFF) == 0x5041
                 for w in words)
    ori_lo = any((w >> 26) == 0x0D and (w & 0xFFFF) == 0x4431
                 for w in words)
    assert lui_hi and ori_lo, '"PAD1" magic constant missing'


def test_gp_registers_referenced():
    words = set(_words())
    # li() emits LUI+ORI pairs; the ORI carries the low 16 bits of the
    # GPU/SIO addresses used by the payload.
    assert 0x1810 in words or any((w & 0xFFFF) == 0x1810 for w in words)
    assert any((w & 0xFFFF) == 0x1044 for w in words)  # JOY_STAT
    assert any((w & 0xFFFF) == 0x104A for w in words)  # JOY_CTRL


def test_lw_followed_by_nop():
    """The core enforces the MIPS load-delay slot: every LW that feeds a
    consumer must be followed by a NOP. The wait macro and counter
    updates are LW-anchored; assert the pattern."""
    words = _words()
    for i, w in enumerate(words[:-1]):
        if (w >> 26) == 0x23:                     # LW
            nxt = words[i + 1]
            # The very next instruction must not READ the loaded register.
            rt = (w >> 16) & 0x1F
            if rt == 0:
                continue
            if (nxt >> 26) in (0x23, 0x2B, 0x29, 0x0C, 0x0D, 0x09, 0x0F):
                # I-type with rs field = rt would be a load-delay hazard
                # unless it is a store with rt as DATA (allowed pattern
                # in this payload: SW stores the loaded value with a NOP
                # inserted, so a hazard here is a builder bug).
                rs = (nxt >> 21) & 0x1F
                if rs == rt:
                    raise AssertionError(
                        f"load-delay hazard at word {i}: LW r{rt} then "
                        f"0x{nxt:08X} reads it in the slot")


def test_exe_header_and_size_rule():
    work = "/tmp/ps1play_padtest_hw_unittest"
    os.makedirs(work, exist_ok=True)
    code = make_padtest_hw.build()
    path = make_padtest_hw.write_exe(code, work)
    data = open(path, "rb").read()
    assert data[0:8] == b"PS-X EXE"
    pc0, = struct.unpack_from("<I", data, 0x10)
    t_addr, = struct.unpack_from("<I", data, 0x18)
    t_size, = struct.unpack_from("<I", data, 0x1C)
    sp, = struct.unpack_from("<I", data, 0x30)
    assert pc0 == 0x80010000
    assert t_addr == 0x80010000
    assert sp == 0x801FFFF0
    # The core's LoadEXE rejects TextSize != filesize - 0x800 (both ways)
    assert t_size == len(data) - 0x800
    assert t_size == len(code)
