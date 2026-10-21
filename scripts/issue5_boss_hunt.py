#!/usr/bin/env python3
"""issue5_boss_hunt.py — focused boss-kill probe at the barrier
(issue #5 continuation §6). From the barrier checkpoint: aggressive
grenade + anti-air cycles while watching the STABLE-HP entity slots
(the truck/helicopter candidates found by enc_hp: 14=247, 17=223,
5/11/21=254, 18=160). Success = a stable slot hits 0 AND the camera
unlocks (advance resumes).
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
from validate_inv2 import PAIR                            # noqa: E402

WATCH = [3, 4, 5, 8, 10, 11, 14, 15, 17, 18, 19, 21]
BARRIER_CAM_MAX = 240        # u8 value at the barrier (wrapped)


def _log(*a):
    print("[boss]", *a, file=sys.stderr, flush=True)


def main():
    tag = "boss1"
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"boss_hunt_{tag}_{time.strftime('%Y%m%d_%H%M%S')}")
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
    trace.write({"type": "pair_codrops", "n": codrops})
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

    # walk to the barrier (UNWRAPPED camera: the u8 wraps ~256, the
    # real position at the barrier is ~2303 unwrapped — inv20 evidence)
    phase = 0
    cam_prev = int(p.mem.u16(0xCA2E0))
    cam_unwrapped = cam_prev
    for c in range(90):
        phase = gs_run(p, session, 60, {"RIGHT"}, phase)
        cam = int(p.mem.u16(0xCA2E0))
        d = (cam - cam_prev) & 0xFF
        if d >= 128:
            d -= 256
        cam_unwrapped += d
        cam_prev = cam
        trace.write({"type": "walk", "chunk": c, "cam_u8": cam,
                     "cam_unwrapped": cam_unwrapped})
        if cam_unwrapped >= 2200:
            _log(f"barrier at chunk {c} (unwrapped {cam_unwrapped})")
            break
    p.save_state("cb2")
    p.save_state("cp_deep")
    trace.write({"type": "barrier", "chunk": c,
                 "entities": dump_entities(p)})

    # aggressive kill cycles: grenade x2 then UP+Y burst, watch slots
    unlocked = False
    for cycle in range(40):
        for _g in range(2):
            phase = gs_run(p, session, 8, {"UP"}, phase)
            phase = gs_run(p, session, 22, {"A"}, phase)
        phase = gs_run(p, session, 90, {"UP", "Y"}, phase)
        phase = gs_run(p, session, 40, {"RIGHT", "Y"}, phase)
        d = dump_entities(p)
        hp = {e["i"]: e["hp"] for e in d}
        cam = int(p.mem.u16(0xCA2E0))
        d = (cam - cam_prev) & 0xFF
        if d >= 128:
            d -= 256
        cam_unwrapped += d
        cam_prev = cam
        watch = {i: hp.get(i) for i in WATCH}
        trace.write({"type": "cycle", "n": cycle, "cam_u8": cam,
                     "cam_unwrapped": cam_unwrapped, "watch": watch})
        if cycle % 5 == 0:
            shot(p, outdir, f"cycle_{cycle:03d}.png")
            _log(f"cycle {cycle}: cam={cam} watch={watch}")
        # unlock check: UNWRAPPED camera moved >= +150 past 2303
        if cam_unwrapped >= 2450:
            unlocked = True
            trace.write({"type": "UNLOCKED", "cycle": cycle,
                         "cam_unwrapped": cam_unwrapped})
            _log(f"UNLOCKED at cycle {cycle} "
                 f"(unwrapped {cam_unwrapped})")
            shot(p, outdir, f"UNLOCKED_c{cycle:03d}.png")
            break
        # keep position: if pushed back toward the desert, walk right
        if hp.get(0, 131) != f6:
            trace.write({"type": "pair_drift", "cycle": cycle,
                         "hp": hp.get(0)})
    # if unlocked, advance up to 60 chunks mapping the route
    if unlocked:
        for c in range(60):
            phase = gs_run(p, session, 60, {"RIGHT", "Y"}, phase)
            if c % 30 in (5, 15):
                # channel cadence: jump
                phase = gs_run(p, session, 40, {"RIGHT", "B"}, phase)
            cam = int(p.mem.u16(0xCA2E0))
            d = (cam - cam_prev) & 0xFF
            if d >= 128:
                d -= 256
            cam_unwrapped += d
            cam_prev = cam
            trace.write({"type": "advance", "chunk": c,
                         "cam_unwrapped": cam_unwrapped})
            if c % 10 == 0:
                shot(p, outdir, f"adv_c{c:03d}.png")
    p.save_state("cp_deep")
    trace.write({"type": "run_end", "unlocked": unlocked,
                 "final_cam_unwrapped": cam_unwrapped})
    shot(p, outdir, "final.png")
    session.disable_all()
    _log("done:", outdir, "unlocked:", unlocked)


if __name__ == "__main__":
    main()
