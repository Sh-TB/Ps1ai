#!/usr/bin/env python3
"""issue5_livesprobe.py — discover the LIVES counter from real deaths
and freeze it for traversal (fallback immortality: death -> checkpoint
respawn, never game-over).

Evidence correction first (recorded in the report):
  * the 0xEF13F "blink" freeze does NOT protect — issue5_deathprobe
    d1/d2/d3 + frameprobe f1/f2 all died at the village helicopter
    bomb (~2100-3000f) with it frozen. The b2 900f freeze test was
    shorter than the ~2100f baseline death -> verdict was unsound.
    invuln_blink status: VERIFIED -> TESTED/REJECTED (registry).
  * the village kill = tall vertical explosion from the follower
    helicopter's bomb (frameprobe f2 f002092.png) — it ignores the
    frozen countdown word.

Lives discovery (event-conditioned, smallest diff):
  1. arm bombs freeze (verified), drive right, RAM ring 30f cadence.
  2. on the FIRST death (score telemetry drop), keep sampling through
     respawn; post_respawn.lives == pre_death.lives - 1 identifies the
     lives word (u8/u16), intersected over 2 deaths.
  3. freeze-test: with lives frozen, survive >= 3 deaths and 4000f
     with NO continue screen (PNG-checked) -> LIVES_FREEZE TESTED.
"""
from __future__ import annotations

import argparse
import collections
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
    print("[livesprobe]", *a, flush=True, file=sys.stderr)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def lives_candidates(pre, post, prev_hits=None):
    """Words with post == pre - 1 (u8/u16), bounded 0..9, in RAM."""
    out = set()
    for width in (1, 2):
        if width == 1:
            a, b = pre.astype(np.int32), post.astype(np.int32)
        else:
            n = min(len(pre), len(post)) // 2 * 2
            a = pre[:n].view("<u2").astype(np.int32)
            b = post[:n].view("<u2").astype(np.int32)
        d = b - a
        hits = np.flatnonzero(d == -1)
        for i in hits.tolist():
            v = int(b[i])
            if 0 <= v <= 9:
                out.add((i * width, width))
    if prev_hits is not None:
        out &= prev_hits
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="l1")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_lives_{args.tag}")
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
    ring = collections.deque(maxlen=6)        # (walk_f, frame, snap)
    hits = None
    deaths = 0
    samples = []
    f = 0
    t0 = time.time()
    prev_score = None
    in_death_window = False
    post_snap = None
    while f < 5200 and deaths < 2:
        for s in policy.decide(30, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        ring.append((f, cur["frame"], p.mem.snapshot()))
        sc = cur["score"]
        dropped = prev_score is not None and sc < prev_score - 50
        trace.write({"type": "c", "f": f, "score": sc,
                     "dropped": bool(dropped)})
        if dropped and not in_death_window:
            deaths += 1
            in_death_window = True
            _log(f"death #{deaths} detected at f={f} "
                 f"({prev_score}->{sc}); sampling respawn")
            png(p, outdir, f"death{deaths}_f{f:05d}.png")
            pre = ring[-2][2] if len(ring) >= 2 else ring[-1][2]
            # sample every 10f for 480f through the respawn
            post = None
            for k in range(48):
                p.core.run(10, set())
                f += 10
                s2 = p.mem.snapshot()
                cur2 = tel.snapshot(buttons=[], frame=p.core.frames_run)
                if cur2["score"] >= 200 and k > 6 and post is None:
                    post = s2
                    png(p, outdir, f"respawn{deaths}_f{f:05d}.png")
            if post is not None:
                new = lives_candidates(pre, post, hits)
                samples.append({"death": deaths,
                                "cands": [list(x) for x in
                                          sorted(new)][:24]})
                hits = new if hits is None else new
                _log(f"lives-candidate interset: {len(hits)} "
                     f"-> {[hex(a) for a, _w in sorted(hits)][:10]}")
            in_death_window = False
            prev_score = tel.snapshot(buttons=[],
                                      frame=p.core.frames_run)["score"]
            continue
        prev_score = sc

    res = {"deaths_seen": deaths,
           "candidates": [[hex(a), w] for a, w in sorted(hits or [])][:24],
           "per_death": samples, "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(outdir, "lives_report.json"), "w") as fj:
        json.dump(res, fj, indent=1, default=str)
    _log("report:", os.path.join(outdir, "lives_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
