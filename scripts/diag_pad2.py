#!/usr/bin/env python3
"""diag_pad2.py — cross-check the mirror candidates with the FULL PSX bit
layout (each button must light exactly its own bit). Read-only."""
import sys
sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
p = PS1Play(GAME)
p.boot()
p.core.run(2200, set())
for _ in range(8):
    p.core.run(15, {"START"})
    p.core.run(285, set())
p.core.run(600, set())
p._advance()

# PSX digital pad, active-high mirror hypothesis:
# bit15=SQ(Y) bit14=X(B) bit13=O(A) bit12=TR(X) bit11=R1 bit10=L1
# bit9=R2 bit8=L2 bit7=LEFT bit6=DOWN bit5=RIGHT bit4=UP bit3=START
EXPECT = {"Y": 0x8000, "B": 0x4000, "A": 0x2000, "X": 0x1000,
          "LEFT": 0x0080, "DOWN": 0x0040, "RIGHT": 0x0020,
          "UP": 0x0010, "START": 0x0008}

CANDS = [0x0DA650, 0x0DA660, 0x0DA670, 0x0DA680, 0x0E2B4, 0x0CA2E2,
         0x0D9F94, 0x0DA004, 0x0DA260, 0x0DA2A0, 0x0D4948]
scores = {}
for A in CANDS:
    hits, rows = 0, []
    for b, exp in EXPECT.items():
        p.core.run(12, set())
        v0 = p.mem.u16(A)
        p.core.run(12, {b})
        v1 = p.mem.u16(A)
        p.core.run(12, set())
        p._advance()
        got = v1 & exp
        noise = v1 & ~exp & 0xFFFF
        if got == exp and noise == 0:
            hits += 1
        rows.append(f"{b}:{v1:04x}")
    scores[A] = hits
    print(f"{A:06X} hits={hits}/9  {' '.join(rows)}", flush=True)

best = sorted(scores.items(), key=lambda kv: -kv[1])
print("BEST:", [(hex(a), s) for a, s in best[:4]])
