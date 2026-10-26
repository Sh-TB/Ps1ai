#!/usr/bin/env python3
"""msx_r11_wagons.py — Round 11 / Segment 1 (Issue #7 WAGON RUN).

Fresh live Mission-1 pass with the PROVEN traversal stack (the
msx_wr9_arena flow that accepted 30 continues: RoutePolicy v1
segments + recover_v2 START-tap continue acceptance + px-window stall
ladder) plus the NEW WagonTracker crossing sensor (msx_r11_lib).

A "pass" = ONE fresh-boot process: boot -> gate -> drive RIGHT until
the honest ceiling (camera-locked stall ladder exhaustion, dead loop,
or wall-clock budget).  Continues are the only traversal mechanism and
every recovery is COUNTED + DISCLOSED (method v1_recover_start_taps;
savestate restarts counted separately).

Output per invocation (one pass):
  scratch/round11_msx/wagons/pass_<n>/
      trace.jsonl, wagon_lifecycles.json, raw_rows.json, report.json, PNGs
  scratch/round11_msx/wagons/cumulative.json
      — the session-cumulative crossed counter (the acceptance ledger).

Crossing definition (re-derivable from raw_rows.json): a lifecycle
whose entity first appears AHEAD of the player (> px + 8) and is last
seen BEHIND the player (< px - 8), present >= persist_frames.  The
small/big KIND split is applied offline by msx_r11_lib.split_kinds
from the recorded height word — never guessed online.

ONE beetle boot per process.  No RAM writes, no cheats.  Evidence:
scratch/round11_msx/wagons/.
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
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from issue4_controller import boot                          # noqa: E402
from mission import ensure_mission                          # noqa: E402
from run_mission1_legit import recover_v2                   # noqa: E402
from msx_r11_lib import WagonTracker, split_kinds           # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/round11_msx/wagons"
CUM = os.path.join(SCRATCH, "cumulative.json")
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
FLAGS_WORD = 0x0EE518
CHNK = 60
GRACE = 6
PNG_CAP = 60


def log(*a):
    print("[r11-wagons]", *a, file=sys.stderr, flush=True)


def px_of(m):
    v = int(m.u32(PLAYER_X))
    if v >= 0x80000000:
        v -= 0x100000000
    return v / 65536.0


def alive(m):
    return (int(m.u32(FLAGS_WORD)) & 0xFF) == 0xFF and px_of(m) != 0.0 \
        and int(m.u16(PLAYER_HP)) > 0


def load_cum():
    try:
        return json.load(open(CUM))
    except Exception:                                  # noqa: BLE001
        return {"passes": [], "crossed_total": 0, "continues_total": 0,
                "schema": "ps1play-r11-wagon-cumulative/1"}


def save_cum(d):
    json.dump(d, open(CUM, "w"), indent=1)


def run_pass(p, args, outdir, trace, pass_id):
    """One traversal pass (the proven msx_wr9_arena flow + tracker)."""
    t0 = time.time()

    def J(ev):
        ev["t"] = round(time.time() - t0, 1)
        trace.write(ev)

    m = p.mem
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    tracker = WagonTracker(m.ram, every=args.every,
                           persist_frames=args.persist)
    J({"ev": "pass_start", "pass": pass_id, "px": round(px_of(m), 1),
       "php": int(m.u16(PLAYER_HP)), "score": int(m.u32(A_SCORE))})
    try:
        p.save_state(f"r11_pass{pass_id}_start")
        J({"ev": "checkpoint_saved", "state": f"r11_pass{pass_id}_start"})
    except Exception as e:                             # noqa: BLE001
        J({"ev": "checkpoint_save_failed", "err": repr(e)[:160]})

    prev_px = px_of(m)
    hist = deque(maxlen=8)
    continues = restarts = deaths = 0
    max_px = prev_px
    png_total = band_pngs = 0
    ladder = stuck_streak = 0
    stop = None
    rgb_prev = p.core.frame_rgb()
    c = -1
    for c in range(args.chunks):
        if time.time() - t0 > args.max_s:
            stop = "BUDGET_TIME"
            break
        if not alive(m):
            deaths += 1
            J({"ev": "death", "chunk": c, "attempt": deaths,
               "px": round(px_of(m), 1), "score": int(m.u32(A_SCORE))})
            rgb_d = p.core.frame_rgb()
            if rgb_d is not None and deaths <= 6:
                Image.fromarray(rgb_d).save(os.path.join(
                    outdir, f"death_{deaths:02d}_c{c:03d}.png"))
            if deaths > args.max_deaths:
                stop = "STOP_DEAD_LOOP"
                break
            # the PROVEN continue acceptance: recover_v2 START taps
            recover_v2(p, log=log)
            g2 = ensure_mission(p, tries=4, log=log,
                                want_hp_cands=False)
            continues += 1
            J({"ev": "CONTINUE_ACCEPTED", "chunk": c, "count": continues,
               "disclosed": True, "method": "v1_recover_start_taps",
               "in_mission": bool(g2.get("in_mission"))})
            if not g2.get("in_mission"):
                # savestate restart fallback (disclosed, counted apart)
                try:
                    p.load_state(f"r11_pass{pass_id}_start")
                    restarts += 1
                    J({"ev": "MISSION_RESTART", "chunk": c,
                       "disclosed": True, "count": restarts,
                       "method": "savestate"})
                    g3 = ensure_mission(p, tries=3, log=log,
                                        want_hp_cands=False)
                    if not g3.get("in_mission"):
                        stop = "STOP_RESTART_FAILED"
                        break
                except Exception as e:                 # noqa: BLE001
                    J({"ev": "restart_failed", "err": repr(e)[:160]})
                    stop = "STOP_RESTART_FAILED"
                    break
            rgb_prev = p.core.frame_rgb()
            prev_px = px_of(m)
            hist.clear()
            det.reset()
            continue
        segs = policy.decide(CHNK, det)
        for s in segs:
            btns = set(s["btns"] or set())
            p.core.set_buttons(btns)
            for _ in range(s["frames"]):
                p.core.run_frame()
                fc = p.core.frames_run
                for ev in tracker.poll(fc, px_of(m)):
                    band = ev.get("px0", 0.0) >= 1350.0
                    if band and band_pngs < 100:
                        rgb = p.core.frame_rgb()
                        if rgb is not None:
                            Image.fromarray(rgb).save(os.path.join(
                                outdir,
                                f"cross_s{ev['slot']:02d}_{fc:06d}"
                                f"_px{int(ev['px0'])}.png"))
                            band_pngs += 1
                    elif (not band) and png_total < PNG_CAP:
                        rgb = p.core.frame_rgb()
                        if rgb is not None:
                            Image.fromarray(rgb).save(os.path.join(
                                outdir,
                                f"cross_s{ev['slot']:02d}_{fc:06d}"
                                f".png"))
                            png_total += 1
                    J({"ev": "CROSSED", **ev})
            p.core.set_buttons(set())
        px = px_of(m)
        max_px = max(max_px, px)
        churn = None
        rgb_now = p.core.frame_rgb()
        if rgb_prev is not None and rgb_now is not None:
            churn = round(float(np.abs(
                rgb_prev.astype(np.int16) - rgb_now.astype(np.int16)
            ).mean()), 2)
        rgb_prev = rgb_now
        hist.append((px, churn))
        J({"ev": "chunk", "chunk": c, "frame": p.core.frames_run,
           "px": round(px, 1), "churn": churn,
           "score": int(m.u32(A_SCORE)), "gren": int(m.u8(GRENADES)),
           "php": int(m.u16(PLAYER_HP)),
           "spawns": len(tracker.spawns),
           "crossed": len(tracker.crossed),
           "continues": continues, "restarts": restarts})
        if c % 50 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir, f"progress_c{c:04d}.png"))
        if 1350.0 < px < 2195.0 and c % 10 == 0:
            # ride-band visual context (train-yard band)
            rgb = p.core.frame_rgb()
            if rgb is not None and band_pngs < 130:
                Image.fromarray(rgb).save(os.path.join(
                    outdir, f"ride_c{c:04d}_px{int(px)}.png"))
                band_pngs += 1

    surv = tracker.summary()
    kinds = split_kinds(tracker.crossed)
    rep = {
        "schema": "ps1play-r11-wagons/1", "pass": pass_id,
        "stop_reason": stop or "BUDGET_CHUNKS",
        "chunks_run": c + 1 if c >= 0 else 0,
        "frames": p.core.frames_run,
        "max_px": round(max_px, 1), "final_px": round(px_of(m), 1),
        "continues_accepted": continues, "mission_restarts": restarts,
        "deaths": deaths, "png_capped": png_total,
        "disclosed": {
            "continues": "every death recovery = recover_v2 START taps "
                         "(the v1 flow); each counted, in_mission "
                         "flag recorded",
            "restarts": "savestate mission restarts; each counted",
            "no_ram_writes": True, "no_cheats": True},
        "tracker": surv, "kinds_online": kinds,
        "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(outdir, "report.json"), "w"),
              indent=1)
    json.dump(tracker.crossed,
              open(os.path.join(outdir, "wagon_lifecycles.json"), "w"),
              indent=1)
    json.dump(tracker.raw_rows,
              open(os.path.join(outdir, "raw_rows.json"), "w"))
    J({"ev": "pass_end", "stop": rep["stop_reason"],
       "crossed_persistent": surv["crossed_persistent"],
       "continues": continues})
    log("pass", pass_id, "done:", rep["stop_reason"],
        "max_px", rep["max_px"], "crossed_persistent",
        surv["crossed_persistent"], "continues", continues)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=1300)
    ap.add_argument("--max-s", type=float, default=560.0)
    ap.add_argument("--every", type=int, default=3)
    ap.add_argument("--persist", type=int, default=45)
    ap.add_argument("--max-deaths", type=int, default=40)
    ap.add_argument("--pass-id", type=int, default=None)
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    cum = load_cum()
    pass_id = args.pass_id if args.pass_id is not None \
        else len(cum["passes"]) + 1
    outdir = os.path.join(SCRATCH, f"pass_{pass_id}")
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))
    log("boot (one beetle boot in this process)")
    p, fw = boot()
    log("fw:", fw)
    trace.write({"type": "boot", "fw": fw, "pass": pass_id})
    rep = run_pass(p, args, outdir, trace, pass_id)
    cum["passes"] = [x for x in cum["passes"] if x["pass"] != pass_id]
    cum["passes"].append({
        "pass": pass_id,
        "stop_reason": rep["stop_reason"],
        "max_px": rep["max_px"],
        "continues": rep["continues_accepted"],
        "restarts": rep["mission_restarts"],
        "deaths": rep["deaths"],
        "crossed_persistent": rep["tracker"]["crossed_persistent"],
        "crossed_total": rep["tracker"]["crossed_total"],
        "spawns": rep["tracker"]["spawn_events"],
        "lifecycles": rep["tracker"]["lifecycles_closed"],
        "evidence": outdir, "wall_s": rep["wall_s"]})
    cum["passes"].sort(key=lambda x: x["pass"])
    cum["crossed_total"] = sum(x["crossed_persistent"]
                               for x in cum["passes"])
    cum["continues_total"] = sum(x["continues"] for x in cum["passes"])
    cum["updated_utc"] = time.strftime("%FT%TZ", time.gmtime())
    save_cum(cum)
    log("cumulative crossed_persistent:", cum["crossed_total"],
        "over", len(cum["passes"]), "passes; continues:",
        cum["continues_total"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
