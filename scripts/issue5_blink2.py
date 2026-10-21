#!/usr/bin/env python3
"""issue5_blink2.py — deterministic blink-window sampling at mission
START (not continue-respawn): boot() returns at control handover, so
sample RAM 5-frame-cadence immediately; then reload the savestate and
resample to prove reproducibility; then freeze-test the reproducible
countdown words by walking into live enemies.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.perception import PerceptionGuard       # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from mission import ensure_mission                         # noqa: E402
from issue4_controller import boot                         # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from issue5_invuln import find_countdowns, freeze_test, in_play  # noqa


def _log(*a):
    print("[blink2]", *a, file=sys.stderr, flush=True)


def png(p, evid, name):
    from PIL import Image
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def sample_window(p, evid, tag, snaps_n=30, step=5):
    snaps = [p.mem.snapshot()]
    for _ in range(snaps_n - 1):
        p.core.run(step, set())
        snaps.append(p.mem.snapshot())
    return find_countdowns(snaps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="b2")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_blink_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    _log("=== boot ===")
    p, fwmode = boot()
    tel = TelemetryAdapter(p)
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    ok0, cur = in_play(p, tel)
    _log("in play at boot return:", ok0, "flags", cur["flags_word"],
         "frame", cur["frame"])

    p.save_state("t0")
    cands1 = sample_window(p, outdir, "s1")
    _log(f"sample1: {len(cands1)} countdown candidates")
    p.load_state("t0")
    cands2 = sample_window(p, outdir, "s2")
    _log(f"sample2 (reload): {len(cands2)} countdown candidates")

    pool = {}
    for cd in cands1:
        pool[(cd["addr"], cd["width"])] = 1
    repro = []
    for cd in cands2:
        key = (cd["addr"], cd["width"])
        if key in pool:
            repro.append(cd)
    _log(f"reproducible across reload: {len(repro)}")
    for cd in repro:
        _log("  cand", hex(cd["addr"]), "w", cd["width"],
             "series", cd["series"][:12])
    trace.write({"type": "samples", "s1": len(cands1), "s2": len(cands2),
                 "repro": [c["addr"] for c in repro[:40]]})

    # freeze-test up to 4 reproducible candidates (small addr first)
    tests = []
    for cd in sorted(repro, key=lambda c: c["addr"])[:4]:
        r = freeze_test(p, session, cd["addr"], cd["width"], "t0", outdir)
        tests.append(r)
        trace.write({"type": "blink_freeze_test", **r})
        _log("freeze test:", r)
        if r["verdict"] == "INVULN_VERIFIED":
            break

    res = {"boot": {"firmware": fwmode}, "s1": len(cands1),
           "s2": len(cands2), "repro": repro[:20], "tests": tests,
           "wall_s": round(time.time() - time.time(), 1)}
    with open(os.path.join(outdir, "blink2_report.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    _log("report:", os.path.join(outdir, "blink2_report.json"))
    trace.close()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
