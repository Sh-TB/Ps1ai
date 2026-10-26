#!/usr/bin/env python3
"""msx_wr9_arena.py — Round 9 task 9-a (Issue #7 WAGON RUN): T4 sensor
sanity run + town-arena capture.

ONE beetle boot per process (hard rule 1).  Fresh boot -> ensure_mission
gate -> walk right with the proven v1 cadence (RoutePolicy + StallDetector)
with the WagonSensor polling the whole time.  Two outcomes:

  A) town-arena camera gate detected (camera u32 0x0CA2E0 raw DELTA==0 for
     >= 6 consecutive 60f chunks while alive + chopper/truck census) ->
     savestate `wr9_arena` + PNG + full census -> exit (the leader-kill
     script then retries from it).
  B) the gate resolves during traversal -> keep walking with the sensor to
     the train yard; first time >= 2 persistent slots appear save
     `wr9_trainride` + PNG; keep counting to the chunk budget.

No cheats, no RAM writes.  Death recovery = recover_v2 START taps (the v1
flow): any continue acceptance via the in-game countdown is counted and
disclosed.  Evidence: JSONL trace + PNGs + report.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import deque

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

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round9_msx"
OUTDIR = os.path.join(SCRATCH, "arena_t4")

PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
FLAGS_WORD = 0x0EE518
TABLE, STRIDE = 0x0CA268, 0x14C
CHOPPER_ST = (0xAA94, 0xABDC)
TRUCK_ST = (0x9E88,)
FALLER_ST = 0xB4E4
CORPSE_ST = (0x4BE4, 0x5CC8)
CHNK = 60
GRACE = 10


def log(*a):
    print("[wr9-arena]", *a, file=sys.stderr, flush=True)


def px_of(m):
    v = int(m.u32(PLAYER_X))
    if v >= 0x80000000:                      # signed 16.16 world px
        v -= 0x100000000
    return v / 65536.0


def alive(m):
    # 0x0CA2E0 (u32 16.16) is the VERIFIED player-x (grenade dx targeting
    # proven live, truck campaign); telemetry's legacy "camera_fx" label
    # points at the same word.  The arena camera-lock therefore shows up
    # as the player-x freezing (walkable window locked).
    return (int(m.u32(FLAGS_WORD)) & 0xFF) == 0xFF and px_of(m) != 0.0 \
        and int(m.u16(PLAYER_HP)) > 0


def census(m):
    """Raw entity census (36 slots, read-only)."""
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


def classify(slots):
    ch = [s for s in slots if s["st"] in CHOPPER_ST and s["hpA4"] > 0]
    tr = [s for s in slots if s["hpA4"] >= 100 and s["h"] <= 40
          and s["st"] in TRUCK_ST]
    fl = [s for s in slots if s["st"] == FALLER_ST]
    return ch, tr, fl


def redness(rgb, sx):
    """Max per-column red dominance (R-(G+B)/2) near screen-x sx, top rows."""
    if rgb is None:
        return None
    h, w = rgb.shape[:2]
    c0, c1 = max(0, sx - 10), min(w, sx + 11)
    if c1 <= c0:
        return None
    win = rgb[0:min(h, 140), c0:c1].astype(np.int16)
    r = win[:, :, 0] - (win[:, :, 1] + win[:, :, 2]) // 2
    return round(float(r.mean(axis=0).max()), 1)


def png(p, name, outdir):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))
    return rgb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=560)
    ap.add_argument("--budget-s", type=float, default=660.0)
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(OUTDIR, "trace.jsonl"))

    p, fw = boot()                                   # ONE boot
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    in_mission = bool(g.get("in_mission"))
    trace.write({"ev": "boot", "fw": fw, "in_mission": in_mission,
                 "verdict": "BOOTED+INPUT_RESPONSIVE" if in_mission
                 else "GATE_FAILED"})
    log("booted", fw, "in_mission:", in_mission)
    if not in_mission:
        json.dump({"verdict": "GATE_FAILED", "fw": fw},
                  open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 2

    sensor = WagonSensor(m.ram, every=10)
    png(p, "t4_start.png", OUTDIR)

    from ps1play.agent.route import RoutePolicy, StallDetector
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()

    prev_px = px_of(m)
    hist = deque(maxlen=8)          # (px, churn) per chunk — px IS the
                                    # camera-locked window proxy (see alive())
    gate_saved = train_saved = False
    deaths = continues = 0
    ladder = 0
    stuck_streak = 0
    max_px = prev_px
    stop = None
    gate_info = None
    rgb_prev = p.core.frame_rgb()
    arena_px = None

    for c in range(args.chunks):
        if time.time() - t0 > args.budget_s:
            stop = "BUDGET_WALL"
            break
        if not alive(m):
            deaths += 1
            trace.write({"ev": "death", "chunk": c, "px": px_of(m),
                         "score": int(m.u32(A_SCORE))})
            log("death", deaths, "at c", c, "px", round(px_of(m), 1))
            if deaths > 30:
                stop = "STOP_DEAD_LOOP"
                break
            recover_v2(p, log=log)
            g2 = ensure_mission(p, tries=4, log=log, want_hp_cands=False)
            continues += 1
            trace.write({"ev": "continue_accepted", "chunk": c,
                         "count": continues, "disclosed": True,
                         "method": "v1_recover_start_taps",
                         "in_mission": bool(g2.get("in_mission"))})
            rgb_prev = p.core.frame_rgb()
            prev_px = px_of(m)
            hist.clear()
            det.reset()
            continue
        segs = policy.decide(CHNK, det)
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
            for ev in sensor.poll(p.core.frames_run):
                if ev["type"] == "spawn":
                    rgb = p.core.frame_rgb()
                    if rgb is not None and \
                            len(sensor.spawns) <= 120:
                        Image.fromarray(rgb).save(os.path.join(
                            OUTDIR, f"wspawn_{ev['slot']:02d}_"
                            f"{ev['fp']}_{p.core.frames_run:06d}.png"))
        rgb_now = p.core.frame_rgb()
        churn = None
        if rgb_prev is not None and rgb_now is not None:
            churn = round(float(np.abs(
                rgb_prev.astype(np.int16) -
                rgb_now.astype(np.int16)).mean()), 2)
        rgb_prev = rgb_now
        px = px_of(m)
        max_px = max(max_px, px)
        hist.append((px, churn))
        trace.write({"ev": "chunk", "c": c, "frame": p.core.frames_run,
                     "px": round(px, 1), "churn": churn,
                     "score": int(m.u32(A_SCORE)),
                     "gren": int(m.u8(GRENADES)),
                     "spawns": len(sensor.spawns)})
        if c % 50 == 0:
            png(p, f"progress_c{c:04d}.png", OUTDIR)
        # ---- arena-gate detector ----
        if c >= GRACE and len(hist) >= 6 and not gate_saved:
            last6 = list(hist)[-6:]
            pxs = [h[0] for h in last6]
            chs = [h[1] for h in last6 if h[1] is not None]
            # stuck = <2.0 px advance over 360 frames while alive
            # (normal traversal ~2 px/frame).  NOTE: churn is NOT part
            # of the rule — the arena set-piece keeps the screen
            # churning (T4 lesson: churn 5-12 while pinned).  TWO
            # consecutive windows required (720f) so mid-town
            # ambush stalls don't false-capture.
            if (max(pxs) - min(pxs)) < 2.0 and \
                    (pxs[-1] - pxs[0]) < 2.0:
                stuck_streak += 1
            else:
                stuck_streak = 0
            if stuck_streak >= 2:
                slots = census(m)
                ch, tr, fl = classify(slots)
                trace.write({"ev": "gate_candidate", "c": c, "px": round(px, 1),
                             "choppers": ch, "trucks": tr, "fallers": len(fl),
                             "slots": slots[:20]})
                if ch or tr:
                    rgb = png(p, "wr9_arena.png", OUTDIR)
                    red = [{**x, "red": redness(rgb, x["sx"])}
                           for x in ch] if rgb is not None else ch
                    gate_info = {"chunk": c, "px": round(px, 1),
                                 "px_window": [round(min(pxs), 1),
                                               round(max(pxs), 1)],
                                 "frame": p.core.frames_run,
                                 "choppers": red, "trucks": tr,
                                 "fallers": len(fl), "score":
                                 int(m.u32(A_SCORE))}
                    try:
                        p.save_state("wr9_arena")
                        gate_info["state_saved"] = True
                    except Exception as e:                # noqa: BLE001
                        gate_info["state_saved"] = False
                        gate_info["err"] = repr(e)[:120]
                    trace.write({"ev": "ARENA_GATE", **gate_info})
                    log("ARENA_GATE c", c, "px", round(px, 1),
                        "choppers", len(red), "truck", len(tr),
                        "state_saved:", gate_info.get("state_saved"))
                    gate_saved = True
                    arena_px = px
                    stop = "ARENA_GATE_CAPTURED"
                    break
                else:
                    # camera-locked but no set-piece: pit/stall -> ladder
                    ladder += 1
                    trace.write({"ev": "camlock_no_combat", "c": c,
                                 "ladder": ladder})
                    if ladder == 1:
                        p.core.run(20, {"RIGHT"})
                        p.core.run(40, {"RIGHT", "B"})
                    elif ladder == 2:
                        p.core.run(8, set())
                        p.core.run(30, {"A"})
                        p.core.run(30, {"RIGHT", "Y"})
                    elif ladder == 3:
                        p.core.run(60, {"LEFT", "Y"})
                        p.core.run(120, {"RIGHT", "Y"})
                    else:
                        stop = "STOP_CAMLOCK_NO_COMBAT"
                        break
                    hist.clear()
                    rgb_prev = p.core.frame_rgb()
                    continue
        # ---- train-ride marker ----
        if not train_saved and len(sensor.spawns) >= 10 and px > 1700 \
                and len(sensor.persistent_slots()) >= 2:
            png(p, "wr9_trainride.png", OUTDIR)
            try:
                p.save_state("wr9_trainride")
                train_saved = True
                trace.write({"ev": "TRAIN_RIDE", "c": c,
                             "px": round(px, 1),
                             "persistent": sensor.persistent_slots()})
                log("TRAIN_RIDE marker at c", c)
            except Exception as e:                    # noqa: BLE001
                trace.write({"ev": "trainride_save_fail",
                             "err": repr(e)[:120]})
        prev_px = px

    summ = sensor.summary()
    rep = {
        "schema": "ps1play-wr9-arena/1",
        "verdicts": {
            "BOOTED": True, "INPUT_RESPONSIVE": in_mission,
            "STATE_CHANGE_CONFIRMED": max_px > 2.0,
        },
        "stop_reason": stop or "BUDGET_CHUNKS",
        "chunks": args.chunks, "frames": p.core.frames_run,
        "deaths": deaths, "continues_accepted": continues,
        "continues_disclosed": True,
        "max_px": round(max_px, 1),
        "final_px": round(px_of(m), 1),
        "arena_gate": gate_info,
        "trainride_marker": train_saved,
        "sensor": summ,
        "wall_s": round(time.time() - t0, 1),
        "disclosure": ("no-cheat run; continues (if any) accepted via the "
                       "in-game countdown are counted+disclosed"),
    }
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    json.dump(sensor.spawns + sensor.despawns, open(
        os.path.join(OUTDIR, "wagon_events.json"), "w"))
    trace.write({"ev": "run_end", **{k: v for k, v in rep.items()
                                     if k != "sensor"}})
    log("done:", rep["stop_reason"], "frames", rep["frames"],
        "max_px", rep["max_px"], "continues", continues,
        "spawns", summ["spawn_events"])
    p.close() if hasattr(p, "close") else None
    return 0


if __name__ == "__main__":
    sys.exit(main())
