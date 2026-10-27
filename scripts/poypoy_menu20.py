#!/usr/bin/env python3
"""poypoy_menu20.py — passive boot timeline: find the REAL interactive mode-select.

Ground truth assembled from menu11/17/19 + PNGs:
  * the arena scene (characters + rocks + "Poy Poy" logo) is the ATTRACT
    DEMO — it starts BY ITSELF around f4500 (menu11 A: f4520 mean 182.1)
  * the state reached by the menu17 gate walk (anchor 6210, "candidate_menu")
    is input-disabled showcase/demo-adjacent, NOT the interactive menu
  * X-hold in the demo skips to title (m19 xhold_f120), any direction-hold
    also skips (left==right 3-byte mirror)
So the interactive mode select must exist EARLIER in the boot timeline.
This probe runs the boot with ZERO input, sampling a PNG + RAM hash every
150 frames to f5400 — mapping every auto screen and the exact demo start.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/tmp/my-project/emu/games_psx/evidence/poypoy_menu20"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu20"


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    samples = []
    f_end = 5400
    step = 150
    prev_hash = None
    boundaries = []
    for f in range(0, f_end + 1, step):
        # advance to exactly f from boot (monotonic frames_run)
        while p.core.frames_run < f:
            p.core.run(min(50, f - p.core.frames_run), set())
        img = p.core.frame_rgb()
        ram = p.mem.snapshot()
        h = hashlib.sha256(bytes(ram)).hexdigest()[:16]
        row = {"f": f, "ram": h}
        if img is not None:
            a = np.asarray(img)
            row["mean"] = round(float(a.mean()), 1)
            row["w"] = int(a.shape[1])
            name = f"m20_f{f:05d}.png"
            Image.fromarray(img).save(os.path.join(EVID, name))
        if h != prev_hash:
            boundaries.append(f)
        prev_hash = h
        samples.append(row)
    out["samples"] = samples
    out["ram_boundaries"] = boundaries
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu20.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("RAM boundaries at:", boundaries)
    print("sampled", len(samples), "frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
