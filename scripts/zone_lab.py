#!/usr/bin/env python3
"""zone_lab.py — empirical tactics lab for the MSX M1 truck-zone wall.

Reach the zone (walk+fire from mission start until the camera locks),
save a state, then try tactics from the SAME state:
  A  hold LEFT+fire            (meet the truck soldiers)
  B  alternate L/R fire 60f    (v6 style)
  C  A + grenade every 120f
  D  B + grenade every 120f
  E  B + jump-grenade every 150f (anti-air arc)
  F  hold RIGHT+fire           (baseline)
Cleared = camera scrolls again (churn > 6000 twice in a row).
Zero writes, zero cheats — pure input experiments on a savestate."""
import os
import sys
import time

import numpy as np

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

from ps1play.api import PS1Play                              # noqa: E402
from mission import ensure_mission                           # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v4_mission1/lab"
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, name):
    from PIL import Image
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(
            os.path.join(OUT, name))


def churn_of(p, s_before):
    return int(np.count_nonzero(s_before != p.mem.snapshot()))


def main():
    p = PS1Play(GAME)
    p.boot()
    r = p.enter_gameplay3()
    log("enter:", r.get("in_game"))
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")

    # ---- walk+fire to the zone (camera locks) ------------------------
    burst = 0
    hop_cd = 200
    hop_hold = 0
    log("[lab] walking to the zone...")
    for f in range(2400):
        btns = {"RIGHT"}
        burst = (burst + 1) % 14
        if burst < 8:
            btns.add("Y")
        if hop_hold > 0:
            btns.add("B")
            hop_hold -= 1
        elif hop_cd <= 0:
            hop_hold = 13
            hop_cd = 160 + 13
        else:
            hop_cd -= 1
        p.core.set_buttons(btns)
        p.core.run_frame()
        if f % 60 == 0 and f > 300:
            s0 = p.mem.snapshot()
            p.core.run(60, {"RIGHT", "Y"})
            c = churn_of(p, s0)
            p._advance()
            if c < 2500:
                log(f"[lab] zone entered at f={f} (churn={c})")
                break
    p.save_state("zs")
    log("[lab] zone state saved")

    # ---- tactics -------------------------------------------------------
    def run_tactic(name, steps):
        """steps: list of (frames, btns). Returns cleared bool."""
        p.load_state("zs")
        p.core.run(5, set())
        p._advance()
        t0 = time.time()
        streak = 0
        hist = []
        score0 = int(p.mem.u32(0x0EE318))
        for frames, btns in steps:
            s0 = p.mem.snapshot()
            p.core.run(frames, btns)
            c = churn_of(p, s0)
            p._advance()
            streak = streak + 1 if c > 6000 else 0
            hist.append(c)
            if streak >= 2:
                break
        cleared = streak >= 2
        score1 = int(p.mem.u32(0x0EE318))
        png(p, f"end_{name}.png")
        log(f"[lab] {name}: cleared={cleared} "
            f"churn={hist[-8:]} score={score0}->{score1} "
            f"({round(time.time() - t0, 1)}s)")
        return cleared

    def build(kind, total=1500):
        steps = []
        t = 0
        gi = 0
        while t < total:
            if kind == "A":
                steps.append((60, {"LEFT", "Y"}))
            elif kind == "B":
                side = "LEFT" if (len(steps) // 1) % 2 == 0 else "RIGHT"
                steps.append((60, {side, "Y"}))
            elif kind == "C":
                if gi % 2 == 1:
                    steps.append((8, {"LEFT", "A"}))
                    t += 8
                steps.append((52, {"LEFT", "Y"}))
                gi += 1
                t += 52
                continue
            elif kind == "D":
                if gi % 2 == 1:
                    steps.append((8, {"LEFT", "A"}))
                    t += 8
                side = "LEFT" if gi % 4 < 2 else "RIGHT"
                steps.append((52, {side, "Y"}))
                gi += 1
                t += 52
                continue
            elif kind == "E":
                if gi % 3 == 2:            # jump + grenade at apex
                    steps.append((7, {"LEFT", "B", "A"}))
                    steps.append((7, {"LEFT", "B"}))
                    t += 14
                side = "LEFT" if gi % 4 < 2 else "RIGHT"
                steps.append((46, {side, "Y"}))
                gi += 1
                t += 46
                continue
            elif kind == "F":
                steps.append((60, {"RIGHT", "Y"}))
            t += 60
        return steps

    results = {}
    for kind in ("A", "B", "C", "D", "E", "F"):
        results[kind] = run_tactic(kind, build(kind))
    log("[lab] RESULTS:", results)


if __name__ == "__main__":
    main()
