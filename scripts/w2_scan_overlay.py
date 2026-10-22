#!/usr/bin/env python3
"""w2_scan_overlay.py — targeted static scan of ENEMY.BIN (extracted
from the local disc at LBA 2758) for the writers of slot0+0x7A
(0x800CA2E2, the progress/stage word) and the base materialization
0x800CA268.

Searches (capstone disasm over the whole mapped image):
  1. `lui rX, 0x0C80` followed within 4 insns by `addiu rX, rX, 0xA268`
     (little-endian op halves 0x0C80 / 0xA268) -> base builder
  2. stores with offset 0x7A: `sh rY, 0x7a(rZ)` / `sb` / `sw`
  3. the enclosing function per hit (via the 468-function table)
"""
from __future__ import annotations

import json
import os
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
DISC = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
LBA = 2758                 # ENEMY.BIN (from overlay_index.json)
RAW_SECTOR = 2352
DATA_OFF = 24              # MODE2/2352: 24-byte sync/header+subhead?

OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_gate_probe"


def extract_overlay():
    size = 115400
    with open(DISC, "rb") as f:
        f.seek(LBA * RAW_SECTOR + DATA_OFF)
        data = f.read(size)
    return data


def main():
    data = extract_overlay()
    print(f"ENEMY.BIN: {len(data)} bytes, "
          f"nonzero {sum(1 for b in data if b) / len(data):.1%}")
    base_va = 0x8009C0E8
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.detail = False

    # linear disassembly (4-byte aligned words across the image)
    hits_base = []       # materializations of 0x800CA268
    hits_store7a = []    # stores at offset 0x7A
    lui_reg = {}
    count = 0
    for off in range(0, len(data) - 4, 4):
        # cheap prefilter on the little-endian word
        w = data[off] | (data[off + 1] << 8) | (data[off + 2] << 16) | \
            (data[off + 3] << 24)
        op = w >> 26
        # LUI: op 0x0F, rt field = (w >> 16) & 31, imm = w & 0xFFFF
        if op == 0x0F and (w & 0xFFFF) == 0x0C80:
            lui_reg[(off, (w >> 16) & 31)] = off
        # ADDIU: op 0x09, imm 0xA268
        if op == 0x09 and (w & 0xFFFF) == 0xA268:
            rs = (w >> 21) & 31
            rt = (w >> 16) & 31
            if rs == rt:     # addiu rX, rX, imm
                for (lo, reg), o in list(lui_reg.items()):
                    if reg == rt and 0 < off - o <= 32:
                        hits_base.append((o, off))
                        break
        # stores: SB op 0x28, SH op 0x29, SW op 0x2B
        if op in (0x28, 0x29, 0x2B):
            imm = w & 0xFFFF
            if imm == 0x7A:
                hits_store7a.append((off, op, (w >> 16) & 31,
                                     (w >> 21) & 31))
        count += 1
    print(f"scanned {count} words")
    print(f"base builders (lui 0x0C80 + addiu 0xA268): {len(hits_base)}")
    for lo, hi in hits_base:
        print(f"   lui@{hex(base_va + lo)} addiu@{hex(base_va + hi)}")
    print(f"stores @ +0x7A: {len(hits_store7a)}")
    for off, op, rt, rs in hits_store7a:
        print(f"   {hex(base_va + off)} op={'sb' if op == 0x28 else 'sh' if op == 0x29 else 'sw'} rt=r{rt} base=r{rs}")

    # disassemble around each store hit for context
    out = {"base_builders": [[hex(base_va + a), hex(base_va + b)]
                             for a, b in hits_base],
           "store7a": []}
    md2 = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    for off, op, rt, rs in hits_store7a:
        start = max(0, off - 80)
        code = data[start:off + 8]
        ins = list(md2.disasm(code, base_va + start))
        ctx = [f"{i.address:#x}: {i.mnemonic} {i.op_str}" for i in ins]
        out["store7a"].append({"va": hex(base_va + off), "ctx": ctx})
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "w2_scan_overlay.json"), "w"),
              indent=1)
    print("saved w2_scan_overlay.json")


if __name__ == "__main__":
    main()
