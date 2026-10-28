#!/usr/bin/env python3
"""r36_gifs.py — evidence GIFs for the two NEW R36 games (mirrored in repo).

LostPlumber: the RIGHT-scroll causality chain (idle -> RIGHT hold -> new
terrain) from boot2 shots. VoXide: title render chain from boot1 shots.
No game bytes — PNG-derived frames only (same policy as r23 gif scripts).
"""
import glob
import os

from PIL import Image

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "docs", "evidence_gifs")
os.makedirs(OUT, exist_ok=True)


def make(png_dir, order, dst, scale=2, fps=8):
    frames = []
    for tag in order:
        hits = sorted(glob.glob(os.path.join(png_dir, f"{tag}_*.png")))
        if not hits:
            print(f"  miss: {tag}")
            continue
        im = Image.open(hits[-1]).convert("P", palette=Image.ADAPTIVE)
        im = im.resize((im.width // scale, im.height // scale))
        frames.append(im)
    if not frames:
        print(f"  no frames for {dst}")
        return
    frames[0].save(dst, save_all=True, append_images=frames[1:],
                   duration=int(1000 / fps), loop=0)
    print(f"wrote {dst}: {len(frames)} frames")


# LostPlumber: world scroll under RIGHT (boot2: idle -> right -> idle2')
make(os.path.join(REPO, "scratch/r36/lostplumber/shots2"),
     ["idle0", "idle1", "pre_right", "post_right"],
     os.path.join(OUT, "r36_lostplumber_scroll.gif"), scale=2)

# VoXide: title render + menu (boot1)
make(os.path.join(REPO, "scratch/r36/voxide/shots"),
     ["b600", "b1200", "idle2", "post_START"],
     os.path.join(OUT, "r36_voxide_title.gif"), scale=2)
