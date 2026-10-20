#!/usr/bin/env python3
"""issue5_continue_diag.py — capture the death->continue sequence and
identify the accepting button empirically.

Play until the first game_over (flags 0xFF->0x1), then:
  phase A (no input): one PNG per 25 frames for 15 s  -> see the prompt
  phase B (one variable): try START, Y, X, B, A, SELECT each 2.5 s
  apart; save a PNG before each probe; stop when flags return to 0xFF.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from ps1play import labconfig                                # noqa: E402
from ps1play.telemetry import TelemetryAdapter               # noqa: E402
from mission import ensure_mission                           # noqa: E402
from issue4_real_start import boot_to_demo, owns_pad         # noqa: E402
from issue4_controller import boot                           # noqa: E402

OUT = ("/home/z/my-project/work/msx_recomp/evidence/"
       "issue5_continue_diag")
os.makedirs(OUT, exist_ok=True)


def snap_png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUT, name))


def main():
    p, _fw = boot()
    tel = TelemetryAdapter(p)
    snap_png(p, "start.png")
    # advance until game over (bounded: ~90 chunks)
    gone = False
    for c in range(90):
        p.core.run(60, {"RIGHT"})
        p.core.run(60, {"RIGHT", "Y"})
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        if cur["flags_word"] == 0x1:
            print(f"[diag] game over at chunk {c} frame {cur['frame']}",
                  flush=True)
            gone = True
            break
    if not gone:
        print("[diag] no game over in 90 chunks")
        return
    # phase A: passive capture
    for i in range(24):
        p.core.run(25, set())
        snap_png(p, f"passive_{i:02d}.png")
        if tel.snapshot(buttons=[], frame=p.core.frames_run)["flags_word"] \
                == 0xFF:
            print(f"[diag] flags back to 0xFF during passive at {i}")
            break
    # phase B: single-button probes
    for btn in ("START", "Y", "X", "B", "A", "SELECT", "RIGHT"):
        snap_png(p, f"probe_{btn}_before.png")
        p.core.run(20, {btn})
        p.core.run(130, set())
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        snap_png(p, f"probe_{btn}_after.png")
        print(f"[diag] probe {btn}: flags={cur['flags_word']:#x}",
              flush=True)
        if cur["flags_word"] == 0xFF:
            print(f"[diag] *** {btn} RESUMED PLAY ***")
            break
    print("diag done")


if __name__ == "__main__":
    main()
