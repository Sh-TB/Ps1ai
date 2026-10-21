#!/usr/bin/env python3
"""issue5_patch_ab.py — isolate the bombs_patch effect on early-run
deaths.  Two arms from independent fresh boots, 40 chunks each:
  arm A: NO cheats (pure policy loop)
  arm B: bombs_patch 800398BE 2400 enabled from chunk 0
Deaths are counted with the chunk-level score-collapse oracle
(score drops >30 below the running max; flags!=0xFF).  The suspicion:
with this boot's root slot = 0xA0 handle, NOPing the sb at 0x800398BC
may corrupt a non-grenade field and cause the respawn storm seen in
inv12 (5 score collapses in 9 chunks)."""
from __future__ import annotations

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.agent.gameshark import GameShark, GSCode     # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.telemetry import TelemetryAdapter            # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402

SCORE_ADDR = 0x0EE318


def _log(*a):
    print("[patchab]", *a, file=sys.stderr, flush=True)


def run_arm(with_patch, chunks=40):
    p, fwmode = boot()
    g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
    gs = GameShark(p.mem)
    if with_patch:
        code = GSCode("800398BE 2400")
        ok, hi = gs.branch_plausible(code.addr)
        _log(f"patch branch_plausible={ok} pre_hi={hex(hi)}")
        gs.enable("bombs_patch", [code])
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    smax = int(p.mem.u32(SCORE_ADDR))
    deaths = []
    rgb_prev = p.core.frame_rgb()
    for c in range(chunks):
        segs = policy.decide(60, det)
        for s in segs:
            p.core.set_buttons(set(s["btns"] or set()))
            for _ in range(s["frames"]):
                p.core.run_frame()
                gs.tick()
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        evs = tel.events(prev, cur)
        s = int(p.mem.u32(SCORE_ADDR))
        dec = (s < smax - 30) or cur["flags_word"] != 0xFF or \
            any(e["type"] == "death_candidate" for e in evs)
        smax = max(smax, s)
        if dec:
            deaths.append({"chunk": c, "score": s,
                           "flags": hex(cur["flags_word"])})
            smax = s                     # restart the max after respawn
        prev = cur
    _log(f"arm {'PATCH' if with_patch else 'CLEAN'}: "
         f"deaths={len(deaths)} {deaths[:10]}")
    out = {"with_patch": with_patch, "deaths": deaths,
           "n_deaths": len(deaths)}
    del p
    return out


def main():
    a = run_arm(False)
    b = run_arm(True)
    print({"clean": a["n_deaths"], "patched": b["n_deaths"],
           "clean_detail": a["deaths"][:12],
           "patched_detail": b["deaths"][:12]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
