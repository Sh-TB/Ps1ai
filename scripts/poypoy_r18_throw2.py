#!/usr/bin/env python3
"""poypoy_r18_throw2.py — decisive identical-schedule throw branches.

From carry.ckpt (HARRY holding the orb, t0):
  ref    : 30 idle, 2 idle, 60 idle      (no second button)
  bB     : 30 idle, 2 B,    60 idle
  bA     : 30 idle, 2 A,    60 idle
  bX     : 30 idle, 2 X,    60 idle
PNGs: +8/+16/+32 after the tap window and at the end — catches the throw
animation if any. RAM diff of each branch vs ref (same schedule) = causal.
Also a no-carry baseline: restore MATCH -> 92f idle -> PNG.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_throwprobe"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r18_match.ckpt")
CK = os.path.join(EVID, "carry.ckpt")
RAMSZ = 2 * 1024 * 1024


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # no-carry baseline of the same wall-time window
    p.load_state(MATCH)
    p.core.run(92, set())
    snap(p, "w_nocarry_92.png")
    nocarry = ram(p)

    p.load_state(CK)
    p.core.run(30, set())
    p.core.run(2, set())
    ref_mid = snap(p, "w_ref_m32.png")
    p.core.run(60, set())
    ref = ram(p)
    snap(p, "w_ref_92.png")
    out["ref_vs_nocarry"] = int((ref[:RAMSZ] != nocarry[:RAMSZ]).sum())

    for name, btn in (("bB", {"B"}), ("bA", {"A"}), ("bX", {"X"})):
        p.load_state(CK)
        p.core.run(30, set())
        p.core.run(2, btn)
        snap(p, f"w_{name}_m30.png")
        p.core.run(8, set())
        snap(p, f"w_{name}_m38.png")
        p.core.run(8, set())
        snap(p, f"w_{name}_m46.png")
        p.core.run(16, set())
        snap(p, f"w_{name}_m62.png")
        p.core.run(28, set())
        st = ram(p)
        snap(p, f"w_{name}_92.png")
        out[name] = int((st[:RAMSZ] != ref[:RAMSZ]).sum())

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "throw2.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
