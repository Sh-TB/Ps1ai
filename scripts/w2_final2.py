#!/usr/bin/env python3
"""w2_final2.py — kill the mosque then INSTANTLY run right (no idle
windows — both previous runs died while idling post-kill).

Continuity filter for honest metrics: tile progress counts only while
|d(tile)| <= 2.5/frame from the previous counted frame (a real running
player at ~0.625 tile/f; a scene cut / restart / demo jump breaks the
chain and the counter resets to the current tile). PNGs every 100f.
Rescue taps on the 45f low-churn pause (continue sustain).
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


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def main(trav_frames=1500):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_final2")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    def frame_n(ch=1):
        p.core.run_frame()
        session.gs.tick()

    frame = 0

    # ---- POS: dismount + walk into the lob window ----
    for _ in range(10):
        p.core.set_buttons({"LEFT"})
        frame_n()
        frame += 1
    for _ in range(240):
        t = xfix(slot_words(m, 0))
        if 22.0 <= t <= 28.0:
            break
        p.core.set_buttons({"LEFT"} if t > 28.0 else {"RIGHT"})
        frame_n()
        frame += 1
    gp.log(f"POS: tile {xfix(slot_words(m, 0)):.1f}")
    score0 = m.u16(gp.A_SCORE)

    # ---- KILL: lob LEFT until +800 (delta 32) ----
    mosque_dead = False
    for k in range(45 * 80):
        cyc = k % 80
        btns = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
        p.core.set_buttons(btns)
        frame_n()
        frame += 1
        if k % 80 == 8:
            d = (m.u16(gp.A_SCORE) - score0) & 0xFF
            if d == 32:
                mosque_dead = True
                gp.log(f"f{frame}: +800 -> mosque down")
                gp.png(p, f"w2f2_mosque_f{frame:05d}.png")
                break
        if k % 240 == 0:
            gp.log(f"f{frame} KILL: score={m.u16(gp.A_SCORE)}")
    gp.log(f"KILL done: dead={mosque_dead} "
           f"score {score0}->{m.u16(gp.A_SCORE)}")

    # ---- INSTANT TRAVERSE ----
    out = open(os.path.join(EVID, "w2_final2.jsonl"), "w")
    chain_x = xfix(slot_words(m, 0))        # continuity anchor
    max_tile = chain_x
    max_prog = 0
    prog_at_max = 0
    low = 0
    pauses = 0
    stall = 0
    hop_until = -1
    last_x = None
    live_frames = 0
    for k in range(trav_frames):
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        ch = idle_churn(p, 20)
        # continuity: real traversal only
        if abs(ptile - chain_x) <= 2.5:
            chain_x = ptile
            if ptile > max_tile:
                max_tile = ptile
                prog_at_max = m.u16(gp.A_PROGRESS)
                live_frames += 1
        else:
            # cut: re-anchor (do not count the jump)
            chain_x = ptile
        prog = m.u16(gp.A_PROGRESS)
        if abs(prog - (prog_at_max if max_prog else prog)) < 999:
            pass
        max_prog = max(max_prog, prog) if abs(
            ptile - (last_x or ptile)) <= 2.5 else max_prog
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        if last_x is not None and abs(ptile - last_x) < 0.01:
            stall += 1
        else:
            stall = 0
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        last_x = ptile
        p.core.set_buttons(btns)
        frame_n()
        frame += 1
        out.write(json.dumps({"f": frame, "tile": ptile, "prog": prog,
                              "churn": ch}) + "\n")
        low = low + 1 if ch < 250 else 0
        if low == 30:
            pauses += 1
            gp.png(p, f"w2f2_pause{pauses}_f{frame:05d}.png")
            gp.log(f"f{frame}: pause #{pauses} (tile {ptile:.1f})")
        if low >= 45:
            p.core.run(10, {"START"})
            for _ in range(70):
                frame_n()
            frame += 80
            low = 0
            stall = 0
            hop_until = -1
            chain_x = xfix(slot_words(m, 0))   # re-anchor after respawn
        if k % 100 == 0:
            gp.png(p, f"w2f2_trav_f{frame:05d}.png")
            gp.log(f"f{frame} TRAV: tile={ptile:.1f} prog={prog} "
                   f"churn={ch} maxTile={max_tile:.1f} "
                   f"(prog@max={prog_at_max}) pauses={pauses}")
    out.close()
    gp.unfreeze(session, "w2_final2")
    gp.png(p, "w2f2_end.png")
    summary = {"mosque_dead": mosque_dead, "max_tile": max_tile,
               "prog_at_max_tile": prog_at_max, "max_prog": max_prog,
               "pauses": pauses, "live_frames": live_frames,
               "wall_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EVID, "w2_final2.json"), "w"),
              indent=1)
    gp.log("DONE:", json.dumps(summary))


if __name__ == "__main__":
    main()
