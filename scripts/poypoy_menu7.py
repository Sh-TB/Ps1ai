#!/usr/bin/env python3
"""poypoy_menu7.py — corrected boot-path walker (calib-strip evidence).

TRUE boot sequence (scripts/poypoy_calib.py strip):
  boot -> early title (~420) -> START -> BLACK -> Konami cinematic ->
  "WAIT A MOMENT" -> "NOW LOADING" -> (c) splash "PRESS START!" (~1830)
  -> [START] -> main title -> [START] -> MODE SELECT

Every previous menu probe (menu3/4/5/6, flow1/2) pressed buttons at
absolute frames that landed INSIDE the cinematic/load phase — their
"MODE SELECT" baselines and "confirm found" verdicts are void.

menu7 walks the real path: START on the early title, wait out the
cinematic+loads (~2000f, NO input), START on the (c) splash, START on
the main title, then screenshot the REAL MODE SELECT, press DOWN+X,
and poll for the next static screen (team select = ENTRY).
Every static screen is screenshotted for post-run classification.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def poll_static(p, limit=6000, settle=120):
    """Wait for a STATIC, non-black screen; (img, frames_waited) | None.

    Black-reject: the cinematic/load phase holds a static BLACK screen
    (calib strip f630-f810) which naive motion detection accepts."""
    waited = 0
    while waited < limit:
        p.core.run(settle, set())
        waited += settle
        s0 = p.core.frame_rgb()
        if s0 is None or float(np.asarray(s0).mean()) < 25.0:
            continue
        p.core.run(60, set())
        if diff(s0, p.core.frame_rgb()) or 0 < 6.0:
            p.core.run(60, set())          # extra settle
            return s0, waited
    return None, waited


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"events": [], "started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu7")
    p.boot()
    p.wait(480)
    snap(p, "m7_00_early_title.png")
    p.core.run(90, {"START"})                # -> cinematic + loads
    splash, w = poll_static(p, limit=6000)
    if splash is None:
        out["error"] = "no static screen after cinematic"
        _finish(out, p)
        return 2
    snap(p, "m7_01_post_cinematic.png")
    out["events"].append({"event": "post_cinematic_static",
                          "frame": p.core.frames_run, "waited": w})
    print(json.dumps(out["events"][-1]))

    p.core.run(90, {"START"})                # splash -> next
    s2, w = poll_static(p, limit=4000)
    snap(p, "m7_02_after_splash_start.png")
    out["events"].append({"event": "after_splash_start",
                          "frame": p.core.frames_run, "waited": w,
                          "static": s2 is not None})
    print(json.dumps(out["events"][-1]))

    # up to 3 START presses to reach the real MODE SELECT, screenshot
    # each static screen
    ms = None
    for i in range(3):
        if s2 is None:
            break
        snap(p, f"m7_03_{i}_static.png")
        p.core.run(90, {"START"})
        s3, w = poll_static(p, limit=4000)
        out["events"].append({"event": f"start_{i}",
                              "frame": p.core.frames_run, "waited": w,
                              "static": s3 is not None})
        print(json.dumps(out["events"][-1]))
        if s3 is None:
            break
        s2 = s3
    ms = s2
    if ms is None:
        out["error"] = "no static screen before MODE SELECT probes"
        _finish(out, p)
        return 2
    snap(p, "m7_04_candidate_menu.png")

    # MODE SELECT reached: EXHIBITION is highlighted at ROOT (m7_04
    # evidence) — NO DOWN (down moves the cursor to POYPOY CUP)
    p.core.run(20, {"X"})
    out["events"].append({"event": "X_pressed",
                          "frame": p.core.frames_run})
    s4, w = poll_static(p, limit=8000)
    if s4 is not None:
        snap(p, "m7_05_after_X.png")
        same = diff(ms, s4) or 0
        out["events"].append({"event": "after_X_static",
                              "frame": p.core.frames_run, "waited": w,
                              "diff_vs_menu": round(same, 1)})
        print(json.dumps(out["events"][-1]))
        out["verdict"] = ("still_same_menu" if same < 15.0
                          else "new_static_screen")
    else:
        out["verdict"] = "no_static_after_X"
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu7.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
