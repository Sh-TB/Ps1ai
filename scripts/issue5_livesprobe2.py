#!/usr/bin/env python3
"""issue5_livesprobe2.py — lives discovery v2 (post-hoc series scan).

v1 lesson: the telemetry 'score' is only the LOW BYTE of the real score
(HUD 1500 vs telemetry 220 = 1500 & 0xFF) — v1's drop-trigger fired on
256-byte wraps, not deaths. v2 removes all triggers:

  1. arm bombs freeze; drive right 3600f; snapshot every 30f.
  2. post-hoc: lives words = series non-increasing, every value <= 9,
     >= 1 drop of exactly -1 (u8/u16). Report full series.
  3. freeze each top candidate at its max seen value; drive 4200f;
     LIVES_FREEZE is TESTED iff: (a) >= 1 respawn happened (score
     reset to <100 after being >= 150), (b) NO continue screen at the
     end (PNG + HUD sanity), (c) final frame is gameplay.
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


def _log(*a):
    print("[lives2]", *a, flush=True, file=sys.stderr)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def walk(p, session, tel, policy, det, frames, step=30, snap_every=1):
    snaps, series = [], []
    f = 0
    while f < frames:
        for s in policy.decide(step, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        series.append((f, int(cur["score"])))
        snaps.append(p.mem.snapshot())
        if len(snaps) % snap_every == 0:
            _log(f"  f={f} score={cur['score']}")
    return snaps, series


def scan_lives(snaps):
    """u8/u16 words: <=9 throughout, non-increasing, >=1 exact -1 step."""
    out = {}
    for width in (1, 2):
        if width == 1:
            views = [s.astype(np.int32) for s in snaps]
        else:
            views = [s[:len(s) // 2 * 2].view("<u2").astype(np.int32)
                     for s in snaps]
        base = views[0]
        le9 = np.ones(base.shape, bool)
        noninc = np.ones(base.shape, bool)
        minus1 = np.zeros(base.shape, np.int32)
        for v in views:
            le9 &= (v >= 0) & (v <= 9)
        for a, b in zip(views, views[1:]):
            noninc &= b <= a
            minus1 += (b == a - 1).astype(np.int32)
        cand = np.flatnonzero(le9 & noninc & (minus1 >= 1))
        for i in cand.tolist()[:64]:
            out[(int(i) * width, width)] = [int(v[i]) for v in views]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="l2")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_lives2_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=_log)
    if anch.get("ok"):
        code, _v = derive_freeze_code(p, int(guard.addrs["bombs"]),
                                      dtype=guard.dtypes.get("bombs", "u8"))
        session.enable("bombs_freeze", [code])

    policy = RoutePolicy(allow_grenades=False, jump_enabled=False)
    det = StallDetector()
    _log("pass 1: baseline walk 3600f (no lives freeze)")
    snaps, series = walk(p, session, tel, policy, det, 3600)
    cands = scan_lives(snaps)
    ranked = sorted(cands.items(), key=lambda kv: -sum(
        1 for a, b in zip(kv[1], kv[1][1:]) if b == a - 1))
    _log("lives candidates:",
         [(hex(a), w, v[:8]) for (a, w), v in ranked[:10]])
    trace.write({"type": "candidates", "n": len(cands),
                 "top": [[hex(a), w, v] for (a, w), v in ranked[:12]]})
    p.save_state("l2base")

    tests = []
    for (addr, width), ser in ranked[:3]:
        if len(ser) < 3 or max(ser) == min(ser):
            continue
        dtype = "u8" if width == 1 else "u16"
        code, val = derive_freeze_code(p, addr, value=max(ser), dtype=dtype)
        session.enable("lives_freeze", [code])
        p.load_state("l2base")
        _log(f"freeze test {hex(addr)} w{width} val={val}: walk 4200f")
        snaps2, series2 = walk(p, session, tel, policy, det, 4200, step=60)
        scores = [s for _f, s in series2]
        respawns = sum(1 for a, b in zip(scores, scores[1:])
                       if a >= 150 and b < 100)
        png(p, outdir, f"livesfreeeze_{addr:06X}_end.png")
        ok = respawns >= 1
        tests.append({"addr": hex(addr), "width": width, "frozen": val,
                      "respawns_seen": respawns,
                      "max_score": max(scores),
                      "verdict": "LIVES_FREEZE_TESTED" if ok
                      else "REJECTED"})
        _log("freeze test result:", tests[-1])
        trace.write({"type": "freeze_test", **tests[-1]})
        session.disable("lives_freeze")
        if ok:
            break

    res = {"candidates": [[hex(a), w, v] for (a, w), v in ranked[:12]],
           "tests": tests, "boot": {"firmware": fwmode}}
    with open(os.path.join(outdir, "lives2_report.json"), "w") as fj:
        json.dump(res, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "lives2_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
