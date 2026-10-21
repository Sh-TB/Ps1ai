#!/usr/bin/env python3
"""issue5_encounter.py — controlled A/B at THE wall: the village
truck+helicopter encounter (every death in recon6/7 clusters there).

Checkpoint-based experimentation (Phase 8): ONE boot, ONE savestate
taken just before the encounter, then policy variants reloaded from
the SAME state (verified in-process reload).

Variants (one variable each, same 2400f horizon):
  A baseline      RoutePolicy(grenade period 150, jump on)
  B fire-held     RIGHT+Y held continuously (no burst gaps)
  C gre60+fire    grenade period 60 + fire-held
  D gre60+ground  grenade period 60 + fire-held + no jump
Metrics: survival frames (visual churn collapse = death fade), score
series, end PNG per variant. Cheats: bombs freeze only (verified).
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
from ps1play.agent.cheatprof import (                      # noqa: E402
    CheatSession, CHEAT_ASSISTED, derive_freeze_code)
from ps1play.agent.perception import PerceptionGuard        # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_recon import arm_cheats                          # noqa: E402


def _log(*a):
    print("[enc]", *a, flush=True, file=sys.stderr)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def churn(p, prev_rgb):
    rgb = p.core.frame_rgb()
    if rgb is None or prev_rgb is None:
        return None, rgb
    c = round(float(np.abs(rgb.astype(np.int16) -
                          prev_rgb.astype(np.int16)).mean()), 2)
    return c, rgb


class FireHeldPolicy(RoutePolicy):
    """Variant B/C/D backbone: RIGHT+Y always; optional grenade cadence;
    optional jump."""

    def __init__(self, grenade_period=0, jump=False):
        super().__init__(allow_grenades=grenade_period > 0,
                         jump_enabled=jump)
        self.gp = grenade_period

    def decide(self, chunk, detector):
        segs = []
        prev = None
        for _ in range(chunk):
            btns = {"RIGHT", "Y"}
            if self.gp and self.fc % self.gp == 0:
                self.press = 4
                self.stats["grenade"] += 1
            if self.jump_enabled:
                if self.hop_hold > 0:
                    btns.add("B")
                    self.hop_hold -= 1
                elif self.hop_cd <= 0:
                    self.hop_hold = self.JUMP_HOLD
                    self.hop_cd = self.JUMP_PERIOD + self.JUMP_HOLD
                    self.stats["jump"] += 1
                else:
                    self.hop_cd -= 1
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


def run_variant(p, session, tel, policy, evid, tag, frames=2400):
    p.load_state("pretruck")
    det = StallDetector()
    prev_rgb = p.core.frame_rgb()
    dead_at = None
    score0 = tel.snapshot(buttons=[], frame=p.core.frames_run)["score"]
    f = 0
    dark = 0
    while f < frames:
        for s in policy.decide(60, det):
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
    cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
    png(p, evid, f"var_{tag}_end_f{f:05d}.png")
    res = {"variant": tag, "survived_f": f if dead_at is None else dead_at,
           "died": dead_at is not None, "score0": int(score0),
           "score_end": int(cur["score"]), "stats": dict(policy.stats)}
    _log("variant:", res)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="e1")
    ap.add_argument("--pre-frames", type=int, default=1800)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_enc_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    info = arm_cheats(p, session, outdir)
    bmb = None
    if info:
        bmb = info["bombs_addr"]
    _log("bombs freeze:", bmb)

    # walk to the pre-encounter point with the baseline policy
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
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
        ("A_baseline", RoutePolicy(allow_grenades=True, jump_enabled=True)),
        ("B_fireheld", FireHeldPolicy(grenade_period=0, jump=False)),
        ("C_gre60_fire", FireHeldPolicy(grenade_period=60, jump=False)),
        ("D_gre60_grd", FireHeldPolicy(grenade_period=60, jump=False)),
    ]
    # D differs from C only by jump: rebuild C with jump ON for a clean
    # single-variable pair (C=jump on, D=jump off)
    variants[2] = ("C_gre60_fire", FireHeldPolicy(grenade_period=60,
                                                  jump=True))
    results = []
    for tag, pol in variants:
        results.append(run_variant(p, session, tel, pol, outdir, tag))
        trace.write({"type": "variant", **results[-1]})

    out = {"pre_frames": args.pre_frames, "results": results,
           "bombs": bmb, "boot": {"firmware": fwmode}}
    with open(os.path.join(outdir, "enc_report.json"), "w") as fj:
        json.dump(out, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "enc_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
