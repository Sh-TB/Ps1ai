#!/usr/bin/env python3
"""flow_probe6.py — A/B the two frontends in separate processes.
--engine a = PSXHeadless (Task-2, works) | --engine b = LibretroCore (ps1play).
Identical tap schedule; snap at t=3400 and t=4900."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")
from PIL import Image

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/tmp/flow6"
os.makedirs(OUT, exist_ok=True)
engine = sys.argv[1] if len(sys.argv) > 1 else "a"

if engine == "a":
    from psx_headless import PSXHeadless
    fe = PSXHeadless("/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so",
                     "/home/z/my-project/ps1-test/emu/system",
                     "/home/z/my-project/ps1-test/emu/saves", verbose=False)
    fe.load_game(GAME)

    def run(n, btns):
        fe._buttons = set(btns)
        for _ in range(n):
            fe.lib.retro_run()
else:
    from ps1play.api import PS1Play
    p = PS1Play(GAME)
    p.boot()
    fe = p.core

    def run(n, btns):
        fe.run(n, btns)

def snap(tag):
    rgb = None
    if hasattr(fe, "frame_rgb"):
        rgb = fe.frame_rgb()
    elif hasattr(fe, "frame") and fe.frame is not None:
        rgb = fe.frame
    if rgb is None:
        return
    Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/{engine}_{tag}.png")

run(1000, set())
for _t in range(1000, 5300, 300):
    run(15, {"START"})
    run(285, set())
    if _t in (3000, 3300, 4600, 4900):
        snap(f"t{_t + 300}")
print("engine", engine, "done")
