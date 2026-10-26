#!/usr/bin/env python3
"""msx_r10_cap.py — Round 10 (Issue #7): regenerate the px-2212 arena pin.

The round-9 savestate `wr9_arena` was lost in the local-clone reset, so
the pin must be re-walked before any arena experiment.  Round-10
execution reality: the sandbox reaps background processes when the
driver call ends, so the walk is made RESUMABLE and TIME-BOUNDED to fit
one tool call:

  * boot -> ensure_mission -> if savestate `r10_walk` exists, load it
    and continue the walk from the checkpointed px (boot gate THEN
    state load, the round-9 leaderkill pattern);
  * walk right with RoutePolicy/StallDetector; every save-every chunks
    save_state `r10_walk` (overwrite) + sidecar JSON {px, frame,
    continues_total};
  * on death: recover_v2 continue (counted + disclosed, per run AND
    cumulative in the sidecar), then re-save the walk checkpoint;
  * pin rule (identical to round-9 cap2): alive AND px >= --pin-px AND
    px-window < --pin-window over --pin-chunks chunks, streak >= 2
    (>= 360 frames pinned) -> save_state `wr9_arena` + full census +
    PNG + TRIO verification (three st 0xA0D0 slots with hpA4 >= 300)
    -> exit;
  * --max-s hard-stops the run gracefully before the tool timeout;
    report.json records stop_reason so the next call resumes.

ONE beetle boot per process.  No RAM writes, no cheats.  Continues are
counted and disclosed per-run and cumulatively.  Evidence:
scratch/round10_msx/cap/.
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
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/round10_msx"
OUTDIR = os.path.join(SCRATCH, "cap")
CHNK = 60

PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
FLAGS_WORD = 0x0EE518
TABLE, STRIDE = 0x0CA268, 0x14C
ARMORED_ST = 0xA0D0            # round-9: trio family (slots 10-12)
SIDECAR = os.path.join(OUTDIR, "walk_checkpoint.json")


def log(*a):
    print("[r10-cap]", *a, file=sys.stderr, flush=True)


def px_of(m):
    v = int(m.u32(PLAYER_X))
    if v >= 0x80000000:                      # signed 16.16 world px
        v -= 0x100000000
    return v / 65536.0


def alive(m):
    return (int(m.u32(FLAGS_WORD)) & 0xFF) == 0xFF and px_of(m) != 0.0 \
        and int(m.u16(PLAYER_HP)) > 0


def census(m):
    tv = m.ram[TABLE:TABLE + 36 * STRIDE].view("<u2").astype(np.int32) \
        .reshape(36, STRIDE // 2)
    out = []
    for s in range(1, 36):
        st = int(tv[s, 0])
        xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
        if not st and not xw:
            continue
        out.append({"slot": s, "st": st,
                    "x": round(xw / 65536.0, 1), "h": int(tv[s, 63]),
                    "sx": int(tv[s, 71]), "hpA4": int(tv[s, 82])})
    return out


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, name))
    return rgb


def load_sidecar():
    try:
        return json.load(open(SIDECAR))
    except Exception:                                 # noqa: BLE001
        return {"continues_total": 0, "runs": 0}


def save_sidecar(d):
    json.dump(d, open(SIDECAR, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=10000)
    ap.add_argument("--max-s", type=float, default=480.0,
                    help="hard wall-clock stop (fits one tool call)")
    ap.add_argument("--pin-px", type=float, default=1400.0)
    ap.add_argument("--pin-window", type=float, default=10.0)
    ap.add_argument("--pin-chunks", type=int, default=3)
    ap.add_argument("--save-every", type=int, default=30,
                    help="chunks between r10_walk checkpoint saves")
    ap.add_argument("--resume", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    side = load_sidecar()
    run_idx = int(side.get("runs", 0)) + 1
    side["runs"] = run_idx
    trace = JsonlTrace(os.path.join(OUTDIR, f"trace_run{run_idx}.jsonl"))

    p, fw = boot()
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    in_mission = bool(g.get("in_mission"))
    resumed = False
    if in_mission and args.resume:
        try:
            p.load_state("r10_walk")
            resumed = True
            if not alive(m):                # checkpoint not in-mission?
                recover_v2(p, log=log)
                ensure_mission(p, tries=4, log=log, want_hp_cands=False)
        except Exception as e:                # noqa: BLE001
            log("no r10_walk checkpoint (", repr(e)[:80], ")")
    trace.write({"ev": "boot", "fw": fw, "run": run_idx,
                 "in_mission": in_mission, "resumed": resumed,
                 "continues_total_before": side.get("continues_total", 0)})
    log("booted", fw, "in_mission:", in_mission, "resumed:", resumed)
    if not in_mission:
        json.dump({"verdict": "GATE_FAILED", "fw": fw, "run": run_idx},
                  open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 2

    sensor = WagonSensor(m.ram, every=10)
    if not resumed:
        png(p, "cap_start.png")
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()

    deaths = continues = 0
    pin_streak = 0
    win = []
    respawns = []                       # checkpoint map records
    start_px = px_of(m)
    max_px = start_px
    stop = None
    gate = None

    for c in range(args.chunks):
        if time.time() - t0 > args.max_s:
            stop = "TIME_WALL"
            break
        if not alive(m):
            deaths += 1
            trace.write({"ev": "death", "chunk": c,
                         "px": round(px_of(m), 1)})
            log("death", deaths, "at c", c, "px", round(px_of(m), 1))
            if deaths > 40:
                stop = "STOP_DEAD_LOOP"
                break
            recover_v2(p, log=log)
            ensure_mission(p, tries=4, log=log, want_hp_cands=False)
            continues += 1
            side["continues_total"] = int(side.get("continues_total", 0)) + 1
            rpx = px_of(m)
            respawns.append({"n": side["continues_total"], "chunk": c,
                             "frame": p.core.frames_run,
                             "respawn_px": round(rpx, 1)})
            trace.write({"ev": "continue_accepted", "chunk": c,
                         "count_run": continues,
                         "count_total": side["continues_total"],
                         "disclosed": True,
                         "respawn_px": round(rpx, 1)})
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
                     "px": round(px, 1), "score": int(m.u32(A_SCORE)),
                     "php": int(m.u16(PLAYER_HP)),
                     "gren": int(m.u8(GRENADES)),
                     "spawns": len(sensor.spawns)})
        if c % 100 == 0:
            png(p, f"cap_c{c:04d}.png")
            log("c", c, "px", round(px, 1), "max", round(max_px, 1),
                "deaths", deaths, "continues", continues, "wall",
                round(time.time() - t0, 1))
        if c and c % args.save_every == 0 and px > start_px:
            try:
                p.save_state("r10_walk")
                save_sidecar({"continues_total": side["continues_total"],
                              "runs": side["runs"],
                              "px": round(px, 1),
                              "frame": p.core.frames_run,
                              "saved_at": time.strftime("%H:%M:%S")})
            except Exception as e:                    # noqa: BLE001
                log("walk save failed:", repr(e)[:100])
        if len(win) >= args.pin_chunks and px >= args.pin_px and \
                (max(win) - min(win)) < args.pin_window:
            pin_streak += 1
        else:
            pin_streak = 0
        if pin_streak >= 2:                      # >= 360 frames pinned
            slots = census(m)
            trio = [s for s in slots
                    if s["st"] == ARMORED_ST and s["hpA4"] >= 300]
            rgb = png(p, "wr9_arena_pin.png")
            gate = {"chunk": c, "px": round(px, 1),
                    "frame": p.core.frames_run,
                    "px_window": [round(min(win), 1), round(max(win), 1)],
                    "score": int(m.u32(A_SCORE)),
                    "php": int(m.u16(PLAYER_HP)),
                    "gren": int(m.u8(GRENADES)),
                    "census_slots": slots,
                    "trio": trio,
                    "trio_verified": len(trio) == 3}
            try:
                p.save_state("wr9_arena")
                gate["state_saved"] = True
            except Exception as e:                    # noqa: BLE001
                gate["state_saved"] = False
                gate["err"] = repr(e)[:120]
            trace.write({"ev": "ARENA_CAPTURED", **gate})
            log("ARENA pin captured c", c, "px", round(px, 1),
                "trio", len(trio), "slots", len(slots),
                "saved:", gate.get("state_saved"))
            stop = "ARENA_CAPTURED"
            break

    rep = {"schema": "ps1play-r10-cap/1", "run": run_idx,
           "verdicts": {"BOOTED": True, "INPUT_RESPONSIVE": in_mission,
                        "STATE_CHANGE_CONFIRMED": max_px > 2.0},
           "stop_reason": stop or "BUDGET_CHUNKS",
           "resumed": resumed, "start_px": round(start_px, 1),
           "frames": p.core.frames_run,
           "deaths": deaths, "continues_accepted_run": continues,
           "continues_accepted_total": side.get("continues_total", 0),
           "continues_disclosed": True,
           "max_px": round(max_px, 1), "final_px": round(px_of(m), 1),
           "arena": {k: v for k, v in (gate or {}).items()
                     if k != "census_slots"},
           "trio_verified": bool(gate and gate.get("trio_verified")),
           "respawn_map": respawns,
           "sensor_spawns": len(sensor.spawns),
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
    json.dump(sensor.spawns + sensor.despawns, open(
        os.path.join(OUTDIR, f"wagon_events_run{run_idx}.json"), "w"))
    if gate:
        json.dump(gate["census_slots"], open(
            os.path.join(OUTDIR, "arena_census.json"), "w"), indent=1)
    log("done:", rep["stop_reason"], "frames", rep["frames"],
        "max_px", rep["max_px"], "continues", continues,
        "trio_verified:", rep["trio_verified"])
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
