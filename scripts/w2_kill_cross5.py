#!/usr/bin/env python3
"""w2_kill_cross5.py — the full next-experiment: kill the rain source
(mosque) with a REACHING grenade volley, measure rain-stop with the
clean faller signature, then cross past the wreck and forensically
examine the 1164px barrier.

Phases (all from `arena2`, freeze on):
  POS   dismount (10f, the ejection carries the player left) then
        ADAPTIVE walk into the lob window tile 22..28
  KILL  lob LEFT (A, 80f period) up to 45 grenades; success signal =
        score jump >= 700 in one event (the +800 mosque) — check every
        10f; also watch slot6 HP and screenshot every 120f
  RAIN  300f idle: faller-rate at X~915 (the rain signature) — compare
        vs the pre-kill baseline recorded during POS/KILL
  CROSS hop-anti-stall walk RIGHT: max tile, prog; on a >= 90f stall at
        the far right: dump slots + PNG (barrier forensics)
  death/continue pause detector: churn < 250 sustained 30f
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
            if hp and 0 < ph - h <= 20 and h > 60 and ph > 70 and \
                    w[71] not in (0,):
                evs.append({"tag": tag, "f": frame, "slot": s,
                            "X": round(xfix(w), 1), "h": h, "hp": hp})
            self.prev[s] = w
        return evs


def main():
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_kc5")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    rain = Rain(m)
    out = open(os.path.join(EVID, "w2_kc5.jsonl"), "w")
    frame = 0
    pause_deaths = 0
    low_churn = 0

    def churn_tick():
        nonlocal low_churn, pause_deaths
        ch = idle_churn(p, 20)
        low_churn = low_churn + 1 if ch < 250 else 0
        if low_churn == 30:
            pause_deaths += 1
            gp.png(p, f"w2kc5_pause{pause_deaths}_f{frame:05d}.png")
            gp.log(f"f{frame}: death/continue pause #{pause_deaths} "
                   f"(churn={ch})")
        return ch

    # ---- POS: dismount + adaptive walk into the lob window ----
    for _ in range(10):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    for _ in range(240):                      # bounded positioning
        w0 = slot_words(m, 0)
        t = xfix(w0)
        if 22.0 <= t <= 28.0:
            break
        btns = {"LEFT"} if t > 28.0 else {"RIGHT"}
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        churn_tick()
        frame += 1
    w0 = slot_words(m, 0)
    gp.log(f"POS: player tile {xfix(w0):.1f}")
    score0 = m.u16(gp.A_SCORE)

    # ---- KILL: lob LEFT until +800 or budget ----
    mosque_dead = False
    n_grenades = 0
    kill_frames = 45 * 80
    for k in range(kill_frames):
        cyc = k % 80
        btns = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
        if cyc < 8:
            n_grenades += 1
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "KILL"):
            out.write(json.dumps(e) + "\n")
        frame += 1
        churn_tick()
        if k % 10 == 0:
            sc = m.u16(gp.A_SCORE)
            if (sc - score0) % 256 >= 200 and \
                    (sc - score0) % 256 <= 120:      # +800 low-byte wrap
                pass
        if k % 80 == 8:                          # right after a lob
            sc = m.u16(gp.A_SCORE)
            d = (sc - score0) & 0xFF
            if d >= 0x20 and d <= 0x60:          # +800 = 0x320 -> low
                # +800 low byte delta = 0x20 (800 & 0xFF = 0x20)
                gp.log(f"f{frame}: score delta {d} (+800?) -> mosque!")
                mosque_dead = True
                gp.png(p, f"w2kc5_mosque_f{frame:05d}.png")
                break
        if k % 240 == 0:
            gp.png(p, f"w2kc5_kill_f{frame:05d}.png")
            gp.log(f"f{frame} KILL: grenades={n_grenades} "
                   f"score={m.u16(gp.A_SCORE)} (start {score0})")
    gp.png(p, "w2kc5_kill_end.png")
    score1 = m.u16(gp.A_SCORE)
    gp.log(f"KILL done: mosque_dead={mosque_dead} score {score0}->"
           f"{score1} grenades={n_grenades}")

    # ---- RAIN: 300f idle measurement ----
    pre_rate = None
    post_events = []
    for k in range(300):
        p.core.set_buttons(set())
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "RAIN"):
            post_events.append(e)
            out.write(json.dumps(e) + "\n")
        frame += 1
        churn_tick()
    n915 = sum(1 for e in post_events if abs(e["X"] - 915) < 5)
    gp.log(f"RAIN: {len(post_events)} fallers, {n915} at ~915 "
           f"(rain {'ACTIVE' if n915 > 10 else 'QUIET'})")

    # ---- CROSS: hop-anti-stall walk right + barrier forensics ----
    stall = 0
    last_x = None
    hop_until = -1
    max_tile = 0.0
    forensics_done = False
    for k in range(900):
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        if last_x is not None and abs(ptile - last_x) < 0.01:
            stall += 1
        else:
            stall = 0
            max_tile = max(max_tile, ptile)
        last_x = ptile
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        if stall >= 90 and not forensics_done:
            forensics_done = True
            gp.png(p, f"w2kc5_barrier_f{frame:05d}.png")
            dump = {s: {"X": round(xfix(slot_words(m, s)), 1),
                        "hp": slot_words(m, s)[71],
                        "h": slot_words(m, s)[63]}
                    for s in range(40) if slot_words(m, s)[71]}
            gp.log(f"f{frame} BARRIER at tile {ptile:.1f}: slots=" +
                   json.dumps(dump))
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "CROSS"):
            out.write(json.dumps(e) + "\n")
        frame += 1
        churn_tick()
        if k % 150 == 0:
            gp.png(p, f"w2kc5_cross_f{frame:05d}.png")
            gp.log(f"f{frame} CROSS: tile={ptile:.1f} "
                   f"prog={m.u16(gp.A_PROGRESS)} "
                   f"maxTile={max_tile:.1f}")
    out.close()
    gp.unfreeze(session, "w2_kc5")
    gp.png(p, "w2kc5_end.png")
    json.dump({"mosque_dead": mosque_dead, "score0": score0,
               "score1": score1, "grenades": n_grenades,
               "rain_events_300f": len(post_events),
               "rain_at_915": n915, "max_tile": max_tile,
               "pause_deaths": pause_deaths,
               "wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_kc5.json"), "w"), indent=1)
    gp.log("done:", json.dumps({"mosque_dead": mosque_dead,
                                "rain915": n915, "max_tile": max_tile,
                                "deaths": pause_deaths}))


if __name__ == "__main__":
    main()
