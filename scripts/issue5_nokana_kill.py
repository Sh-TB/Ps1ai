#!/usr/bin/env python3
"""issue5_nokana_kill.py — SUSTAINED Iron Nokana kill attempt
(issue #5 continuation §6).

nokana probe: fresh-arena arms land real damage (slots 15/20/8/19/10
drop ~100-200 per 900f arm; 11/21 full kills on soldiers) but each arm
reloaded the arena checkpoint — resetting the fight. This run: ONE
continuous sequence from the fresh arena, no reloads:

  loop 24x: [crouch-Y 90f, grenade, stand-Y 60f, reposition LEFT 12f]
  screenshots every 200f + entity dumps every 2 loops + camera track.
Success: camera unlock (advance resumes) or a big HP pool at 0.
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
from ps1play.agent.perception import PerceptionGuard      # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_explore_invuln import gs_run                  # noqa: E402
from issue5_encounter_hp import dump_entities, JsonlTrace, shot  # noqa
from issue5_ab_invuln import confirm_codrops              # noqa: E402
from issue5_nokana import Cam, reach_arena                # noqa: E402
from validate_inv2 import PAIR                            # noqa: E402


def _log(*a):
    print("[nokill]", *a, file=sys.stderr, flush=True)


def main():
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"nokana_kill_{time.strftime('%Y%m%d_%H%M%S')}")
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
    p.save_state("arena")
    trace.write({"type": "arena", "cam": arena_cam})

    unlocked = False
    for loop in range(24):
        phase = gs_run(p, session, 12, {"LEFT"}, phase)
        phase = gs_run(p, session, 90, {"DOWN", "Y"}, phase)
        phase = gs_run(p, session, 8, {"UP"}, phase)
        phase = gs_run(p, session, 22, {"A"}, phase)
        phase = gs_run(p, session, 60, {"Y"}, phase)
        if loop % 2 == 0:
            hp = {e["i"]: e["hp"] for e in dump_entities(p)}
            u = cam.update()
            trace.write({"type": "loop", "n": loop, "cam": u,
                         "hp": hp})
            _log(f"loop {loop}: cam={u} hp_big="
                 f"{ {i: h for i, h in hp.items() if h > 100} }")
        if loop % 1 == 0 and loop % 2 == 1:
            shot(p, outdir, f"kill_loop{loop:03d}.png")
        u = cam.update()
        if u >= arena_cam + 150:
            unlocked = True
            trace.write({"type": "UNLOCKED", "loop": loop, "cam": u})
            _log(f"UNLOCKED loop {loop} cam {u}")
            shot(p, outdir, f"UNLOCKED_loop{loop:03d}.png")
            break

    if unlocked:
        # advance mapping: 40 chunks with channel-jump cadence
        for c in range(40):
            phase = gs_run(p, session, 60, {"RIGHT", "Y"}, phase)
            if c % 3 == 2:
                phase = gs_run(p, session, 40, {"RIGHT", "B"}, phase)
            u = cam.update()
            trace.write({"type": "advance", "chunk": c, "cam": u})
            if c % 10 == 0:
                shot(p, outdir, f"adv_c{c:03d}.png")
                _log(f"advance c{c} cam={u}")
    p.save_state("cp_deep")
    trace.write({"type": "run_end", "unlocked": unlocked,
                 "final_cam": cam.update()})
    shot(p, outdir, "final.png")
    session.disable_all()
    _log("done:", outdir, "unlocked:", unlocked)


if __name__ == "__main__":
    main()
