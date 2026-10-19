#!/usr/bin/env python3
"""flow_probe.py — ground-truth the attract cycle: what screen is WHEN,
and what happens after START x2 on the coin-up screen."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
import numpy as np
from PIL import Image
from ps1play.api import PS1Play

OUT = "/tmp/flow"
os.makedirs(OUT, exist_ok=True)
p = PS1Play("/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue")
p.boot()


def snap(tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/{tag}.png")


def stats():
    rgb = p.core.frame_rgb()
    if rgb is None:
        return None
    a = np.asarray(rgb, dtype=np.int32)
    band = a[222:240, 60:260]
    white = float(((band[:, :, 0] > 190) & (band[:, :, 1] > 190) &
                   (band[:, :, 2] > 190)).mean())
    dark = float((a.max(axis=2) < 60).mean())
    return white, dark


def churn(frames, btns):
    s0 = p.mem.snapshot()
    p.core.run(frames, btns)
    return int(np.count_nonzero(s0 != p.mem.snapshot()))


p.core.run(1000, set())
for _ in range(20):
    p.core.run(15, {"START"})
    p.core.run(285, set())
p._advance()
print("after boot taps t =", p.t, flush=True)

# free-run the attract cycle with periodic stats/snaps
for k in range(40):
    snap(f"f{k:02d}")
    w, d = stats()
    c = churn(30, set())
    p._advance()
    print(f"f{k:02d} t={p.t} white={w:.3f} dark={d:.2f} churn30={c}",
          flush=True)

# now deliberately: coin screen -> START x2 with WIDE gap, watch closely
print("--- injecting START x2 ---", flush=True)
p.core.run(15, {"START"})
p.core.run(90, set())
p.core.run(15, {"START"})
p._advance()
for k in range(16):
    snap(f"g{k:02d}")
    w, d = stats()
    c = churn(60, {"RIGHT", "Y"})
    p._advance()
    print(f"g{k:02d} t={p.t} white={w:.3f} dark={d:.2f} churn60(RY)={c}",
          flush=True)
