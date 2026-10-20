#!/usr/bin/env python3
"""real_menu_yes.py — confirm the menu's OK? dialog and follow the flow.

Observed: circle (B) on the mode menu opens an "OK? YES" dialog next to
ARCADE MISSION. This probe confirms YES (try CROSS first, then START)
and traces the result toward the difficulty select / mission 1.
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_menu_yes"
os.makedirs(OUT, exist_ok=True)

END = 7600
SNAP_EVERY = 6

STEPS = [
    (2450, 2468, "START"),    # Agetec -> mode menu
    (3900, 3918, "B"),        # circle -> OK? dialog (menu ready ~24s)
    (4200, 4218, "A"),        # cross = confirm YES
    (4700, 4718, "B"),        # circle = confirm YES (fallback)
    (5200, 5218, "START"),    # start = confirm YES (fallback)
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
    print("done")


if __name__ == "__main__":
    main()
