#!/usr/bin/env python3
"""real_select_trace.py — high-resolution trace of the CROSS-select
transition on the real Metal Slug X main menu.

From real_menu_input_diag: CROSS on the menu at f2750 produced a black
interval (~f2800-2940) then returned to the menu. Question: does a
difficulty-select screen (or any intermediate art) render inside that
window, and does the game settle back deterministically?

Method: boot -> warmup 2400f -> hold CROSS 24f at 2750 -> snapshot
EVERY 6 frames from 2400 to 3400, chain-diff, and group snapshots into
runs of visually identical screens. Read-only.
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_select_trace"
os.makedirs(OUT, exist_ok=True)

WARMUP = 2400
CROSS_AT = 2750
CROSS_LEN = 24
END = 3400
SNAP_EVERY = 6


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
    print("boot:", json.dumps(info, default=str))

    snaps = []
    prev_small = None
    for f in range(1, END + 1):
        btn = "A" if (CROSS_AT <= f < CROSS_AT + CROSS_LEN) else ""
        p.core.set_buttons(btn)
        p.core.run_frame()
        if f >= WARMUP and f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is None:
                continue
            arr = np.asarray(rgb)
            png = os.path.join(OUT, f"f{f:05d}.png")
            Image.fromarray(arr).save(png)
            d = small_diff(arr, prev_small)
            snaps.append({"frame": f, "png": os.path.basename(png),
                          "diff_vs_prev_snap": round(d, 2) if d < 998 else None,
                          "mean": round(float(arr.mean()), 1)})
            prev_small = arr

    # group into runs of identical screens (diff < 1.0)
    runs = []
    cur = None
    for s in snaps:
        if cur is None or (s["diff_vs_prev_snap"] is not None
                           and s["diff_vs_prev_snap"] < 1.0):
            if cur is None:
                cur = {"start": s["frame"], "end": s["frame"],
                       "png": s["png"], "mean": s["mean"]}
            else:
                cur["end"] = s["frame"]
        else:
            runs.append(cur)
            cur = {"start": s["frame"], "end": s["frame"],
                   "png": s["png"], "mean": s["mean"]}
    if cur:
        runs.append(cur)
    print("runs (start-end, mean_brightness, sample_png):")
    for r in runs:
        print(f"  {r['start']:5d}-{r['end']:5d} mean={r['mean']:6.1f} {r['png']}")
    with open(os.path.join(OUT, "runs.json"), "w") as fh:
        json.dump({"snaps": snaps, "runs": runs}, fh, indent=1)


if __name__ == "__main__":
    main()
