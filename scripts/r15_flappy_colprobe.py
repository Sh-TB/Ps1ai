#!/usr/bin/env python3
"""r15_flappy_colprobe.py — read the REAL collision geometry from RAM.

Pools (source structs):
  PhysicsCompnt_t stride 10: [parent u8][gravity u8][pos i16 x,y][vel i16 x,y]
  ColShapeCompnt_t stride 8: [parent u8][w u8][h u8][pad][ptr -> Vec2]

Per frame during the first pipe approach:
  bird world pos/vel, every pipe shape (w,h,pos), my own AABB overlap
  verdict vs the game's actual death.
"""
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from hellopong_r12_lib import make_jrn, save_png           # noqa: E402
from r15_flappy_play import (bird_y, green_mask, gap_target,   # noqa
                             ground_ok, gameover_like)

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "flappybird.cue")
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")
OUT = os.path.join(REPO, "scratch", "round15_flappy", "colprobe")
WS = "/home/z/my-project/emu/games_homebrew/ws_r15_flappy"


def i16(buf, off):
    return int(np.frombuffer(buf, dtype="<i2", count=1, offset=off)[0])


def find_shape_pool(s):
    """Scan for ColShape entries: player (0,20,20) then pipes (odd,32,h)."""
    n = len(s)
    for base in range(0x1000, n - 21 * 8, 4):
        if s[base] != 0 or s[base + 1] != 20 or s[base + 2] != 20:
            continue
        ok = 0
        for k in range(1, 5):
            e = base + 8 * k
            if s[e + 1] == 32 and 1 <= s[e] <= 60:
                ok += 1
        if ok >= 3:
            return base
    return None


def find_physics_pool(s):
    """[parent 0][gravity 1] then plausible world pos; stride 10 or 12."""
    n = len(s)
    for stride in (10, 12):
        for base in range(0x1000, n - 30 * stride, 4):
            if s[base] != 0 or s[base + 1] != 1:
                continue
            px = i16(s, base + 2)
            py = i16(s, base + 4)
            if not (abs(px) < 25000 and abs(py) < 25000 and px == 0):
                continue
            ok = 0
            for k in range(1, 5):
                e = base + stride * k
                if 1 <= s[e] <= 60 and s[e + 1] == 0:
                    ok += 1
            if ok >= 3:
                return base, stride
    return None, None


def main():
    os.makedirs(OUT, exist_ok=True)
    jrn = make_jrn(OUT, "[fcol]")
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    jrn({"ev": "boot", "core": p.boot()})
    for _ in range(700):
        p.core.run(1, set())
    p.core.run(3, {"B"})
    p.core.run(4, set())
    p.core.run(2, {"B"})
    p.core.run(4, set())

    rows = []
    buttons = set()
    press = cool = 0
    by_prev = None
    dead_at = None
    for idx in range(400):
        p.core.run(1, buttons)
        fr = p.core.frame_rgb()
        by, npx = bird_y(fr)
        # simple mid hover servo
        vy_s = None if by is None or by_prev is None else by - by_prev
        by_prev = by
        if press > 0:
            press -= 1
            if press == 0:
                cool = 3
            buttons = {"B"}
        elif cool > 0:
            cool -= 1
            buttons = set()
        elif by is not None:
            if (by > 122 and (vy_s is None or vy_s >= -0.5)) or by > 134:
                buttons = {"B"}
                press = 1
            else:
                buttons = set()
        else:
            buttons = set()
        if gameover_like(fr) and dead_at is None:
            dead_at = idx
        if idx % 2:
            continue
        s = bytes(p.mem.snapshot())
        sp = find_shape_pool(s)
        pp = find_physics_pool(s)
        row = {"i": idx, "by_vis": None if by is None else round(by, 1),
               "dead": dead_at}
        if pp[0] is not None:
            base, stride = pp
            row["bird_world"] = (i16(s, base + 2), i16(s, base + 4))
            row["bird_vel"] = (i16(s, base + 6), i16(s, base + 8))
            row["pool"] = [hex(base), stride]
        if sp is not None:
            shapes = []
            for k in range(10):
                e = sp + 8 * k
                pid, w, h = s[e], s[e + 1], s[e + 2]
                ptr = int(np.frombuffer(s, dtype="<u4", count=1,
                                        offset=e + 4)[0])
                if ptr == 0 or ptr < 0x1000 or ptr > 0x200000:
                    break
                px = i16(s, ptr)
                py = i16(s, ptr + 2)
                # camera space
                cx = (px >> 5) + 160
                cy = (py >> 5) + 120
                shapes.append({"pid": pid, "w": w, "h": h,
                               "world": (px, py), "cam": (cx, cy)})
            row["shapes"] = shapes
            row["spool"] = hex(sp)
        rows.append(row)
    jrn({"ev": "rows", "rows": rows})
    save_png(OUT, p.core.frame_rgb(), "final.png")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
