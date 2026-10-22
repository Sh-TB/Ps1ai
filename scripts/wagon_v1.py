#!/usr/bin/env python3
"""wagon_v1.py — Issue #7 T7: the Task-12 v1 controller loop (the only
flow that ever reached the train/POW area live — issue4 evidence
progress_c200.png) + the wagon sensor counting.

Key difference vs the Task-13 controller (issue5_controller.py): the
v1 death recovery (recover_v2 START taps) ACCEPTS the in-game CONTINUE
countdown — checkpoint respawn with a fresh mission timer and fresh
lives.  Silent acceptance was the v1 honesty defect (fixed in Task 13
by counting), but the checkpoint respawn itself is the ONLY mechanism
that ever advanced past the town arena, because every accepted continue
both resets the 300 s timer and respawns at the game's own checkpoint.

This runner therefore:
  * keeps the v1 recovery flow (continue acceptance),
  * COUNTS + DISCLOSES every accepted continue (Task-13 honesty, no
    silent loops),
  * never claims a no-continue clear,
  * runs the wagon sensor (ps1play/agent/wagon.py) the whole time.

No cheats, no RAM writes: continues are a legal in-game option.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import (                           # noqa: E402
    TelemetryAdapter, JsonlTrace, replay_gain)
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.agent.wagon import WagonSensor               # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode                # noqa: E402
from mission import ensure_mission                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from issue4_controller import boot                        # noqa: E402

STARTUP_GRACE = 6
STALL_CHUNKS = 6
PNG_CAP = 90
PAIR = (0xCA2F6, 0xCA2FE)   # VERIFIED player-HP pair (Issue #5 A/B)


def gs_tick_run(p, session, frames, btns, sensor, out, png_total):
    """Frame-by-frame run with the GameShark tick + sensor polling
    (the ONLY sanctioned way to run frames while a freeze is active —
    a freeze must never silently stop)."""
    p.core.set_buttons(set(btns) if btns else set())
    for _ in range(frames):
        p.core.run_frame()
        if session is not None:
            session.gs.tick()
        for ev in sensor.poll(p.core.frames_run):
            if ev["type"] == "spawn" and png_total[0] < PNG_CAP:
                rgb = p.core.frame_rgb()
                if rgb is not None:
                    Image.fromarray(rgb).save(os.path.join(
                        out["dir"], f"wspawn_{ev['slot']:02d}_"
                        f"{ev['fp']}_{p.core.frames_run:06d}.png"))
                    png_total[0] += 1


def _log(*a):
    print("[wagon-v1]", *a, file=sys.stderr, flush=True)


def run_once(p, chunks, trace, label, outdir, sensor, start_chunk=0,
             session=None):
    out = {"dir": outdir}
    png_total = [0]
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    trace.write({"type": "run_start", "label": label, "start": prev,
                 "start_chunk": start_chunk})
    stall_streak = 0
    ladder = 0
    frozen_chunks = 0
    deaths = 0
    continues = 0
    stop = None
    camera_series = [prev["camera_fx"]]
    max_score = prev["score"]
    rgb_prev = p.core.frame_rgb()
    for c in range(start_chunk, start_chunk + chunks):
        if stop:
            break
        segs = policy.decide(60, det)
        for s in segs:
            if session is not None:
                gs_tick_run(p, session, s["frames"], s["btns"], sensor,
                            out, png_total)
            else:
                p.core.run(s["frames"],
                           set(s["btns"]) if s["btns"] else None)
                for ev in sensor.poll(p.core.frames_run):
                    if ev["type"] == "spawn" and png_total[0] < PNG_CAP:
                        rgb = p.core.frame_rgb()
                        if rgb is not None:
                            Image.fromarray(rgb).save(os.path.join(
                                outdir, f"wspawn_{ev['slot']:02d}_"
                                f"{ev['fp']}_"
                                f"{p.core.frames_run:06d}.png"))
                            png_total[0] += 1
        cur = tel.snapshot(buttons=sorted(set().union(
            *[s["btns"] or set() for s in segs])),
            frame=p.core.frames_run)
        gain = tel.scroll_gain(prev, cur)
        camera_series.append(cur["camera_fx"])
        rgb_now = p.core.frame_rgb()
        churn_px = None
        if rgb_prev is not None and rgb_now is not None:
            churn_px = round(float(np.abs(
                rgb_prev.astype(np.int16) -
                rgb_now.astype(np.int16)).mean()), 3)
        rgb_prev = rgb_now
        evs = tel.events(prev, cur)
        max_score = max(max_score, cur["score"])
        for e in evs:
            trace.write({"type": "event", "chunk": c, **e})
        trace.write({"type": "chunk", "chunk": c, "telemetry": cur,
                     "scroll_gain": gain, "churn_px": churn_px,
                     "spawns_so_far": len(sensor.spawns)})
        # ---- death -> v1 recovery = CONTINUE acceptance (disclosed) --
        cam_regress = gain < -50
        if any(e["type"] == "death_candidate" for e in evs) or \
                cam_regress:
            deaths += 1
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": deaths,
                         "trigger": "score_collapse" if not cam_regress
                         else "camera_regress"})
            if deaths > 40:
                stop = "STOP_DEAD_LOOP"
                break
            recover_v2(p, log=_log)
            g = ensure_mission(p, tries=4, log=_log, want_hp_cands=False)
            # a successful re-gate after recover_v2's START taps means
            # play resumed; if the taps landed on the continue countdown
            # this was a CONTINUE (checkpoint respawn, fresh timer) and
            # it is counted + disclosed (the v1 honesty defect, fixed).
            continues += 1
            trace.write({"type": "continue_accepted", "chunk": c,
                         "count": continues, "disclosed": True,
                         "method": "v1_recover_start_taps"})
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            rgb_prev = p.core.frame_rgb()
            continue
        # ---- stall ladder on pixel churn (v1) ----
        in_grace = c < STARTUP_GRACE
        stalled = churn_px is not None and churn_px < 3.0 and gain <= 0
        stall_streak = 0 if (not stalled or in_grace) else \
            stall_streak + 1
        if not stalled:
            ladder = 0
        if stall_streak >= STALL_CHUNKS:
            ladder += 1
            stall_streak = 0
            if ladder == 1:
                if session is not None:
                    gs_tick_run(p, session, 20, {"RIGHT"}, sensor, out,
                                png_total)
                    gs_tick_run(p, session, 40, {"RIGHT", "B"}, sensor,
                                out, png_total)
                else:
                    p.core.run(20, {"RIGHT"})
                    p.core.run(40, {"RIGHT", "B"})
            elif ladder == 2:
                if cur["grenades"] > 0:
                    if session is not None:
                        gs_tick_run(p, session, 8, set(), sensor, out,
                                    png_total)
                        gs_tick_run(p, session, 30, {"A"}, sensor, out,
                                    png_total)
                    else:
                        p.core.run(8, set())
                        p.core.run(30, {"A"})
                if session is not None:
                    gs_tick_run(p, session, 30, {"RIGHT", "Y"}, sensor,
                                out, png_total)
                else:
                    p.core.run(30, {"RIGHT", "Y"})
            elif ladder == 3:
                if session is not None:
                    gs_tick_run(p, session, 60, {"LEFT", "Y"}, sensor,
                                out, png_total)
                    gs_tick_run(p, session, 120, {"RIGHT", "Y"}, sensor,
                                out, png_total)
                else:
                    p.core.run(60, {"LEFT", "Y"})
                    p.core.run(120, {"RIGHT", "Y"})
            else:
                stop = f"STOP_STALLED chunk={c}"
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        frozen_chunks = frozen_chunks + 1 if gain <= 0 else 0
        if c % 50 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir, f"progress_c{c:04d}.png"))
            try:
                p.save_state(f"{label}_deep")
                json.dump({"chunk": c}, open(os.path.join(
                    outdir, "runstate.json"), "w"))
                trace.write({"type": "checkpoint_saved", "chunk": c,
                             "state": f"{label}_deep"})
            except Exception as e:                 # noqa: BLE001
                trace.write({"type": "checkpoint_save_failed",
                             "chunk": c, "err": repr(e)[:150]})
        prev = cur
    gains = replay_gain(camera_series)
    summ = sensor.summary()
    report = {
        "schema": "ps1play-wagon-v1/1",
        "label": label,
        "chunks_run": (c + 1) if c >= 0 else 0,
        "start_chunk": start_chunk,
        "stop_reason": stop or "BUDGET_CHUNKS",
        "deaths": deaths,
        "continues_accepted": continues,
        "continues_disclosed": True,
        "max_score": max_score,
        "scroll_gain_total": sum(g for g in gains if g > 0),
        "sensor": summ,
        "disclosure": ("CHEAT_ASSISTED_EXPLORATION: hp_pair freeze + "
                       "grenades patch active; never a no-cheat clear"
                       if session is not None else
                       "no-cheat run; every continue accepted via the "
                       "in-game countdown is counted and disclosed; a "
                       "clear after continues is never a no-continue "
                       "clear"),
    }
    trace.write({"type": "run_end", **{k: v for k, v in report.items()
                                       if k != "sensor"}})
    json.dump(report, open(os.path.join(outdir, "wagon_report.json"),
                           "w"), indent=1)
    json.dump(sensor.spawns + sensor.despawns,
              open(os.path.join(outdir, "wagon_events.json"), "w"))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=600)
    ap.add_argument("--budget-min", type=float, default=9.0)
    ap.add_argument("--tag", default="v1a")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    ap.add_argument("--explore", action="store_true",
                    help="enable the VERIFIED hp_pair freeze + grenades "
                         "patch (CHEAT_ASSISTED_EXPLORATION, disclosed)")
    ap.add_argument("--resume-tag", default=None,
                    help="continue a previous run: boot, gate, load "
                         "<tag>_deep savestate, resume chunk numbering "
                         "(disclosed in the trace)")
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue7_wagon_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    p, fwmode = boot()
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    _log("mission gate:", g.get("in_mission"))
    sensor = WagonSensor(p.mem.ram, every=10)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))
    trace.write({"type": "boot", "fw": fwmode,
                 "in_mission": bool(g.get("in_mission"))})
    start_chunk = 0
    if args.resume_tag:
        try:
            rs = json.load(open(os.path.join(
                args.evidence_dir, f"issue7_wagon_{args.resume_tag}",
                "runstate.json")))
            start_chunk = rs["chunk"] + 1
            p.load_state(f"{args.resume_tag}_deep")
            g2 = ensure_mission(p, tries=4, log=_log,
                                want_hp_cands=False)
            trace.write({"type": "resumed", "from_chunk": start_chunk,
                         "from_tag": args.resume_tag,
                         "in_mission": bool(g2.get("in_mission")),
                         "disclosed": True})
            _log("resumed from", args.resume_tag, "chunk", start_chunk,
                 "gate:", g2.get("in_mission"))
        except Exception as e:                     # noqa: BLE001
            _log("resume failed:", repr(e)[:200])
            start_chunk = 0
    session = None
    if args.explore:
        v0, v1 = int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1]))
        session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        codes = [GSCode(f"8{PAIR[0]:07X} {v0 & 0xFFFF:04X}"),
                 GSCode(f"8{PAIR[1]:07X} {v1 & 0xFFFF:04X}"),
                 GSCode("800398BE 2400")]
        session.enable("wagon_v1_explore", codes)
        trace.write({"type": "cheats_enabled",
                     "codes": [c.raw for c in codes],
                     "disclosed": True,
                     "mode": "CHEAT_ASSISTED_EXPLORATION"})
        _log("explore freeze:", [c.raw for c in codes])
    rep = run_once(p, args.chunks, trace, args.tag, outdir, sensor,
                   start_chunk=start_chunk, session=session)
    rep["wallclock_s"] = round(time.time() - t0, 1)
    json.dump(rep, open(os.path.join(outdir, "wagon_report.json"),
                        "w"), indent=1)
    _log("done:", rep["stop_reason"], "chunks:", rep["chunks_run"],
         "continues:", rep["continues_accepted"],
         "spawns:", rep["sensor"]["spawn_events"])


if __name__ == "__main__":
    main()
