#!/usr/bin/env python3
"""nav_probe.py — empirically find which button confirms MSX menus.
Takes a small PNG after every probe step (development-time observation,
like a human reading the screen once; the learned sequence is then
persisted in the profile and replayed forever with ZERO tokens)."""
import sys, os, time
sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/extracted/metal_slug_x/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v2/nav"
os.makedirs(OUT, exist_ok=True)

p = PS1Play(GAME)
print("boot:", p.boot()["core"])

def png(tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        im = Image.fromarray(rgb)
        im.thumbnail((320, 240))
        im.save(f"{OUT}/{tag}.png")

def step(tag, frames, btns=None, wait=45):
    p.core.run(frames, btns or set())
    p.core.run(wait, set())
    p._advance()
    png(tag)
    print(f"[nav] {tag}")

# 1) fresh boot, then the coarse boot script (START taps -> main menu)
p.core.run(1200, set())
png("00_bios")
p.run_steps(p.plugin.boot_script())
png("01_after_bootscript")

# 2) close any popup: press START (reselect) then probe buttons on the
#    OK?/YES dialog one by one, screenshot after each
step("02_menu", 15, {"START"})
step("03_dlg_open", 15, {"B"})            # try cross first (PS1 'OK')
step("04_up", 12, {"UP"})
step("05_cross", 15, {"B"})
step("06_circle", 15, {"A"})
step("07_start", 15, {"START"})
step("08_down_cross", 15, {"DOWN"})
step("09_cross2", 15, {"B"})
step("10_run", 300, {"RIGHT", "Y"})
p.shutdown()
print("done")
