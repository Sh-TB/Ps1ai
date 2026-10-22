#!/usr/bin/env python3
"""w2_jump_truck.py — THE falsification test: the "camera gate" was a
u16-truncation phantom (MemoryView.u16 drops the high byte); the real
blocker = the armored truck as a solid obstacle at ~1126-1186px.

From `lock`: walk back LEFT to ~1080-1100, then RUN RIGHT with a FULL
jump timed to land past the truck's tail (~1190+). Several jump-start
offsets, one factor each. Metric: the player's TRUE x (u32 fixed read
via bytes, NOT the buggy u16!) and the camera u32.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402
from mission import idle_churn                  # noqa: E402

EVID = gp.EVID
TABLE, STRIDE = gp.TABLE, gp.STRIDE


def cam_u32(m):
    return int.from_bytes(m.ram[0x0CA2E0:0x0CA2E4].tobytes(), "little")


def player_x(m):
    """TRUE player x as float px: u32 fixed at slot0+0x78."""
    off = TABLE + 0x78
    w = int.from_bytes(m.ram[off:off + 4].tobytes(), "little")
    return w / 65536.0


def player_h(m):
    return int.from_bytes(m.ram[TABLE + 0x7E:TABLE + 0x80].tobytes(),
                          "little")


def main():
    p, fw = gp.boot()
    m = p.mem
    results = {}
    for name, back, lead in (("j1", 60, 6), ("j2", 90, 4),
                             ("j3", 40, 8), ("j4", 75, 5)):
        p.load_state("lock")
        session = gp.freeze_now(p, f"w2jt_{name}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        # walk back LEFT
        for _ in range(back):
            p.core.set_buttons({"LEFT"})
            p.core.run_frame()
            session.gs.tick()
        x0 = player_x(m)
        # run RIGHT; jump `lead` frames after the x passes 1100
        jumped = False
        max_x = x0
        t_jump = -1
        for k in range(360):
            px = player_x(m)
            if not jumped and px >= 1090 and k > back + 10:
                # lead frames of pure run, then B
                if t_jump < 0:
                    t_jump = k + lead
            if t_jump > 0 and k >= t_jump and not jumped:
                p.core.set_buttons({"RIGHT", "B"})
                jumped = True
            else:
                p.core.set_buttons({"RIGHT"})
            p.core.run_frame()
            session.gs.tick()
            max_x = max(max_x, player_x(m))
            if k % 60 == 0:
                gp.png(p, f"w2jt_{name}_f{k:03d}.png")
        results[name] = {"x0": round(x0, 1), "max_x": round(max_x, 1),
                         "cam_end": cam_u32(m) / 65536.0,
                         "h_end": player_h(m),
                         "crossed": max_x > 1195}
        gp.png(p, f"w2jt_{name}_end.png")
        r = results[name]
        gp.log(f"arm {name}: x {r['x0']} -> max {r['max_x']} "
               f"cam={r['cam_end']:.1f} crossed={r['crossed']}")
    gp.unfreeze(session, "w2jt")
    json.dump(results, open(os.path.join(EVID, "w2_jump_truck.json"),
                            "w"), indent=1)
    gp.log("saved w2_jump_truck.json")


if __name__ == "__main__":
    main()
