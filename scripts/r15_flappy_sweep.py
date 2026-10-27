#!/usr/bin/env python3
"""r15_flappy_sweep.py — learn the REAL collision geometry by playing.

The source has a FIXME (phantom collisions, camera-space test) and the
col-shape component stores a POINTER into a shared static array. Rather
than trusting derived geometry, hold the bird at fixed heights Y and see
which Y values let pipes pass (survive 500 frames) vs die.

One boot, one life per Y (restart after each), Y in 40..190 step 10.
Evidence -> scratch/round15_flappy/sweep/
"""
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from hellopong_r12_lib import make_jrn, save_png           # noqa: E402
from r15_flappy_play import (bird_y, green_mask, gap_target,   # noqa
                             ground_ok, gameover_like)

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "flappybird.cue")
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")
OUT = os.path.join(REPO, "scratch", "round15_flappy", "sweep")
WS = "/home/z/my-project/emu/games_homebrew/ws_r15_flappy"

HOLD = 520


def start_life(p, jrn):
    # from any state: if game-over -> START; then Get Ready -> B
    for w in range(120):
        fr = p.core.frame_rgb()
        if gameover_like(fr):
            p.core.run(3, {"START"})
            p.core.run(4, set())
            break
        p.core.run(1, set())
    for w in range(400):
        fr = p.core.frame_rgb()
        if ground_ok(fr) and not gameover_like(fr):
            break
        p.core.run(1, set())
    p.core.run(3, {"B"})
    p.core.run(4, set())
    p.core.run(2, {"B"})
    p.core.run(4, set())
    jrn({"ev": "life_started"})


def hold_height(p, jrn, Y):
    """Servo-hold bird at Y. Returns 'alive' after HOLD frames or 'dead'."""
    buttons = set()
    press = cool = 0
    by_prev = None
    for idx in range(HOLD):
        p.core.run(1, buttons)
        fr = p.core.frame_rgb()
        by, npx = bird_y(fr)
        vy = None if by is None or by_prev is None else by - by_prev
        by_prev = by
        if press > 0:
            press -= 1
            if press == 0:
                cool = 3
            buttons = {"B"}
        elif cool > 0:
            cool -= 1
            buttons = set()
        elif by is not None:
            if (by > Y + 2 and (vy is None or vy >= -0.5)) or by > Y + 12:
                buttons = {"B"}
                press = 1
            else:
                buttons = set()
        else:
            buttons = set()
        if gameover_like(fr):
            return "dead", idx
        if by is None:
            # allow brief occlusion behind pipes; 45 consecutive = dead
            miss = getattr(hold_height, "_miss", 0) + 1
            hold_height._miss = miss
            if miss > 45:
                return "dead", idx
        else:
            hold_height._miss = 0
    return "alive", HOLD


def main():
    os.makedirs(OUT, exist_ok=True)
    jrn = make_jrn(OUT, "[fsweep]")
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    jrn({"ev": "boot", "core": p.boot()})
    for _ in range(700):
        p.core.run(1, set())

    results = []
    for Y in range(40, 200, 10):
        start_life(p, jrn)
        hold_height._miss = 0
        verdict, at = hold_height(p, jrn, Y)
        fr = p.core.frame_rgb()
        save_png(OUT, fr, f"Y{Y:03d}_{verdict}.png")
        results.append({"Y": Y, "verdict": verdict, "at_frame": at})
        jrn({"ev": "sweep_result", **results[-1]})
    jrn({"ev": "sweep_summary", "results": results})
    alive = [r["Y"] for r in results if r["verdict"] == "alive"]
    jrn({"ev": "survivable_band", "alive_ys": alive,
         "min": min(alive) if alive else None,
         "max": max(alive) if alive else None})
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
