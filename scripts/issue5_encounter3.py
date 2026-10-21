#!/usr/bin/env python3
"""issue5_encounter3.py — VALID checkpoint-based A/B at the wall.

Methodology fix (e1/e2 lesson): the f-count 'pretruck' landed on the
CONTINUE screen (flags_word cannot distinguish it — 255 there too), so
both earlier rounds measured countdown expiry, not combat. v3:

  1. walk until the FIRST churn collapse (real death fade)
  2. rapid-accept the continue (START/Y spam, churn-gated resume)
     -> the game respawns at its own village CHECKPOINT, i.e. right
        before the truck/helicopter encounter
  3. verify in-play (churn alive), save 'pretruck'
  4. variants from the SAME state, churn-gated 2600f horizon:
       A baseline RoutePolicy / B fire-held / E retreat-pulse /
       G gre40-fire
  5. metric = survival frames + end PNG (all states churn-verified)
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
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_recon import arm_cheats                          # noqa: E402
from issue5_encounter import churn, png                      # noqa: E402
from issue5_encounter2 import PulsePolicy, StopPulsePolicy   # noqa: E402


def _log(*a):
    print("[enc3]", *a, flush=True, file=sys.stderr)


def run_frames_alive(p, session, tel, policy, det, max_f, evid=None,
                     tag=""):
    """Run `policy` until churn collapse (death) or max_f.
    Returns (frames_run, died)."""
    prev_rgb = p.core.frame_rgb()
    dark, f = 0, 0
    while f < max_f:
        for s in policy.decide(60, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        c, rgb = churn(p, prev_rgb)
        prev_rgb = rgb
        if c is not None and c < 1.0:
            dark += 60
            if dark >= 60:          # first dark window = death fade —
                return f, True      # return IMMEDIATELY (the continue
                                    # countdown is already running)
        else:
            dark = 0
    return f, False


def rapid_accept(p, session, tel, evid, trace, tag, total=2600, period=30):
    """START/Y spam through GAME OVER + countdown + (if missed) the
    main-menu relaunch path; churn-gated resume with settle verify."""
    prev_rgb = p.core.frame_rgb()
    f = 0
    btn = "START"
    while f < total:
        session.run_frames(period - 8, set())
        session.run_frames(8, {btn})
        btn = "Y" if btn == "START" else "START"
        f += period
        c, rgb = churn(p, prev_rgb)
        prev_rgb = rgb
        if c is not None and c > 3.0:
            # screen came alive -> verify it STAYS alive (mission banner
            # is static-ish); a false trigger just continues the spam
            session.run_frames(120, set())
            c2, _ = churn(p, p.core.frame_rgb())
            if c2 is not None and c2 > 1.5:
                _log(f"[{tag}] resume detected at accept-f={f}")
                png(p, evid, f"{tag}_resumed.png")
                return True
            prev_rgb = p.core.frame_rgb()
    png(p, evid, f"{tag}_accept_failed.png")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="e3")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_enc3_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    info = arm_cheats(p, session, outdir)
    _log("bombs freeze:", info and info.get("bombs_addr"))

    # 1) walk to the first real death
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    f, died = run_frames_alive(p, session, tel, policy, det, 4200)
    _log(f"first death: f={f} died={died}")
    png(p, outdir, f"firstdeath_f{f:05d}.png")
    trace.write({"type": "first_death", "f": f, "died": died})

    # 2) continue -> checkpoint respawn
    ok = rapid_accept(p, session, tel, outdir, trace, "accept1")
    if not ok:
        sys.exit("!! continue accept failed")
    # settle + verify alive
    session.run_frames(120, set())
    c, _ = churn(p, p.core.frame_rgb())
    _log("post-accept churn:", c)

    # 3) save the checkpoint state
    p.save_state("pretruck")
    png(p, outdir, "pretruck.png")

    # 4) variants
    variants = [
        ("A_baseline", RoutePolicy(allow_grenades=True, jump_enabled=True)),
        ("B_fireheld", PulsePolicy(fwd=240, back=0)),
        ("E_retreat", PulsePolicy(fwd=60, back=30)),
        ("G_gre40", PulsePolicy(fwd=240, back=0, grenade_period=40)),
    ]
    results = []
    for tag, pol in variants:
        p.load_state("pretruck")
        pf, died = run_frames_alive(p, session, tel, pol, None, 2600)
        png(p, outdir, f"var_{tag}_end_f{pf:05d}.png")
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        r = {"variant": tag, "survived_f": pf, "died": died,
             "score_end": int(cur["score"]),
             "stats": getattr(pol, "stats", {})}
        results.append(r)
        trace.write({"type": "variant", **r})
        _log("variant:", r)

    out = {"results": results, "bombs": info and info.get("bombs_addr"),
           "boot": {"firmware": fwmode}}
    with open(os.path.join(outdir, "enc3_report.json"), "w") as fj:
        json.dump(out, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "enc3_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
