#!/usr/bin/env python3
"""w2_overlay_cam.py — scan ENEMY.BIN (raw bytes, correct method) for:
  - ROOT-relative accesses at offset 0x840/0x841/0x842/0x843
    (the camera u32 @0xCA2E0 = ROOT(0x800C9AA0)+0x840)
  - any 16-bit store/load imm 0x3DC/0x48C (the clamp limits)
  - the enclosing context disasm
"""
from __future__ import annotations

import json
import os

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

DISC = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
LBA, RAW, DATA_OFF, SIZE = 2758, 2352, 24, 115400
BASE_VA = 0x8009C0E8
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_gate_probe"


def main():
    with open(DISC, "rb") as f:
        f.seek(LBA * RAW + DATA_OFF)
        data = f.read(SIZE)
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    hits = {0x840: [], 0x841: [], 0x842: [], 0x843: [],
            0x3DC: [], 0x48C: [], 0x3E8: [], 0x466: []}
    lui = {}
    for i in range(SIZE // 4):
        off = i * 4
        w = int.from_bytes(data[off:off + 4], "little")
        op = w >> 26
        if op == 0x0F:
            lui[(w >> 16) & 31] = w & 0xFFFF
        if op in (0x23, 0x2B, 0x21, 0x29, 0x20, 0x28):
            imm = w & 0xFFFF
            if imm >= 0x8000:
                imm -= 0x10000
            rs = (w >> 21) & 31
            if lui.get(rs) == 0x0C80 and abs(imm) in (0xA2E0, 0xA2E2,
                                                      0xA2E4):
                hits.setdefault("CAM_ABS", []).append((off, op, imm))
            if imm in hits and op in (0x2B, 0x29, 0x21, 0x23):
                hits[imm].append((off, op))
    for k, v in hits.items():
        print(f"{k}: {len(v) if isinstance(v, list) else v}"
              if k != "CAM_ABS" else f"CAM_ABS: {len(v)}")
        for off, op, *rest in (v if isinstance(v, list) else [])[:8]:
            opn = {0x23: "lw", 0x2B: "sw", 0x21: "lhu", 0x29: "sh",
                   0x20: "lb", 0x28: "sb"}.get(op, hex(op))
            print(f"   {hex(BASE_VA + off)} {opn}")

    # context for the camera hits
    out = {}
    for off, op, imm in hits.get("CAM_ABS", []):
        start = max(0, off - 120)
        ins = md.disasm(data[start:off + 48], BASE_VA + start)
        ctx = [f"{i.address:#x}: {i.mnemonic} {i.op_str}" for i in ins]
        out[hex(BASE_VA + off)] = ctx
        print(f"--- {hex(BASE_VA + off)}")
        for l in ctx[-12:]:
            print("   ", l)
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "w2_overlay_cam.json"), "w"),
              indent=1)


if __name__ == "__main__":
    main()
