#!/usr/bin/env python3
"""validate_iframe.py — test the PUBLISHED "Invisible P1" data address
0x800CA30C (value 0x68) as the player's native invulnerability (i-frame)
timer on SLUS-01212 retail.

Background (Issue #5 addendum + web research 2026-10-21):
  * gamehacking.org retail set has NO data-form invincibility code; the
    3-line instruction patch FAILED live (cheats.json invuln=FAILED).
  * CheatCC (2001) + Almar's Beta page list `800CA30C 0068` = "Invisible
    P1" / "P1 Invisible". 0x800CA30C sits in the same fixed player-state
    data region as the live-VERIFIED HP anchor 0x800CABE4 and the live
    VERIFIED score 0x800EE318 (published retail data layout is FIXED on
    this revision — score proved it).
  * Hypothesis: [0x800CA30C] is the P1 invulnerability-window countdown
    (game-native i-frames). Writing 0x68 every frame (hardware-GS
    semantics) should hold the player in the game's own immune state:
    damage never lands, death never triggers.

Protocol (same evidence discipline as validate_cheats.py):
  A. read-only dynamics: sample u16@0xCA30C (and the P2 mirror 0xCA458)
     every frame across hit events — countdown after hit = i-frame.
  B. baseline / treatment / disable x2 from one savestate:
     HP must drop (baseline), hold + player alive (treatment), drop
     again (disable). Alive-ness = flags_word u32@0x0EE518 (0xFF=play).
  C. fallback: re-derive hp_freeze anchor this boot (find_player_hp) +
     quick freeze verify, so the exploration profile always has a
     VERIFIED survival method.

Output: verdict JSON + PNG evidence in the evidence dir.
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

from validate_cheats import Validator, parse_args, log, png  # noqa: E402
from ps1play.agent.gameshark import GSCode                   # noqa: E402
from ps1play.agent.cheatprof import ST_VERIFIED, ST_FAILED   # noqa: E402

IFRAME_P1 = 0x800CA30C & 0x1FFFFF
IFRAME_P2 = 0x800CA458 & 0x1FFFFF
FLAGS = 0x800EE518 & 0x1FFFFF   # u32: 0xFF=gameplay active (verified v3)
SCORE = 0x800EE318 & 0x1FFFFF   # u32 per-life score (causality-verified)
CLUSTER = {                 # fixed-layout player-state cluster words
    "hp_pub_prev": 0x800CABE4 & 0x1FFFFF,   # hp anchor on 2026-10-20 boot
    "near_f6": 0x800CA2F6 & 0x1FFFFF,       # today's dropper candidates
    "near_fe": 0x800CA2FE & 0x1FFFFF,
    "per_life": 0x800CA2E0 & 0x1FFFFF,      # per-life accumulator (Issue #3)
}
HP_PAIR = (CLUSTER["near_f6"], CLUSTER["near_fe"])
WALK_F = 300               # walk-right frames to reach the soldier pack
DANGER_F = 600             # idle-in-danger frames

# published data-form codes (CheatCC 2001 / Almar beta page, NTSC-U)
CAND_P1 = GSCode("800CA30C 0068")


def read_flags(p):
    return int(p.mem.u32(FLAGS)) & 0xFF


def sample_series(p, session, frames, with_code=None, sample_every=1):
    """Read-only-ish sampler of the i-frame words during idle-in-danger.
    Returns list of dicts."""
    series = []
    for i in range(frames):
        p.core.run_frame()
        if with_code is not None:
            session.gs.tick()
        if i % sample_every == 0:
            row = {
                "f": i,
                "p1": int(p.mem.u16(IFRAME_P1)),
                "p2": int(p.mem.u16(IFRAME_P2)),
                "flags": read_flags(p),
            }
            for k, a in CLUSTER.items():
                row[k] = int(p.mem.u16(a))
            series.append(row)
    return series


def dynamics_phase(v, frames_s=360):
    """Phase A: observe the candidate words across a damage event."""
    p, session = v.p, v.session
    p.load_state("cb")
    p.core.run(30, set())                    # settle, no input
    log(f"[dyn] sampling {frames_s} frames idle-in-danger ...")
    series = sample_series(p, session, frames_s, sample_every=2)
    vals = [s["p1"] for s in series]
    png(p, v.evid, "05_dyn_end.png")
    return {
        "frames": frames_s,
        "p1_min": min(vals), "p1_max": max(vals),
        "p1_unique": sorted(set(vals))[:20],
        "flags_unique": sorted({s["flags"] for s in series}),
        "series_head": series[:40],
        "series_tail": series[-40:],
    }


def protocol_phase(v, attempts=2, idle=None):
    """Phase B: damage-gate protocol with the i-frame freeze.

    Primary metric: the HP-pair words (0xCA2F6/0xCA2FE — the words that
    provably DROP on every hit this boot). Baseline: they must drop.
    Treatment (0xCA30C frozen at 0x68): they must NOT move at all
    (= damage mechanism fully closed). Secondary: player survives the
    whole window in treatment / dies in baseline."""
    p, session = v.p, v.session
    idle = idle or DANGER_F

    def run_arm(with_code):
        p.load_state("cb")
        p.core.run(10, set())
        sc0 = int(p.mem.u32(SCORE))
        cl0 = {k: int(p.mem.u16(a)) for k, a in CLUSTER.items()}

        def dead_now(p):
            # death evidence: flags left gameplay OR score collapsed
            # to 0 from a positive start (score is per-life)
            if read_flags(p) != 0xFF:
                return True
            return sc0 > 0 and int(p.mem.u32(SCORE)) <= 0

        if with_code:
            session.enable("_ifr", [CAND_P1])
            for _ in range(2):                # hardware-GS pre-engage
                p.core.run_frame()
                session.gs.tick()
        # walk RIGHT into the first soldier pack (the savestate spot is
        # the mission start where idle is safe — baseline proved it)
        p.core.set_buttons({"RIGHT"})
        for _ in range(WALK_F):
            p.core.run_frame()
            if with_code:
                session.gs.tick()
        p.core.set_buttons(set())
        died_frame = None
        series = []
        for i in range(idle):
            p.core.run_frame()
            if with_code:
                session.gs.tick()
            if i % 4 == 0:
                series.append({"f": i,
                               "p1": int(p.mem.u16(IFRAME_P1)),
                               "hpf6": int(p.mem.u16(HP_PAIR[0])),
                               "hpfe": int(p.mem.u16(HP_PAIR[1])),
                               "flags": read_flags(p)})
            if died_frame is None and i > 60 and dead_now(p):
                died_frame = i
                break
        p._advance()
        cl1 = {k: int(p.mem.u16(a)) for k, a in CLUSTER.items()}
        alive = not dead_now(p)
        if with_code:
            session.disable("_ifr")
        return {"score0": sc0, "cluster0": cl0, "cluster1": cl1,
                "died_frame": died_frame, "alive": alive,
                "flags": read_flags(p),
                "p1_series": series[::4]}

    arm = {"baseline": [], "treatment": [], "disabled_recovery": []}
    for _ in range(attempts):
        arm["baseline"].append(run_arm(False))
    for _ in range(attempts):
        arm["treatment"].append(run_arm(True))
    for _ in range(attempts):
        arm["disabled_recovery"].append(run_arm(False))

    def pair_delta(r):
        return (r["cluster1"]["near_f6"] - r["cluster0"]["near_f6"],
                r["cluster1"]["near_fe"] - r["cluster0"]["near_fe"])

    base_dmg = all(any(d < 0 for d in pair_delta(r))
                   for r in arm["baseline"])
    treat_clean = all(all(d == 0 for d in pair_delta(r))
                      for r in arm["treatment"])
    rec_dmg = all(any(d < 0 for d in pair_delta(r))
                  for r in arm["disabled_recovery"])
    treat_alive = all(r["alive"] for r in arm["treatment"])
    base_dead = all(not r["alive"] for r in arm["baseline"])
    works = bool(base_dmg and treat_clean and rec_dmg and treat_alive)
    j = {"works": works, "code": CAND_P1.raw, "addr": hex(IFRAME_P1),
         "dtype": "u16", "baseline_damaged": base_dmg,
         "baseline_died": base_dead,
         "treatment_hp_clean": treat_clean,
         "treatment_alive": treat_alive,
         "disable_recovered": rec_dmg,
         "pair_deltas": {k: [pair_delta(r) for r in arm[k]]
                         for k in arm},
         "readings": arm,
         "action": f"walk {WALK_F}f + idle {idle}f"}
    png(p, v.evid, "20_iframe_after.png")
    return (ST_VERIFIED if works else ST_FAILED), j


def main():
    args = parse_args()
    args.codes = "bombs"          # calibration needs the bombs anchor only
    v = Validator(args)
    try:
        v.boot_and_calibrate()
    except SystemExit as e:
        log("boot failed:", e)
        raise

    # HP anchor this boot (freeze-verified) — reused by every phase
    hp = v.guard.find_player_hp(log=log)
    if hp is not None:
        v.counter_addrs["hp"] = hp
        log(f"[anchor] hp @ {hp:#x}")

    verdict = {"t": time.strftime("%Y-%m-%d %H:%M:%S"),
               "identity": v.ident, "if_p1": hex(IFRAME_P1),
               "if_p2": hex(IFRAME_P2), "hp_addr": hex(hp) if hp else None}

    log("== Phase A: dynamics ==")
    verdict["dynamics"] = dynamics_phase(v)

    log("== Phase B: protocol ==")
    st, j = protocol_phase(v, attempts=args.attempts)
    verdict["protocol"] = j
    verdict["status"] = st

    log("== Phase C: hp_freeze fallback (re-derive + quick verify) ==")
    try:
        from validate_cheats import derive_freeze_code
        from ps1play.agent.cheatprof import quick_verify_freeze
        if hp is not None:
            v.p.load_state("cb")
            v.p.core.run(10, set())
            code, val = derive_freeze_code(v.p, hp, dtype="u16")
            ok, det = quick_verify_freeze(
                v.p, v.session, code, hp, "cb",
                frames=300, dtype="u16")
            verdict["hp_freeze"] = {"code": code.raw, "value": val,
                                    "works": bool(ok), "detail": str(det)}
        else:
            verdict["hp_freeze"] = {"blocked": "no hp anchor"}
    except Exception as e:                                     # noqa: BLE001
        verdict["hp_freeze"] = {"error": repr(e)}

    out = os.path.join(v.evid, "iframe_verdict.json")
    with open(out, "w") as f:
        json.dump(verdict, f, indent=1, default=str)
    log("verdict:", out)
    log("STATUS:", verdict["status"])
    log("PROTOCOL:", json.dumps(verdict["protocol"], default=str)[:600])


if __name__ == "__main__":
    main()
