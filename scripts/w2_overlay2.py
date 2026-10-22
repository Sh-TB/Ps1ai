#!/usr/bin/env python3
"""w2_overlay2.py — is the SECOND overlay (handler region
0x800B9F5C..0x800BC34C) resident at the lock? If yes, disassemble the
handlers with capstone and find the CAMERA write / unlock condition.

The encounter handlers were installed by the 8 FUN_800A87F8 callers
(ENEMY.BIN) as DATA words into ROOT+0 — their addresses lie past the
ENEMY.BIN end (0x800B8430) => a per-section overlay or a later block.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32  # noqa: E402

import msx_gate_probe as gp                     # noqa: E402

EVID = gp.EVID

HANDLERS = [0x800B9F5C, 0x800BAF1C, 0x800BADBC, 0x800BB9C8,
            0x800BBFEC, 0x800BC34C]
ZONE_LO, ZONE_HI = 0x800B7000, 0x800BD800


def main():
    p, fw = gp.boot()
    m = p.mem
    p.load_state("lock")
    session = gp.freeze_now(p, "w2_ov2")

    ram = m.ram
    lo, hi = ZONE_LO - 0x80000000, ZONE_HI - 0x80000000
    zone = ram[lo:hi]
    nz = int(np.count_nonzero(zone))
    gp.log(f"zone {hex(ZONE_LO)}..{hex(ZONE_HI)}: {nz}/{len(zone)} "
           f"nonzero bytes ({100.0 * nz / len(zone):.1f}%)")
    # nonzero clusters per 0x100
    clusters = {}
    for off in range(0, len(zone), 0x100):
        c = int(np.count_nonzero(zone[off:off + 0x100]))
        if c:
            clusters[hex(ZONE_LO + off)] = c
    gp.log(f"nonzero 0x100-clusters: {len(clusters)}")
    for k in list(clusters)[:24]:
        gp.log(f"   {k}: {clusters[k]}")

    # disassemble each handler head
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    out = {}
    for h in HANDLERS:
        off = h - 0x80000000
        code = bytes(ram[off:off + 120])
        ins = list(md.disasm(code, h))
        lines = [f"{i.address:#x}: {i.mnemonic} {i.op_str}" for i in ins[:30]]
        out[hex(h)] = lines
        gp.log(f"--- handler {hex(h)}")
        for l in lines[:20]:
            gp.log("   ", l)
    # also look for camera-word writes: any immediate 0xCA2E2/0x0CA2E2
    # inside the zone (as 16-bit half of an lui/addiu pair is hard to
    # grep; instead grep the raw 32-bit little-endian patterns)
    for pattern, name in ((b"\xe2\xa2\x0c\x80", "0x800CA2E2 le32"),
                          (b"\xe2\xa2\x0c", "0x0CA2E2 le24")):
        idx = zone.find(pattern)
        gp.log(f"pattern {name}: {'at ' + hex(ZONE_LO + idx) if idx >= 0 else 'not found'}")
    json.dump(out, open(os.path.join(EVID, "w2_overlay2.json"), "w"),
              indent=1)
    gp.unfreeze(session, "w2_ov2")
    gp.log("saved")


if __name__ == "__main__":
    main()
