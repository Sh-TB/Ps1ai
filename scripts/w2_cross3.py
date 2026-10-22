#!/usr/bin/env python3
"""w2_cross3.py — dash-through crossing with entity-level death
detection.

Changes vs cross2 (evidence-driven):
  * death = slot0 entity HP == 0 (player entity gone), NOT prog drops
    (the checkpoint is inside this zone; prog-based detection is blind)
  * no endless side-dodge: the saturation is a FIXED band at ~914.8 px
    (~55 px wide); running through takes ~4 frames at 15 px/f. Hold
    RIGHT except when an airborne bomb is within 60 px AND low
    (h < 110, impact imminent) — then wait for its impact, then dash.
  * record death tile + the exact bomb that was falling at death.
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
DANGER = 60.0


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
    session = gp.freeze_now(p, "w2_cross3")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    for _ in range(dismount):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()

    out = open(os.path.join(EVID, "w2_cross3.jsonl"), "w")
    spawns = open(os.path.join(EVID, "w2_cross3_spawns.jsonl"), "w")
    prev = {s: slot_words(m, s) for s in range(40)}
    deaths = 0
    prog_max = 0
    max_tile = 0.0
    frame = 0
    wait_frames = 0
    prev_gone = False
    while frame < frames:
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        ppx = ptile * PX_PER_TILE
        player_gone = w0[71] == 0
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

        if player_gone:
            btns = set()          # dead/respawning: wait it out
        else:
            btns = {"RIGHT"}
            imminent = [t for t in threats
                        if abs(t[1] - ppx) < DANGER and t[2] < 110]
            if imminent and ppx < min(t[1] for t in imminent):
                # bomb right of us, about to impact: wait, then dash
                btns = set()
                wait_frames += 1
        if player_gone and not prev_gone:
            deaths += 1
            gp.png(p, f"w2c3_death{deaths}_f{frame:05d}.png")
            gp.log(f"f{frame}: PLAYER GONE #{deaths} tile={ptile:.1f} "
                   f"prog={m.u16(gp.A_PROGRESS)} "
                   f"threats={[(s, round(x, 1), h) for s, x, h in threats][:4]}")
        prev_gone = player_gone
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        prog = m.u16(gp.A_PROGRESS)
        prog_max = max(prog_max, prog)
        if not player_gone:
            max_tile = max(max_tile, ptile)
        out.write(json.dumps({
            "f": frame, "p_tile": ptile, "gone": player_gone,
            "prog": prog,
            "threats": [[s, round(x, 1), h] for s, x, h in threats]})
            + "\n")
        frame += 1
        if frame % 250 == 0:
            gp.png(p, f"w2c3_f{frame:05d}.png")
            gp.log(f"f{frame} tile={ptile:.1f} prog={prog} "
                   f"maxE={prog_max} maxTile={max_tile:.1f} "
                   f"deaths={deaths} wait={wait_frames}")
    out.close()
    spawns.close()
    gp.unfreeze(session, "w2_cross3")
    gp.png(p, "w2c3_end.png")
    summary = {"frames": frames, "deaths": deaths, "prog_max": prog_max,
               "max_tile": max_tile, "wait_frames": wait_frames,
               "wall_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EVID, "w2_cross3.json"), "w"),
              indent=1)
    gp.log("done:", json.dumps(summary))


if __name__ == "__main__":
    main()
