#!/usr/bin/env python3
"""poypoy_menu3.py — brute-force the MODE SELECT confirm button.

Every pad button gets one 30f hold + 120f settle from MODE SELECT
(cursor on EXHIBITION); diff + screenshot per step. One boot (H5).
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


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu3")
    p.boot()
    p.wait(420)
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.core.run(90, {"START"})
    p.core.run(90, set())
    p.core.run(60, {"START"})
    p.core.run(120, set())
    prev = p.core.frame_rgb()
    rows = []
    for btn in ("TR", "SELECT", "L1", "R1", "L2", "R2", "SQ",
                "O", "X"):
        p.core.run(30, {btn})
        p.core.run(40, set())
        img = p.core.frame_rgb()
        d = diff(prev, img)
        rows.append({"btn": btn, "diff": d})
        if img is not None:
            Image.fromarray(img).save(f"{EVID}/m3_{btn}.png")
        prev = img
        print(f"{btn:7s} diff={d}")
        if d and d > 40:                     # screen changed -> stop
            out["confirm_found"] = btn
            break
    out["steps"] = rows
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/menu3_probe.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
