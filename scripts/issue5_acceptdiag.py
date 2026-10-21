#!/usr/bin/env python3
"""issue5_acceptdiag.py — dense diagnostics of the CONTINUE screen:
die, then alternate START/Y every 30f with a PNG after every tap.
Answers: when does the countdown appear, what does each tap do, which
button accepts, and what is the exact menu-relaunch sequence.
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import TelemetryAdapter             # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_recon import arm_cheats                          # noqa: E402
from issue5_encounter import churn, png                      # noqa: E402
from issue5_encounter3 import run_frames_alive                # noqa: E402


def _log(*a):
    print("[diag]", *a, flush=True, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="ad1")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_acceptdiag_{args.tag}")
    os.makedirs(outdir, exist_ok=True)

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    arm_cheats(p, session, outdir)

    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    f, died = run_frames_alive(p, session, tel, policy, det, 4200)
    _log(f"death detected f={f} died={died}")
    png(p, outdir, f"death_f{f:05d}.png")

    # dense tap loop: every 30f, alternate START/Y, PNG after each tap
    btn = "START"
    for i in range(60):
        session.run_frames(22, set())
        session.run_frames(8, {btn})
        png(p, outdir, f"t{i:02d}_{btn.lower()}.png")
        _log(f"tap {i} {btn} at +{(i + 1) * 30}f")
        btn = "Y" if btn == "START" else "START"
        # stop early if gameplay resumed (churn alive twice in a row)
        c, _ = churn(p, p.core.frame_rgb())
        if c is not None and c > 3.0:
            session.run_frames(60, set())
            c2, _ = churn(p, p.core.frame_rgb())
            if c2 is not None and c2 > 2.0:
                _log(f"gameplay resumed at tap {i}")
                png(p, outdir, f"RESUMED_t{i:02d}.png")
                break
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
