#!/usr/bin/env python3
"""diag_opening.py — ONE mission life, PNG every 45 frames.
Purpose: see the exact choreography of the MSX M1 opening zone
(soldier timings, truck, chopper) to design a scripted opening.
No calibration, no recovery — pure observation."""
import os
import sys
import time

import numpy as np

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

from ps1play.api import PS1Play                              # noqa: E402
from mission import ensure_mission                           # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v4_mission1/diag"
os.makedirs(OUT, exist_ok=True)

FIRE_ON, FIRE_OFF = 8, 6


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, name):
    from PIL import Image
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(
            os.path.join(OUT, name))


def main():
    p = PS1Play(GAME)
    p.boot()
    r = p.enter_gameplay3()
    log("enter:", r.get("in_game"))
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")

    # minimal policy: walk right + tap fire + jump every 110f (13f hold)
    burst = 0
    hop_cd = 120
    hop_hold = 0
    s_prev = p.mem.snapshot()
    t0 = time.time()
    T = 4500
    for f in range(T):
        btns = {"RIGHT"}
        burst = (burst + 1) % (FIRE_ON + FIRE_OFF)
        if burst < FIRE_ON:
            btns.add("Y")
        if hop_hold > 0:
            btns.add("B")
            hop_hold -= 1
        elif hop_cd <= 0:
            hop_hold = 13
            hop_cd = 110 + 13
        else:
            hop_cd -= 1
        p.core.set_buttons(btns)
        p.core.run_frame()
        if f % 45 == 0:
            s_now = p.mem.snapshot()
            churn = int(np.count_nonzero(s_prev != s_now))
            s_prev = s_now
            score = int(p.mem.u32(0x0EE318))
            png(p, f"d{f:04d}.png")
            log(f"f={f} churn={churn} score={score}")
        # stop at continue screen: pad ignored + churn collapses
        if f > 600 and f % 150 == 0:
            churn = int(np.count_nonzero(s_prev != p.mem.snapshot()))
            if churn < 60:
                log(f"dead screen at f={f}, stopping")
                break
    p._advance()
    log("diag done in", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
