#!/usr/bin/env python3
"""flow_probe2.py — dump the boot flow frame-by-frame (every 150f from
t=3900 to t=13500) with the EXACT Task-2 tap schedule, so we can SEE
where the menu/dialog/mission flow actually goes."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
import numpy as np
from PIL import Image
from ps1play.api import PS1Play

OUT = "/tmp/flow2"
os.makedirs(OUT, exist_ok=True)
p = PS1Play("/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue")
p.boot()


def snap(t):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/t{t:06d}.png")


p.core.run(1000, set())
p._advance()
for _t in range(1000, 5300, 300):
    p.core.run(15, {"START"})
    p.core.run(285, set())
    p._advance()

# now dump everything with zero input
for t in range(5300, 13500, 150):
    snap(t)
    p.core.run(150, set())
    p._advance()
print("done, frames dumped to", OUT)
