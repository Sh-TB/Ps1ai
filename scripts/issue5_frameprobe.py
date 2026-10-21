#!/usr/bin/env python3
"""issue5_frameprobe.py — watch the deterministic village death
frame-by-frame: from a fresh boot, walk ~2300f with the blink frozen,
then record a PNG every 8 frames for 900 frames (the death window).
Answers: WHAT kills Marco (projectile? crush? scripted?) and whether
any dodge window exists.
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
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_recon import _blink_candidates                   # noqa: E402


def _log(*a):
    print("[frameprobe]", *a, flush=True, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="f1")
    ap.add_argument("--pre", type=int, default=2300)
    ap.add_argument("--window", type=int, default=1000)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_frameprobe_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    cands = _blink_candidates(p)
    cd = sorted(cands, key=lambda c: (c["width"], c["addr"]))[0]
    dtype = "u8" if cd["width"] == 1 else "u16"
    code, _v = derive_freeze_code(p, cd["addr"],
                                  value=max(int(cd["series"][0]), 32),
                                  dtype=dtype)
    session.enable("invuln_blink", [code])
    _log("blink frozen:", code.raw)

    policy = RoutePolicy(allow_grenades=False, jump_enabled=False)
    det = StallDetector()
    f = 0
    for _ in range(args.pre // 100):
        for s in policy.decide(100, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        if cur["flags_word"] != 0xFF:
            _log("died early at f=", f)
    _log(f"pre-walk done at f={f}; dense recording starts")
    dense = 0
    for i in range(args.window // 8):
        for s in policy.decide(8, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(os.path.join(
                outdir, f"f{f:06d}.png"))
        trace.write({"type": "d", "f": f, "flags": cur["flags_word"],
                     "score": cur["score"]})
        dense += 8
        if cur["flags_word"] != 0xFF:
            _log("death during dense window at f=", f)
            break
    _log("done; dense frames:", dense)
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
