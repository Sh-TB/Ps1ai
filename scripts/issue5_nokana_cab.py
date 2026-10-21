#!/usr/bin/env python3
"""issue5_nokana_cab.py — time-boxed cab-position kill + timer discovery
(issue #5 continuation §6).

Learnings folded in:
  * point-blank RIGHT walk ends ON the truck roof — the cab (weak
    point) is at the truck's LEFT end: drop off the roof's left side,
    fight from the ground beside the cab.
  * the mission TIMER expires during long experiments (timer 200 seen)
    — restarts polluted earlier arms. Find the timer word live (scan
    u16 == observed HUD value), record it, and TIME-BOX the kill.
  * from the fresh arena the whole kill must fit ~2000 timer units.
"""
from __future__ import annotations

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
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode                # noqa: E402
from ps1play.agent.perception import PerceptionGuard      # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_explore_invuln import gs_run                  # noqa: E402
from issue5_encounter_hp import dump_entities, JsonlTrace, shot  # noqa
from issue5_ab_invuln import confirm_codrops              # noqa: E402
from issue5_nokana import Cam, reach_arena                # noqa: E402
from validate_inv2 import PAIR                            # noqa: E402

RAM_WORDS = 0x1FC000


def _log(*a):
    print("[cab]", *a, file=sys.stderr, flush=True)


def find_timer(p):
    """Scan for a u16 whose value is plausibly the HUD timer (down-
    counting). Call right after reading the HUD value from a shot."""
    ram = p.mem.snapshot()[:RAM_WORDS].view("<u2")
    cands = np.flatnonzero((ram >= 150) & (ram <= 210))
    return [int(c) * 2 for c in cands[:40]]


def main():
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"nokana_cab_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    if not g.get("in_mission"):
        sys.exit("!! gate failed")
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=_log)
    if anch.get("ok"):
        bombs_addr = guard.addrs["bombs"]
        v = int(p.mem.u8(bombs_addr))
        session.enable("bombs_freeze",
                       [GSCode(f"3{bombs_addr:07X} 00{v & 0xFF:02X}")])
    p.save_state("cb")
    codrops, _ = confirm_codrops(p)
    if codrops < 3:
        sys.exit("!! pair not reproduced")
    p.load_state("cb")
    p.core.run(10, set())
    f6, fe = int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1]))
    session.enable("invuln_explore",
                   [GSCode(f"8{PAIR[0]:07X} {f6:04X}"),
                    GSCode(f"8{PAIR[1]:07X} {fe:04X}")])
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    cam = Cam(p)
    phase, arena_cam = reach_arena(p, session, cam, trace, outdir)

    # approach + drop to the ground beside the cab
    for step in range(30):
        phase = gs_run(p, session, 20, {"RIGHT"}, phase)
    for step in range(8):
        phase = gs_run(p, session, 15, {"LEFT"}, phase)
    shot(p, outdir, "cab_position.png")
    p.save_state("pb")
    trace.write({"type": "pb_saved"})
    # timer discovery at the arena (HUD ~mid-range here)
    tc = find_timer(p)
    trace.write({"type": "timer_candidates", "n": len(tc),
                 "addrs": [hex(a) for a in tc[:20]]})
    _log(f"timer candidates in [150,210]: {len(tc)} "
         f"({[hex(a) for a in tc[:8]]})")

    # TIME-BOXED kill: 12 cycles only
    unlocked = False
    for cyc in range(12):
        phase = gs_run(p, session, 100, {"DOWN", "Y"}, phase)
        phase = gs_run(p, session, 8, {"UP"}, phase)
        phase = gs_run(p, session, 22, {"A"}, phase)
        phase = gs_run(p, session, 50, {"Y"}, phase)
        shot(p, outdir, f"cab_cyc{cyc:03d}.png")
        hp = {e["i"]: e["hp"] for e in dump_entities(p)}
        big = {i: h for i, h in hp.items() if h > 100 and i != 0}
        u = cam.update()
        trace.write({"type": "cycle", "n": cyc, "cam": u, "big": big})
        _log(f"cycle {cyc}: cam={u} big={big}")
        if u >= arena_cam + 150:
            unlocked = True
            trace.write({"type": "UNLOCKED", "cycle": cyc})
            _log(f"UNLOCKED at cycle {cyc}")
            break
    p.save_state("cp_deep")
    trace.write({"type": "run_end", "unlocked": unlocked})
    shot(p, outdir, "final.png")
    session.disable_all()
    _log("done:", outdir, "unlocked:", unlocked)


if __name__ == "__main__":
    main()
