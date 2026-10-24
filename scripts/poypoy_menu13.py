#!/usr/bin/env python3
"""poypoy_menu13.py — deterministic-baseline causality + one driven round.

Fixes menu12's two mistakes: (a) anchor at +800f after X (early
round-1, not the final seconds), (b) use the EMULATOR'S DETERMINISM:
replaying the NONE arm twice from the same savestate yields the
animation baseline (expected diff ~0); any arm diff clearly above
that baseline is pure input causality.

Phases:
  A. boot -> START -> menu -> X -> +800f -> save anchor
  B. arms: none1, none2, LEFT, RIGHT (150f each, reload before each)
     verdict: determinism check (none1 vs none2 ~ 0) AND
              d(left,none1) / d(right,none1) >> determinism baseline
  C. driven round: reload -> roam+X policy ~2400f -> screenshots
     every 300f (the agent's first full driven round)
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu13"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu13"
CKPT = os.path.join(WS, "battle_anchor.ckpt")


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
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
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
    p.core.run(30, set())
    p.core.run(20, {"X"})
    p.core.run(800, set())
    p.save_state(CKPT)
    out["anchor"] = p.core.frames_run
    snap(p, "m13_anchor.png")
    print(json.dumps({"anchor": out["anchor"]}))

    # ---- arms (150f) ----------------------------------------------------
    shots = {}
    for name, btns in (("none1", set()), ("none2", set()),
                       ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(CKPT)
        p.core.run(150, btns)
        shots[name] = snap(p, f"m13_{name}.png")
    d = {f"{a}_vs_{b}": round(diff(shots[a], shots[b]) or 0, 2)
         for a, b in (("none1", "none2"), ("left", "none1"),
                      ("right", "none1"), ("left", "right"))}
    baseline = d["none1_vs_none2"]
    d["determinism_baseline"] = baseline
    d["verdict"] = ("input_has_effect_REAL_MATCH"
                    if baseline < 2.0 and max(d["left_vs_none1"],
                                              d["right_vs_none1"]) >
                    max(3.0, 3 * baseline)
                    else "inconclusive")
    out["causality"] = d
    print(json.dumps(d))

    # ---- driven round ----------------------------------------------------
    plays = []
    p.load_state(CKPT)
    f_end = p.core.frames_run + 2400
    i = 0
    while p.core.frames_run < f_end:
        btn = {"LEFT"} if (i // 30) % 2 == 0 else {"RIGHT"}
        p.core.run(30, btn)
        p.core.run(15, {"X"})
        if i % 10 == 0:
            img = snap(p, f"m13_play_{i:03d}.png")
            plays.append({"i": i, "frame": p.core.frames_run,
                          "mean": round(float(np.asarray(img).mean()), 1)})
            print(json.dumps(plays[-1]))
        i += 1
    out["play_samples"] = plays
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu13.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
