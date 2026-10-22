#!/usr/bin/env python3
"""w2_dodge_cross.py — THE CROSSING ATTEMPT: adaptive dodge + advance.

Evidence so far (this session):
  * mortars fall STRAIGHT DOWN (X fixed during fall, 16.16 fixed at
    slot+0x78/0x7A), height word slot+0x7E: ~180..210 -> 64 (ground),
    accelerating; fall time ~50..130f -> impact X is known EARLY
  * the barrage script hit X=914.8 (= the parked truck / player-on-
    truck at 37.5 tiles) repeatedly; earlier volleys walked 1067->915
  * dismount = 60f LEFT (previous session's pattern)

Protocol: dismount -> loop 1200f:
  every frame: scan 40 slots; airborne bomb = w[63] > 64 (0x7E)
    with the slot alive; predicted impact X = current X (vx~0)
  DODGE: if any bomb |X_bomb - X_player| < 55 -> hold direction AWAY
    from that bomb (left/right), else ADVANCE RIGHT
  record: spawns (X, hp, h0), player X, prog, deaths (prog drops),
  the tracked-vs-scripted answer falls out of the spawn X log.

EXPLORATION DISCLOSURE: hp_pair freeze active (arena deaths may still
bypass it; deaths are recorded, not hidden).
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
DODGE_DIST = 55.0


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def main(frames=1200):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_dodgecross")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    # dismount: 60f LEFT (previous session's proven pattern)
    for _ in range(60):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
    gp.png(p, "w2dc_dismounted.png")
    w0 = slot_words(m, 0)
    gp.log(f"dismounted: player X={xfix(w0):.1f}")

    out = open(os.path.join(EVID, "w2_dodge_cross.jsonl"), "w")
    spawns = open(os.path.join(EVID, "w2_dodge_spawns.jsonl"), "w")
    prev = {s: slot_words(m, s) for s in range(40)}
    deaths = 0
    prog_max = 0
    last_prog = m.u16(gp.A_PROGRESS)
    dodge_frames = 0
    frame = 0
    while frame < frames:
        w0 = slot_words(m, 0)
        px = xfix(w0)
        # --- find airborne bombs + new spawns
        threats = []
        for s in range(1, 40):
            w = slot_words(m, s)
            h, hp = w[63], w[71]
            php = prev[s][71]
            if php == 0 and hp != 0 and h > 64:
                spawns.write(json.dumps({
                    "f": frame, "slot": s, "X": xfix(w), "h0": h,
                    "hp": hp, "pX": px}) + "\n")
            if hp != 0 and h > 64:
                threats.append((s, xfix(w), h))
            prev[s] = w
        # --- decide
        btns = {"RIGHT"}
        if threats:
            near = [t for t in threats if abs(t[1] - px) < DODGE_DIST]
            if near:
                # away from the CLOSEST threat
                _, bx, _ = min(near, key=lambda t: abs(t[1] - px))
                btns = {"LEFT"} if bx < px else {"RIGHT"}
                dodge_frames += 1
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        prog = m.u16(gp.A_PROGRESS)
        if prog < last_prog - 60:
            deaths += 1
            gp.png(p, f"w2dc_death{deaths}_f{frame:05d}.png")
            gp.log(f"f{frame}: DEATH#{deaths} prog {last_prog}->{prog}")
        last_prog = prog
        prog_max = max(prog_max, prog)
        out.write(json.dumps({
            "f": frame, "pX": px, "prog": prog,
            "btn": "L" if btns == {"LEFT"} else
                   ("R" if btns == {"RIGHT"} else "?"),
            "threats": [[s, round(x, 1), h] for s, x, h in threats]})
            + "\n")
        frame += 1
        if frame % 200 == 0:
            gp.png(p, f"w2dc_f{frame:05d}.png")
            gp.log(f"f{frame} pX={px:.1f} prog={prog} "
                   f"threats={len(threats)} deaths={deaths} "
                   f"maxE={prog_max}")
    out.close()
    spawns.close()
    gp.unfreeze(session, "w2_dodgecross")
    gp.png(p, "w2dc_end.png")
    summary = {"frames": frames, "deaths": deaths,
               "prog_max": prog_max, "dodge_frames": dodge_frames,
               "wall_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EVID, "w2_dodge_cross.json"),
                            "w"), indent=1)
    gp.log("done:", json.dumps(summary))


if __name__ == "__main__":
    main()
