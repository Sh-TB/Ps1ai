#!/usr/bin/env python3
"""w2_cross4.py — continuous dash with anti-mount hop + death forensics.

Known: holding RIGHT at the truck auto-mounts and stalls (cross2/3).
The boot-run evidence shows a continuous hold travels past the truck,
so the mount is escapable with a hop (B) when tile-x stalls.

Protocol: dismount 24f LEFT -> hold RIGHT; if tile-x unchanged for
45 frames while RIGHT is held -> B tap (18f). Record per frame: tile,
prog, slot0 alive; on player-gone transitions log tile + nearby
threats (the death cause context) + PNG.
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

EVID = gp.EVID
TABLE, STRIDE = gp.TABLE, gp.STRIDE
PX_PER_TILE = 24.39


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def main(frames=1200, dismount=24):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_cross4")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    for _ in range(dismount):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()

    out = open(os.path.join(EVID, "w2_cross4.jsonl"), "w")
    prev = {s: slot_words(m, s) for s in range(40)}
    deaths = 0
    prog_max = 0
    max_tile = 0.0
    frame = 0
    stall = 0
    hop_until = -1
    last_tile = -1.0
    prev_gone = True
    while frame < frames:
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        player_gone = w0[71] == 0
        threats = []
        for s in range(1, 40):
            w = slot_words(m, s)
            h, hp = w[63], w[71]
            php = prev[s][71]
            if hp != 0 and h > 64:
                threats.append((s, xfix(w), h))
            prev[s] = w
        # --- control
        if frame < hop_until:
            btns = {"RIGHT", "B"}
        elif player_gone:
            btns = set()
        else:
            btns = {"RIGHT"}
            if abs(ptile - last_tile) < 0.01:
                stall += 1
            else:
                stall = 0
            if stall >= 45:              # mounted / blocked: hop
                hop_until = frame + 18
                stall = 0
        last_tile = ptile
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        prog = m.u16(gp.A_PROGRESS)
        prog_max = max(prog_max, prog)
        if not player_gone:
            max_tile = max(max_tile, ptile)
        if player_gone and not prev_gone:
            deaths += 1
            gp.png(p, f"w2c4_death{deaths}_f{frame:05d}.png")
            gp.log(f"f{frame}: DEATH #{deaths} tile={ptile:.2f} "
                   f"prog={prog} "
                   f"threats={[(s, round(x, 1), h) for s, x, h in threats][:5]}")
        prev_gone = player_gone
        out.write(json.dumps({
            "f": frame, "p_tile": ptile, "gone": player_gone,
            "prog": prog, "hop": frame < hop_until,
            "threats": [[s, round(x, 1), h] for s, x, h in threats]})
            + "\n")
        frame += 1
        if frame % 200 == 0:
            gp.png(p, f"w2c4_f{frame:05d}.png")
            gp.log(f"f{frame} tile={ptile:.2f} prog={prog} "
                   f"maxTile={max_tile:.2f} deaths={deaths}")
    out.close()
    gp.unfreeze(session, "w2_cross4")
    gp.png(p, "w2c4_end.png")
    summary = {"frames": frames, "deaths": deaths, "prog_max": prog_max,
               "max_tile": max_tile,
               "wall_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EVID, "w2_cross4.json"), "w"),
              indent=1)
    gp.log("done:", json.dumps(summary))


if __name__ == "__main__":
    main()
