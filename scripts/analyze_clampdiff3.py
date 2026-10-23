#!/usr/bin/env python3
"""analyze_clampdiff3.py — offline re-analysis of the clampdiff3
snapshots: full pin-flip list (wider address range incl. the ENEMY.BIN
overlay 0x9C0E8-0xA9268), freezer list, and limit-constant candidates
in multiple encodings (u32 16.16, u16 px, u16 tile)."""
import numpy as np

D = "/home/z/my-project/work/msx_recomp/evidence/clamp_globals/clampdiff3"
A = np.load(f"{D}/snapA.npy")
B = np.load(f"{D}/snapB.npy")
C = np.load(f"{D}/snapC.npy")
a32, b32, c32 = (x.view("<u4") for x in (A, B, C))
a16, b16, c16 = (x.view("<u2") for x in (A, B, C))

dAB = a32 != b32
dBC = b32 != c32

def lo(i):
    return int(i * 4)

flip = np.where(~dAB & dBC)[0]
print(f"FLIP_AT_PIN total {len(flip)}; by region:")
regions = [("overlay 0x9C0E8-0xA9268", 0x9C0E8, 0xA9268),
           ("data 0xA9268-0xF0000", 0xA9268, 0xF0000),
           ("data 0xF0000-0x140000", 0xF0000, 0x140000),
           ("heap/other 0x140000-0x1F0000", 0x140000, 0x1F0000),
           ("low/kernel <0x9C0E8", 0, 0x9C0E8)]
for name, lo_a, hi_a in regions:
    sel = [int(i) for i in flip if lo_a <= i * 4 < hi_a]
    print(f"  {name}: {len(sel)}")
    for i in sel[:14]:
        print(f"    0x{i*4:X}: B={int(b32[i]):#010x} "
              f"C={int(c32[i]):#010x}")

freezer = np.where(dAB & ~dBC)[0]
sel = [int(i) for i in freezer if 0x9C0E8 <= i * 4 < 0xF0000]
print(f"\nFREEZE_AT_PIN in overlay+data: {len(sel)}")
for i in sel[:24]:
    print(f"    0x{i*4:X}: A={int(a32[i]):#010x} "
          f"B={int(b32[i]):#010x}")

# limit constants near the pin value
for val, label in [(0x048BFFFF, "0x048BFFFF (1163.99998)"),
                   (0x048C0000, "0x048C0000 (1164.0)"),
                   (0x048B0000, "0x048B0000 (1163.0)")]:
    m = (a32 == b32) & (b32 == c32) & (a32 == val)
    hits = [int(i) for i in np.where(m)[0]]
    print(f"\nconst {label}: {len(hits)} ->",
          [f"{i*4:X}" for i in hits][:20])

# u16 forms
for val in (1163, 1164, 72, 73, 74):
    m = (a16 == b16) & (b16 == c16) & (a16 == val)
    hits = [int(i) * 2 for i in np.where(m)[0]
            if 0x80000 <= i * 2 < 0x1F0000]
    if hits:
        print(f"u16 {val}: {len(hits)} -> {[f'{h:X}' for h in hits[:16]]}")
