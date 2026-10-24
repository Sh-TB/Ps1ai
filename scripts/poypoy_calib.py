#!/usr/bin/env python3
"""poypoy_calib.py — raw timing strip of the boot -> menu path.

The menu5/6 "MODE SELECT" baseline was captured at an unverified
moment (the START_down run's "ms" screenshot is a CINEMATIC frame, yet
the baseline diff passed) — the baseline itself is unreliable.

This strip screenshots EVERY 60f from boot through START x2 with the
original verified waits (90/90/60/240), 30 shots total, no other
input. Reading the strip gives: true transition times, the real MODE
SELECT screen, and the default cursor position.
"""
import os
import sys

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_calib"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))


def main():
    os.makedirs(EVID, exist_ok=True)
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_calib")
    p.boot()
    # press START at the same absolute times as the verified script:
    # 90f hold starting at 420, 90 idle, 60 hold, 240 settle
    for i in range(30):
        f = i * 60
        if f == 420:
            p.core.run(90, {"START"})
        elif f == 600:
            p.core.run(60, {"START"})
        elif f in (510, 540, 570):
            p.core.run(60, set())
        elif f == 660:
            p.core.run(60, set())
        else:
            p.core.run(60, set())
        snap(p, f"c_{i:02d}_f{p.core.frames_run}.png")
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
