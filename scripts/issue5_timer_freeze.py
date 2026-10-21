#!/usr/bin/env python3
"""issue5_timer_freeze.py — the THIRD death path: mission-timer expiry
(issue #5 continuation §5/§6).

Evidence: cab run — HUD timer 200 at the arena, kill cycles then hit
the CONTINUE? countdown (death) despite the VERIFIED HP freeze. The
timer expiry KILLS regardless of HP. Full exploration invincibility
needs the timer frozen too.

Method (strict-series, like the lives scan):
  1. at the arena, scan u16 candidates in [200, 4200]
  2. run 60f, keep only candidates that DECREASED by 20..140
  3. repeat 3x (intersection)  -> the down-counting timer word(s)
  4. freeze ALL survivors (w16 at current value), verify the HUD value
     holds across 300f while it would have dropped
  5. with the timer frozen: sustained point-blank kill on Iron Nokana
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
    print("[timer]", *a, file=sys.stderr, flush=True)


def scan_band(p):
    ram = p.mem.snapshot()[:RAM_WORDS].view("<u2")
    idx = np.flatnonzero((ram >= 200) & (ram <= 4200))
    return {int(i) * 2: int(ram[i]) for i in idx}


def strict_series(p, session, rounds=3, window=60):
    cands = scan_band(p)
    trace_series = []
    for r in range(rounds):
        v0 = {a: int(p.mem.u16(a)) for a in cands}
        gs_run(p, session, window, {"RIGHT"}, 0)
        keep = {}
        for a in cands:
            v1 = int(p.mem.u16(a))
            d = v0[a] - v1
            if 20 <= d <= 140:                # strict down-count
                keep[a] = v1
        trace_series.append({"round": r, "n": len(keep),
                             "addrs": [hex(a) for a in
                                       sorted(keep)][:24]})
        cands = keep
        if len(cands) <= 4:
            break
    return cands, trace_series


def main():
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"timer_freeze_{time.strftime('%Y%m%d_%H%M%S')}")
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

    # ---- timer strict-series scan (walk keeps the world alive) ----
    twords, series = strict_series(p, session)
    trace.write({"type": "timer_scan", "series": series,
                 "final": [hex(a) for a in sorted(twords)]})
    _log(f"timer candidates after strict series: "
         f"{[hex(a) for a in sorted(twords)]}")
    if not twords:
        sys.exit("!! no down-counting timer word found")

    # ---- freeze ALL timer candidates ----
    codes = []
    for a in sorted(twords):
        v = int(p.mem.u16(a))
        codes.append(GSCode(f"8{a:07X} {v & 0xFFFF:04X}"))
    session.enable("timer_freeze", codes)
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    trace.write({"type": "timer_freeze_on",
                 "codes": [c.raw for c in codes]})

    # verify: 600f of play — frozen values must hold
    vals0 = {a: int(p.mem.u16(a)) for a in twords}
    gs_run(p, session, 600, {"RIGHT", "Y"}, 0)
    vals1 = {a: int(p.mem.u16(a)) for a in twords}
    held = all(vals1[a] == vals0[a] for a in twords)
    trace.write({"type": "timer_freeze_verify", "held": held,
                 "vals0": {hex(a): v for a, v in vals0.items()},
                 "vals1": {hex(a): v for a, v in vals1.items()}})
    _log(f"timer freeze held={held}")
    if not held:
        session.disable("timer_freeze")
        sys.exit("!! timer freeze failed verification")

    p.save_state("arena_timer")

    # ---- sustained point-blank kill with UNLIMITED time ----
    for step in range(30):
        phase = gs_run(p, session, 20, {"RIGHT"}, phase)
    for step in range(6):
        phase = gs_run(p, session, 15, {"LEFT"}, phase)
    shot(p, outdir, "pb_position.png")
    unlocked = False
    for cyc in range(40):
        phase = gs_run(p, session, 100, {"DOWN", "Y"}, phase)
        phase = gs_run(p, session, 8, {"UP"}, phase)
        phase = gs_run(p, session, 22, {"A"}, phase)
        phase = gs_run(p, session, 50, {"Y"}, phase)
        if cyc % 3 == 2:
            shot(p, outdir, f"kill_cyc{cyc:03d}.png")
        hp = {e["i"]: e["hp"] for e in dump_entities(p)}
        big = {i: h for i, h in hp.items() if h > 100 and i != 0}
        u = cam.update()
        trace.write({"type": "cycle", "n": cyc, "cam": u, "big": big})
        _log(f"cycle {cyc}: cam={u} big={big}")
        if u >= arena_cam + 150:
            unlocked = True
            trace.write({"type": "UNLOCKED", "cycle": cyc})
            _log(f"UNLOCKED at cycle {cyc}")
            shot(p, outdir, f"UNLOCKED_c{cyc:03d}.png")
            break
    if unlocked:
        for c in range(60):
            phase = gs_run(p, session, 60, {"RIGHT", "Y"}, phase)
            if c % 3 == 2:
                phase = gs_run(p, session, 40, {"RIGHT", "B"}, phase)
            u = cam.update()
            trace.write({"type": "advance", "chunk": c, "cam": u})
            if c % 10 == 0:
                shot(p, outdir, f"adv_c{c:03d}.png")
                _log(f"advance c{c} cam={u}")
    p.save_state("cp_deep")
    trace.write({"type": "run_end", "unlocked": unlocked})
    shot(p, outdir, "final.png")
    session.disable_all()
    _log("done:", outdir, "unlocked:", unlocked)


if __name__ == "__main__":
    main()
