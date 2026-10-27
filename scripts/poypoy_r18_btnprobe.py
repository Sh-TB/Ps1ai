#!/usr/bin/env python3
"""poypoy_r18_btnprobe.py — clean same-schedule button causality.

calib3's tap probes compared 92-frame runs against a 60-frame idle (schedule
mismatch -> polluted). This probe: every run is EXACTLY restore -> 30 idle ->
30 [tap@f0+2f hold | idle] -> snap. Diff vs idle run = causal effect of the
button; PNG shows the visual result (grab = block overhead, throw = block flies).

Probed: B (cross) short, B held 30f, A (circle) short, X (square) short,
UP+B (throw upward?), and a 90f B press near an orb.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_btnprobe"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r18_match.ckpt")
RAMSZ = 2 * 1024 * 1024


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def run(p, tap, hold, tail):
    """restore -> 30 idle -> hold frames of tap -> tail idle. Always 30+30 after idle."""
    p.load_state(MATCH)
    p.core.run(30, set())
    p.core.run(hold, tap)
    p.core.run(tail, set())
    return ram(p)


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # idle reference: 30+30 (2f idle + 28 idle) = same shape as taps
    idle = run(p, set(), 2, 28)
    snap(p, "b_idle.png")
    idle2 = run(p, set(), 2, 28)
    out["ambient"] = int((idle[:RAMSZ] != idle2[:RAMSZ]).sum())

    probes = [
        ("B_short", {"B"}, 2, 28),
        ("B_hold", {"B"}, 30, 0),
        ("A_short", {"A"}, 2, 28),
        ("X_short", {"X"}, 2, 28),
        ("UP_B", {"UP", "B"}, 2, 28),
    ]
    for name, tap, hold, tail in probes:
        st = run(p, tap, hold, tail)
        snap(p, f"b_{name}.png")
        out[name] = int((st[:RAMSZ] != idle[:RAMSZ]).sum())

    # a longer tail for B: does a throw animation play? (60f more after tap)
    st = run(p, {"B"}, 2, 88)
    snap(p, "b_B_short_t90.png")
    out["B_short_t90"] = int((st[:RAMSZ] != idle[:RAMSZ]).sum())

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "btnprobe.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
