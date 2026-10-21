#!/usr/bin/env python3
"""issue5_encounter2.py — round 2 at the wall: bomb-lead dodge tactics.

Round-1 result: fire-held (RIGHT+Y always) doubled survival (1860f vs
960f baseline) but every variant still dies. The kill = tall vertical
explosions (helicopter bombs, frameprobe f2 f002092.png) that land on a
LEADING target — walking into them. Round 2 tests the dodge shape:

  E retreat-pulse  advance 60f / retreat 30f (bombs can't lead)
  F slow-advance   advance 45f / stop 15f
  G gre40-fire     fire-held + grenade every 40f (max DPS on truck)
All from the SAME pretruck savestate (one boot, in-process reload).
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
from ps1play.agent.route import StallDetector              # noqa: E402
from issue4_controller import boot                          # noqa: E402
from issue5_recon import arm_cheats                         # noqa: E402
from issue5_encounter import churn, png                      # noqa: E402


def _log(*a):
    print("[enc2]", *a, flush=True, file=sys.stderr)


class PulsePolicy:
    """Fire-held with a forward/retreat pulse."""

    def __init__(self, fwd=60, back=30, grenade_period=0):
        self.fwd, self.back = fwd, back
        self.gp = grenade_period
        self.fc = 0
        self.press = 0
        self.stats = {"grenade": 0}

    def decide(self, chunk, detector=None):
        segs = []
        prev = None
        for _ in range(chunk):
            u = self.fc % (self.fwd + self.back)
            btns = {"Y"}
            if u < self.fwd:
                btns.add("RIGHT")
            else:
                btns.add("LEFT")
            if self.gp and self.fc % self.gp == 0:
                self.press = 4
                self.stats["grenade"] += 1
            if self.press > 0:
                btns.add("A")
                self.press -= 1
            self.fc += 1
            if prev is not None and prev["btns"] == btns:
                prev["frames"] += 1
            else:
                prev = {"frames": 1, "btns": btns}
                segs.append(prev)
        return segs


class StopPulsePolicy:
    """Fire-held with stop pulses (advance 45f / stand 15f)."""

    def __init__(self, fwd=45, stop=15, grenade_period=0):
        self.fwd, self.stop = fwd, stop
        self.gp = grenade_period
        self.fc = 0
        self.press = 0
        self.stats = {"grenade": 0}

    def decide(self, chunk, detector=None):
        segs = []
        prev = None
        for _ in range(chunk):
            u = self.fc % (self.fwd + self.stop)
            btns = {"Y", "RIGHT"} if u < self.fwd else {"Y"}
            if self.gp and self.fc % self.gp == 0:
                self.press = 4
                self.stats["grenade"] += 1
            if self.press > 0:
                btns.add("A")
                self.press -= 1
            self.fc += 1
            if prev is not None and prev["btns"] == btns:
                prev["frames"] += 1
            else:
                prev = {"frames": 1, "btns": btns}
                segs.append(prev)
        return segs


def run_variant(p, session, tel, policy, evid, tag, frames=2600):
    p.load_state("pretruck")
    prev_rgb = p.core.frame_rgb()
    dead_at, dark, f = None, 0, 0
    while f < frames:
        for s in policy.decide(60):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        c, rgb = churn(p, prev_rgb)
        prev_rgb = rgb
        if c is not None and c < 1.0:
            dark += 60
            if dark >= 180 and dead_at is None:
                dead_at = f
                break
        else:
            dark = 0
    png(p, evid, f"var_{tag}_end_f{f:05d}.png")
    cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
    res = {"variant": tag, "survived_f": f if dead_at is None else dead_at,
           "died": dead_at is not None, "score_end": int(cur["score"]),
           "stats": getattr(policy, "stats", {})}
    _log("variant:", res)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="e2")
    ap.add_argument("--pre-frames", type=int, default=1800)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_enc2_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    info = arm_cheats(p, session, outdir)
    _log("bombs freeze:", info and info.get("bombs_addr"))

    policy = __import__("ps1play.agent.route", fromlist=["RoutePolicy"]) \
        .RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    f = 0
    while f < args.pre_frames:
        for s in policy.decide(60, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
    p.save_state("pretruck")
    png(p, outdir, "pretruck.png")
    _log(f"pretruck saved at f={f}")

    variants = [
        ("E_retreat_pulse", PulsePolicy(fwd=60, back=30)),
        ("F_slow_advance", StopPulsePolicy(fwd=45, stop=15)),
        ("G_gre40_fire", PulsePolicy(fwd=240, back=0, grenade_period=40)),
    ]
    results = []
    for tag, pol in variants:
        results.append(run_variant(p, session, tel, pol, outdir, tag))
        trace.write({"type": "variant", **results[-1]})

    out = {"pre_frames": args.pre_frames, "results": results,
           "bombs": info and info.get("bombs_addr"),
           "boot": {"firmware": fwmode}}
    with open(os.path.join(outdir, "enc2_report.json"), "w") as fj:
        json.dump(out, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "enc2_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
