#!/usr/bin/env python3
"""poypoy_menu14.py — interactivity probe via OPTIONS + long wheel watch.

Working theory after menu8-13: the MODE SELECT seen at ~1770 may be
the ATTRACT's showcase rendering (input disabled); the interactive
gate may be START (the splash says "PRESS START!").

This probe, from the template-matched menu:
  A. DOWN DOWN (cursor to OPTIONS) -> X -> watch 2500f:
     - OPTIONS OPENS (new static screen persisting >1500f) = the menu
       IS interactive -> continue
     - nothing / attract continues = showcase rendering
  B. if interactive: re-enter menu path, DOWN (EXHIBITION is the item
     BELOW the default? m7_04 shows EXHIBITION highlighted at root) --
     press X on EXHIBITION, then watch 12k frames for the WHEEL: an
     animated screen persisting >3000f that is NOT splash/title/menu
     and NOT the demo field cycle (demo cycles back to splash within
     ~2500f; a wheel waits for input indefinitely)
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu14"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu14"


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


def reach_menu(p, menu_t):
    p.wait(480)
    p.core.run(90, {"START"})
    starts, t0 = 0, p.core.frames_run
    while p.core.frames_run - t0 < 30000 and starts <= 4:
        img = p.core.frame_rgb()
        if img is not None and float(np.asarray(img).mean()) >= 25.0:
            if (diff(menu_t, img) or 999) < 15.0:
                return True
        p.core.run(150, set())
        if (p.core.frames_run - t0) // 3000 >= starts + 1:
            starts += 1
            p.core.run(90, {"START"})
    return False


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base("/home/z/my-project/emu/games_psx/evidence/"
                         "poypoy_flow2/f2_45_static.png")
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    if not reach_menu(p, menu_t):
        out["error"] = "menu never matched"
        _finish(out, p)
        return 2
    # ---- A: OPTIONS interactivity probe --------------------------------
    p.core.run(10, {"DOWN"})
    p.core.run(15, set())
    p.core.run(10, {"DOWN"})
    p.core.run(15, set())
    snap(p, "m14_cursor_options.png")
    p.core.run(20, {"X"})
    opts = None
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < 2500:
        p.core.run(150, set())
        img = p.core.frame_rgb()
        if img is None or float(np.asarray(img).mean()) < 25.0:
            continue
        if (diff(menu_t, img) or 999) < 15.0:
            continue                         # still the menu
        if (diff(splash_t, img) or 999) < 15.0:
            out["A"] = {"verdict": "attract_took_over"}
            print(json.dumps(out["A"]))
            break
        # candidate options screen: check it persists 1500f
        s0 = img
        p.core.run(1500, set())
        img2 = p.core.frame_rgb()
        if (diff(s0, img2) or 999) < 10.0:
            snap(p, "m14_options.png")
            opts = img2
            out["A"] = {"verdict": "menu_is_interactive",
                        "frame": p.core.frames_run}
            print(json.dumps(out["A"]))
            break
    if opts is None and "A" not in out:
        out["A"] = {"verdict": "no_persistent_screen"}
        print(json.dumps(out["A"]))
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu14.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
