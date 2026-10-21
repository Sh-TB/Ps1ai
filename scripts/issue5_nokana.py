#!/usr/bin/env python3
"""issue5_nokana.py — Iron Nokana (MSX M1 mid-boss) kill probe
(issue #5 continuation §6; web-verified identity).

The barrier at unwrapped cam ~2303 = the Iron Nokana mid-boss arena.
Web knowledge: the mid-boss is a heavy armored truck; it advances,
stops, fires arcing shells + deploys soldiers; it is killed by sustained
fire (bullets/grenades) from the LEFT side at its body height.

Probe arms (each from a fresh arena approach — NOT the stale cb2 whose
timer already burned):
  N1 CROUCH_FIRE : crouch (DOWN) + Y bursts — low shots at truck body
  N2 STAND_FIRE  : standing Y bursts at mid range
  N3 GRENADES    : arcing grenades (A) over the truck
  N4 SLUG_CHECK  : DOWN+B (leave-vehicle check) — are we IN a vehicle?

Visual + entity evidence each 60f; watch all slots for ANY HP pool
that decreases under fire. Success = a big pool drops steadily.
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

N_ENT = 40


def _log(*a):
    print("[nokana]", *a, file=sys.stderr, flush=True)


class Cam:
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


def reach_arena(p, session, cam, trace, outdir):
    """Walk RIGHT from mission start until the camera locks (arena)."""
    phase = 0
    cam.prev = int(p.mem.u16(0xCA2E0))
    cam.val = cam.prev
    last = cam.val
    still = 0
    for c in range(60):
        phase = gs_run(p, session, 60, {"RIGHT"}, phase)
        u = cam.update()
        trace.write({"type": "approach", "chunk": c, "cam": u})
        if abs(u - last) < 2:
            still += 1
        else:
            still = 0
        last = u
        if still >= 4:
            _log(f"arena locked at chunk {c} (cam {u})")
            break
    return phase, u


def fire_arm(p, session, trace, outdir, cam, name, segs, nshot=6):
    before = dump_entities(p)
    bmap = {e["i"]: e["hp"] for e in before}
    phase = 0
    f = 0
    for btns, frames in segs:
        phase = gs_run(p, session, frames, set(btns), phase)
        f += frames
        if len([1 for b, fr in segs if fr]) and f % 300 < frames:
            pass
    # screenshots spread through the arm are handled by the caller loop
    after = dump_entities(p)
    amap = {e["i"]: e["hp"] for e in after}
    delta = {i: amap.get(i, 0) - bmap.get(i, 0)
             for i in set(bmap) | set(amap)
             if amap.get(i, 0) != bmap.get(i, 0)}
    trace.write({"type": "arm", "name": name, "hp_delta": delta,
                 "cam": cam.update()})
    _log(f"arm {name}: delta={delta}")
    return delta


def main():
    base = labconfig.resolve_path("evidence_dir")
    outdir = os.path.join(
        base, f"nokana_{time.strftime('%Y%m%d_%H%M%S')}")
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
        sys.exit("!! pair not reproduced this boot")
    p.load_state("cb")
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
    phase, arena_cam = reach_arena(p, session, cam, trace, outdir)
    p.save_state("arena")          # fresh arena checkpoint (timer OK)
    trace.write({"type": "arena", "cam": arena_cam})

    # reposition: back off 30f so shots have range, then arms
    arms = {
        "CROUCH_FIRE": [([], 30), (["DOWN", "Y"], 60)] * 10,
        "STAND_FIRE": [([], 30), (["Y"], 60)] * 10,
        "GRENADES": [([], 20), (["A"], 24), (["Y"], 40)] * 10,
        "CROUCH_FIRE2": [([], 30), (["DOWN", "Y"], 120)] * 6,
    }
    for name, segs in arms.items():
        p.load_state("arena")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        # spread screenshots inside the arm
        before = dump_entities(p)
        bmap = {e["i"]: e["hp"] for e in before}
        phase = 0
        fsum = 0
        for k, (btns, frames) in enumerate(segs):
            phase = gs_run(p, session, frames, set(btns), phase)
            fsum += frames
            if k % 8 == 3:
                shot(p, outdir, f"{name}_f{fsum:05d}.png")
        after = dump_entities(p)
        amap = {e["i"]: e["hp"] for e in after}
        delta = {i: amap.get(i, 0) - bmap.get(i, 0)
                 for i in set(bmap) | set(amap)
                 if amap.get(i, 0) != bmap.get(i, 0)}
        trace.write({"type": "arm", "name": name, "hp_delta": delta,
                     "frames": fsum})
        _log(f"arm {name} ({fsum}f): delta={delta}")
        shot(p, outdir, f"{name}_end.png")
    trace.write({"type": "run_end"})
    session.disable_all()
    _log("done:", outdir)


if __name__ == "__main__":
    main()
