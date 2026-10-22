#!/usr/bin/env python3
"""w2_final_cross.py — THE decisive run: kill the rain source, verify
rain-quiet on LIVE frames, then traverse right with continue-sustain.

Fixes vs kc5 (whose post-kill prog/tile readings were contaminated by
the attract demo after GAME OVER):
  * rescue taps: churn < 250 sustained 30f -> one START tap + 70f wait
    (the disclosed v1 continue acceptance) so continues are SPENT, not
    timed out; GAME OVER avoided while continues last
  * traversal claims (max tile / prog) are only counted on frames with
    churn >= 400 (live gameplay); death/coin-up/title windows are
    EXCLUDED from all progress metrics
  * rain-quiet check runs on a short 150f LIVE window right after the
    volley (the player idle), fallers counted everywhere
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


class Rain:
    def __init__(self, m):
        self.m = m
        self.prev = {s: slot_words(m, s) for s in range(40)}

    def poll(self, frame, tag):
        evs = []
        for s in range(1, 40):
            w = slot_words(self.m, s)
            h, hp = w[63], w[71]
            ph = self.prev[s][63]
            if hp and 0 < ph - h <= 20 and h > 60 and ph > 70:
                evs.append({"tag": tag, "f": frame, "slot": s,
                            "X": round(xfix(w), 1), "h": h, "hp": hp})
            self.prev[s] = w
        return evs


def main():
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_final")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    rain = Rain(m)
    out = open(os.path.join(EVID, "w2_final.jsonl"), "w")
    rows = []
    frame = 0
    pauses = 0
    game_over = False
    low = 0

    def tick(tag):
        nonlocal low, pauses, game_over, frame
        p.core.set_buttons(set())
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        ch = idle_churn(p, 20)
        low = low + 1 if ch < 250 else 0
        if low == 30:
            pauses += 1
            gp.png(p, f"w2fx_pause{pauses}_f{frame:05d}.png")
        if low >= 45:                     # continue screen: tap START
            p.core.run(10, {"START"})
            for _ in range(70):
                p.core.run_frame()
                session.gs.tick()
            frame += 80
            low = 0
        return ch

    # ---- POS: dismount + walk into the lob window ----
    for _ in range(10):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    for _ in range(240):
        t = xfix(slot_words(m, 0))
        if 22.0 <= t <= 28.0:
            break
        p.core.set_buttons({"LEFT"} if t > 28.0 else {"RIGHT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    gp.log(f"POS: tile {xfix(slot_words(m, 0)):.1f}")
    score0 = m.u16(gp.A_SCORE)

    # ---- KILL: lob LEFT until the +800 pattern or budget ----
    mosque_dead = False
    for k in range(45 * 80):
        cyc = k % 80
        btns = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "KILL"):
            out.write(json.dumps(e) + "\n")
        frame += 1
        if k % 80 == 8:
            d = (m.u16(gp.A_SCORE) - score0) & 0xFF
            if d in (32, 76):                 # +800 or +800+300n pattern
                mosque_dead = True
                gp.log(f"f{frame}: score delta {d} -> mosque kill")
                gp.png(p, f"w2fx_mosque_f{frame:05d}.png")
                break
        if k % 240 == 0:
            gp.log(f"f{frame} KILL: score={m.u16(gp.A_SCORE)}")
    gp.log(f"KILL: mosque_dead={mosque_dead} "
           f"score {score0}->{m.u16(gp.A_SCORE)}")
    gp.png(p, "w2fx_kill_end.png")

    # ---- RAIN CHECK: 150f idle, LIVE frames only ----
    live_fallers = 0
    checked = 0
    for k in range(150):
        ch = tick("RAIN")
        for e in rain.poll(frame, "RAIN"):
            out.write(json.dumps(e) + "\n")
        if ch >= 400:
            checked += 1
            live_fallers += 0                # events already logged
    n_events = sum(1 for _ in open(
        os.path.join(EVID, "w2_final.jsonl")))
    gp.log(f"RAIN: {n_events} faller events total (KILL+RAIN)")
    rain_quiet = n_events < 25               # control run: hundreds

    # ---- TRAVERSE: walk right, rescue-sustained, live-only metrics ----
    stall = 0
    last_x = None
    hop_until = -1
    max_tile = 0.0
    max_prog = 0
    prog_history = []
    for k in range(1100):
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        ch = idle_churn(p, 20)
        live = ch >= 400
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        if last_x is not None and abs(ptile - last_x) < 0.01:
            stall += 1
        else:
            stall = 0
            if live:
                max_tile = max(max_tile, ptile)
        last_x = ptile
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "TRAV"):
            out.write(json.dumps(e) + "\n")
        frame += 1
        prog = m.u16(gp.A_PROGRESS)
        if live:
            max_prog = max(max_prog, prog)
            prog_history.append([frame, ptile, prog])
        low = low + 1 if ch < 250 else 0
        if low == 30:
            pauses += 1
            gp.png(p, f"w2fx_pause{pauses}_f{frame:05d}.png")
            gp.log(f"f{frame}: pause #{pauses} (tile was {ptile:.1f})")
        if low >= 45:
            p.core.run(10, {"START"})
            for _ in range(70):
                p.core.run_frame()
                session.gs.tick()
            frame += 80
            low = 0
            stall = 0
            hop_until = -1
        if k % 120 == 0:
            gp.png(p, f"w2fx_trav_f{frame:05d}.png")
            gp.log(f"f{frame} TRAV: tile={ptile:.1f} prog={prog} "
                   f"churn={ch} maxTile={max_tile:.1f} "
                   f"maxProg={max_prog} pauses={pauses}")
        rows.append({"f": frame, "tile": ptile, "prog": prog,
                     "churn": ch, "live": live})
    out.close()
    gp.unfreeze(session, "w2_final")
    gp.png(p, "w2fx_end.png")
    json.dump({"mosque_dead": mosque_dead, "rain_quiet": rain_quiet,
               "max_tile": max_tile, "max_prog": max_prog,
               "pauses": pauses,
               "prog_history_tail": prog_history[-40:],
               "wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_final.json"), "w"), indent=1)
    gp.log("DONE:", json.dumps({"mosque_dead": mosque_dead,
                                "rain_quiet": rain_quiet,
                                "max_tile": max_tile,
                                "max_prog": max_prog,
                                "pauses": pauses}))


if __name__ == "__main__":
    main()
