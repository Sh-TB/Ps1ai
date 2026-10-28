#!/usr/bin/env python3
"""r34_buzzybee_gif.py — BuzzyBee r34 deep-systems evidence GIF
(repo-mirrored): gameplay -> idle death -> game-over screen
(bestScore rendered) -> auto-return to title."""
import glob
import os

from PIL import Image

GIFF = "/home/z/my-project/ps1ai/scratch/r34/gif_frames"
SHOTS = "/home/z/my-project/ps1ai/scratch/r34/shots"
GIF = ("/home/z/my-project/ps1ai/docs/evidence_gifs/"
       "r34_buzzybee_deep_systems.gif")

frames = []
# gameplay head: first 8 loop frames are still the live run-1 tail
loop = sorted(glob.glob(os.path.join(GIFF, "loop_*.png")))
assert loop, "no gif frames"
pick = [
    loop[0],        # gameplay tail just before death transition
    loop[6],        # death transition
    loop[10],       # game-over screen drawn (YOUR LAST ATTEMPT: 1000)
    loop[30],       # game-over screen hold (6.4s window)
    loop[55],       # still holding / about to return
    os.path.join(SHOTS, "returned_title_f02392.png"),  # auto-return title
]
for p in pick:
    assert os.path.exists(p), f"missing {p}"
    frames.append(Image.open(p).convert("RGB").quantize(colors=128))
os.makedirs(os.path.dirname(GIF), exist_ok=True)
frames[0].save(GIF, save_all=True, append_images=frames[1:],
               duration=[600, 300, 700, 700, 700, 900],
               loop=0, optimize=True)
print("GIF", GIF, "frames:", len(frames), "bytes:", os.path.getsize(GIF))
