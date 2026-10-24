#!/usr/bin/env python3
"""nortis_play.py — Nortis (homebrew, no license) local play-test.

License status unchanged: BLOCKED for distribution (no license file);
played locally through the license-patched image per the established
manifest policy. This probe walks title -> menu -> gameplay with
screenshots and diffs. One boot per process (H5).
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/nortis_play"
os.makedirs(EVID, exist_ok=True)
CUE = "/home/z/my-project/emu/games_homebrew/patched/nortis_lic.cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_nortis_play2")
    p.boot()
    p.wait(420)
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.wait(120)
    steps = [("settle", set(), 60),
             ("start_1", {"START"}, 90), ("settle_1", set(), 150),
             ("x_1", {"X"}, 60), ("settle_2", set(), 150),
             ("x_2", {"X"}, 60), ("settle_3", set(), 180),
             ("start_2", {"START"}, 60), ("settle_4", set(), 180),
             ("right_1", {"RIGHT"}, 30), ("x_3", {"X"}, 60),
             ("settle_5", set(), 240),
             ("left_1", {"LEFT"}, 30), ("x_4", {"X"}, 60),
             ("settle_6", set(), 240),
             ("up_1", {"UP"}, 30), ("x_5", {"X"}, 60),
             ("settle_7", set(), 240),
             ("x_6", {"X"}, 60), ("settle_8", set(), 240)]
    prev = p.core.frame_rgb()
    rows = []
    for i, (label, btns, frames) in enumerate(steps):
        p.core.run(frames, btns)
        img = p.core.frame_rgb()
        d = diff(prev, img)
        rows.append({"step": i, "label": label, "btns": sorted(btns),
                     "frames": frames, "diff": d})
        if img is not None:
            Image.fromarray(img).save(f"{EVID}/n{i:02d}_{label}.png")
        prev = img
        print(f"{i:02d} {label:10s} diff={d}")
    out["steps"] = rows
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/play_probe.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
