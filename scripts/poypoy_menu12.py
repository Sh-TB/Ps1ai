#!/usr/bin/env python3
"""poypoy_menu12.py — in-battle input causality + first driven play.

Locked so far: X on the real MODE SELECT (menu@~1770 after one START
@480) starts a match (READY! at +300f; arm A diverges from the
attract at every sample).

This run:
  1. boot -> START -> menu (template) -> X -> wait 1500f (READY -> GO
     -> early battle) -> SAVE STATE battle_anchor
  2. causality arms: LEFT 120f | RIGHT 120f | none 120f (3 reloads)
  3. verdict: input_has_effect -> REAL PLAYABLE MATCH reached
  4. then drive the match ~3600f with a first battle policy
     (roam + X cadence), screenshots every 600f — the first ACTUAL
     PLAY of Poy Poy by the agent.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu12"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu12"
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
    p.core.run(20, {"X"})                    # enter exhibition
    p.core.run(1500, set())                  # READY -> GO -> battle
    p.save_state(CKPT)
    out["anchor"] = p.core.frames_run
    snap(p, "m12_anchor.png")
    print(json.dumps({"anchor": out["anchor"]}))

    # ---- causality arms ------------------------------------------------
    p.load_state(CKPT)
    p.core.run(120, {"LEFT"})
    s_l = snap(p, "m12_left.png")
    p.load_state(CKPT)
    p.core.run(120, {"RIGHT"})
    s_r = snap(p, "m12_right.png")
    p.load_state(CKPT)
    p.core.run(120, set())
    s_n = snap(p, "m12_none.png")
    out["causality"] = {
        "left_vs_none": round(diff(s_l, s_n) or 0, 2),
        "right_vs_none": round(diff(s_r, s_n) or 0, 2),
        "left_vs_right": round(diff(s_l, s_r) or 0, 2),
        "none_vs_anchor": round(diff(s_n, load_base(
            os.path.join(EVID, "m12_anchor.png"))) or 0, 2)}
    c = out["causality"]
    c["verdict"] = ("input_has_effect_REAL_MATCH"
                    if max(c["left_vs_none"], c["right_vs_none"]) > 3.0
                    else "input_ignored")
    print(json.dumps(out["causality"]))

    # ---- drive the match (first real play) ------------------------------
    plays = []
    p.load_state(CKPT)
    f_end = p.core.frames_run + 3600
    i = 0
    while p.core.frames_run < f_end:
        # simple first policy: roam toward the far side, X cadence to
        # grab/throw, direction swap every 40f
        btn = {"LEFT"} if (i // 40) % 2 == 0 else {"RIGHT"}
        p.core.run(40, btn)
        p.core.run(20, {"X"})
        if i % 10 == 0:
            img = snap(p, f"m12_play_{i:03d}.png")
            plays.append({"i": i, "frame": p.core.frames_run,
                          "mean": round(float(np.asarray(img).mean()), 1)})
            print(json.dumps(plays[-1]))
        i += 1
    out["play_samples"] = plays
    out["play_frames"] = 3600
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu12.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
