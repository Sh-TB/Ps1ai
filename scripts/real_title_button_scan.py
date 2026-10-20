#!/usr/bin/env python3
"""real_title_button_scan.py — find the button that starts a 1P game.

Empirical map so far:
  mode menu: CROSS selects ARCADE MISSION -> arcade replay (SNK, title)
  arcade title: START returns to the PS1 mode menu; idle -> attract demo
  attract demo renders REAL Mission-1 scenes (observed)

Hypothesis: the Agetec port maps "1P START" to another pad button.
Scan, one button per 320-frame window on the stable title:
  SELECT, L1, R1, L2, R2, B(circle), Y(square)
Watch for the difficulty-select screen (the pre-mission level picker).
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_title_btnscan"
os.makedirs(OUT, exist_ok=True)

END = 8000
SNAP_EVERY = 6

# menu CROSS at 2750; title stabilizes ~4200; scan windows of 320f
SCAN = [
    (4400, "SELECT"), (4720, "L1"), (5040, "R1"),
    (5360, "L2"), (5680, "R2"), (6000, "B"), (6320, "Y"),
]


def buttons_at(f):
    if 2750 <= f < 2774:
        return "A"
    for s, btn in SCAN:
        if s <= f < s + 18:
            return btn
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
            png = os.path.join(OUT, f"f{f:05d}.png")
            Image.fromarray(arr).save(png)
            d = small_diff(arr, prev)
            snaps.append({"frame": f, "png": os.path.basename(png),
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
        if r["end"] - r["start"] >= 24 or r["start"] >= 4300:
            print(f"  {r['start']:5d}-{r['end']:5d} "
                  f"mean={r['mean']:6.1f} {r['png']}")
    with open(os.path.join(OUT, "runs.json"), "w") as fh:
        json.dump({"snaps": snaps, "runs": runs, "scan": SCAN}, fh, indent=1)
    print("runs.json written")


if __name__ == "__main__":
    main()
