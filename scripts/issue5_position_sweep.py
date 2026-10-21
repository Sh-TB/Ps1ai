#!/usr/bin/env python3
"""issue5_position_sweep.py — X-position sweep for the boss-helicopter
hit problem (issue #5 continuation §6).

Evidence so far: at the camera-locked barrier (~2303) the stable
entity slots 14 (hp 247), 17 (223), 18 (160) take NO damage from
right-pinned fire (boss1: 40 grenade+antiair cycles). The helicopter
hovers top-LEFT while the truck pins the player right — X mismatch.

This probe: from the SAME barrier checkpoint (cb2 saved by
issue5_boss_hunt) run anti-air bursts from different player X
positions and watch slots 14/17/18:
  arm LEFT   : walk LEFT ~15 chunks, UP+Y bursts
  arm CENTER : stay, UP+Y bursts longer
  arm JUMPUP : stationary UP+B (jump) + UP+Y (aim high)
  arm GRENADE_UP : UP-hold grenade arcs (A with UP)
Each arm restarts from cb2 (GS re-engaged every time).
"""
from __future__ import annotations

import json
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode                # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_explore_invuln import gs_run                  # noqa: E402
from issue5_encounter_hp import dump_entities, JsonlTrace, shot  # noqa
from validate_inv2 import PAIR                            # noqa: E402

WATCH = [5, 8, 14, 17, 18, 19, 21]


def _log(*a):
    print("[sweep]", *a, file=sys.stderr, flush=True)


def arms(p, session, phase, trace, outdir):
    results = {}

    def from_cb2(name):
        p.load_state("cb2")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        return dump_entities(p)

    plan = [
        ("LEFT_AA", [( ["LEFT"], 900 ), (["UP", "Y"], 1500),
                     (["LEFT", "Y"], 600)]),
        ("CENTER_AA", [([], 60), (["UP", "Y"], 2400)]),
        ("JUMP_AA", [([], 60)] +
                    [([], 10), (["UP", "B"], 26), (["Y"], 50),
                     (["UP", "Y"], 60)] * 12),
        ("GRENADE_UP", [([], 60)] +
                       [(["UP"], 8), (["A"], 24), (["UP", "Y"], 90)] * 10),
    ]
    for name, segs in plan:
        before = from_cb2(name)
        bmap = {e["i"]: e["hp"] for e in before}
        for btns, frames in segs:
            phase = gs_run(p, session, frames, set(btns), phase)
        after = dump_entities(p)
        amap = {e["i"]: e["hp"] for e in after}
        delta = {i: amap.get(i, 0) - bmap.get(i, 0)
                 for i in set(bmap) | set(amap)
                 if amap.get(i, 0) != bmap.get(i, 0)}
        results[name] = {"hp_delta": delta, "after": after}
        shot(p, outdir, f"arm_{name}.png")
        trace.write({"type": "arm", "name": name, "hp_delta": delta,
                     "after": after})
        _log(f"arm {name}: delta={delta}")
    return results


def main():
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"pos_sweep_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    if not g.get("in_mission"):
        sys.exit("!! gate failed")
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    # load the barrier savestate FIRST, then derive the freeze codes
    # from the loaded RAM (cb2 carries boss1's frozen pair values)
    p.load_state("cb2")
    p.core.run(10, set())
    f6, fe = int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1]))
    session.enable("invuln_explore",
                   [GSCode(f"8{PAIR[0]:07X} {f6:04X}"),
                    GSCode(f"8{PAIR[1]:07X} {fe:04X}")])
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    trace.write({"type": "cheat", "pair": [f6, fe]})

    phase = 0
    res = arms(p, session, phase, trace, outdir)
    trace.write({"type": "run_end", "arms": list(res)})
    session.disable_all()
    _log("done:", outdir)


if __name__ == "__main__":
    main()
