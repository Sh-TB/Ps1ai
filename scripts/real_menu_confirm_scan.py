#!/usr/bin/env python3
"""real_menu_confirm_scan.py — find the mode-menu CONFIRM button.

Proven: menu cursor moves with UP/DOWN (pixel-verified). CROSS does
NOT confirm. Scan confirm candidates on ARCADE MISSION (default):
  1. START held 40f
  2. SELECT held 18f
  3. B (circle) held 18f
Watch for the difficulty-select screen after each.
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_menu_confirm"
os.makedirs(OUT, exist_ok=True)

END = 6200
SNAP_EVERY = 6

STEPS = [
    (2450, 2468, "START"),    # Agetec -> mode menu
    (2700, 2718, "SELECT"),   # arcade heritage: SELECT = insert coin
    (2900, 2918, "SELECT"),   # second coin (some games need 2)
    (3100, 3140, "START"),    # start on ARCADE MISSION
    (3600, 3618, "A"),        # fallback: CROSS after coins
    (4100, 4118, "B"),        # fallback: circle after coins
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
            snaps.append({"frame": f, "diff": round(d, 2) if d < 998 else None,
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
            cur = {"start": s["frame"], "end": s["frame"], "mean": s["mean"]}
    if cur:
        runs.append(cur)
    for r in runs:
        if r["end"] - r["start"] >= 24:
            print(f"  {r['start']:5d}-{r['end']:5d} mean={r['mean']:6.1f}")
    with open(os.path.join(OUT, "runs.json"), "w") as fh:
        json.dump({"snaps": snaps, "runs": runs}, fh, indent=1)


if __name__ == "__main__":
    main()
