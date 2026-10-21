#!/usr/bin/env python3
"""disasm_range.py — capstone disassembly of VA ranges in SLUS_012.12
(or any PS-EXE / overlay loaded at a known VA).

Usage:
  python3 scripts/disasm_range.py 0x80032700 0x80032800 [--exe PATH]
  python3 scripts/disasm_range.py 0x8003273C 0x80032770 --ctx 8

PS-EXE mapping: runtime VA 0x80010000 -> file offset 0x800 (header).
"""
import argparse
import struct
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

DEFAULT_EXE = "/home/z/my-project/ps1ai/ps1play/re/SLUS_012.12"
EXE_VA = 0x80010000
EXE_OFF = 0x800


def load(path):
    with open(path, "rb") as f:
        return f.read()


def va_to_off(va, exe):
    """Map runtime VA -> file offset using the PS-EXE header (t_addr)."""
    # read t_addr/t_size from header: offset 0x18 = t_addr (0x800...), 0x1C t_size
    t_addr = struct.unpack_from("<I", exe, 0x18)[0]
    t_size = struct.unpack_from("<I", exe, 0x1C)[0]
    off = va - t_addr + EXE_OFF
    if 0 <= off < len(exe):
        return off
    raise ValueError(f"VA {va:#010x} out of EXE range (t_addr={t_addr:#010x} size={t_size:#x})")


def disasm(exe, lo, hi, overlay_va=None, overlay_path=None):
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    if overlay_path:
        blob = load(overlay_path)
        base = overlay_va
        def rd(a, n):
            o = a - base
            return blob[o:o + n]
    else:
        blob = exe
        def rd(a, n):
            o = va_to_off(a, exe)
            return exe[o:o + n]
    code = rd(lo, hi - lo)
    out = []
    for ins in md.disasm(code, lo):
        raw = int.from_bytes(ins.bytes, "little")
        note = ""
        if raw == 0:
            note = "NOP"
        elif (raw >> 16) == 0x2400:
            note = "PUBLISHED-PATCH TARGET (half=0x2400 => addiu $0)"
        out.append(f"{ins.address:#010x}  {ins.bytes.hex()}  {ins.mnemonic:<8} {ins.op_str}{('  ; ' + note) if note else ''}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lo", type=lambda x: int(x, 0))
    ap.add_argument("hi", type=lambda x: int(x, 0))
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--overlay", default=None)
    ap.add_argument("--overlay-va", type=lambda x: int(x, 0), default=0x8009C0E8)
    a = ap.parse_args()
    exe = None if a.overlay else load(a.exe)
    print(disasm(exe, a.lo, a.hi, a.overlay_va, a.overlay))


if __name__ == "__main__":
    main()
