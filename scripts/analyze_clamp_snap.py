#!/usr/bin/env python3
"""analyze_clamp_snap.py — post-hoc filters over the saved clampdiff
full-RAM snapshots: exact/near-992 limit constants (u32/u16) + the
0xEB598 scroll word neighbours."""
import sys

import numpy as np

D = "/home/z/my-project/work/msx_recomp/evidence/clamp_globals/clampdiff1"
A = np.load(f"{D}/snapA.npy")
B = np.load(f"{D}/snapB.npy")
a32 = A.view("<u4")
b32 = B.view("<u4")

m = (a32 == b32) & (a32 == 0x03E00000)
print("exact 992.0 u32 unchanged:",
      [hex(int(i) * 4) for i in np.where(m)[0].tolist()])

px = (a32.astype(np.uint32) >> 16).astype(np.int64)
frac = (a32 & 0xFFFF) / 65536.0
m2 = (a32 == b32) & (px >= 985) & (px <= 996) & (frac < 0.1)
hits = [(hex(int(i) * 4), int(a32[i]), round(float(px[i] + frac[i]), 3))
        for i in np.where(m2)[0].tolist()]
print("near-992 u32 unchanged:", hits)

a16 = A.view("<u2")
b16 = B.view("<u2")
m3 = (a16 == b16) & (a16 == 992)
print("u16 992 unchanged total:", int(m3.sum()),
      [hex(int(i) * 2) for i in np.where(m3)[0].tolist()[:24]])
m4 = (a16 == b16) & (a16 == 62)
print("u16 62 unchanged total:", int(m4.sum()))

# scroll word neighbours: dump +-0x40 bytes around 0xEB598
S = 0xEB598
print("\nscroll word neighbourhood (u32, A -> B):")
for off in range(S - 0x40, S + 0x44, 4):
    va, vb = int(a32[off // 4]), int(b32[off // 4])
    mark = " <-- SCROLL" if off == S else ""
    print(f"  0x{off:X}: {va:#010x} -> {vb:#010x}{mark}")

# trajectory of the scroll word from the per-row window dump is not
# available (outside window) — print A/B px at least
print("\nscroll px A:", int(a32[S // 4]) / 65536.0,
      "B:", int(b32[S // 4]) / 65536.0)
