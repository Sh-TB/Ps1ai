#!/usr/bin/env python3
"""real_title_advance_probe.py — can the real title screen advance?

Continues from real_disc_boot_probe findings: the SLUS-01212 disc boots
through the official OpenBIOS override path and renders the game's own
title screen with "NOW LOADING!" by frame ~1260.

This probe: after boot, taps START periodically and snapshots the
screen, hunting for the next OBSERVED transition (warning screen,
attract intro, or menu). Strictly observational: inputs only, no RAM
writes, no cheats.
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
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_title_advance"
os.makedirs(OUT, exist_ok=True)

WARMUP = 1200          # through BIOS cube + game boot to title loading
TOTAL = 3600
TAP_START_AT = 150     # tap START every N frames after warmup
SNAP_EVERY = 60


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
    timeline = []
    taps = []
    t0 = time.time()
    for f in range(1, TOTAL + 1):
        if f <= WARMUP:
            btn = None
        else:
            # hold START for 12 frames out of every TAP window (AC pattern)
            btn = "START" if (f - WARMUP) % TAP_START_AT < 12 else None
            if btn and (f - WARMUP) % TAP_START_AT == 1:
                taps.append(f)
        p.core.run(buttons=btn) if False else None
        # run exactly one frame with the chosen button state
        if btn:
            p.core.set_buttons(btn)
        else:
            p.core.set_buttons("")
        p.core.run_frame()
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                arr = np.asarray(rgb)
                png = os.path.join(OUT, f"f{f:05d}.png")
                Image.fromarray(arr).save(png)
                m = diff_metric(arr, prev)
                timeline.append({"frame": f, "png": os.path.basename(png),
                                 "diff": m, "shape": list(arr.shape)})
                prev = arr
    elapsed = time.time() - t0

    events = [t for t in timeline if t["diff"] is not None and t["diff"] > 3.0]
    report = {"game": os.path.basename(GAME),
              "taps": taps, "elapsed_s": round(elapsed, 1),
              "big_changes": events, "timeline": timeline}
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print("taps:", taps)
    print("big_changes:", [(e["frame"], round(e["diff"], 1)) for e in events])
    print("report:", os.path.join(OUT, "report.json"))


if __name__ == "__main__":
    main()
