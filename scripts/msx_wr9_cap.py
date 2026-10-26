#!/usr/bin/env python3
"""msx_wr9_cap.py — Round 9 task 9-a (Issue #7 WAGON RUN): capture the
town-arena set-piece state `wr9_arena`.

The round-9 T4 sensor run (scratch/issue6_round9_msx/arena_t4/, 55,524
frames, 30 disclosed continues) walked M1 to the pin point px ~1500-1600
(progress_c0450.png shows the ARMORED TRUCK on screen) but the strict
2x360f pin detector never fired before the chunk budget.  This capture
loosens exactly one thing: the arena is defined as

    alive AND px >= CAPT_PX AND (choppers OR trucks) in the entity census

held for CONFIRM consecutive chunks.  On confirm: save_state `wr9_arena`
+ census + redness PNG -> exit.  Death recovery = recover_v2 START taps
(continues counted+disclosed, the v1 honesty rule).

ONE beetle boot per process.  No RAM writes, no cheats.  Evidence:
scratch/issue6_round9_msx/cap/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                    # noqa: E402
from ps1play.agent.wagon import WagonSensor                 # noqa: E402
from issue4_controller import boot                          # noqa: E402
from mission import ensure_mission                          # noqa: E402
from run_mission1_legit import recover_v2                   # noqa: E402
from msx_wr9_arena import (CHOPPER_ST, TRUCK_ST, FALLER_ST,  # noqa: E402
                           TABLE, STRIDE, FLAGS_WORD, PLAYER_HP,
                           A_SCORE, GRENADES, census, classify,
                           redness, alive, px_of)
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from PIL import Image                                       # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round9_msx"
OUTDIR = os.path.join(SCRATCH, "cap")
CHNK = 60


def log(*a):
    print("[wr9-cap]", *a, file=sys.stderr, flush=True)


def png(p, name, outdir):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))
    return rgb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=760)
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--capt-px", type=float, default=1380.0)
    ap.add_argument("--confirm", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(OUTDIR, "trace.jsonl"))

    p, fw = boot()                                   # ONE boot
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
    png(p, "cap_start.png", OUTDIR)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()

    deaths = continues = 0
    confirm = 0
    max_px = px_of(m)
    stop = None
    gate = None

    for c in range(args.chunks):
        if time.time() - t0 > args.budget_s:
            stop = "BUDGET_WALL"
            break
        if not alive(m):
            deaths += 1
            trace.write({"ev": "death", "chunk": c, "px": round(px_of(m), 1),
                         "score": int(m.u32(A_SCORE))})
            log("death", deaths, "at c", c, "px", round(px_of(m), 1))
            if deaths > 40:
                stop = "STOP_DEAD_LOOP"
                break
            recover_v2(p, log=log)
            g2 = ensure_mission(p, tries=4, log=log, want_hp_cands=False)
            continues += 1
            trace.write({"ev": "continue_accepted", "chunk": c,
                         "count": continues, "disclosed": True,
                         "method": "v1_recover_start_taps",
                         "in_mission": bool(g2.get("in_mission"))})
            confirm = 0
            continue
        segs = policy.decide(CHNK, det)
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
            for ev in sensor.poll(p.core.frames_run):
                pass
        px = px_of(m)
        max_px = max(max_px, px)
        slots = census(m)
        ch, tr, fl = classify(slots)
        trace.write({"ev": "chunk", "c": c, "frame": p.core.frames_run,
                     "px": round(px, 1), "score": int(m.u32(A_SCORE)),
                     "choppers": len(ch), "trucks": len(tr),
                     "fallers": len(fl), "spawns": len(sensor.spawns)})
        if c % 60 == 0:
            png(p, f"cap_c{c:04d}.png", OUTDIR)
        # ---- arena capture ----
        if px >= args.capt_px and (ch or tr):
            confirm += 1
            if confirm == 1:
                png(p, f"cap_cand_c{c:04d}.png", OUTDIR)
            trace.write({"ev": "arena_candidate", "c": c,
                         "px": round(px, 1), "confirm": confirm,
                         "choppers": ch[:6], "trucks": tr[:6]})
            if confirm >= args.confirm:
                rgb = png(p, "wr9_arena_census.png", OUTDIR)
                red = [{**x, "red": redness(rgb, x["sx"])} for x in ch] \
                    if rgb is not None else ch
                gate = {"chunk": c, "px": round(px, 1),
                        "frame": p.core.frames_run,
                        "choppers": red, "trucks": tr, "fallers": len(fl),
                        "score": int(m.u32(A_SCORE)),
                        "php": int(m.u16(PLAYER_HP)),
                        "gren": int(m.u8(GRENADES))}
                try:
                    p.save_state("wr9_arena")
                    gate["state_saved"] = True
                except Exception as e:                    # noqa: BLE001
                    gate["state_saved"] = False
                    gate["err"] = repr(e)[:120]
                trace.write({"ev": "ARENA_CAPTURED", **gate})
                log("ARENA captured c", c, "px", round(px, 1),
                    "choppers", len(red), "trucks", len(tr),
                    "saved:", gate.get("state_saved"))
                stop = "ARENA_CAPTURED"
                break
        else:
            confirm = 0

    rep = {
        "schema": "ps1play-wr9-cap/1",
        "verdicts": {"BOOTED": True, "INPUT_RESPONSIVE": in_mission,
                     "STATE_CHANGE_CONFIRMED": max_px > 2.0},
        "stop_reason": stop or "BUDGET_CHUNKS",
        "frames": p.core.frames_run,
        "deaths": deaths, "continues_accepted": continues,
        "continues_disclosed": True,
        "max_px": round(max_px, 1), "final_px": round(px_of(m), 1),
        "arena": gate,
        "sensor_spawns": len(sensor.spawns),
        "wall_s": round(time.time() - t0, 1),
    }
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
    trace.write({"ev": "run_end", **{k: v for k, v in rep.items()
                                     if k != "arena"}})
    log("done:", rep["stop_reason"], "frames", rep["frames"],
        "max_px", rep["max_px"], "captured:", bool(gate))
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
