#!/usr/bin/env python3
"""poypoy_r18_reenter.py — re-enter the real match from the surviving ladder.

The /tmp duplicate-tree cleanup deleted the r17_match_*.ckpt states (they
lived only under the /tmp workspace). The ladder checkpoints (m23_b0 =
STAGE SELECT with the arena thumbnails) survive in the home tree, so the
match is re-entered the verified way: UP x2 + B-confirm, 1200 frames of
intro, checkpoint saved under the home workspace.

Verdict REAL_MATCH requires the round-17 direction census to pass
(left_vs_right >> det_none).
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_calib"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
B0 = os.path.join(WS, "m23_b0.ckpt")


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def census(p, ckpt):
    snaps = {}
    for name, btns in (("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(ckpt)
        p.core.run(120, set())
        p.core.run(90, btns)
        snaps[name] = ram(p)
    p.load_state(ckpt)
    p.core.run(120, set())
    p.core.run(90, set())
    n2 = ram(p)
    det = int((n2 != snaps["left"]).sum())
    out = {
        "det_none": det,
        "left_vs_right": int((snaps["left"] != snaps["right"]).sum()),
        "left_vs_none": int((snaps["left"] != n2).sum()),
    }
    out["verdict"] = ("REAL_MATCH" if out["left_vs_right"] > max(500, 5 * out["det_none"])
                      else "not_yet")
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    p.load_state(B0)
    p.core.run(120, set())
    snap(p, "re_b0_restore.png")

    for _ in range(2):
        p.core.run(20, set())
        p.core.run(30, {"UP"})
        p.core.run(120, set())
    snap(p, "re_before_confirm.png")
    p.core.run(60, {"B"})
    p.core.run(1200, set())
    snap(p, "re_match_1200.png")
    ck = os.path.join(WS, "r18_match.ckpt")
    p.save_state(ck)
    out["checkpoint"] = ck

    out["census"] = census(p, ck)
    snap(p, "re_census.png")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r18_reenter.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out["census"], indent=1))
    return 0 if out["census"]["verdict"] == "REAL_MATCH" else 1


if __name__ == "__main__":
    sys.exit(main())
