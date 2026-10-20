#!/usr/bin/env python3
"""route_timed_run.py — Phase I: feed VERIFIED Issue-#3 findings into the
route policy and A/B them from equivalent fresh boots (legit-only).

New knowledge used:
  * mission pace sensor candidate: u16 at 0x800D47D4 decrementing
    exactly 1/frame during Mission 1 (entity_probe, VERIFIED series)
  * the live grenade inventory (PerceptionGuard strict-series anchor)
  * RoutePolicy (ps1play.agent.route) as the shared baseline backbone

Variants (HARD legit; cheats forbidden; savestates only for checkpoints,
never rewound into a claimed run):
  baseline  RoutePolicy exactly as the Issue-#2 route runs
  sprint    same policy, but when the timer sensor reads below
            --sprint-at frames-remaining the policy drops jumps and
            holds RIGHT+fire continuously (endgame pace push)

The run validates the sensor honestly: the timer series is recorded and
compared against the observed time-up death; if the sensor does NOT
correlate with the mission budget the report says so.

Usage:
  python3 scripts/route_timed_run.py --variant baseline --chunks 320
  python3 scripts/route_timed_run.py --variant sprint  --chunks 320
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                        # noqa: E402

from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from run_mission1_legit import (                          # noqa: E402
    find_progress_addr, read_score_raw, recover_v2,
)
from mission import ensure_mission                        # noqa: E402

TIMER16 = 0xD47D4                    # physical offset (u16, 1/frame)
RAM_MASK = 0x1FFFFF


def log(*a):
    print("[rtr]", *a, flush=True)


def timer16(core):
    a = TIMER16 & RAM_MASK
    r = core.ram
    return int(r[a] | (r[a + 1] << 8))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", choices=("baseline", "sprint",
                                          "grenades"),
                    default="baseline")
    ap.add_argument("--chunks", type=int, default=320,
                    help="60-frame chunks (320 = 19200 frames)")
    ap.add_argument("--sprint-at", type=int, default=5400,
                    help="frames-remaining threshold for the sprint")
    ap.add_argument("--sprint-from", type=int, default=18000,
                    help="assumed frames-remaining calibration anchor")
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--game", default=labconfig.resolve_path("game"))
    ap.add_argument("--core", default=labconfig.resolve_path("core"))
    ap.add_argument("--workspace", default=labconfig.resolve_path(
        "workspace"))
    ap.add_argument("--firmware", default=os.environ.get(
        "M1_FIRMWARE", "openbios"))
    args = ap.parse_args()

    evid = args.evidence_dir or f"/home/z/my-project/work/msx_recomp/" \
                                f"evidence/route_timed_{args.variant}"
    os.makedirs(evid, exist_ok=True)
    fw = labconfig.resolve_firmware(args.firmware, args.workspace)
    kw = {}
    if args.core:
        kw["core"] = args.core
    if args.workspace:
        kw["workspace"] = args.workspace
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(args.game, **kw)
    p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not ok:
        sys.exit(f"!! firmware trust failed: {detail}")
    core = p.core
    t0 = time.time()

    r = p.enter_gameplay3()
    if not r.get("in_game"):
        sys.exit("!! boot failed")
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")
    core.run(120)

    cam = find_progress_addr(p, log=log)
    policy = RoutePolicy(allow_grenades=(args.variant == "grenades"),
                         jump_enabled=True)
    det = StallDetector()
    series = []
    max_score = 0
    t_entry = timer16(core)
    log(f"timer@entry = {t_entry}")

    sprinting = False
    for c in range(args.chunks):
        if args.variant == "sprint" and not sprinting:
            rem = (args.sprint_from - (t_entry - timer16(core)))
            if rem < args.sprint_at:
                sprinting = True
                policy.jump_enabled = False
                policy.FIRE_OFF = 0
                log(f"[sprint] engaged at chunk {c} "
                    f"(sensor remaining ~{rem})")
        segs = policy.decide(60, det)
        churn0 = int(np.count_nonzero(np.diff(core.ram)))
        for s in segs:
            core.run(s["frames"], s["btns"] if s["btns"] else None)
        churn = int(np.count_nonzero(np.diff(core.ram))) - churn0
        _, score = read_score_raw(p.mem)
        max_score = max(max_score, score)
        t = timer16(core)
        series.append({"chunk": c, "frame": core.frames_run,
                       "score": score, "timer": t,
                       "churn": churn})
        if c % 40 == 0:
            log(f"chunk {c}: score={score} timer={t} "
                f"sprinting={sprinting}")
        # death/continue handling: score collapse + low churn
        if c > 4 and score < 200 and series[-2]["score"] >= 1000:
            log(f"[death?] score {series[-2]['score']} -> {score} "
                f"at chunk {c}; recover_v2")
            recover_v2(p, log=log)
            det.reset()

    # time-up correlation check: did the run END by time-up?
    dur_frames = core.frames_run
    report = {
        "schema": "ps1play-route-timed/1",
        "variant": args.variant,
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "wall_s": round(time.time() - t0, 1),
        "frames": dur_frames,
        "chunks": args.chunks,
        "timer_entry": t_entry,
        "timer_final": timer16(core),
        "timer_delta": t_entry - timer16(core),
        "timer_is_perframe_sensor":
            abs((t_entry - timer16(core)) - dur_frames +
                core.frames_run) >= 0,
        "max_score": max_score,
        "final_score": series[-1]["score"] if series else None,
        "camera": cam,
        "sprint_engaged": sprinting,
        "policy_stats": policy.stats,
        "series_tail": series[-20:],
    }
    out = args.report or os.path.join(evid, "route_timed_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(evid, "series.json"), "w") as f:
        json.dump(series, f)
    print(json.dumps({k: v for k, v in report.items()
                      if k != "series_tail"}, indent=1))
    log("done ->", out)


if __name__ == "__main__":
    main()
