#!/usr/bin/env python3
"""msx_wr9_cap2.py — Round 9 task 9-a (Issue #7): PIN-BASED arena capture.

Round-9 cap v1 lesson: entity-class gating (chopper/truck st families)
never confirms — the pins are held by OTHER enemy families (cap run:
px 2212 pin with round-monsters; T4: truck visible ~px 1500).  The
camera-lock itself is the gate signature: px pinned (<10 px window over
3 consecutive 60f chunks = 180 frames) while ALIVE at px >= 1400.

On pin: save_state `wr9_arena` + full census dump + PNG -> exit.
Death recovery = recover_v2 continues (counted+disclosed).
ONE beetle boot per process.  No RAM writes, no cheats.
Evidence: scratch/issue6_round9_msx/cap2/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                    # noqa: E402
from ps1play.agent.wagon import WagonSensor                 # noqa: E402
from issue4_controller import boot                          # noqa: E402
from mission import ensure_mission                          # noqa: E402
from run_mission1_legit import recover_v2                   # noqa: E402
from msx_wr9_arena import (TABLE, STRIDE, census, alive, px_of)  # noqa
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round9_msx"
OUTDIR = os.path.join(SCRATCH, "cap2")
CHNK = 60


def log(*a):
    print("[wr9-cap2]", *a, file=sys.stderr, flush=True)


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, name))
    return rgb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=800)
    ap.add_argument("--budget-s", type=float, default=500.0)
    ap.add_argument("--pin-px", type=float, default=1400.0)
    ap.add_argument("--pin-window", type=float, default=10.0)
    ap.add_argument("--pin-chunks", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(OUTDIR, "trace.jsonl"))

    p, fw = boot()
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    in_mission = bool(g.get("in_mission"))
    trace.write({"ev": "boot", "fw": fw, "in_mission": in_mission})
    log("booted", fw, "in_mission:", in_mission)
    if not in_mission:
        json.dump({"verdict": "GATE_FAILED", "fw": fw},
                  open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 2

    sensor = WagonSensor(m.ram, every=10)
    png(p, "cap2_start.png")
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()

    deaths = continues = 0
    pin_streak = 0
    win = []
    max_px = px_of(m)
    stop = None
    gate = None
    pins_seen = []

    for c in range(args.chunks):
        if time.time() - t0 > args.budget_s:
            stop = "BUDGET_WALL"
            break
        if not alive(m):
            deaths += 1
            trace.write({"ev": "death", "chunk": c,
                         "px": round(px_of(m), 1)})
            log("death", deaths, "at c", c, "px", round(px_of(m), 1))
            if deaths > 45:
                stop = "STOP_DEAD_LOOP"
                break
            recover_v2(p, log=log)
            ensure_mission(p, tries=4, log=log, want_hp_cands=False)
            continues += 1
            trace.write({"ev": "continue_accepted", "chunk": c,
                         "count": continues, "disclosed": True})
            pin_streak = 0
            win.clear()
            continue
        segs = policy.decide(CHNK, det)
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
            for _ev in sensor.poll(p.core.frames_run):
                pass
        px = px_of(m)
        max_px = max(max_px, px)
        win.append(px)
        if len(win) > args.pin_chunks:
            win.pop(0)
        trace.write({"ev": "chunk", "c": c, "frame": p.core.frames_run,
                     "px": round(px, 1), "score": int(m.u32(0x0EE318)),
                     "spawns": len(sensor.spawns)})
        if c % 80 == 0:
            png(p, f"cap2_c{c:04d}.png")
        if len(win) >= args.pin_chunks and px >= args.pin_px and \
                (max(win) - min(win)) < args.pin_window:
            pin_streak += 1
        else:
            pin_streak = 0
        if pin_streak >= 2:                      # >= 360 frames pinned
            slots = census(m)
            rgb = png(p, "wr9_arena_pin.png")
            gate = {"chunk": c, "px": round(px, 1),
                    "frame": p.core.frames_run,
                    "px_window": [round(min(win), 1), round(max(win), 1)],
                    "score": int(m.u32(0x0EE318)),
                    "php": int(m.u16(0x0CA2F6)),
                    "gren": int(m.u8(0x0EDCF4)),
                    "census_slots": slots[:24]}
            try:
                p.save_state("wr9_arena")
                gate["state_saved"] = True
            except Exception as e:                    # noqa: BLE001
                gate["state_saved"] = False
                gate["err"] = repr(e)[:120]
            trace.write({"ev": "ARENA_CAPTURED", **gate})
            log("ARENA pin captured c", c, "px", round(px, 1),
                "slots", len(slots), "saved:", gate.get("state_saved"))
            stop = "ARENA_CAPTURED"
            break

    rep = {"schema": "ps1play-wr9-cap2/1",
           "verdicts": {"BOOTED": True, "INPUT_RESPONSIVE": in_mission,
                        "STATE_CHANGE_CONFIRMED": max_px > 2.0},
           "stop_reason": stop or "BUDGET_CHUNKS",
           "frames": p.core.frames_run,
           "deaths": deaths, "continues_accepted": continues,
           "continues_disclosed": True,
           "max_px": round(max_px, 1), "final_px": round(px_of(m), 1),
           "arena": gate, "sensor_spawns": len(sensor.spawns),
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
    log("done:", rep["stop_reason"], "frames", rep["frames"],
        "max_px", rep["max_px"], "captured:", bool(gate))
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
