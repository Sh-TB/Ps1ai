#!/usr/bin/env python3
"""poypoy_menu21.py — press START at the REAL title window (f~2400).

Passive timeline (menu20): boot auto-plays everything — KONAMI @1200,
title @2400, attract demo by ~f3300 ("GO!!"). The earlier gate walk pressed
STARTs only AFTER the splash (all auto) and never at the title window.
This probe anchors at f2350 (title) and arms: none / START-hold-60f /
X-hold-60f / SQUARE-hold-60f, sampling PNG + RAM delta at +240/+600/+1200.
MENU_REACHED = a stable, input-responsive state distinct from the demo.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/tmp/my-project/emu/games_psx/evidence/poypoy_menu21"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu21"
TITLE_CKPT = os.path.join(WS, "title2350.ckpt")


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def snap_ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def arm(p, name, btns, hold, base_ram):
    p.load_state(TITLE_CKPT)
    rel = 0
    if hold:
        p.core.run(hold, btns)
        rel += hold
    out = {}
    for f in (240, 600, 1200):
        if f > rel:
            p.core.run(f - rel, set())
            rel = f
        ram = snap_ram(p)
        base = base_ram.get(f)
        out[f"ram_delta_f{f}"] = int((ram != base).sum()) if base is not None else None
        out[f"png_f{f}"] = f"m21_{name}_f{f}.png"
        snap(p, out[f"png_f{f}"])
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    while p.core.frames_run < 2350:
        p.core.run(50, set())
    p.save_state(TITLE_CKPT)
    snap(p, "m21_title2350.png")
    # baseline: no input (demo should auto-start ~f3000)
    base_ram = {}
    p.load_state(TITLE_CKPT)
    rel = 0
    for f in (240, 600, 1200):
        p.core.run(f - rel, set())
        rel = f
        base_ram[f] = snap_ram(p)
    p.load_state(TITLE_CKPT)
    p.core.run(240, set())
    n2 = snap_ram(p)
    out["baseline_det_f240"] = int((n2 != base_ram[240]).sum())
    arms = {
        "none": (set(), 0),
        "starthold": ({"START"}, 60),
        "bhold": ({"B"}, 60),      # B = PSX CROSS (the disc's "select" per on-screen help)
        "xhold": ({"X"}, 60),      # X = PSX TRIANGLE (mirror mapping — flappy lesson)
    }
    results = {}
    for name, (btns, hold) in arms.items():
        results[name] = arm(p, name, btns, hold, base_ram)
        print(name, "deltas", results[name]["ram_delta_f240"],
              results[name]["ram_delta_f600"], results[name]["ram_delta_f1200"])
    out["arms"] = results
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu21.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
