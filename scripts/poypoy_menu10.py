#!/usr/bin/env python3
"""poypoy_menu10.py — decisive in-battle causality probe.

Ambiguity to kill: the attract demo plays CPU-vs-CPU exhibition
matches that are visually IDENTICAL to a real match (same field,
same watermark). Two independent discriminators:

  D1  START during the battle: the attract demo EXITS to the title /
      menu; a real match does not (Poy Poy has no mid-match START
      exit to the boot title).
  D2  same-state input A/B: save the state at the battle frame, then
      hold LEFT vs RIGHT vs no-input in three reloads — a real match
      moves the player; a demo ignores input.

Run: reach MODE SELECT (template), X -> walk the wheel flow with
periodic X, then at the first stable field frame: save state, run
D1, reload, run D2, report verdicts + screenshots.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu10"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
CKPT = "/home/z/my-project/emu/games_psx/ws_poypoy_menu10/poybattle.ckpt"


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
    os.makedirs(os.path.dirname(CKPT), exist_ok=True)
    out = {"events": [], "started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base("/home/z/my-project/emu/games_psx/evidence/"
                         "poypoy_flow2/f2_45_static.png")
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu10")
    p.boot()
    p.wait(480)
    p.core.run(90, {"START"})
    starts, t0 = 0, p.core.frames_run
    while p.core.frames_run - t0 < 30000 and starts <= 4:
        img = p.core.frame_rgb()
        if img is not None and float(np.asarray(img).mean()) >= 25.0:
            if (diff(menu_t, img) or 999) < 15.0:
                break
        p.core.run(150, set())
        if (p.core.frames_run - t0) // 3000 >= starts + 1:
            starts += 1
            p.core.run(90, {"START"})
    out["events"].append({"event": "menu", "frame": p.core.frames_run})
    p.core.run(30, set())
    p.core.run(20, {"X"})                    # EXHIBITION -> wheel flow
    # wheel walk: X every 300f, up to 12 presses, log screens
    for i in range(12):
        p.core.run(300, set())
        img = snap(p, f"m10_w{i:02d}.png")
        row = {"i": i, "frame": p.core.frames_run,
               "d_menu": round(diff(menu_t, img) or 0, 1),
               "d_splash": round(diff(splash_t, img) or 0, 1),
               "mean": round(float(np.asarray(img).mean()), 1)}
        out["events"].append(row)
        print(json.dumps(row))
        if row["d_splash"] < 15.0:
            out["events"].append({"event": "back_at_splash", "i": i})
            print(json.dumps(out["events"][-1]))
            break
        p.core.run(20, {"X"})
    # the LAST field-like screen before any splash = battle candidate
    p.save_state(CKPT)
    out["events"].append({"event": "saved_state",
                          "frame": p.core.frames_run})
    print(json.dumps(out["events"][-1]))

    # ---- D1: START during the battle ----------------------------------
    p.core.run(30, {"START"})
    p.core.run(120, set())
    img = snap(p, "m10_d1_after_start.png")
    d1_menu = diff(menu_t, img) or 0
    d1_splash = diff(splash_t, img) or 0
    out["D1"] = {"d_menu": round(d1_menu, 1),
                 "d_splash": round(d1_splash, 1),
                 "verdict": ("demo_exits" if min(d1_menu, d1_splash) < 15
                             else "no_exit_real_match")}
    print(json.dumps(out["D1"]))

    # ---- D2: same-state input A/B/C ------------------------------------
    p.load_state(CKPT)
    p.core.run(120, {"LEFT"})
    s_left = snap(p, "m10_d2_left.png")
    p.load_state(CKPT)
    p.core.run(120, {"RIGHT"})
    s_right = snap(p, "m10_d2_right.png")
    p.load_state(CKPT)
    p.core.run(120, set())
    s_none = snap(p, "m10_d2_none.png")
    d2 = {"left_vs_none": round(diff(s_left, s_none) or 0, 1),
          "right_vs_none": round(diff(s_right, s_none) or 0, 1),
          "left_vs_right": round(diff(s_left, s_right) or 0, 1)}
    d2["verdict"] = ("input_has_effect" if max(d2["left_vs_none"],
                                                d2["right_vs_none"]) > 4.0
                     else "input_ignored_demo")
    out["D2"] = d2
    print(json.dumps(d2))
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu10.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
