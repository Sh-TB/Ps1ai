#!/usr/bin/env python3
"""real_menu_input_diag.py — does pad input reach the REAL game's menu?

Established chain: disc -> OpenBIOS -> title "NOW LOADING!" -> main menu
(~frame 2340, ARCADE MISSION highlighted by default).

Diagnostic ladder, each step isolated with its own snapshots:
  A. hold DOWN 30f   -> expect cursor moves to COMBAT SCHOOL
  B. hold UP 30f     -> expect back to ARCADE MISSION
  C. hold CROSS 12f  -> expect ARCADE MISSION select (difficulty screen)
  D. hold START 12f  -> same expectation if C was a no-op
Every step prints the screen diff of the following snapshots.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WORKSPACE = "/home/z/my-project/ps1-test/emu"
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_menu_input_diag"
os.makedirs(OUT, exist_ok=True)

STEPS = [
    ("A_DOWN",   2450, 2480, "DOWN"),
    ("B_UP",     2600, 2630, "UP"),
    ("C_CROSS",  2750, 2762, "A"),       # libretro JP_A = PSX cross
    ("D_START",  2950, 2962, "START"),
]
OBSERVE_UNTIL = 3300


def diff_metric(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.asarray(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def main():
    p = PS1Play(GAME, core=CORE, workspace=WORKSPACE,
                var_overrides={b"beetle_psx_override_bios": b"openbios"},
                verbose=False)
    info = p.boot()
    print("boot:", json.dumps(info, default=str))

    prev = None
    log = []
    t0 = time.time()
    for f in range(1, OBSERVE_UNTIL + 1):
        btn = ""
        for name, s, e, spec in STEPS:
            if s <= f < e:
                btn = spec
        p.core.set_buttons(btn)
        p.core.run_frame()
        if f % 30 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                arr = np.asarray(rgb)
                Image.fromarray(arr).save(
                    os.path.join(OUT, f"f{f:05d}.png"))
                m = diff_metric(arr, prev)
                log.append({"frame": f, "diff": m})
                prev = arr
    elapsed = time.time() - t0
    interesting = [x for x in log if x["diff"] is not None and x["diff"] > 2.0]
    print("elapsed_s:", round(elapsed, 1))
    print("changes at:", [(x["frame"], round(x["diff"], 1))
                          for x in interesting])
    with open(os.path.join(OUT, "diag.json"), "w") as fh:
        json.dump({"steps": STEPS, "log": log}, fh, indent=1)


if __name__ == "__main__":
    main()
