#!/usr/bin/env python3
"""Query the round-8 diff tracks at the known global addresses (and a
window around SECTION_*) — read-only, tells the per-window story."""
import os
import sys

import numpy as np

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round8_msx"
TRACKS = {
    "A": os.path.join(SCRATCH, "diff2_074813_trkA.npz"),
    "B": os.path.join(SCRATCH, "diff2_074813_trkB.npz"),
    "C": os.path.join(SCRATCH, "diff2_074813_trkC.npz"),
    "D": os.path.join(SCRATCH, "diff2_074813_trkD.npz"),
    "E": os.path.join(SCRATCH, "diff3_075410_trkE.npz"),
}
ADDRS = {
    "PLAYER_X": 0x0CA2E0, "PLAYER_HP": 0x0CA2F6,
    "GRENADES": 0x0EDCF4, "SECTION_STATE": 0x0EB5F4,
    "SECTION_FLAGS": 0x0EB5F6, "SECTION_PROGRESS": 0x0EB5D4,
    "A_SCORE": 0x0EE318, "FLAGS_WORD": 0x0EE518,
}
LO, HI = 0x0EB5D0, 0x0EB610   # window around the section globals

T = {}
for k, p in TRACKS.items():
    z = np.load(p)
    T[k] = {n: z[n] for n in ("val0", "first_f", "last_f", "count", "final")}


def u16(t, off):
    return (int(t["val0"][off]) | (int(t["val0"][off + 1]) << 8),
            int(t["final"][off]) | (int(t["final"][off + 1]) << 8))


for name, a in ADDRS.items():
    print(f"== {name} @0x{a:06X}")
    for k in "ABCDE":
        t = T[k]
        ch = int(t["count"][a]) > 0 or int(t["count"][a + 1]) > 0
        v0, f1 = u16(t, a)
        ff = min(int(t["first_f"][a]), int(t["first_f"][a + 1]))
        ll = max(int(t["last_f"][a]), int(t["last_f"][a + 1]))
        print(f"  {k}: changed={ch} u16 {v0}->{f1} first_f={ff} last_f={ll}")

print(f"== section window 0x{LO:06X}..0x{HI:06X} (u16 slots that changed)")
for off in range(LO, HI, 2):
    row = []
    for k in "ABCDE":
        t = T[k]
        ch = int(t["count"][off]) > 0 or int(t["count"][off + 1]) > 0
        if ch:
            v0, f1 = u16(t, off)
            row.append(f"{k}:{v0:#x}->{f1:#x}(f{min(int(t['first_f'][off]), int(t['first_f'][off+1]))})")
    if row:
        print(f"  0x{off:06X}: {'; '.join(row)}")
