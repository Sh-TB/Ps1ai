#!/usr/bin/env python3
"""real_menu_confirm2.py — exhaustive confirm-button sweep on the real
mode menu, with pixel-level cursor/selection checks after each step.

Also probes whether the on-screen MOUSE CURSOR reacts (the port renders
an arrow; it may be PSX-mouse driven, but first exhaust pad buttons).
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_menu_confirm2"
os.makedirs(OUT, exist_ok=True)

END = 6600
SNAP_EVERY = 6

STEPS = [
    (2450, 2468, "START"),      # Agetec -> mode menu
    (2700, 2718, "Y"),          # square
    (2950, 2968, "L1"),
    (3200, 3218, "R1"),
    (3450, 3510, "A"),          # cross held 60f
    (3700, 3760, "A"),          # cross held again
    (3950, 3968, "SELECT"),
    (4200, 4290, "START"),      # START held 90f
    (4500, 4518, "A"),          # cross after everything
    (4800, 4818, "B"),          # circle again
]


def buttons_at(f):
    for s, e, b in STEPS:
        if s <= f < e:
            return b
    return ""


def menu_rows(arr):
    g = np.asarray(arr.convert("L")).astype(int) \
        if isinstance(arr, Image.Image) else \
        np.asarray(Image.fromarray(arr).convert("L")).astype(int)
    crop = g[38:92, 18:210]
    return [(crop[i * 13:(i + 1) * 13] > 180).sum() for i in range(4)]


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

    prev = None
    rows_log = []
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
            prev = arr
        if f in (2680, 2780, 3030, 3280, 3560, 3830, 4050, 4350, 4620, 4900,
                 5300, 6000):
            rgb = p.core.frame_rgb()
            if rgb is not None:
                rows_log.append({"frame": f, "rows": menu_rows(rgb)})

    for x in rows_log:
        print(f"  f{x['frame']}: rows={x['rows']}")
    with open(os.path.join(OUT, "rows.json"), "w") as fh:
        json.dump(rows_log, fh, indent=1, default=int)


if __name__ == "__main__":
    main()
