#!/usr/bin/env python3
"""poypoy_menu11.py — THE differential experiment.

Question: does X on the real MODE SELECT drive the exhibition flow,
or is everything we saw the attract demo?

Known attract facts (m6 hands-off timeline): menu@2890 -> demo@3390
with ZERO input; demo field screens are visually identical to real
matches; any button press during the demo skips it (menu10).

Design (one beetle boot, H5):
  1. reach the real MODE SELECT (template), SAVE STATE (menu anchor)
  2. Arm A: reload -> ONE X -> screenshot every 300f x 10
  3. Arm B: reload -> hands off  -> screenshot every 300f x 10
  4. verdict: per-sample A-vs-B diff; identical paths (all < 15) =
     X is inert (attract), divergence = X drives the flow
  5. if diverged: arm A continues with an X cadence (wheel walk),
     save the final field state, and run the D2 input A/B/C probe.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu11"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu11"
CKPT = os.path.join(WS, "menu_anchor.ckpt")


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
    os.makedirs(WS, exist_ok=True)
    out = {"A": [], "B": [], "started": time.strftime("%FT%TZ",
                                                      time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    p = PS1Play(CUE, workspace=WS)
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
    p.save_state(CKPT)
    out["anchor_frame"] = p.core.frames_run
    print(json.dumps({"anchor": out["anchor_frame"]}))

    # ---- Arm A: ONE X --------------------------------------------------
    p.load_state(CKPT)
    p.core.run(30, set())
    p.core.run(20, {"X"})
    for i in range(10):
        p.core.run(300, set())
        img = snap(p, f"m11_A{i:02d}.png")
        out["A"].append({"i": i, "frame": p.core.frames_run,
                         "mean": round(float(np.asarray(img).mean()), 1)})
    # ---- Arm B: hands off ----------------------------------------------
    p.load_state(CKPT)
    for i in range(10):
        p.core.run(300, set())
        img = p.core.frame_rgb()
        out["B"].append({"i": i, "frame": p.core.frames_run})
        out["B"][-1]["diff_vs_A"] = round(diff(img, load_A(out, i)) or 0, 1) \
            if False else None
    # pair-wise compare from the saved A screenshots
    maxd, first_div = 0.0, None
    for i in range(10):
        a = np.array(Image.open(os.path.join(EVID, f"m11_A{i:02d}.png"))
                     .convert("RGB"))
        # re-run arm B frame capture pairwise: reload + advance i*300
        p.load_state(CKPT)
        p.core.run(300 * (i + 1), set())
        b = p.core.frame_rgb()
        d = diff(a, b)
        out["B"][i]["diff_vs_A"] = round(d or 0, 1)
        if d and d > maxd:
            maxd = d
        if d and d > 15 and first_div is None:
            first_div = i
        print(json.dumps(out["B"][i]))
    out["verdict"] = ("X_drives_flow" if first_div is not None
                      else "X_inert_attract")
    out["max_divergence"] = round(maxd, 1)
    out["first_divergence_at"] = first_div
    print(json.dumps({"verdict": out["verdict"],
                      "max_divergence": out["max_divergence"],
                      "first_divergence_at": first_div}))
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu11.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


def load_A(out, i):
    return None


if __name__ == "__main__":
    sys.exit(main())
