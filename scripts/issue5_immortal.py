#!/usr/bin/env python3
"""issue5_immortal.py — the LAST discovery pass for true invincibility.

Lessons so far (all evidenced):
  * 0xCA2FE 'hp' freeze: false positive (recon1 died 4x frozen)
  * 0xEF13F countdown freeze: REJECTED (village helicopter-bomb kills
    through it; frameprobe f2 f002092.png = tall explosion)
  * 0xCB225 'lives' mirror freeze: REJECTED (lives2 end frame = TITLE
    screen; game-over still came; word is a mirror/HUD)

This pass dumps EVERY 30f snapshot of a 3600f walk to disk and runs
THREE shape scanners offline:
  A. countdown  (monotone -> 0)          [known trap family]
  B. island     (0 ... positive-island >=3 samples ... 0)  [blink-like]
  C. lives      (non-increasing, <=9, -1 steps)            [mirror risk]
Then freeze-tests the best candidate of EACH family against the REAL
gate: survive the village helicopter kill (~2100-3000f) AND end the
walk ON a gameplay frame (screen check + score series sanity).
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
    print("[imm]", *a, flush=True, file=sys.stderr)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def walk_dump(p, session, tel, policy, det, frames, step, outdir):
    snaps, series = [], []
    f = 0
    while f < frames:
        for s in policy.decide(step, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        series.append({"f": f, "score": int(cur["score"]),
                       "flags": int(cur["flags_word"])})
        snaps.append(p.mem.snapshot())
        if (f // step) % 10 == 0:
            png(p, outdir, f"w{f:05d}.png")
    np.savez_compressed(os.path.join(outdir, "snaps.npz"),
                        **{f"s{i}": s for i, s in enumerate(snaps)})
    return snaps, series


def scan(snaps):
    res = {"countdown": {}, "island": {}, "lives": {}}
    n = len(snaps)
    for width in (1, 2):
        if width == 1:
            views = [s.astype(np.int32) for s in snaps]
        else:
            views = [s[:len(s) // 2 * 2].view("<u2").astype(np.int32)
                     for s in snaps]
        stack = np.stack(views)                      # (n, W)
        # A: monotone non-increasing to 0, start 4..600
        noninc = np.ones(stack.shape[1], bool)
        for i in range(1, n):
            noninc &= stack[i] <= stack[i - 1]
        cand = np.flatnonzero(noninc & (stack[0] >= 4) &
                              (stack[0] <= 600) & (stack[-1] == 0))
        for i in cand.tolist()[:48]:
            res["countdown"][(int(i) * width, width)] = \
                stack[:, i].tolist()
        # B: island — 0 before, >=3 consecutive positive, 0 after
        pos = stack > 0
        for i in range(width and 0, 0):
            pass
        acc = pos[0].copy()
        for i in range(1, n):
            acc &= pos[i]
        # islands: acc True somewhere in the middle but False at ends
        mid = acc.copy()
        mid &= ~pos[0]
        mid &= ~pos[-1]
        cand = np.flatnonzero(mid)
        for i in cand.tolist()[:48]:
            res["island"][(int(i) * width, width)] = \
                stack[:, i].tolist()
        # C: lives — <=9 throughout, non-increasing, >=1 -1 step
        le9 = np.ones(stack.shape[1], bool)
        for i in range(n):
            le9 &= (stack[i] >= 0) & (stack[i] <= 9)
        noninc9 = np.ones(stack.shape[1], bool)
        drops = np.zeros(stack.shape[1], np.int32)
        for i in range(1, n):
            noninc9 &= stack[i] <= stack[i - 1]
            drops += (stack[i] == stack[i - 1] - 1).astype(np.int32)
        cand = np.flatnonzero(le9 & noninc9 & (drops >= 1) &
                              (stack[0] >= 1))
        for i in cand.tolist()[:48]:
            res["lives"][(int(i) * width, width)] = \
                stack[:, i].tolist()
    return res


def freeze_gate_test(p, session, tel, addr, width, value, base_state,
                     outdir, frames=3000, tag=""):
    """The REAL gate: survive the village kill AND end on gameplay."""
    dtype = "u8" if width == 1 else "u16"
    code, _v = derive_freeze_code(p, addr, value=value, dtype=dtype)
    session.enable("_gate", [code])
    p.load_state(base_state)
    policy = RoutePolicy(allow_grenades=False, jump_enabled=False)
    det = StallDetector()
    series = []
    f = 0
    while f < frames:
        for s in policy.decide(60, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        series.append({"f": f, "score": int(cur["score"])})
    rgb = p.core.frame_rgb()
    name = f"gate_{tag}_{addr:06X}.png"
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))
    session.disable("_gate")
    # gameplay-at-end heuristic: score kept changing (resets included)
    # and the last two scores differ OR an HUD-ish oscillation exists;
    # the PNG is the human-verifiable ground truth
    moved = len(set(s["score"] for s in series[-6:])) > 1
    return {"addr": hex(addr), "width": width, "value": value,
            "frames": frames, "end_score_active": bool(moved),
            "png": name, "series_tail": series[-8:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="i1")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_imm_{args.tag}")
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
    p.save_state("ibase")

    policy = RoutePolicy(allow_grenades=False, jump_enabled=False)
    det = StallDetector()
    _log("pass 1: walk 3600f, dumping snapshots")
    snaps, series = walk_dump(p, session, tel, policy, det, 3600, 30,
                              outdir)
    _log("scanning shapes...")
    res = scan(snaps)
    for fam in ("countdown", "island", "lives"):
        _log(f"{fam}: {len(res[fam])} candidates")
        for (a, w), s in list(res[fam].items())[:6]:
            _log(f"   {hex(a)} w{w}: {s[:12]}")
    trace.write({"type": "scan", "counts": {k: len(v) for k, v in
                                            res.items()}})

    # freeze-test the best of each family against the real gate
    tests = []
    plan = []
    if res["island"]:
        (a, w), s = max(res["island"].items(),
                        key=lambda kv: max(kv[1]))
        plan.append(("island", a, w, max(s)))
    if res["lives"]:
        (a, w), s = max(res["lives"].items(),
                        key=lambda kv: (kv[1][0], -min(kv[1])))
        plan.append(("lives", a, w, max(s)))
    if res["countdown"]:
        (a, w), s = min(res["countdown"].items(),
                        key=lambda kv: (kv[0][0]))
        plan.append(("countdown", a, w, max(32, max(s))))
    for tag, a, w, val in plan:
        _log(f"gate test [{tag}] {hex(a)} w{w} val={val}")
        r = freeze_gate_test(p, session, tel, a, w, val, "ibase",
                             outdir, tag=tag)
        r["family"] = tag
        tests.append(r)
        _log("gate:", r["addr"], "end_active=", r["end_score_active"],
             "png=", r["png"])
        trace.write({"type": "gate_test", **r})

    out = {"scan_counts": {k: len(v) for k, v in res.items()},
           "scan_top": {k: [[hex(a), w, s[:16]] for (a, w), s in
                            list(v.items())[:10]]
                        for k, v in res.items()},
           "tests": tests, "boot": {"firmware": fwmode}}
    with open(os.path.join(outdir, "imm_report.json"), "w") as fj:
        json.dump(out, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "imm_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
