#!/usr/bin/env python3
"""poypoy_r17_firsttouch.py — Round 17: first pickup/throw attempts in the REAL match.

r17_stageselect proved REAL_MATCH (penguin arena, census left_vs_right
47,573 / 50,049, det 0). This probe runs a simple scripted behavior from
the mid-match checkpoint:
  walk UP toward the arena center, tap game-X (ps1play B = PSX CROSS =
  pickup/throw) on a cadence, snap every tap, then a throw attempt toward
  the nearest opponent direction.
Honest verdict: OPEN_LOOP_SCRIPTED (no vision servo yet) — evidence is
per-tap PNG frames showing whether HARRY picks a rock up / throws it.
"""
import json
import os
import sys
import time

from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r17_firsttouch"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22"
M2 = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22/r17_match_2400.ckpt"


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    p.load_state(M2)
    p.core.run(120, set())
    snap(p, "ft_restore.png")

    # approach: walk UP toward arena center in bursts, small B taps between
    for i in range(4):
        p.core.run(60, {"UP"})
        p.core.run(10, set())
        p.core.run(8, {"B"})          # game-X tap = pickup attempt
        p.core.run(90, set())
        snap(p, f"ft_walk_tap{i}.png")
    p.save_state(os.path.join(WS, "r17_ft_after_walk.ckpt"))

    # if carrying: throw toward the right (opponents cluster right in HUD view)
    p.core.run(40, {"RIGHT"})
    p.core.run(8, {"B"})
    p.core.run(120, set())
    snap(p, "ft_throw_right.png")

    # a slam/jump probe (game-□ = ps1play Y)
    p.core.run(10, {"Y"})
    p.core.run(90, set())
    snap(p, "ft_slam.png")

    # second walk + tap cycle from the fresh state
    p.load_state(os.path.join(WS, "r17_ft_after_walk.ckpt"))
    for i in range(4):
        p.core.run(50, {"UP", "RIGHT"})
        p.core.run(10, set())
        p.core.run(8, {"B"})
        p.core.run(80, set())
        snap(p, f"ft_walk2_tap{i}.png")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r17_firsttouch.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("frames captured:", len([f for f in os.listdir(EVID) if f.endswith('.png')]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
