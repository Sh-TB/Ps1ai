#!/usr/bin/env python3
"""flow_probe4.py — test the INSERT-COIN hypothesis: on the coin-up
screen, SELECT should insert the credit, then START launches 1P."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play

OUT = "/tmp/flow4"
os.makedirs(OUT, exist_ok=True)
p = PS1Play("/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue")
p.boot()


def snap(tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/{tag}.png")


# reach the coin-up black screen (~t=4000 per probe3)
p.core.run(1000, set())
p._advance()
for _t in range(1000, 4000, 300):
    p.core.run(15, set())          # NO taps this time — stay idle!
    p.core.run(285, set())
    p._advance()
snap("00_arrive")                  # where are we? (expect PRESS START)

# 1) SELECT alone (insert coin?)
p.core.run(15, {"SELECT"})
p.core.run(90, set())
p._advance()
snap("01_after_select")

# 2) START after coin
p.core.run(15, {"START"})
p.core.run(120, set())
p._advance()
snap("02_after_start")

# 3) keep watching 1200f
for k in range(6):
    p.core.run(200, set())
    p._advance()
    snap(f"03_watch{k}")
print("done ->", OUT)
