#!/usr/bin/env python3
"""flow_probe7.py — engine A + the EXACT run_frames codepath (gif, snaps).
If THIS reaches the menu but my manual loop doesn't, bisect run_frames."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")
from psx_headless import PSXHeadless

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/tmp/flow7"
os.makedirs(OUT, exist_ok=True)

fe = PSXHeadless("/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so",
                 "/home/z/my-project/ps1-test/emu/system",
                 "/home/z/my-project/ps1-test/emu/saves", verbose=False)
fe.load_game(GAME)

sched = []
for start in range(1000, 5300, 300):
    sched.append((start, start + 15, {3}))       # JP_START=3
sched.append((5150, 5165, {3}))
fe.run_frames(6000, button_schedule=sched, snapshot_frames=(3400, 4900),
              out_dir=OUT, gif_every=0)
print("snaps in", OUT)
