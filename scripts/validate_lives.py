#!/usr/bin/env python3
"""validate_lives.py — find the LIVES counter via controlled deaths and
verify a lives-freeze (exploration survival layer 2).

Why: HP-pair freeze (hp_pair_freeze, VERIFIED) closes all DAMAGE death,
but instant-death hazards (village water channels) kill via a separate
path and drain lives silently — flags_word stays 0xFF through normal
deaths, so the FSM missed the drain until the CONTINUE? countdown
appeared and expired (cp_deep poisoning, run inv1 c279).

Protocol (Issue-2 evidence discipline):
  A. death-event scan x2: from savestate cb (no cheats), danger-walk
     into the soldier pack and idle until death (flags leaves 0xFF or
     per-life score collapse); diff full RAM across the death window;
     collect words that dropped by exactly 1 (u8 and u16); intersect.
  B. freeze trial per candidate (bounded 5): freeze (GS per-frame tick)
     from a fresh cb, force another death, require: value held AND
     gameplay continued (flags back to 0xFF within 60f of respawn).
  C. winner -> long falsifier: 2 more forced deaths with freeze on;
     lives still held and play continued each time.
"""
import argparse
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

from validate_cheats import Validator, parse_args, log, png  # noqa: E402
from ps1play.agent.gameshark import GSCode                   # noqa: E402
from ps1play.agent.cheatprof import ST_VERIFIED, ST_FAILED   # noqa: E402
from validate_inv2 import danger_walk, FLAGS, read_flags     # noqa: E402

SCORE = 0xEE318
RAM_BYTES = 0x1FC000
DEATH_WAIT = 2600            # max idle frames to wait for a death


def wait_death(p, session=None, codes=None, max_f=DEATH_WAIT):
    """Walk+fire (pit-jump cadence) until death = flags leave 0xFF.
    Returns the death frame or None."""
    for f in range(max_f):
        b = {"RIGHT", "Y"}
        if (f % 30) < 8:
            b.add("B")
        p.core.run_frame()
        p.core.set_buttons(b)
        if session is not None and codes is not None:
            for _ in range(1):
                session.gs.tick()
        if read_flags(p) != 0xFF and f > 30:
            p.core.set_buttons(set())
            return f
    p.core.set_buttons(set())
    return None


def death_scan(p, session, deaths=2, max_f=4200):
    """Walk+fire until death, then diff pre-death vs post-respawn.
    Lives -1 lands somewhere between the death and the respawn, so the
    scan compares the last pre-death frame against post-respawn+60f and
    keeps words that dropped by EXACTLY 1 with old value 1..9 (u8+u16).
    """
    cands = None
    events = []
    for i in range(deaths):
        p.load_state("cb")
        p.core.run(10, set())
        pre = None
        t_end = None
        dframe = None
        for f in range(max_f):
            b = {"RIGHT", "Y"}
            if (f % 30) < 8:
                b.add("B")
            p.core.run_frame()
            p.core.set_buttons(b)
            fl = read_flags(p)
            if fl != 0xFF and pre is None and f > 30:
                pre = p.mem.snapshot()[:RAM_BYTES].copy()
                dframe = f
            if pre is not None and fl == 0xFF:
                for _ in range(60):
                    p.core.run_frame()
                t_end = p.mem.snapshot()[:RAM_BYTES].copy()
                break
        p.core.set_buttons(set())
        if t_end is None:
            log(f"[death {i}] no completed death/respawn within {max_f}f")
            continue
        hitset = set()
        a_old8 = pre.astype(np.int16)
        a_new8 = t_end.astype(np.int16)
        o16 = pre.view("<u2").astype(np.int32)
        n16 = t_end.view("<u2").astype(np.int32)
        d8 = np.flatnonzero((a_new8 == a_old8 - 1) &
                            (a_old8 >= 1) & (a_old8 <= 9))
        d16 = np.flatnonzero((n16 == o16 - 1) &
                             (o16 >= 1) & (o16 <= 9))
        hitset |= {int(w) for w in d8}
        hitset |= {int(w) * 2 + 0x1000000 for w in d16}
        wl = sorted(hitset)
        events.append({"death_frame": dframe, "droppers": wl[:60]})
        cands = set(wl) if cands is None else (cands & set(wl))
        log(f"[death {i}] f={dframe} droppers={len(wl)} "
            f"intersect={len(cands) if cands else 0} sample={wl[:14]}")
    return events, sorted(cands) if cands else []


def freeze_test_lives(p, session, addr, is_u16, val, deaths=2):
    """Freeze candidate; force `deaths` deaths; each must leave the
    value held AND gameplay resumed within 90f of the death."""
    code = GSCode(f"{'8' if is_u16 else '3'}{addr:07X} "
                  f"{val & 0xFFFF:04X}" if is_u16 else
                  f"3{addr:07X} 00{val & 0xFF:02X}")
    read = (lambda: int(p.mem.u16(addr))) if is_u16 else \
           (lambda: int(p.mem.u8(addr)))
    results = []
    for d in range(deaths):
        p.load_state("cb")
        p.core.run(10, set())
        v0 = read()
        code2 = GSCode(f"{'8' if is_u16 else '3'}{addr:07X} "
                       f"{v0 & 0xFFFF:04X}" if is_u16 else
                       f"3{addr:07X} 00{v0 & 0xFF:02X}")
        session.enable(f"_lv{d}", [code2])
        r = wait_death(p, session, [code2], max_f=DEATH_WAIT + 1200)
        held = (read() == v0)
        # gameplay must resume: wait up to 600f more with the freeze on
        resumed = False
        if r is not None:
            for _ in range(600):
                p.core.run_frame()
                session.gs.tick()
                if read_flags(p) == 0xFF:
                    resumed = True
                    break
        session.disable(f"_lv{d}")
        results.append({"death": d, "death_frame": r, "v0": v0,
                        "v_end": read(), "held": bool(held),
                        "resumed": bool(resumed)})
        log(f"[freeze {addr:#x} u{'16' if is_u16 else '8'} death{d}] "
            f"held={held} resumed={resumed} v0={v0} vend={read()}")
        p.load_state("cb")
        p.core.run(10, set())
    ok = bool(results) and all(r["held"] and r["resumed"]
                               for r in results)
    return {"addr": hex(addr), "dtype": "u16" if is_u16 else "u8",
            "code": code2.raw, "results": results}, ok


def main():
    args = parse_args()
    args.codes = "bombs"
    v = Validator(args)
    v.boot_and_calibrate()
    verdict = {"t": time.strftime("%Y-%m-%d %H:%M:%S"),
               "identity": v.ident}

    log("== A: death-event scan ==")
    events, cands = death_scan(v.p, v.session, deaths=2)
    verdict["death_events"] = events
    parsed = []
    for c in cands:
        if c & 0x1000000:
            parsed.append((c & 0xFFFFFF, True))
        else:
            parsed.append((c, False))
    verdict["candidates"] = [{"addr": hex(a), "u16": u} for a, u in parsed]
    png(v.p, v.evid, "10_after_deaths.png")

    log("== B: freeze trials ==")
    winner = None
    trials = []
    for a, u in parsed[:3]:
        if v.out_of_budget():
            break
        read = (lambda: int(v.p.mem.u16(a))) if u else \
               (lambda: int(v.p.mem.u8(a)))
        val = read()
        if val <= 0 or val > 9:
            continue
        r, ok = freeze_test_lives(v.p, v.session, a, u, val, deaths=2)
        trials.append(r)
        if ok and winner is None:
            winner = (a, u, val)
    verdict["freeze_trials"] = trials

    log("== C: long falsifier ==")
    if winner is not None:
        a, u, val = winner
        r, ok = freeze_test_lives(v.p, v.session, a, u, val, deaths=2)
        verdict["long_falsifier"] = r
        verdict["winner"] = {"addr": hex(a), "u16": u, "value": val}
        verdict["status"] = ST_VERIFIED if ok else ST_FAILED
        png(v.p, v.evid, "30_lives_winner.png")
    else:
        verdict["long_falsifier"] = None
        verdict["winner"] = None
        verdict["status"] = ST_FAILED

    out = os.path.join(v.evid, "lives_verdict.json")
    with open(out, "w") as f:
        json.dump(verdict, f, indent=1, default=str)
    log("verdict:", out)
    log("STATUS:", verdict["status"], "WINNER:", verdict["winner"])


if __name__ == "__main__":
    main()
