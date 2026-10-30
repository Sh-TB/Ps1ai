#!/usr/bin/env python3
"""r55c_frames.py — dump selected recorded frames as PNGs for visual
inspection (occlusion tail, flap response, death moment)."""
import os
import sys

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r55")
PNG = os.path.join(OUT, "png")
os.makedirs(PNG, exist_ok=True)


def dump(k, picks_small, picks_full=None):
    z = np.load(os.path.join(OUT, f"life_k{k:03d}.npz"))
    fr = z["frames"]
    ful = z["fullres"]
    occl_idx = np.nonzero(z["occl"] == 1)[0]
    for i in picks_small:
        if i < len(fr):
            Image.fromarray(fr[i]).resize(
                (320, 240), Image.NEAREST).save(
                os.path.join(PNG, f"k{k:03d}_small_{i:04d}.png"))
    if picks_full and ful.ndim == 4 and len(ful):
        for j in picks_full:
            if j < len(ful):
                src_step = int(occl_idx[j]) if j < len(occl_idx) else -1
                Image.fromarray(ful[j]).save(os.path.join(
                    PNG, f"k{k:03d}_full_{j:03d}_step{src_step:04d}.png"))
    print("dumped to", PNG)


if __name__ == "__main__":
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    picks = [int(x) for x in (sys.argv[2].split(",")
                              if len(sys.argv) > 2 else
                              ["80", "150", "200", "250", "300", "400",
                               "500", "515", "525", "530", "536", "549"])]
    picks_f = ([int(x) for x in sys.argv[3].split(",")]
               if len(sys.argv) > 3 else None)
    dump(k, picks, picks_f)
