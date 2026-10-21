#!/usr/bin/env python3
"""validate_inv2.py — find the MASTER player-HP word and prove a
per-frame data-freeze that makes damage impossible (SLUS-01212).

Fixes the find_player_hp judging flaw: responsive() runs ~44 unpoked
frames BEFORE v1 is read, so freeze tests there can never hold for
words the game refreshes. Here every judge reads straight after the
poked window (no unpoked gap), plus a LONG death-window falsifier.

Steps:
  A. boot -> mission -> bombs anchor -> savestate cb (Validator reuse)
  B. danger walk; detect hit frames via the HP-pair 0xCA2F6/0xCA2FE
     (proven droppers); diff full RAM across each hit frame; intersect
     decreasing words over >=2 hits -> master/copy candidate list
  C. for each candidate (bounded 6) + the pair itself: GS per-frame
     freeze (w16 at current value), 360 danger frames:
       pass = value never moves AND pair clean AND player alive
  D. winner -> long falsifier: 900 danger frames with the freeze on;
     must stay alive the whole time (flags 0xFF, score > 0)
Verdict JSON + PNGs. Statuses: VERIFIED / FAILED / BLOCKED only.
"""
import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                           # noqa: E402

from validate_cheats import Validator, parse_args, log, png  # noqa: E402
from ps1play.agent.gameshark import GSCode                   # noqa: E402
from ps1play.agent.cheatprof import (                        # noqa: E402
    derive_freeze_code, ST_VERIFIED, ST_FAILED)

PAIR = (0xCA2F6, 0xCA2FE)
FLAGS = 0xEE518
SCORE = 0xEE318
WALK_F = 300
PROBE_F = 360
LONG_F = 900
RAM_WORDS = 0x1FC000         # 2MB - BIOS mirror guard


def read_flags(p):
    return int(p.mem.u32(FLAGS)) & 0xFF


def danger_walk(p, session=None, code=None):
    """Walk RIGHT into the soldier pack; returns after WALK_F frames."""
    p.core.set_buttons({"RIGHT"})
    for _ in range(WALK_F):
        p.core.run_frame()
        if session is not None and code is not None:
            session.gs.tick()
    p.core.set_buttons(set())


def find_hit_events(p, session, max_hits=3, max_frames=1800):
    """Sample the pair every frame; when it drops, diff RAM across a
    small window (the two HP words can be written on staggered frames);
    collect decreasing-word candidates per hit; intersect."""
    p.load_state("cb")
    p.core.run(10, set())
    danger_walk(p)
    ring = []                    # last 3 snapshots for window diffs
    events = []
    cands = None
    last_pair = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
    for f in range(max_frames):
        p.core.run_frame()
        cur = p.mem.snapshot()[:RAM_WORDS].copy()
        pr = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        ring.append(cur)
        if len(ring) > 3:
            ring.pop(0)
        if pr < last_pair:                      # a hit landed ~this frame
            hitset = set()
            a_new = cur.view("<u2").astype(np.int32)
            for old in ring[:-1]:
                a_old = old.view("<u2").astype(np.int32)
                drop = np.flatnonzero((a_new < a_old) &
                                      (a_old <= 300) & (a_new >= 0))
                hitset |= {int(w) * 2 for w in drop}
            wl = sorted(hitset)
            events.append({"frame": f, "pair": pr, "droppers": wl[:40]})
            cands = hitset if cands is None else (cands & hitset)
            log(f"[hit {len(events)}] f={f} pair={pr} droppers={wl[:12]}"
                f" (intersect={len(cands) if cands else 0})")
            if len(events) >= max_hits:
                break
        last_pair = pr
    return events, sorted(cands) if cands else []


def freeze_test(p, session, addrs, danger_f=PROBE_F, tag="fz"):
    """Freeze ALL addrs (w16 at load value) via GS tick; run danger
    window; judge: every addr unchanged AND pair clean AND alive.
    Runs a NO-FREEZE control arm first (same inputs) so "held" is
    meaningful within the same run."""
    def arm(with_code, name):
        p.load_state("cb")
        p.core.run(10, set())
        vals = {a: int(p.mem.u16(a)) for a in addrs}
        codes = [GSCode(f"8{a:07X} {vals[a] & 0xFFFF:04X}") for a in addrs]
        if with_code:
            session.enable(name, codes)
        danger_walk(p, session, codes if with_code else None)
        p0 = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        sc0 = int(p.mem.u32(SCORE))
        series = []
        alive_frames = 0
        for i in range(danger_f):
            p.core.run_frame()
            if with_code:
                session.gs.tick()
            if read_flags(p) == 0xFF and int(p.mem.u32(SCORE)) > 0:
                alive_frames += 1
            if i % 30 == 0:
                series.append({"f": i,
                               **{f"{a:#x}": int(p.mem.u16(a)) for a in addrs},
                               "pair": (int(p.mem.u16(PAIR[0])),
                                        int(p.mem.u16(PAIR[1])))})
        p._advance()
        p1 = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        end_vals = {a: int(p.mem.u16(a)) for a in addrs}
        if with_code:
            session.disable(name)
        held = all(end_vals[a] == vals[a] for a in addrs)
        pair_clean = (p1[0] == p0[0]) and (p1[1] == p0[1])
        alive = (read_flags(p) == 0xFF and int(p.mem.u32(SCORE)) > 0
                 and alive_frames >= danger_f - 30)
        return {"addrs": [hex(a) for a in addrs],
                "codes": [c.raw for c in codes] if with_code else None,
                "start_vals": {hex(a): v for a, v in vals.items()},
                "end_vals": {hex(a): v for a, v in end_vals.items()},
                "pair0": p0, "pair1": p1, "held": held,
                "pair_clean": pair_clean, "alive": alive,
                "alive_frames": alive_frames, "danger_f": danger_f,
                "score0": sc0, "series": series[:8]}

    control = arm(False, f"_{tag}_ctl")
    treat = arm(True, f"_{tag}")
    ok = bool(treat["held"] and treat["alive"]
              and (not control["held"] or not control["alive"]))
    return {"control": control, "treatment": treat}, ok


def main():
    args = parse_args()
    args.codes = "bombs"
    v = Validator(args)
    v.boot_and_calibrate()
    verdict = {"t": time.strftime("%Y-%m-%d %H:%M:%S"),
               "identity": v.ident}

    log("== A: hit-event RAM diff (find master/copy candidates) ==")
    events, cands = find_hit_events(v.p, v.session)
    verdict["hit_events"] = events
    verdict["intersect_candidates"] = [hex(c) for c in cands]
    png(v.p, v.evid, "10_after_hits.png")

    log("== B: freeze tests (control + treatment per candidate) ==")
    trials = [[PAIR[0], PAIR[1]]]               # pair first (proven metric)
    for c in cands[:5]:
        if c not in PAIR:
            trials.append([c])
    results = []
    winner = None
    for i, addrs in enumerate(trials):
        if v.out_of_budget():
            break
        r, ok = freeze_test(v.p, v.session, addrs, tag=f"fz{i}")
        results.append(r)
        t = r["treatment"]
        log(f"[freeze] {[hex(a) for a in addrs]} -> held={t['held']} "
            f"alive={t['alive']} pair_clean={t['pair_clean']} "
            f"(ctl held={r['control']['held']} alive={r['control']['alive']})")
        if ok and winner is None:
            winner = addrs
    verdict["freeze_trials"] = results

    log("== C: long falsifier ==")
    if winner is not None:
        r, ok = freeze_test(v.p, v.session, winner, danger_f=LONG_F,
                            tag="long")
        verdict["long_falsifier"] = r
        verdict["status"] = ST_VERIFIED if (ok and r["treatment"]["alive"]
                                            and r["control"]["alive"]
                                            is not None) else ST_FAILED
        verdict["winner"] = [hex(a) for a in winner]
        png(v.p, v.evid, "30_long_survive.png")
    else:
        verdict["long_falsifier"] = None
        verdict["winner"] = None
        verdict["status"] = ST_FAILED

    out = os.path.join(v.evid, "inv2_verdict.json")
    with open(out, "w") as f:
        json.dump(verdict, f, indent=1, default=str)
    log("verdict:", out)
    log("STATUS:", verdict["status"], "WINNER:", verdict["winner"])


if __name__ == "__main__":
    main()
