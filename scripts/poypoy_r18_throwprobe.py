#!/usr/bin/env python3
"""poypoy_r18_throwprobe.py — stage 2: which button THROWS a carried orb.

Measured so far: B tap near an orb = GRAB (orb lifted at t+90f). Now:
restore -> 30 idle -> B tap (grab) -> 60f settle (carry established) ->
[candidate tap | idle] -> 60f settle -> PNG + RAM diff vs a no-second-button
carry reference. Candidates: B (re-press), A, X, UP+B, LEFT+B (aimed throw).
The PNG after each candidate shows whether the orb left HARRY's hands.
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
RAMSZ = 2 * 1024 * 1024


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def carry_base(p):
    """restore -> 30 idle -> B tap -> 60 settle. Returns (ckpt_path)."""
    p.load_state(MATCH)
    p.core.run(30, set())
    p.core.run(2, {"B"})
    p.core.run(60, set())
    ck = os.path.join(EVID, "carry.ckpt")
    p.save_state(ck)
    return ck


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    ck = carry_base(p)
    snap(p, "t_carry.png")            # should show HARRY carrying the orb

    # reference: carry + 60 more idle
    p.load_state(ck)
    p.core.run(62, set())
    ref = ram(p)
    snap(p, "t_ref60.png")

    cands = [
        ("B_again", {"B"}, 0),
        ("A", {"A"}, 0),
        ("X", {"X"}, 0),
        ("UP_B", {"UP", "B"}, 0),
        ("LEFT_B", {"LEFT", "B"}, 0),
        ("B_dir_LEFT", {"B"}, 0),
    ]
    for name, tap, _ in cands:
        p.load_state(ck)
        p.core.run(30, set())
        p.core.run(2, tap)
        p.core.run(60, set())
        st = ram(p)
        snap(p, f"t_{name}.png")
        out[name] = int((st[:RAMSZ] != ref[:RAMSZ]).sum())

    # carrying + walking: does HARRY move slower? (LEFT while carry, 30f)
    p.load_state(ck)
    p.core.run(30, {"LEFT"})
    walk_carry = ram(p)
    out["carry_walk_LEFT_bytes"] = int((walk_carry[:RAMSZ] != ref[:RAMSZ]).sum())
    snap(p, "t_walk_left.png")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "throwprobe.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
