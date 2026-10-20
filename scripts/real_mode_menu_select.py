#!/usr/bin/env python3
"""real_mode_menu_select.py — interact with the real mode-select menu.

Corrected flow map (all OBSERVED):
  BIOS cube -> title-loading -> Agetec "PRESS 1P OR 2P START" (f~2448)
  START on Agetec screen -> MODE MENU (blueprint, f~2460, mean~8)
  idle on Agetec screen -> arcade attract replay (NOT input)

This probe: START@2450 -> menu; then
  DOWN@2700  (cursor should move to COMBAT SCHOOL — interactivity proof)
  UP@2900    (cursor back to ARCADE MISSION)
  CROSS@3100 (select ARCADE MISSION -> difficulty select?)
observe to f5200, snapshot every 6 frames.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WORKSPACE = "/home/z/my-project/ps1-test/emu"
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_mode_menu_select"
os.makedirs(OUT, exist_ok=True)

END = 5200
SNAP_EVERY = 6

STEPS = [
    (2450, 2468, "START"),
    (2700, 2718, "DOWN"),
    (2900, 2918, "UP"),
    (3100, 3118, "A"),        # CROSS
]


def buttons_at(f):
    for s, e, b in STEPS:
        if s <= f < e:
            return b
    return ""


def small_diff(a, b):
    if a is None or b is None:
        return 999.0
    if a.shape != b.shape:
        b = np.asarray(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def main():
    p = PS1Play(GAME, core=CORE, workspace=WORKSPACE,
                var_overrides={b"beetle_psx_override_bios": b"openbios"},
                verbose=False)
    info = p.boot()
    print("boot:", json.dumps(info, default=str), flush=True)

    snaps = []
    prev = None
    for f in range(1, END + 1):
        p.core.set_buttons(buttons_at(f))
        p.core.run_frame()
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is None:
                continue
            arr = np.asarray(rgb)
            Image.fromarray(arr).save(os.path.join(OUT, f"f{f:05d}.png"))
            d = small_diff(arr, prev)
            snaps.append({"frame": f, "png": os.path.basename(png_path(f)),
                          "diff": round(d, 2) if d < 998 else None,
                          "mean": round(float(arr.mean()), 1)})
            prev = arr
    runs = []
    cur = None
    for s in snaps:
        same = cur is not None and s["diff"] is not None and s["diff"] < 1.5
        if same:
            cur["end"] = s["frame"]
        else:
            if cur:
                runs.append(cur)
            cur = {"start": s["frame"], "end": s["frame"],
                   "png": s["png"], "mean": s["mean"]}
    if cur:
        runs.append(cur)
    for r in runs:
        print(f"  {r['start']:5d}-{r['end']:5d} mean={r['mean']:6.1f} {r['png']}")
    with open(os.path.join(OUT, "runs.json"), "w") as fh:
        json.dump({"snaps": snaps, "runs": runs, "steps": STEPS}, fh, indent=1)


def png_path(f):
    return f"f{f:05d}.png"


if __name__ == "__main__":
    main()
