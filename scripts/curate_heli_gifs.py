#!/usr/bin/env python3
"""curate_heli_gifs.py — build the curated heli-ladder GIF set for
docs/gif_evidence/heli_ladder/ (compact: leading frames only for the
long survivors)."""
from __future__ import annotations

import os
from PIL import Image

EVID = "/home/z/my-project/work/msx_recomp/evidence/heli_ladder/gif"
OUT = "/home/z/my-project/ps1ai/docs/gif_evidence/heli_ladder"
os.makedirs(OUT, exist_ok=True)

# pattern -> max frames to include (12f stride => 5 fps)
PLAN = {
    "01_stand_in_corridor": 150,     # full death arc
    "02_walk_right": 55,             # corridor crossing + clamp arrival
    "06_run_to_wall_hold": 60,       # walk + truck ram at the clamp
    "07_wall_upfire": 90,            # static up-fire + melee death
    "10_prone_in_corridor": 150,     # prone == stand (same blast)
}

for name, keep in PLAN.items():
    gdir = os.path.join(EVID, name)
    frames = sorted(os.listdir(gdir))[:keep]
    ims = [Image.open(os.path.join(gdir, f)).convert(
        "P", palette=Image.ADAPTIVE) for f in frames]
    # half resolution to keep bytes low
    ims = [im.resize((im.width // 2, im.height // 2),
                     Image.NEAREST) for im in ims]
    path = os.path.join(OUT, f"heli_{name}.gif")
    ims[0].save(path, save_all=True, append_images=ims[1:],
                duration=200, loop=0)
    print(name, len(ims), os.path.getsize(path) // 1024, "KB")
print("done ->", OUT)
