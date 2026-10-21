#!/usr/bin/env python3
"""issue5_truckhop.py — the LAST tactical variant at the wall:
bunny-hop through the encounter (hop every ~50f) — jumps the armored
truck as it drives through and breaks the helicopter bomb's ground
lock. A/B from an in-process savestate taken just before the encounter:

  arm CTRL  : fire-held baseline (recon10 policy)  [dies every pass]
  arm HOP   : fire-held + hop every 50f
  arm HOPNG : hop + grenade every 100f
Verdict per arm: died (churn collapse) or PASSED (survived the window
AND the walk continues past the encounter — end PNG is gameplay).
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
from mission import responsive                              # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_recon import (arm_cheats, FireHeldPolicy, visual_dark,
                          recover_full)                      # noqa


def _log(*a):
    print("[hop]", *a, flush=True, file=sys.stderr)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


class HopPolicy(FireHeldPolicy):
    def __init__(self, hop_period=50, **kw):
        super().__init__(**kw)
        self.hp_ = hop_period

    def decide(self, chunk, detector):
        segs = []
        prev = None
        for _ in range(chunk):
            btns = {"RIGHT", "Y"}
            if self.fc % self.hp_ < 14:
                btns.add("B")
            if self.allow_grenades and \
                    self.fc % self.GRENADE_PERIOD == 0:
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


def run_arm(p, session, tel, policy, evid, tag, frames=2600):
    p.load_state("prewall")
    prev_rgb = p.core.frame_rgb()
    dead_at, dark, f = None, 0, 0
    while f < frames:
        for s in policy.decide(60, None):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        if visual_dark(p, wf=30, windows=1):
            dark += 30
            if dark >= 150:
                dead_at = f
                break
        else:
            dark = 0
    png(p, evid, f"arm_{tag}_f{f:05d}.png")
    cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
    return {"arm": tag, "frames": f, "died": dead_at is not None,
            "score_end": int(cur["score"]),
            "stats": dict(getattr(policy, "stats", {}))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="h1")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_hop_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    arm_cheats(p, session, outdir)

    # walk toward the encounter; on the (likely) death, recover via the
    # game's own continue/menu path — the checkpoint respawn lands right
    # AT the village encounter, i.e. the perfect prewall point
    pol = FireHeldPolicy(allow_grenades=True, jump_enabled=True)
    pol.GRENADE_PERIOD = 120
    from ps1play.agent.route import RoutePolicy as _RP, StallDetector as _SD
    det = _SD()
    from issue5_encounter3 import run_frames_alive as _rfa
    f, died = _rfa(p, session, tel, pol, det, 4200)
    _log(f"walk phase: f={f} died={died}")
    if died:
        trace.write({"type": "prewall_death", "f": f})
        ok = recover_full(p, tel, trace, outdir, 0, "prewall_rec")
        if not ok:
            sys.exit("!! prewall recovery failed")
        f = 0
        pol2 = FireHeldPolicy(allow_grenades=True, jump_enabled=True)
        pol2.GRENADE_PERIOD = 120
        while f < 150:                       # short settle-walk at cp
            for s in pol2.decide(60, None):
                session.run_frames(s["frames"], set(s["btns"] or set()))
                f += s["frames"]
        ok2, _g = responsive(p)
        if not ok2:
            sys.exit("!! not responsive at prewall")
    p.save_state("prewall")
    png(p, outdir, "prewall.png")
    _log(f"prewall saved (walk_f={f}, from_death={died})")

    arms = [
        ("CTRL", FireHeldPolicy(allow_grenades=True, jump_enabled=False)),
        ("HOP", HopPolicy(hop_period=50, allow_grenades=False)),
        ("HOPNG", HopPolicy(hop_period=50, allow_grenades=True)),
    ]
    arms[1][1].GRENADE_PERIOD = 0
    arms[2][1].GRENADE_PERIOD = 100
    results = []
    for tag, pol2 in arms:
        r = run_arm(p, session, tel, pol2, outdir, tag)
        results.append(r)
        trace.write({"type": "arm", **r})
        _log("arm:", r)

    out = {"results": results, "boot": {"firmware": fwmode}}
    with open(os.path.join(outdir, "hop_report.json"), "w") as fj:
        json.dump(out, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "hop_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
