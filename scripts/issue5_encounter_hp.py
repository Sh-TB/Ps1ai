#!/usr/bin/env python3
"""issue5_encounter_hp.py — LIVE entity-HP probe at the truck/helicopter
barrier (issue #5 continuation §4/§6).

Uses the §4-verified entity table (base 0x800CA268, stride 0x14C,
HP +0x8E u16, spawn 0xA0) to watch the encounter's entities live:

  1. boot -> mission -> cheats (hp_pair freeze, VERIFIED profile)
  2. walk RIGHT to the barrier (camera lock ~2303)
  3. per-chunk dump: HP fields of the first 24 entity slots + per_life
  4. then controlled fire variants (straight Y / UP+Y / grenades) and
     record which entity HP fields move (the truck/helicopter HP
     behavior: do they even live in this table?)

Output: evidence/explore_enc_hp_<tag>/{trace.jsonl, report.json, PNGs}
CHEAT_ASSISTED_EXPLORATION (opt-in) — never a no-cheat clear.
"""
from __future__ import annotations

import argparse
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
from validate_inv2 import PAIR, read_flags                # noqa: E402

ENT_BASE = 0xCA268      # PHYSICAL offset (VA 0x800CA268 & 0x1FFFFF)
ENT_STRIDE = 0x14C
HP_OFF = 0x8E
PER_LIFE = 0xCA2E0
N_ENT = 40


def _log(*a):
    print("[enc-hp]", *a, file=sys.stderr, flush=True)


def shot(p, outdir, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))


def dump_entities(p):
    out = []
    for i in range(N_ENT):
        hp = int(p.mem.u16(ENT_BASE + i * ENT_STRIDE + HP_OFF))
        f0 = int(p.mem.u32(ENT_BASE + i * ENT_STRIDE))
        if hp or f0:
            out.append({"i": i, "hp": hp, "handler": f0})
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--opt-in", action="store_true")
    ap.add_argument("--tag", default="enchp1")
    ap.add_argument("--chunks", type=int, default=80,
                    help="walk chunks before the fire variants")
    ap.add_argument("--evidence-dir", default=None)
    a = ap.parse_args(argv)
    if not a.opt_in:
        ap.error("--opt-in required (VERIFIED freeze cheats)")
    if a.evidence_dir is None:
        base = labconfig.resolve_path("evidence_dir")
        a.evidence_dir = os.path.join(
            base, f"enc_hp_{a.tag}_{time.strftime('%Y%m%d_%H%M%S')}")
    return a


def main():
    args = parse_args()
    os.makedirs(args.evidence_dir, exist_ok=True)
    trace = JsonlTrace(os.path.join(args.evidence_dir, "trace.jsonl"))

    p, fwmode = boot()
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    if not g.get("in_mission"):
        sys.exit("!! gate failed")
    trace.write({"type": "run_start", "firmware": fwmode,
                 "t": time.strftime("%H:%M:%S")})

    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=_log)
    if anch.get("ok"):
        bombs_addr = guard.addrs["bombs"]
        v = int(p.mem.u8(bombs_addr))
        session.enable("bombs_freeze",
                       [GSCode(f"3{bombs_addr:07X} 00{v & 0xFF:02X}")])
        trace.write({"type": "cheat", "name": "bombs_freeze",
                     "addr": hex(bombs_addr)})
    p.save_state("cb")
    # pair co-drop gate (same protocol as the A/B)
    from issue5_ab_invuln import confirm_codrops
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
    trace.write({"type": "cheat", "name": "hp_pair_freeze",
                 "codes": [f"{f6:#x}", f"{fe:#x}"]})

    phase = 0
    # walk to the barrier, dumping entity HP each chunk
    prev_dump = None
    for c in range(args.chunks):
        phase = gs_run(p, session, 60, {"RIGHT"}, phase)
        d = dump_entities(p)
        cam = int(p.mem.u16(PER_LIFE))
        moved = d != prev_dump
        trace.write({"type": "walk_chunk", "chunk": c, "cam": cam,
                     "entities": d, "changed": moved})
        prev_dump = d
        if c % 20 == 0:
            shot(p, args.evidence_dir, f"walk_c{c:03d}.png")
        if cam >= 2290 and cam <= 2320:
            _log(f"barrier reached at chunk {c} (cam {cam})")
            break

    shot(p, args.evidence_dir, "barrier_arrival.png")
    p.save_state("cb2")          # barrier checkpoint BEFORE variants
    base_dump = dump_entities(p)
    trace.write({"type": "barrier_entities", "entities": base_dump})

    # controlled fire variants from the barrier position
    variants = [
        ("straight_Y", [({"RIGHT", "Y"}, 120)] * 4),
        ("up_Y_antiair", [({"UP", "Y"}, 120)] * 4),
        ("grenade_arc", [({"RIGHT"}, 20), ({"A"}, 24),
                         ({"RIGHT", "Y"}, 60)] * 3),
        ("jump_shoot", [({"RIGHT", "B"}, 30), ({"RIGHT", "Y"}, 60)] * 3),
        ("stand_Y", [({"Y"}, 120)] * 4),
    ]
    for name, segs in variants:
        before = dump_entities(p)
        cam0 = int(p.mem.u16(PER_LIFE))
        for btns, frames in segs:
            phase = gs_run(p, session, frames, btns, phase)
        after = dump_entities(p)
        cam1 = int(p.mem.u16(PER_LIFE))
        bmap = {e["i"]: e["hp"] for e in before}
        amap = {e["i"]: e["hp"] for e in after}
        delta = {i: amap.get(i, 0) - bmap.get(i, 0)
                 for i in set(bmap) | set(amap)
                 if amap.get(i, 0) != bmap.get(i, 0)}
        trace.write({"type": "variant", "name": name,
                     "cam": [cam0, cam1],
                     "hp_delta": delta,
                     "after": after})
        shot(p, args.evidence_dir, f"variant_{name}.png")
        _log(f"variant {name}: hp_delta={delta} cam {cam0}->{cam1}")
        # reset to the barrier checkpoint for variant comparability
        p.load_state("cb2")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()

    # refresh checkpoints for the next exploration leg
    p.save_state("cb2")
    p.save_state("cp_deep")
    trace.write({"type": "checkpoint", "state": "cb2+cp_deep",
                 "cam": int(p.mem.u16(PER_LIFE))})
    session.disable_all()
    _log("done:", args.evidence_dir)


class JsonlTrace:
    def __init__(self, path):
        self.f = open(path, "a")

    def write(self, rec):
        rec["t"] = time.strftime("%H:%M:%S")
        self.f.write(json.dumps(rec, default=str) + "\n")
        self.f.flush()


def _have(state):
    return True


if __name__ == "__main__":
    main()
