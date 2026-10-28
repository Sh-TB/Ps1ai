#!/usr/bin/env python3
"""r35a_gif.py — assemble the R35-A wall-assault evidence GIF from the
attempt PNGs (honest frames: checkpoint, chopper candidates, wall,
death). Mirrored to docs/evidence_gifs/r35_msx_wall_assault.gif."""
import glob
import os

from PIL import Image

REPO = "/home/z/my-project/ps1ai"
P = os.path.join(REPO, "scratch", "r35a", "png")

PICKS = [
    "r35a_checkpoint.png",
    "r35a_atk1_choppercand_f11.png",
    "r35a_atk1_choppercand_f46.png",
    "r35a_atk1_choppercand_f143.png",
    "r35a_atk1_px1000_f126.png",
    "r35a_atk1_px1050_f158.png",
    "r35a_atk1_PAST_CLAMP_f234.png",
    "r35a_atk1_death_f603_20.png",
    "r35a_atk1_death_f603_40.png",
    "r35a_atk1_end_f603.png",
]
frames = []
for name in PICKS:
    path = os.path.join(P, name)
    if not os.path.exists(path):
        alt = sorted(glob.glob(os.path.join(P, name.split("_f")[0] + "*.png")))
        if not alt:
            continue
        path = alt[0]
    im = Image.open(path).convert("P", palette=Image.ADAPTIVE)
    im = im.resize((im.width // 2, im.height // 2))
    frames.append((name, im))

out = os.path.join(REPO, "scratch", "r35a", "r35_msx_wall_assault.gif")
frames[0][1].save(out, save_all=True, append_images=[f[1] for f in frames[1:]],
                  duration=900, loop=0)
print("GIF:", out, len(frames), "frames,", os.path.getsize(out), "bytes")
print("frames:", [f[0] for f in frames])

dst = os.path.join(REPO, "docs", "evidence_gifs", "r35_msx_wall_assault.gif")
frames[0][1].save(dst, save_all=True,
                  append_images=[f[1] for f in frames[1:]],
                  duration=900, loop=0)
print("mirrored:", dst, os.path.getsize(dst), "bytes")
