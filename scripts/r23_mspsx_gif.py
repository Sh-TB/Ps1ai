#!/usr/bin/env python3
"""r23_mspsx_gif.py — assemble the MSPSX r23 evidence GIF (repo-mirrored)."""
import glob
import os

from PIL import Image

OUT = "/home/z/my-project/ps1ai/scratch/r23/mspsx"
GIF = "/home/z/my-project/ps1ai/docs/evidence_gifs/r23_mspsx_reveal_running.gif"

# ordered narrative: title -> title_stable -> game -> cursor anchors -> reveal
PICK = [
    "shots/title_f00542.png", "shots/title_stable_f00602.png",
    "shots/p_start_15_f00619.png", "shots/game_f00665.png",
    "shots/p_right_10_f00707.png", "shots/p_down_10_f00739.png",
    "shots/pre_reveal_f00759.png", "shots/p_b_10_f00809.png",
    "shots/p_b_30_f00829.png", "shots/p_b_55_f00854.png",
    "shots/p_b_80_f00879.png", "shots/post_reveal_f00889.png",
]
frames = []
for rel in PICK:
    p = os.path.join(OUT, rel)
    assert os.path.exists(p), f"missing {p}"
    frames.append(Image.open(p).convert("P").quantize(colors=128))
os.makedirs(os.path.dirname(GIF), exist_ok=True)
frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=450,
               loop=0, optimize=True)
n_all = len(glob.glob(os.path.join(OUT, "shots", "*.png")))
print("GIF", GIF, "frames:", len(frames), "of", n_all, "shots",
      "bytes:", os.path.getsize(GIF))
