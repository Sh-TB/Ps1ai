#!/usr/bin/env python3
"""diag_pad.py — probe the GameShark pad-mirror word 0x0D4948 (read-only)
on any menu screen, then globally scan for the REAL mirror words.
No gameplay needed: the game polls the pad everywhere."""
import sys
sys.path.insert(0, "/home/z/my-project")
import numpy as np
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
p = PS1Play(GAME)
p.boot()
p.core.run(2200, set())
for _ in range(8):                    # push past logos into game menus
    p.core.run(15, {"START"})
    p.core.run(285, set())
p.core.run(600, set())
p._advance()

A = 0x0D4948
for off in (0, -2, 2, -4, 4):
    addr = A + off
    row = []
    for b in ("Y", "RIGHT", "B", "START"):
        p.core.run(15, set())
        v0 = p.mem.u16(addr)
        p.core.run(15, {b})
        v1 = p.mem.u16(addr)
        p.core.run(15, set())
        v2 = p.mem.u16(addr)
        p._advance()
        row.append(f"{b}:{v0:04x}->{v1:04x}->{v2:04x}")
    print(f"addr {addr:06X} ({hex(A+off)}):", "  ".join(row), flush=True)


def mscan(mask, buttons, reps=3):
    """words whose `mask` bits are SET while holding buttons, CLEAR idle."""
    surv = None
    for _ in range(reps):
        p.core.run(20, set())
        idle = p.mem.snapshot()
        p.core.run(20, buttons)
        act = p.mem.snapshot()
        p._advance()
        iv = idle[:0x1FC000].view("<u2")
        av = act[:0x1FC000].view("<u2")
        sel = set(int(i) * 2 for i in
                  np.flatnonzero(((av & mask) != 0) & ((iv & mask) == 0)))
        surv = sel if surv is None else (surv & sel)
    return sorted(surv or ())[:16]


print("Y(bit15) mirrors:  ", [hex(a) for a in mscan(0x8000, {"Y"})], flush=True)
print("RIGHT(bit5) mirrors:", [hex(a) for a in mscan(0x0020, {"RIGHT"})],
      flush=True)
