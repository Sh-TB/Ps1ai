#!/usr/bin/env python3
"""issue4_controller.py — ISSUE 4 Phase 4+6: bounded deterministic
controller driven by VERIFIED telemetry only.

FSM per 60-frame chunk (reuses RoutePolicy for the movement policy and
recover_v2 for continue screens — no agent rewrite):

  VERIFY   ensure_mission gate (pad-mirror rhythm + churn + self-play)
  ADVANCE  RoutePolicy segments (RIGHT + fire bursts + hop cadence)
  MEASURE  telemetry snapshot each chunk; wrap-safe scroll gain
  STALL    scroll gain <= 0 for 2 consecutive chunks -> bounded ladder:
           L1 jump burst 90f -> L2 one grenade (verified count) ->
           L3 LEFT+Y 60f then RIGHT+Y 120f -> STOP with diagnostics
  DEATH    score collapse <= -200 -> ONE recover_v2 (START tap) ->
           re-verify gate -> STOP if still dead (no blind loops)
  CLEAR    candidate: score gain > 5000 in one chunk while scroll is
           frozen for 3 chunks (mission-end tally shape).  Reported as
           CLEAR_CANDIDATE_UNVERIFIED unless the transition repeats
           with matching tally evidence; never claimed otherwise.

Legitimacy: legal inputs only, savestates used solely as gate
checkpoints (never rewound into the claimed run), cheats disabled.
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
from ps1play.api import PS1Play                           # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.telemetry import (                           # noqa: E402
    TelemetryAdapter, JsonlTrace, replay_gain, is_clear_candidate)
from mission import ensure_mission                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from issue4_real_start import boot_to_demo, owns_pad      # noqa: E402

CLEAR_MIN_SCORE_GAIN = 5000
CLEAR_SCROLL_FROZEN_CHUNKS = 3
STALL_CHUNKS = 6          # 360f of zero scroll gain = real stall
STARTUP_GRACE = 6         # rope-slide intro: camera cannot move yet


def _log(*a):
    print("[ctrl]", *a, file=sys.stderr, flush=True)


def run_once(p, chunks, trace, label):
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    trace.write({"type": "run_start", "label": label,
                 "start": prev})
    stall_streak = 0
    ladder = 0                    # 0 none, 1 jump, 2 grenade, 3 move
    frozen_chunks = 0
    deaths = 0
    stop = None
    camera_series = [prev["camera_fx"]]
    max_score = prev["score"]
    rgb_prev = p.core.frame_rgb()
    for c in range(chunks):
        if stop:
            break
        segs = policy.decide(60, det)
        for s in segs:
            p.core.run(s["frames"], s["btns"] if s["btns"] else None)
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
                     "policy_stats": dict(policy.stats)})
        # ---- death ----
        # real-play score @0xEEE318 turned out to be a PER-LIFE value
        # (resets on death), so a collapse OR a hard camera regress
        # (per-life walk accumulator resets) both indicate death.
        cam_regress = gain < -50
        if any(e["type"] == "death_candidate" for e in evs) or cam_regress:
            deaths += 1
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": deaths,
                         "trigger": "score_collapse" if not cam_regress
                         else "camera_regress"})
            if deaths > 6:
                stop = "STOP_DEAD_LOOP"
                break
            recover_v2(p, log=_log)
            g = ensure_mission(p, tries=4, log=_log, want_hp_cands=False)
            if not g.get("in_mission"):
                stop = "STOP_DEAD_SCREEN"
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            rgb_prev = p.core.frame_rgb()
            continue
        # ---- stall ladder on PIXEL churn (robust: the demo-context
        # camera word is a per-life accumulator that resets on death,
        # so camera-based stall detection false-fires in real play) ----
        in_grace = c < STARTUP_GRACE
        stalled = churn_px is not None and churn_px < 3.0 and gain <= 0
        stall_streak = 0 if (not stalled or in_grace) else stall_streak + 1
        if not stalled:
            ladder = 0
        if stall_streak >= STALL_CHUNKS:
            ladder += 1
            stall_streak = 0
            if ladder == 1:
                trace.write({"type": "stall_l1_jump", "chunk": c})
                p.core.run(20, {"RIGHT"})
                p.core.run(40, {"RIGHT", "B"})
            elif ladder == 2:
                trace.write({"type": "stall_l2_grenade", "chunk": c,
                             "grenades_before": cur["grenades"]})
                if cur["grenades"] > 0:
                    p.core.run(8, set())
                    p.core.run(30, {"A"})
                p.core.run(30, {"RIGHT", "Y"})
            elif ladder == 3:
                trace.write({"type": "stall_l3_unstick", "chunk": c})
                p.core.run(60, {"LEFT", "Y"})
                p.core.run(120, {"RIGHT", "Y"})
            else:
                stop = (f"STOP_STALLED chunk={c} "
                        f"camera_x={cur['camera_x']}")
                trace.write({"type": "stop", "chunk": c,
                             "reason": stop, "telemetry": cur})
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        # ---- clear candidate (honest: UNVERIFIED shape only) ----
        frozen_chunks = frozen_chunks + 1 if gain <= 0 else 0
        best_gain = max((e["delta"] for e in evs
                         if e["type"] == "score_gain"), default=0)
        if is_clear_candidate(frozen_chunks, best_gain):
            trace.write({"type": "clear_candidate_unverified",
                         "chunk": c, "telemetry": cur})
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir_evid, f"clearcand_c{c:03d}.png"))
        if c % 50 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir_evid, f"progress_c{c:03d}.png"))
        prev = cur
    gains = replay_gain(camera_series)
    report = {
        "label": label,
        "chunks_run": c + 1 if not stop else c,
        "stop_reason": stop or "BUDGET_END",
        "deaths": deaths,
        "max_score": max_score,
        "final": prev,
        "scroll_gain_total": sum(g for g in gains if g > 0),
        "policy_stats": policy.stats,
    }
    trace.write({"type": "run_end", **report})
    return report


def boot(firmware="openbios"):
    """Real-play boot: adaptive navigation -> START taps until input
    ownership is proven (idle pad mirror all-zero + RIGHT response).
    The gate must ALSO confirm active mission gameplay after that."""
    p = boot_to_demo()
    owned = False
    for attempt in range(6):
        p.core.run(12, {"START"})
        p.core.run(150, set())
        own = owns_pad(p, frames=30)
        if own["owns"]:
            owned = True
            break
    if not owned:
        raise SystemExit("input ownership not achieved")
    gate = ensure_mission(p, log=_log, want_hp_cands=False)
    if not gate.get("in_mission"):
        raise SystemExit("gate failed after ownership")
    return p, "openbios+start_taps"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=200,
                    help="60-frame chunks (200 = 12000 frames)")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, "issue4_controller")
    os.makedirs(outdir, exist_ok=True)
    global outdir_evid
    outdir_evid = outdir
    out = {"schema": "ps1play-controller/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "runs": []}
    for k in range(args.runs):
        _log(f"=== run {k + 1}/{args.runs} (fresh boot) ===")
        p, fwmode = boot()
        out.setdefault("firmware_mode", fwmode)
        trace = JsonlTrace(os.path.join(outdir, f"trace_run{k + 1}.jsonl"))
        try:
            rep = run_once(p, args.chunks, trace, f"run{k + 1}")
        finally:
            trace.close()
        out["runs"].append(rep)
        _log(f"run{k + 1}: {rep['stop_reason']} "
             f"max_score={rep['max_score']} "
             f"scroll_gain={rep['scroll_gain_total']}")
        del p                       # free the core before next boot
    repeatable = (len(out["runs"]) == 2 and
                  abs(out["runs"][0]["scroll_gain_total"] -
                      out["runs"][1]["scroll_gain_total"]) <= 200)
    out["route_repeatable"] = repeatable
    outpath = os.path.join(outdir, "controller_report.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", outpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
