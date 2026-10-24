#!/usr/bin/env python3
"""poypoy_menu9.py — wheel-aware EXHIBITION walker -> real match.

Disc-string ground truth (offsets in the .bin):
  7925868 "Use the Directional button. Press the <SJIS 817E=x> button
           to select."          -> X (CROSS) is CONFIRM
  7925932 "Press the SELECT button ..." -> SELECT has a role too
  7926432 "Press the <x> button to stop the wheel." -> team select is a
           ROULETTE WHEEL: animated until X stops it — static-screen
           polling can NEVER see it (menu8's blind spot)
  7926396 "Press the <SJIS 81A2=triangle> button to exit."

Protocol (one beetle boot, H5):
  1. boot -> START -> template-poll the REAL MODE SELECT
  2. X (confirm EXHIBITION)
  3. wheel walk: every 240f screenshot + press X (stop the wheel /
     confirm); a step completes when the screen changed; up to 14
     steps; log everything for post-run classification
  4. arena detection: a screen that keeps ANIMATING for >1800f after
     the last X (and is not black/demo-watermarked) is likely the
     match -> run the battle input sweep there.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu9"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def load_base(path):
    try:
        return np.array(Image.open(path).convert("RGB"))
    except Exception:
        return None


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"steps": [], "started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu9")
    p.boot()
    p.wait(480)
    p.core.run(90, {"START"})

    # ---- reach the REAL MODE SELECT -----------------------------------
    on_menu = False
    starts, t0 = 0, p.core.frames_run
    while p.core.frames_run - t0 < 30000 and starts <= 4:
        img = p.core.frame_rgb()
        if img is not None and float(np.asarray(img).mean()) >= 25.0:
            if (diff(menu_t, img) or 999) < 15.0:
                on_menu = True
                break
        p.core.run(150, set())
        if (p.core.frames_run - t0) // 3000 >= starts + 1:
            starts += 1
            p.core.run(90, {"START"})
    if not on_menu:
        out["error"] = "menu never matched"
        _finish(out, p)
        return 2
    out["steps"].append({"step": 0, "event": "on_real_menu",
                         "frame": p.core.frames_run})
    print(json.dumps(out["steps"][-1]))

    prev = menu_t
    for step in range(1, 15):
        p.core.run(30, set())
        p.core.run(20, {"X"})                # stop the wheel / confirm
        # wait for the screen to leave the previous one
        changed = False
        t0 = p.core.frames_run
        while p.core.frames_run - t0 < 3600:
            p.core.run(120, set())
            img = p.core.frame_rgb()
            if img is None or float(np.asarray(img).mean()) < 25.0:
                continue
            if (diff(prev, img) or 0) > 25.0:
                changed = True
                break
        cur = snap(p, f"m9_{step:02d}.png")
        row = {"step": step, "frame": p.core.frames_run,
               "changed": bool(changed),
               "d_prev": round(diff(prev, cur) or 0, 1)}
        out["steps"].append(row)
        print(json.dumps(row))
        if not changed:
            # screen stopped responding to X: steady state (arena?)
            break
        prev = cur

    # ---- steady-state classification ----------------------------------
    p.core.run(600, set())
    steady = snap(p, "m9_steady.png")
    p.core.run(600, set())
    anim = diff(steady, p.core.frame_rgb()) or 0
    out["steady"] = {"frame": p.core.frames_run,
                     "anim_over_600f": round(anim, 1)}
    if anim > 10.0:
        # animated steady state: likely the match — battle input sweep
        sweep = []
        arena = p.core.frame_rgb()
        for btn in ("LEFT", "RIGHT", "UP", "X", "SQ", "O"):
            p.core.run(24, {btn})
            p.core.run(90, set())
            d = diff(arena, p.core.frame_rgb())
            sweep.append({"btn": btn, "diff": round(d or 0, 1)})
            p.core.run(60, set())
        out["input_sweep"] = sweep
        out["arena_likely"] = True
        print(json.dumps({"input_sweep": sweep}))
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu9.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
