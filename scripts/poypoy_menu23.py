#!/usr/bin/env python3
"""poypoy_menu23.py — glove confirm -> MATCH ENTRY, the blocker test.

Ladder so far (menu22 checkpoints): title --START--> MODE SELECT --B-->
PLAYER SET UP --B--> PLAYER ENTRY --B--> GLOVE SET UP (s3.ckpt).
GLOVE SET UP needs CROSS ("the [X] button to select") per player.
This probe: from s3.ckpt, alternate B-hold confirms (CPU gloves may
auto-confirm) up to 4 steps, then a long observation (+1800/+3600) and a
LEFT/RIGHT/none census at the final state. REAL_MATCH = directions register
(left_vs_right >> det) — the thing every probe since menu11 hunted for.
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

EVID = "/tmp/my-project/emu/games_psx/evidence/poypoy_menu23"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22"  # reuse the ladder workspace
S3 = os.path.join(WS, "s3_confirm3.ckpt")


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def snap_ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    chain = []
    ck = S3
    for i in range(4):
        p.load_state(ck)
        p.core.run(60, {"B"})
        p.core.run(480, set())
        ck = os.path.join(WS, f"m23_b{i}.ckpt")
        p.save_state(ck)
        snap(p, f"m23_b{i}.png")
        chain.append(ck)

    # long observation from the last checkpoint
    p.load_state(ck)
    p.core.run(1800, set())
    snap(p, "m23_obs1800.png")
    p.core.run(1800, set())
    snap(p, "m23_obs3600.png")
    last = os.path.join(WS, "m23_last.ckpt")
    p.save_state(last)

    # direction census at the final state
    cens = {}
    for probe, btns in (("none", set()), ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(last)
        p.core.run(120, set())
        p.core.run(90, btns)
        cens[probe] = snap_ram(p)
    p.load_state(last)
    p.core.run(120, set())
    p.core.run(90, set())
    n2 = snap_ram(p)
    det = int((n2 != cens["none"]).sum())
    cens_res = {
        "det_none": det,
        "left_vs_right": int((cens["left"] != cens["right"]).sum()),
        "left_vs_none": int((cens["left"] != n2).sum()),
    }
    cens_res["verdict"] = ("REAL_MATCH" if cens_res["left_vs_right"] > max(500, 5 * det)
                           else "not_yet")
    out["census"] = cens_res
    print(json.dumps(cens_res))
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu23.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
