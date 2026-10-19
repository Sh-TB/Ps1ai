#!/usr/bin/env python3
"""flow_probe3.py — dump frames DURING the tap phase too (t=3300..5300),
one snap right after each START tap settles, to catch menu/dialog."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play

OUT = "/tmp/flow3"
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
    if _t >= 3000:
        snap(_t + 300)          # frame right after this tap's settle

for t in range(5450, 9000, 150):
    snap(t)
    p.core.run(150, set())
    p._advance()
print("done ->", OUT)
