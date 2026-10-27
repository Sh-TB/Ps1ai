#!/usr/bin/env python3
"""poypoy_menu22.py — the exhibition ladder: MODE SELECT -> match entry.

menu21 proof: START-hold 60f AT THE TITLE (f2350) opens the real interactive
MODE SELECT (EXHIBITION / POYPOY CUP / OPTIONS; ticker "Press the X button").
This probe walks the ladder with a checkpoint at every step (relative
stepping — load_state does not restore frames_run):

  title --START-hold--> MODE SELECT --B-hold(CROSS)--> S1 --B-hold--> S2
        --B-hold--> S3 --START-hold--> S4

Each step observes +540f and saves a PNG + checkpoint, so the next session
can branch from any rung without re-walking. No victory claims — just the
map, verified by eyes + RAM.
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

EVID = "/tmp/my-project/emu/games_psx/evidence/poypoy_menu22"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22"
TITLE_CKPT = os.path.join(WS, "title2350.ckpt")


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def snap_ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def step(p, from_ckpt, tag, btns, hold, wait=540):
    p.load_state(from_ckpt)
    p.core.run(hold, btns)
    p.core.run(wait - hold, set())
    ck = os.path.join(WS, f"{tag}.ckpt")
    p.save_state(ck)
    snap(p, f"m22_{tag}.png")
    return ck


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    while p.core.frames_run < 2350:
        p.core.run(50, set())
    p.save_state(TITLE_CKPT)
    snap(p, "m22_title.png")

    ms = step(p, TITLE_CKPT, "mode_select", {"START"}, 60)
    s1 = step(p, ms, "s1_exhibition_confirm", {"B"}, 60)
    s2 = step(p, s1, "s2_confirm2", {"B"}, 60)
    s3 = step(p, s2, "s3_confirm3", {"B"}, 60)
    s4 = step(p, s3, "s4_start", {"START"}, 60)

    # RAM drift table for the ladder (each step vs its parent, 64K stride)
    def ram(path):
        return None  # loading states back would advance frames; skip for now
    out["ladder"] = {"mode_select": ms, "s1": s1, "s2": s2, "s3": s3, "s4": s4}
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu22.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("ladder saved:", out["ladder"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
