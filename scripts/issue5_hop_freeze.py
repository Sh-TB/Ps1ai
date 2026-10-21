#!/usr/bin/env python3
"""issue5_hop_freeze.py — hop-over-the-truck under the VERIFIED freeze
(issue #5 continuation §6; user directive: learn the vehicle, jump it).

boss1/sweep learnings: (a) the arena has a mission TIMER — the kill
must happen inside it; (b) slots 14/17/18 never take damage — the
truck may be an unbeatable scripted push-wall; the way past is the
HOP (jump over the truck as it advances).

Arms from cb2 (barrier checkpoint), all under hp_pair freeze:
  HOP_INPLACE : back off LEFT 15f, full jump RIGHT+B 70f, x12
  HOP_RUNUP   : LEFT 60f run, RIGHT run 30f, RIGHT+B 80f hold, x10
  HOP_SPAM    : B held constantly + RIGHT, 3000f
  WAIT_DESCEND: stand + Y (let the truck advance), then hop x10
Success: camera unlock (unwrapped cam > 2450) or sustained advance.
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
    print("[hop]", *a, file=sys.stderr, flush=True)


class Cam:
    """Unwrapped u8 camera tracker."""
    def __init__(self, p):
        self.p = p
        self.prev = int(p.mem.u16(0xCA2E0))
        self.val = self.prev

    def update(self):
        cur = int(self.p.mem.u16(0xCA2E0))
        d = (cur - self.prev) & 0xFF
        if d >= 128:
            d -= 256
        self.val += d
        self.prev = cur
        return self.val


def run_arm(p, session, trace, outdir, name, cam, segs, hop_iter):
    p.load_state("cb2")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    base_unwrapped = cam.update()          # snapshot baseline (discard)
    before = dump_entities(p)
    phase = 0
    for it, segs_i in enumerate(segs() if callable(segs) else segs):
        for btns, frames in segs_i:
            phase = gs_run(p, session, frames, set(btns), phase)
        u = cam.update()
        hp = {e["i"]: e["hp"] for e in dump_entities(p)}
        trace.write({"type": "arm_iter", "arm": name, "iter": it,
                     "cam_unwrapped": u, "watch":
                     {i: hp.get(i) for i in WATCH}})
        if it % 3 == 0:
            shot(p, outdir, f"{name}_it{it:03d}.png")
        # UNLOCK = camera advanced > +150 vs the barrier band
        # (cb2 baseline ~2303; track per-arm via first reading)
        if it == 0:
            arm_base = u
        if u - arm_base > 150:
            trace.write({"type": "UNLOCKED", "arm": name, "iter": it,
                         "cam_unwrapped": u})
            _log(f"UNLOCKED arm {name} iter {it} cam {u}")
            shot(p, outdir, f"{name}_UNLOCKED_it{it:03d}.png")
            return True
    after = dump_entities(p)
    amap = {e["i"]: e["hp"] for e in after}
    bmap = {e["i"]: e["hp"] for e in before}
    delta = {i: amap.get(i, 0) - bmap.get(i, 0)
             for i in set(bmap) | set(amap)
             if amap.get(i, 0) != bmap.get(i, 0)}
    trace.write({"type": "arm_end", "arm": name, "hp_delta": delta})
    _log(f"arm {name} end: delta={delta}")
    return False


def main():
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"hop_freeze_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    if not g.get("in_mission"):
        sys.exit("!! gate failed")
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
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
    cam = Cam(p)

    arms = {
        "HOP_INPLACE": lambda: [[(["LEFT"], 15), (["RIGHT", "B"], 70)]
                                for _ in range(12)],
        "HOP_RUNUP": lambda: [(["LEFT"], 60), (["RIGHT"], 30),
                              (["RIGHT", "B"], 80), (["RIGHT"], 60)] * 1
                             if False else
                             [[(["LEFT"], 60), (["RIGHT"], 30),
                               (["RIGHT", "B"], 80), (["RIGHT"], 60)]
                              for _ in range(10)],
        "HOP_SPAM": [[(["RIGHT", "B"], 3000)]],
        "WAIT_DESCEND": [[(["Y"], 600)] +
                         [(["LEFT"], 15), (["RIGHT", "B"], 70)] * 1
                         for _ in range(1)] +
                        [[(["LEFT"], 15), (["RIGHT", "B"], 70)]
                         for _ in range(10)],
    }
    results = {}
    for name, segs in arms.items():
        results[name] = run_arm(p, session, trace, outdir, name, cam,
                                segs, 0)
        if results[name]:
            break
    trace.write({"type": "verdict", "unlocked_by": results})
    _log("verdict:", results)
    session.disable_all()
    _log("done:", outdir)


if __name__ == "__main__":
    main()
