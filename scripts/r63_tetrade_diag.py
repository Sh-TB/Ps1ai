#!/usr/bin/env python3
"""r63_tetrade_diag.py — why does the struct scan fail? Dump the stack
region around the R10 prior (isGameOver @0x1FF5A8) and test every
assumption individually."""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_r63_tetrade"
OV = {b"beetle_psx_override_bios": b"openbios"}

p = PS1Play(CUE, workspace=WS, var_overrides=OV)
p.boot()
p.core.run(900, set())
p.core.run(60, set())
p.core.run(120, {"START"})
p.core.run(240, set())
p.core.run(12, {"B"})
p.core.run(60, set())
p.core.run(4, {"START"})
p.core.run(280, set())
p.core.run(4, {"START"})
p.core.run(120, set())

ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
a4 = ram.view("<i4")
print("RAM bytes:", len(ram), "| ints:", len(a4))

# 1. the R10 prior: isGameOver observed at 0x1FF5A8 (2,094,504)
BASE_PRIOR = 0x1FF5A8 - 2312
print("prior base:", hex(BASE_PRIOR), BASE_PRIOR)
lo = BASE_PRIOR // 4
seg = a4[lo:lo + 600]
nz = np.flatnonzero(seg)
print("nonzero ints in prior struct window:", len(nz))
print("first 40 nonzero (rel_offset, value):",
      [(int(i) * 4, int(seg[i])) for i in nz[:40]])

# 2. check each secondary condition at the prior base
for off, name in [(800, "type"), (868, "x"), (872, "y"), (876, "wasHeld"),
                  (880, "rot"), (892, "nextTCount"), (896, "next0"),
                  (2184, "hold_type"), (2276, "score"), (2280, "single"),
                  (2284, "double"), (2288, "triple"), (2292, "tetrade"),
                  (2296, "moveCooldown"), (2300, "setTime"),
                  (2304, "level"), (2308, "ghostY"), (2312, "isGameOver"),
                  (2316, "isGamePaused")]:
    v = int(a4[(BASE_PRIOR + off) // 4])
    print(f"  +{off} {name} = {v}")

# 3. raw int histogram in the top 256KB (what value classes exist there)
top = a4[(2 * 1024 * 1024 - 262144) // 4:]
vals, counts = np.unique(top, return_counts=True)
small = [(int(v), int(c)) for v, c in zip(vals, counts) if 0 <= v <= 64]
print("top-256KB small-value histogram (v:count):", small[:30])

# 4. generic window scan diagnostics: how many windows pass each filter
from numpy.lib.stride_tricks import sliding_window_view  # noqa: E402
wins = sliding_window_view(a4, 200)
ok7 = ((wins >= 0) & (wins <= 7)).all(axis=1)
nz40 = ((wins > 0).sum(axis=1) <= 40)
c7 = np.flatnonzero(ok7 & nz40)
print("windows(all-in-0..7 & nz<=40):", len(c7),
      "| last 10 byte-offsets:", [int(c) * 4 for c in c7[-10:]])
p.core.shutdown()
