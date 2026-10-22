#!/usr/bin/env python3
"""w2_player_track.py — find the PLAYER entity robustly and follow the
dash past the truck.

Player-finder: while we hold RIGHT, the player's X-word increases.
Every 10 frames compare all slots' 0x78/0x7A u32 fixed X against
10 frames ago; the slot whose X grew by ~4-40 units (walking speed)
AND is not a known projectile pattern = the player candidate.
Also record churn (death/continue screens are near-static) and PNGs
every 40 frames. Purpose: WHERE does the player go past the truck,
and what does the camera (prog) do.
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


def xs(m):
    out = {}
    for s in range(40):
        base = TABLE + s * STRIDE
        w = m.ram[base:base + STRIDE].view("<u2").astype(np.int32)
        out[s] = ((int(w[61]) << 16) | int(w[60])) / 65536.0
    return out


def main(frames=800, dismount=24):
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_ptrack")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    for _ in range(dismount):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()

    rows = []
    prev_x = xs(m)
    frame = 0
    stall = 0
    last_x = None
    hop_until = -1
    while frame < frames:
        btns = {"RIGHT", "B"} if frame < hop_until else {"RIGHT"}
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        if frame % 10:
            continue
        cur = xs(m)
        # player candidate: X increased by 4..60 in 10f while RIGHT held
        cands = [(s, cur[s]) for s in range(40)
                 if 4 <= cur[s] - prev_x[s] <= 60]
        ch = idle_churn(p, 20)
        prog = m.u16(gp.A_PROGRESS)
        rows.append({"f": frame, "prog": prog, "churn": ch,
                     "moved": [(s, round(cur[s], 1)) for s, _ in cands],
                     "all_x": {s: round(cur[s], 1) for s in range(40)
                               if cur[s]}})
        prev_x = cur
        # stall detection on the primary mover (slot0 or first mover)
        cx = cur[0]
        if last_x is not None and abs(cx - last_x) < 0.01:
            stall += 1
        else:
            stall = 0
        last_x = cx
        if stall >= 5 and frame >= hop_until:   # 50f stalled: hop
            hop_until = frame + 18
            stall = 0
        if frame % 40 == 0:
            gp.png(p, f"w2pt_f{frame:05d}.png")
            gp.log(f"f{frame} prog={prog} churn={ch} "
                   f"movers={[(s, round(cur[s],1)) for s,_ in cands][:4]}")
    json.dump(rows, open(os.path.join(EVID, "w2_player_track.json"),
                         "w"), indent=0)
    gp.unfreeze(session, "w2_ptrack")
    gp.png(p, "w2pt_end.png")
    gp.log("done")


if __name__ == "__main__":
    main()
