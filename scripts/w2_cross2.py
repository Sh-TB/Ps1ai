#!/usr/bin/env python3
"""w2_cross2.py — the calibrated crossing attempt.

Calibration from this session's evidence:
  * bomb X (slot+0x78/0x7A) is 16.16 fixed PIXELS; the player word
    (slot0 same offsets) is TILE-based fixed (37.5 tiles == 914.8 px
    bomb target -> 24.39 px/tile)
  * bombardment is SCRIPTED: it saturates X=914.8 px (the truck) and
    does NOT follow the player (40 spawns across a 1200f walk)
  * riding the truck = survived 1100f of direct saturation
  * historical deaths happened ON FOOT past the truck (prog 191..230)

Protocol: dismount (24f LEFT, stay clear of the X=0 water edge) ->
walk RIGHT with per-frame dodge (same-unit compare, 55 px) -> record
deaths, prog, maxE. Success = prog sustained above the historical
max (230) or monotonic prog gain to a new zone.
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
DODGE_DIST = 55.0


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def main(frames=1500, dismount=24):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_cross2")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    for _ in range(dismount):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
    w0 = slot_words(m, 0)
    gp.log(f"dismounted: player tile X={xfix(w0):.2f} "
           f"(~{xfix(w0) * PX_PER_TILE:.0f} px)")
    gp.png(p, "w2cx_dismounted.png")

    out = open(os.path.join(EVID, "w2_cross2.jsonl"), "w")
    spawns = open(os.path.join(EVID, "w2_cross2_spawns.jsonl"), "w")
    prev = {s: slot_words(m, s) for s in range(40)}
    deaths = 0
    prog_max = 0
    last_prog = m.u16(gp.A_PROGRESS)
    dodge_frames = 0
    frame = 0
    while frame < frames:
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        ppx = ptile * PX_PER_TILE
        threats = []
        for s in range(1, 40):
            w = slot_words(m, s)
            h, hp = w[63], w[71]
            php = prev[s][71]
            if php == 0 and hp != 0 and h > 64:
                spawns.write(json.dumps({
                    "f": frame, "slot": s, "X": xfix(w), "h0": h,
                    "hp": hp, "p_tile": ptile}) + "\n")
            if hp != 0 and h > 64:
                threats.append((s, xfix(w), h))
            prev[s] = w
        btns = {"RIGHT"}
        if threats:
            # only slots whose "height" is FALLING (bombs): a real
            # faller loses >=1 per frame; static entities keep h
            near = [(s, x, h) for s, x, h in threats
                    if abs(x - ppx) < DODGE_DIST and h < 230]
            if near:
                _, bx, _ = min(near, key=lambda t: abs(t[1] - ppx))
                btns = {"LEFT"} if bx < ppx else {"RIGHT"}
                dodge_frames += 1
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        prog = m.u16(gp.A_PROGRESS)
        if prog < last_prog - 60:
            deaths += 1
            gp.png(p, f"w2cx_death{deaths}_f{frame:05d}.png")
            gp.log(f"f{frame}: DEATH#{deaths} prog {last_prog}->{prog} "
                   f"tile={ptile:.1f}")
        last_prog = prog
        prog_max = max(prog_max, prog)
        out.write(json.dumps({
            "f": frame, "p_tile": ptile, "p_px": round(ppx, 1),
            "prog": prog,
            "btn": "L" if btns == {"LEFT"} else "R",
            "threats": [[s, round(x, 1), h] for s, x, h in threats]})
            + "\n")
        frame += 1
        if frame % 250 == 0:
            gp.png(p, f"w2cx_f{frame:05d}.png")
            gp.log(f"f{frame} tile={ptile:.1f} prog={prog} "
                   f"maxE={prog_max} deaths={deaths} "
                   f"dodge={dodge_frames}")
    out.close()
    spawns.close()
    gp.unfreeze(session, "w2_cross2")
    gp.png(p, "w2cx_end.png")
    summary = {"frames": frames, "deaths": deaths, "prog_max": prog_max,
               "dodge_frames": dodge_frames,
               "tile_final": ptile,
               "wall_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EVID, "w2_cross2.json"), "w"),
              indent=1)
    gp.log("done:", json.dumps(summary))


if __name__ == "__main__":
    main()
