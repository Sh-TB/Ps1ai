#!/usr/bin/env python3
"""r23_buzzybee_gif.py — BuzzyBee r23 evidence GIF (repo-mirrored)."""
import os

from PIL import Image

OUT = "/home/z/my-project/ps1ai/scratch/r23/buzzybee/shots_b4"
GIF = ("/home/z/my-project/ps1ai/docs/evidence_gifs/"
       "r23_buzzybee_gameplay_ntsc.gif")
PICK = [
    "b400_f00400.png",        # still black at f400 (shell/early boot)
    "b700_f00700.png",        # NTSC-forced build live: SCREEN_H=240
    "after_START_f00852.png", # gameplay scene rendered (vis_diff 122.4)
    "paused_f00914.png",      # SELECT pause (state 99)
    "after_flap_f01038.png",  # bee moved, world scrolled (score climbing)
]
frames = []
for rel in PICK:
    p = os.path.join(OUT, rel)
    assert os.path.exists(p), f"missing {p}"
    frames.append(Image.open(p).convert("RGB").quantize(colors=128))
os.makedirs(os.path.dirname(GIF), exist_ok=True)
frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=700,
               loop=0, optimize=True)
print("GIF", GIF, "frames:", len(frames), "bytes:", os.path.getsize(GIF))
