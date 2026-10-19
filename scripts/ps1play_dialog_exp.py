#!/usr/bin/env python3
"""dialog_exp.py — decisive experiment on the OK?/YES dialog.
Get to the menu right after boot (before demo timer), then try each
confirm button on the dialog with a screenshot after every step."""
import sys
sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/extracted/metal_slug_x/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v2/dlg"
import os
os.makedirs(OUT, exist_ok=True)

p = PS1Play(GAME)
p.boot()

def png(tag, thumb=True):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(f"{OUT}/{tag}.png")
        if thumb:
            im = Image.fromarray(rgb); im.thumbnail((320, 240))
            im.save(f"{OUT}/{tag}_s.png")

def step(tag, frames, btns, wait=60):
    p.core.run(frames, btns)
    p.core.run(wait, set())
    p._advance()
    png(tag)
    print(f"[dlg] {tag}")

# --- get to the MAIN MENU fast (START at title, before demo timer) ---
p.core.run(2400, set())            # BIOS + logos
p.core.run(15, {"START"})          # title -> menu (hopefully)
p.core.run(90, set())
p._advance()
png("10_menu")

# if a menu item is highlighted (ARCADE MISSION), select it with cross:
step("20_after_cross", 15, {"B"})
step("21_up", 10, {"UP"})
step("22_cross2", 15, {"B"})
step("23_circle", 15, {"A"})
step("24_start", 15, {"START"})
step("25_down", 10, {"DOWN"})
step("26_start2", 15, {"START"})
step("27_triangle", 15, {"X"})
step("28_wait", 1, None, wait=400)
print("done")
