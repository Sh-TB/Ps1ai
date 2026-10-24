#!/usr/bin/env python3
"""poypoy_menu2.py — from MODE SELECT, find the confirm button.

Path so far (poypoy_menuprobes.py): title -> START -> (attract) START
-> MODE SELECT, cursor on EXHIBITION. X (60f hold) did not advance.
This probe taps X / START / O / X-again with settles, capturing each.
One boot per process (H5).
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
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def to_mode_select(p):
    p.wait(420)
    for _ in range(40):
        snap = bytes(p.mem.snapshot())
        if snap.count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.core.run(90, {"START"})
    p.core.run(90, set())
    p.core.run(60, {"START"})
    p.core.run(180, set())


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu2")
    p.boot()
    to_mode_select(p)
    prev = p.core.frame_rgb()
    rows = []
    taps = [("x_tap", {"X"}, 8), ("settle", set(), 120),
            ("start_tap", {"START"}, 8), ("settle2", set(), 120),
            ("o_tap", {"O"}, 8), ("settle3", set(), 120),
            ("x_tap2", {"X"}, 8), ("settle4", set(), 180),
            ("down_tap", {"DOWN"}, 10), ("settle5", set(), 60),
            ("up_tap", {"UP"}, 10), ("settle6", set(), 60),
            ("x_tap3", {"X"}, 8), ("settle7", set(), 180)]
    for i, (label, btns, frames) in enumerate(taps):
        p.core.run(frames, btns)
        img = p.core.frame_rgb()
        d = diff(prev, img)
        rows.append({"step": i, "label": label, "btns": sorted(btns),
                     "frames": frames, "diff": d})
        if img is not None:
            Image.fromarray(img).save(f"{EVID}/m2_{i:02d}_{label}.png")
        prev = img
        print(f"{i:02d} {label:12s} diff={d}")
    out["steps"] = rows
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/menu2_probe.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
