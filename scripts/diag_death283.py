#!/usr/bin/env python3
"""diag_death283.py — replay from cp_deep and capture the exact death
sequence frame-by-frame (screenshots every 20f + flags/pair readings).
Read-only except the GS codes needed to reproduce the run's cheat state.
"""
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.agent.gameshark import GSCode                # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402
from validate_inv2 import PAIR, FLAGS, read_flags         # noqa: E402

OUT = "/home/z/my-project/work/msx_recomp/evidence/diag_death283"
os.makedirs(OUT, exist_ok=True)
RUN = "/home/z/my-project/work/msx_recomp/evidence/explore_invuln_inv1_20261021_060809"
IFRAME = 0xCA30C

p, fw = boot()
import json
rs = json.load(open(os.path.join(RUN, "runstate.json")))
f6, fe = rs["hp_pair"]
p.load_state("cp_deep")
g = ensure_mission(p, tries=4, log=print, want_hp_cands=False)
print("gate:", g.get("in_mission"), "flags:", read_flags(p))

session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
codes = [GSCode(f"8{PAIR[0]:07X} {f6 & 0xFFFF:04X}"),
         GSCode(f"8{PAIR[1]:07X} {fe & 0xFFFF:04X}")]
session.enable("d", codes)

prev = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
print("pair at start:", prev)
import numpy as np
for f in range(420):
    # same pit_mode advance as the runner: RIGHT + B cadence
    b = {"RIGHT"}
    if (f % 30) < 8:
        b.add("B")
    p.core.run_frame()
    p.core.set_buttons(b)
    session.gs.tick()
    if f % 10 == 0:
        fl = read_flags(p)
        pr = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        ifr = int(p.mem.u16(IFRAME))
        print(f"f={f} flags={fl} pair={pr} iframe={ifr}")
        if f % 20 == 0 or fl != 0xFF:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(
                    os.path.join(OUT, f"d_f{f:03d}.png"))
        if fl != 0xFF and f > 30:
            # capture the death sequence densely
            for k in range(1, 8):
                p.core.run_frame()
                session.gs.tick()
                rgb = p.core.frame_rgb()
                if rgb is not None:
                    Image.fromarray(rgb).save(
                        os.path.join(OUT, f"death_f{f:03d}_{k}.png"))
            break
print("done; files:", len(os.listdir(OUT)))
