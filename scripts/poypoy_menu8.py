#!/usr/bin/env python3
"""poypoy_menu8.py — template-locked MODE SELECT confirm.

Evidence locked so far:
  - REAL MODE SELECT = m7_04 screenshot (black bg, "MODE SELECT",
    EXHIBITION highlighted MAGENTA at root, help bar)
  - the attract cycle passes through this menu periodically
  - DOWN moves the cursor OFF EXHIBITION (m7_05) — presses go at ROOT
  - black/cinematic/load phases must be rejected (not "static menus")

Protocol:
  1. boot -> START -> poll until the screen template-matches the REAL
     MODE SELECT (periodic gentle START every 3000f, max 4, to advance
     splash/title phases; hands off otherwise)
  2. settle, ONE X press
  3. poll for a static non-black screen that is NOT the menu, splash,
     title, or demo-watermarked -> ENTRY candidate, screenshot, stop.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu8"
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
    out = {"events": [], "started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base("/home/z/my-project/emu/games_psx/evidence/"
                         "poypoy_flow2/f2_45_static.png")
    demo_t = load_base(os.path.join(M7, "m7_05_after_X.png"))
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu8")
    p.boot()
    p.wait(480)
    p.core.run(90, {"START"})               # early title -> cinematic

    # ---- phase 1: reach the REAL MODE SELECT --------------------------
    on_menu = None
    starts = 0
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < 30000 and starts <= 4:
        img = p.core.frame_rgb()
        if img is not None and float(np.asarray(img).mean()) >= 25.0:
            d = diff(menu_t, img)
            if d is not None and d < 15.0:
                on_menu = img
                break
        p.core.run(150, set())
        # gentle advancement: a START every ~3000f pushes splash/title
        if (p.core.frames_run - t0) // 3000 >= starts + 1:
            starts += 1
            p.core.run(90, {"START"})
            out["events"].append({"event": f"adv_start_{starts}",
                                  "frame": p.core.frames_run})
            print(json.dumps(out["events"][-1]))
    if on_menu is None:
        out["error"] = "real MODE SELECT never matched"
        _finish(out, p)
        return 2
    snap(p, "m8_00_on_menu.png")
    out["events"].append({"event": "on_real_menu",
                          "frame": p.core.frames_run})
    print(json.dumps(out["events"][-1]))

    # ---- phase 2: ONE X at root ---------------------------------------
    p.core.run(30, set())
    p.core.run(20, {"X"})
    out["events"].append({"event": "X_pressed", "frame": p.core.frames_run})

    # ---- phase 3: classify what follows --------------------------------
    entry = None
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < 10000:
        p.core.run(120, set())
        img = p.core.frame_rgb()
        if img is None or float(np.asarray(img).mean()) < 25.0:
            continue
        s0 = img
        p.core.run(60, set())
        if diff(s0, p.core.frame_rgb()) or 0 > 6.0:
            continue                        # still animating
        d_menu = diff(menu_t, img) or 999
        d_splash = diff(splash_t, img) or 999
        d_demo = diff(demo_t, img) or 999
        if min(d_menu, d_splash, d_demo) < 15.0:
            continue                        # cycled back to a known screen
        snap(p, "m8_01_ENTRY.png")
        entry = {"frame": p.core.frames_run,
                 "d_menu": round(d_menu, 1),
                 "d_splash": round(d_splash, 1),
                 "d_demo": round(d_demo, 1)}
        break
    out["entry"] = entry
    out["verdict"] = "entry" if entry else "no_entry_after_X"
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu8.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({"verdict": out.get("verdict"),
                      "entry": out.get("entry")}))
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
