#!/usr/bin/env python3
"""poypoy_menuprobes.py — stepwise menu mapping for Poy Poy (USA).

Sends one candidate button per phase, captures the frame after each
step and the mean-abs frame diff, building the menu path toward a real
match. Rule-driven discovery, evidence-first: every step is journaled
with its screenshot so the plugin boot_script can be frozen from DATA.

One boot per process (H5). Evidence: emu/games_psx/evidence/poypoy_menu/
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu"
os.makedirs(EVID, exist_ok=True)
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu")
    p.boot()
    p.wait(420)
    for _ in range(40):
        snap = bytes(p.mem.snapshot())
        if snap.count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.wait(120)                       # title render
    steps = [
        ("title_settle", set(), 60),
        ("start_1", {"START"}, 90),
        ("settle_1", set(), 90),
        ("x_1", {"X"}, 60),
        ("settle_2", set(), 90),
        ("start_2", {"START"}, 60),
        ("settle_3", set(), 60),
        ("x_2", {"X"}, 60),
        ("settle_4", set(), 120),
        ("right_1", {"RIGHT"}, 30),
        ("x_3", {"X"}, 60),
        ("settle_5", set(), 120),
        ("right_2", {"RIGHT"}, 30),
        ("x_4", {"X"}, 60),
        ("settle_6", set(), 180),
        ("x_5", {"X"}, 60),
        ("settle_7", set(), 180),
        ("x_6", {"X"}, 60),
        ("settle_8", set(), 240),
    ]
    prev = p.core.frame_rgb()
    rows = []
    for i, (label, btns, frames) in enumerate(steps):
        p.core.run(frames, btns)
        img = p.core.frame_rgb()
        d = diff(prev, img)
        rows.append({"step": i, "label": label,
                     "btns": sorted(btns), "frames": frames,
                     "diff": d})
        if img is not None:
            Image.fromarray(img).save(f"{EVID}/s{i:02d}_{label}.png")
        prev = img
        print(f"{i:02d} {label:14s} diff={d}")
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
