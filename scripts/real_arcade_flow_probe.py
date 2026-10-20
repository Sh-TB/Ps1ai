#!/usr/bin/env python3
"""real_arcade_flow_probe.py — full flow: mode menu -> ARCADE MISSION ->
title START -> difficulty select -> mission 1.

Observed flow so far (all OBSERVED evidence):
  BIOS cube -> title-loading (f~1230) -> mode-select menu (f~2340)
  CROSS on menu (f2750) -> SNK logo (f~3006) -> title
  "PRESS 1P OR 2P START" (f~4200-4764) -> (attract) NOW LOADING (f~4930)

This probe: same path, then taps START on the title window and observes
the difficulty select and beyond, snapshotting every 12 frames and
sampling read-only RAM signals.
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_arcade_flow"
os.makedirs(OUT, exist_ok=True)

SCORE_ADDR = 0x0EE318
POW_ADDR = 0x087A78
MISSION_ADDR = 0x0D4213

END = 8000
SNAP_EVERY = 12


def buttons_at(f):
    if 2750 <= f < 2774:
        return "A"                     # select ARCADE MISSION on menu
    if 4300 <= f < 8000:
        # START tap: hold 12 of every 150 from 4300 (title onward)
        return "START" if (f - 4300) % 150 < 12 else ""
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
    ram = []
    prev_small = None
    for f in range(1, END + 1):
        p.core.set_buttons(buttons_at(f))
        p.core.run_frame()
        if f % 300 == 0:
            try:
                r = p.core.ram
                rd = lambda a, n=4: int.from_bytes(r[a:a + n], "little")
                ram.append({"frame": f,
                            "score": rd(SCORE_ADDR),
                            "pow": rd(POW_ADDR),
                            "mission": rd(MISSION_ADDR, 1)})
            except Exception as e:                          # noqa: BLE001
                ram.append({"frame": f, "err": str(e)})
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is None:
                continue
            arr = np.asarray(rgb)
            png = os.path.join(OUT, f"f{f:05d}.png")
            Image.fromarray(arr).save(png)
            d = small_diff(arr, prev_small)
            snaps.append({"frame": f, "png": os.path.basename(png),
                          "diff": round(d, 2) if d < 998 else None,
                          "mean": round(float(arr.mean()), 1)})
            prev_small = arr

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
        json.dump({"snaps": snaps, "runs": runs, "ram": ram}, fh, indent=1)
    print("ram tail:", json.dumps(ram[-4:]))
    print("runs.json written")


if __name__ == "__main__":
    main()
