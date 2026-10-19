#!/usr/bin/env python3
"""flow_probe8.py — reach the OK?/YES dialog, then test candidate
confirm buttons one at a time, snapping after each."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play

OUT = "/tmp/flow8"
os.makedirs(OUT, exist_ok=True)
p = PS1Play("/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue")
p.boot()


def snap(tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/{tag}.png")


# boot taps (int-converted now) -> menu -> B selects ARCADE MISSION
p.core.run(1000, set())
p._advance()
for _t in range(1000, 5300, 300):
    p.core.run(15, {"START"})
    p.core.run(285, set())
    p._advance()
snap("00_after_taps")
p.core.run(15, {"B"})          # select highlighted menu item
p.core.run(600, set())
p._advance()
snap("01_after_B")

# candidate confirms, in order
for i, (name, seq) in enumerate([
        ("A", [("A", 15)]),
        ("B", [("B", 15)]),
        ("START", [("START", 15)]),
        ("UP_A", [("UP", 10), ("A", 15)]),
        ("DOWN_A", [("DOWN", 10), ("A", 15)]),
        ("Y", [("Y", 15)]),
        ("X", [("X", 15)]),
]):
    for b, f in seq:
        p.core.run(f, {b})
    p.core.run(150, set())
    p._advance()
    snap(f"02_{i}_{name}")
print("done ->", OUT)
