#!/usr/bin/env python3
"""w2_cam_clamp.py — find the CAMERA CLAMP code in the LIVE EXE text.

1. dump live RAM 0x80010000..0x800A7800 (the text) once
2. capstone-scan for:
   - accesses with offset/imm 0xA2E0 after `lui rX, 0x0C80`
     (the camera u32 writers/readers)
   - immediates 0x3DC (988), 0x48C (1164), 0x3DD, 0x3E0 (the clamp
     limits in px)
   - the enclosing context disasm for each hit
"""
from __future__ import annotations

import json
import os
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402

EVID = gp.EVID
TEXT_LO, TEXT_HI = 0x80010000, 0x800A7800


def main():
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    text = bytes(m.ram[TEXT_LO - 0x80000000:TEXT_HI - 0x80000000].tobytes())
    gp.log(f"text dumped: {len(text)} bytes")

    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    hits_cam = []
    hits_lim = {0x3DC: [], 0x48C: [], 0x3DD: [], 0x3E0: []}
    lui_base = {}          # reg -> last lui imm (0x0C80 expected)
    n = len(text) // 4
    for i in range(n):
        off = i * 4
        w = int.from_bytes(text[off:off + 4], "little")
        op = w >> 26
        if op == 0x0F:      # LUI
            rt = (w >> 16) & 31
            lui_base[rt] = w & 0xFFFF
        if op in (0x23, 0x2B, 0x21, 0x29, 0x20, 0x28):   # lw sw lhu sh lb sb
            imm = w & 0xFFFF
            if imm >= 0x8000:
                imm -= 0x10000
            rs = (w >> 21) & 31
            base_imm = lui_base.get(rs)
            if base_imm == 0x0C80 and abs(imm) in (0xA2E0, 0xA2E1,
                                                   0xA2E2, 0xA2E3):
                hits_cam.append((off, op, imm))
            if op in (0x2B, 0x29, 0x28):    # stores only for limits
                if imm in hits_lim:
                    hits_lim[imm].append(off)
    gp.log(f"camera-word accesses: {len(hits_cam)}")
    for off, op, imm in hits_cam:
        opn = {0x23: "lw", 0x2B: "sw", 0x21: "lhu", 0x29: "sh",
               0x20: "lb", 0x28: "sb"}[op]
        gp.log(f"  {hex(TEXT_LO + off)} {opn} imm={hex(imm & 0xFFFF)}")
    for v, lst in hits_lim.items():
        gp.log(f"store-imm {hex(v)} ({v}): {len(lst)} sites "
               + str([hex(TEXT_LO + o) for o in lst[:6]]))

    # context disasm of the camera accesses
    out = {}
    for off, op, imm in hits_cam:
        start = max(0, off - 100)
        code = text[start:off + 40]
        ins = md.disasm(code, TEXT_LO + start)
        ctx = [f"{i.address:#x}: {i.mnemonic} {i.op_str}" for i in ins]
        out[hex(TEXT_LO + off)] = ctx
        gp.log(f"--- cam access {hex(TEXT_LO + off)}")
        for l in ctx[-14:]:
            gp.log("   ", l)
    json.dump(out, open(os.path.join(EVID, "w2_cam_clamp.json"), "w"),
              indent=1)
    gp.log("saved")


if __name__ == "__main__":
    main()
