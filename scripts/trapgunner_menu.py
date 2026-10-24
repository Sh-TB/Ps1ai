#!/usr/bin/env python3
"""trapgunner_menu.py — boot + menu walk for Trap Gunner (USA).

Session-4 baseline: boots, START switches a 512-wide mode (diff 56.6).
This probe walks START/X with per-step screenshots to map how far a
rule-driven walk gets toward gameplay. One boot per process (H5).
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

EVID = "/home/z/my-project/emu/games_psx/evidence/trapgunner_menu"
os.makedirs(EVID, exist_ok=True)
CUE = "/home/z/my-project/emu/games_psx/trap_gunner/Trap Gunner (USA).cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_tg_menu")
    p.boot()
    p.wait(420)
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.wait(120)
    steps = [("settle", set(), 60),
             ("start_1", {"START"}, 90), ("settle_1", set(), 150),
             ("start_2", {"START"}, 60), ("settle_2", set(), 150),
             ("x_1", {"X"}, 60), ("settle_3", set(), 150),
             ("x_2", {"X"}, 60), ("settle_4", set(), 150),
             ("start_3", {"START"}, 60), ("settle_5", set(), 240),
             ("x_3", {"X"}, 60), ("settle_6", set(), 240),
             ("start_4", {"START"}, 60), ("settle_7", set(), 300)]
    prev = p.core.frame_rgb()
    rows = []
    for i, (label, btns, frames) in enumerate(steps):
        p.core.run(frames, btns)
        img = p.core.frame_rgb()
        d = diff(prev, img)
        rows.append({"step": i, "label": label, "btns": sorted(btns),
                     "frames": frames, "diff": d})
        if img is not None:
            Image.fromarray(img).save(f"{EVID}/t{i:02d}_{label}.png")
        prev = img
        print(f"{i:02d} {label:10s} diff={d}")
    out["steps"] = rows
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/menu_probe.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
