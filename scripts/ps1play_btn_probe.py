#!/usr/bin/env python3
"""btn_probe.py — learn the REAL button mapping empirically.
Enter gameplay, then press each button alone and screenshot the result."""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/extracted/metal_slug_x/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v2/btn"
os.makedirs(OUT, exist_ok=True)

p = PS1Play(GAME)
print("boot:", p.boot()["core"])
r = p.enter_gameplay3()
print("enter:", r.get("in_game"), r.get("detector"))

def png(tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(f"{OUT}/{tag}.png")

png("0_idle")
p.core.run(20, {"Y"}); png("1_Y_square")       # fire?
p.core.run(30, set())
p.core.run(18, {"B"}); p.core.run(6, set()); png("2_B_cross")   # jump?
p.core.run(60, set())
p.core.run(14, {"A"}); p.core.run(10, set()); png("3_A_circle")  # grenade?
p.core.run(60, set())
p.core.run(14, {"X"}); p.core.run(10, set()); png("4_X_triangle")
p.core.run(60, set())
# grenade throw: hold direction-neutral, press A twice
p.core.run(10, {"A"}); p.core.run(20, set()); png("5_A_again")
p.core.run(40, set())
print("done")
