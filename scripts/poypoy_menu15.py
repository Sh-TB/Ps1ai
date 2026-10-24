#!/usr/bin/env python3
"""poypoy_menu15.py — interactive-gate hypothesis test.

Timing reconciliation (the missing piece):
  calib strip (TWO STARTs): splash "PRESS START!" @1830
  menu8-14 (ONE START):     menu template matched @1770 — BEFORE the
  splash => that menu instance was the ATTRACT SHOWCASE (input
  disabled); every confirm attempt since menu8 hit the showcase.

Hypothesis: the interactive gate is START on the splash:
  splash --START--> title --START--> menu (INTERACTIVE) --X--> flow

Protocol:
  1. boot -> START@480 -> wait out cinematic -> poll SPLASH (template)
  2. START -> poll static (title) -> START -> poll static -> verify
     menu template -> screenshot (interactive instance)
  3. X -> direction-causality probe at +700f: hold LEFT 150f vs
     none 150f from a savestate. Demo-skip = instant splash-jump;
     real match = no splash + persistent field (input responded).
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu15"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
F2 = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow2"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu15"
CKPT = os.path.join(WS, "battle2.ckpt")


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


def poll_template(p, tmpl, limit, name=None):
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < limit:
        img = p.core.frame_rgb()
        if img is not None and float(np.asarray(img).mean()) >= 25.0:
            if (diff(tmpl, img) or 999) < 15.0:
                if name:
                    snap(p, name)
                return img
        p.core.run(100, set())
    return None


def poll_static_nonblack(p, limit):
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < limit:
        p.core.run(100, set())
        s0 = p.core.frame_rgb()
        if s0 is None or float(np.asarray(s0).mean()) < 25.0:
            continue
        p.core.run(60, set())
        if diff(s0, p.core.frame_rgb()) or 0 < 6.0:
            return s0
    return None


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base(os.path.join(F2, "f2_45_static.png"))
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(480)
    p.core.run(90, {"START"})
    splash = poll_template(p, splash_t, 12000, "m15_splash.png")
    if splash is None:
        out["error"] = "splash never matched"
        _finish(out, p)
        return 2
    out["splash_frame"] = p.core.frames_run
    print(json.dumps({"splash": out["splash_frame"]}))

    # gate: START on splash -> (title?) -> START -> menu
    p.core.run(90, {"START"})
    s1 = poll_static_nonblack(p, 5000)
    snap(p, "m15_after_splash_start.png")
    out["after_gate1"] = s1 is not None
    if s1 is not None:
        p.core.run(90, {"START"})
        s2 = poll_static_nonblack(p, 5000)
        snap(p, "m15_after_second_start.png")
        out["after_gate2"] = s2 is not None
        if s2 is not None:
            d_menu = diff(menu_t, s2) or 0
            out["menu_template_diff"] = round(d_menu, 1)
            print(json.dumps({"menu_diff": round(d_menu, 1)}))

    # from wherever we are: X + causality probe (works only if the
    # interactive menu is up; the probe verdict tells the truth)
    p.core.run(20, {"X"})
    p.core.run(700, set())
    p.save_state(CKPT)
    snap(p, "m15_plus700.png")
    p.core.run(150, {"LEFT"})
    s_l = snap(p, "m15_left.png")
    p.load_state(CKPT)
    p.core.run(150, set())
    s_n = snap(p, "m15_none.png")
    splash_d = min(diff(splash_t, s_l) or 999, diff(splash_t, s_n) or 999)
    out["probe"] = {
        "left_vs_none": round(diff(s_l, s_n) or 0, 2),
        "left_is_splash": bool((diff(splash_t, s_l) or 999) < 15),
        "none_is_splash": bool((diff(splash_t, s_n) or 999) < 15),
        "either_splash_jump": bool(splash_d < 15)}
    pr = out["probe"]
    if pr["either_splash_jump"]:
        pr["verdict"] = "attract_demo_skip"
    elif pr["left_vs_none"] > 3.0:
        pr["verdict"] = "input_responds_REAL_MATCH"
    else:
        pr["verdict"] = "no_signal"
    print(json.dumps(pr))
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu15.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
