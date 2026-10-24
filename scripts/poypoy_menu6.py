#!/usr/bin/env python3
"""poypoy_menu6.py — one-touch discriminator: does the confirm press
enter the EXHIBITION flow, or does everything we saw belong to the
attract sequence?

Timing evidence so far (frames from boot):
  - menu4: NO effective input -> demo/cinematic started ~1310-1550f
  - flow1: DOWN+X at ~880f -> cinematic changes at 950/1025/1100f
    (~380f BEFORE the attract baseline) -> the press plausibly TRIGGERED
    the flow; but every later button press during loads may have
    derailed it back to the boot splash ("PRESS START!" -> title ->
    demo cycle seen in flow2).

Protocol (per candidate, one beetle boot each — H5):
  boot -> verified path to MODE SELECT -> DOWN-highlight -> ONE
  candidate press -> HANDS OFF: screenshot every 500f for 12k frames.
  Verdicts:
    entry        a static screen (>1200f stable) that matches NONE of
                 the baselines (splash/title/mode-select) — a menu
                 waiting for input, impossible during the attract cycle
    attract_cycle the splash->title->demo loop (baseline sequence)
    undecided    nothing static for 12k frames
Candidates: X (down), START (down), START (root) — CLI-selectable.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu6"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M5 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu5"
F2 = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow2"


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--btn", default="X")
    ap.add_argument("--down", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"{args.btn}_{'down' if args.down else 'root'}"
    out = {"tag": tag, "started": time.strftime("%FT%TZ", time.gmtime()),
           "samples": []}

    p = PS1Play(CUE, workspace=f"/home/z/my-project/emu/games_psx/ws_poypoy_menu6_{tag}")
    p.boot()
    p.wait(420)
    p.core.run(90, {"START"})
    p.core.run(30, set())
    p.core.run(60, {"START"})
    p.core.run(240, set())
    ms_base = load_base(os.path.join(M5, "ms_base.png"))
    ms_now = snap(p, f"m6_{tag}_ms.png")
    if ms_base is not None and diff(ms_base, ms_now) > 15:
        out["error"] = "did not reach MODE SELECT"
        out["finished"] = time.strftime("%FT%TZ", time.gmtime())
        with open(os.path.join(EVID, f"m6_{tag}.json"), "w") as f:
            json.dump(out, f, indent=1, default=str)
        try:
            p.core.close()
        except Exception:
            pass
        return 2
    splash = load_base(os.path.join(F2, "f2_45_static.png"))   # © splash
    title = load_base(os.path.join(M5, "title_base.png"))

    if args.down:
        p.core.run(10, {"DOWN"})
        p.core.run(20, set())
    p.core.run(20, {args.btn})               # THE one press
    out["press_frame"] = p.core.frames_run
    print(json.dumps({"press_frame": out["press_frame"]}))

    # hands off: sample every 500f
    stable = 0
    last = p.core.frame_rgb()
    verdict = "undecided"
    unknown_static = None
    for i in range(24):                      # 24 x 500f = 12k frames
        p.core.run(500, set())
        img = p.core.frame_rgb()
        motion = diff(last, img) or 0
        last = img
        d_splash = diff(splash, img) or 999
        d_title = diff(title, img) or 999
        d_ms = diff(ms_now, img) or 999
        known = min(d_splash, d_title, d_ms) < 15.0
        row = {"f": p.core.frames_run, "motion": round(motion, 1),
               "splash": round(d_splash, 1), "title": round(d_title, 1),
               "ms": round(d_ms, 1), "known": bool(known)}
        out["samples"].append(row)
        print(json.dumps(row))
        if motion < 6.0 and not known:
            stable += 1
            if unknown_static is None:
                unknown_static = img
            if stable >= 3:                  # 1500f static, unknown screen
                snap(p, f"m6_{tag}_ENTRY.png")
                verdict = "entry"
                break
        else:
            stable = 0
            unknown_static = None
    out["verdict"] = verdict
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, f"m6_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({"verdict": verdict}))
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
