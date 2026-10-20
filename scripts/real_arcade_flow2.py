#!/usr/bin/env python3
"""real_arcade_flow2.py — single deterministic taps through the arcade
replay: menu CROSS -> SNK logo -> title -> ONE START tap -> observe.

Isolates exactly one input event on the arcade title (f4500) and traces
the response with 6-frame snapshots to f7000. Read-only RAM sampling.
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_arcade_flow2"
os.makedirs(OUT, exist_ok=True)

END = 7000
SNAP_EVERY = 6


def buttons_at(f):
    if 2750 <= f < 2774:
        return "A"          # ARCADE MISSION on mode menu
    if 4500 <= f < 4524:
        return "A"          # CROSS on the arcade title (confirm)
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
        print(f"  {r['start']:5d}-{r['end']:5d} mean={r['mean']:6.1f} {r['png']}")
    with open(os.path.join(OUT, "runs.json"), "w") as fh:
        json.dump({"snaps": snaps, "runs": runs}, fh, indent=1)
    print("runs.json written")


if __name__ == "__main__":
    main()
