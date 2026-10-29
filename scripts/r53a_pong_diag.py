#!/usr/bin/env python3
"""r53a_pong_diag.py — live diagnosis: is the ball visible? does the AI
move? what do the score words read? Dump candidates from 1-frame delta
hunts (the r14 idiom) instead of equality matching."""
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import PongEnv                # noqa: E402
from ps1play.learn.perception import (pong_ball_centroid,  # noqa: E402
                                      pong_paddle_rows)
from hellopong_r12_lib import make_jrn, save_png       # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")

env = PongEnv()
jr = make_jrn(OUT, "[pongdiag]")
env.p.core.set_port_device(0, port=1)
env.settle()
print("settled", flush=True)

for i in range(6):
    env.run(30, set())
    fr = env.frame()
    cx, cy, n = pong_ball_centroid(fr)
    lp, rp = pong_paddle_rows(fr)
    save_png(OUT, fr, f"diag_{i}.png")
    print(f"sample {i}: ball=({cx},{cy},{n}) paddles=({lp},{rp})",
          flush=True)

# 1-frame delta hunt (r14 idiom)
_, s0 = None, env.p.core.ram.copy()
env.run(1, set())
s1 = env.p.core.ram.copy()
a = s0.view("<i2").astype(int)
b = s1.view("<i2").astype(int)
d = b - a
ball_cands = np.nonzero((np.abs(d) <= 4) & (np.abs(d) > 0)
                        & (b >= 0) & (b < 340))[0]
print("1f delta cands:", len(ball_cands), flush=True)

# track candidates over 20 more 1-frame steps, keep consistent movers
live = set(ball_cands.tolist())
for _ in range(20):
    env.run(1, set())
    s2 = env.p.core.ram.copy()
    c = s2.view("<i2").astype(int)
    d2 = c - b
    keep = set()
    for off in live:
        if 0 < abs(d2[off]) <= 4:
            keep.add(off)
    live = keep
    b = c
print("after 20 tracks:", len(live), flush=True)
vals = [(hex(o * 2), int(b[o])) for o in sorted(live)][:40]
print("candidates (addr, val):", vals, flush=True)

fr = env.frame()
cx, cy, n = pong_ball_centroid(fr)
print("final vision ball:", cx, cy, n, flush=True)
score_base = 0x1FFEB4 // 2
ram = env.p.core.ram
print("score words:",
      [int(np.frombuffer(ram[0x1FFEB4 + 4 * k:0x1FFEB4 + 4 * k + 4]
                         .tobytes(), "<i4")[0]) for k in range(3)],
      flush=True)
save_png(OUT, fr, "diag_final.png")
env.close()
