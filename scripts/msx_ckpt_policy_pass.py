#!/usr/bin/env python3
"""msx_ckpt_policy_pass.py — drive the REAL CombatPolicy from the
chopper_ckpt savestate (the user's savestate directive: one checkpoint
~1 s before the chopper/rain encounter, many strategies, no level
replay).

This is the policy-driven counterpart of msx_helicopter_ladder.py's
fixed patterns: same first-death-endpoint convention, same UNFROZEN
rule (no CheatSession exists in the pass — deaths are real), but the
buttons come from CombatPolicy.decide() on the live entity scan, so
stats[rear_check]/stats[proj_dodge]/stats[proj_unverified] are read
from real policy behaviour inside the chopper zone.

Per-chunk JSONL (READ-ONLY): px, hp pair, flags, score, grenades,
faller census, zone entities, scan, mode, policy stats.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from PIL import Image                                   # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                           # noqa: E402
from ps1play.telemetry import JsonlTrace                # noqa: E402
from ps1play.agent.combat import CombatPolicy, scan_entities  # noqa
from msx_helicopter_ladder import (                     # noqa: E402
    CKPT, EVID, PLAYER_X, A_FLAGS, A_SCORE, A_PAIR0, A_PAIR1,
    GRENADES, FallerCensus, flags_of, log, png, px_of)
from issue4_controller import boot                      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=60)
    ap.add_argument("--tag", default="policy_pass1")
    args = ap.parse_args()

    p, fwmode = boot()
    m = p.mem
    p.load_state(CKPT)
    for _ in range(2):                    # settle (post-load engage)
        p.core.run_frame()
    if flags_of(m) != 0xFF:
        log(f"checkpoint not in active gameplay "
            f"(flags={flags_of(m):#x}) — aborting")
        return 2

    outdir = os.path.join(EVID, args.tag)
    os.makedirs(outdir, exist_ok=True)
    jf = open(os.path.join(outdir, "trace.jsonl"), "w")
    pol = CombatPolicy()
    census = FallerCensus()
    px0 = px_of(m)
    hp0 = int(m.u16(A_PAIR0))
    score0 = int(m.u32(A_SCORE))
    gren0 = int(m.u8(GRENADES))
    t0 = time.time()
    f0 = p.core.frames_run
    log(f"start px={px0:.1f} hp={hp0} gren={gren0} score={score0}")

    death = None
    last_hp = hp0
    damage = []
    max_px = px0
    mode_counts = {}
    last_px = None
    last_segs = None
    c = -1
    for c in range(args.chunks):
        px = px_of(m)
        hp1 = int(m.u16(A_PAIR0))
        scan = scan_entities(m, px=px)
        advanced = 0.0 if last_px is None else (px - last_px)
        intent = any("RIGHT" in (s.get("btns") or set())
                     for s in (last_segs or []))
        pol.observe(px, advanced, intent)
        segs = pol.decide(60, px, scan,
                          grenades=int(m.u8(GRENADES)), hp=hp1)
        last_px, last_segs = px, segs
        mode_counts[pol.mode] = mode_counts.get(pol.mode, 0) + 1
        frame_start = p.core.frames_run
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
        c2 = census.poll(m, px)
        hp1b = int(m.u16(A_PAIR0))
        pxb = px_of(m)
        max_px = max(max_px, pxb)
        if hp1b < last_hp:
            damage.append({"chunk": c, "delta": last_hp - hp1b,
                           "px": round(pxb, 1),
                           "fall_near": c2["fall_near"]})
        last_hp = hp1b
        row = {"chunk": c, "mode": pol.mode,
               "policy_stats": dict(pol.stats),
               "px": round(px, 1), "px_end": round(pxb, 1),
               "hp0": hp1b, "hp1": int(m.u16(A_PAIR1)),
               "flags": flags_of(m),
               "score": int(m.u32(A_SCORE)),
               "gren": int(m.u8(GRENADES)),
               "frame_start": frame_start,
               "fall_total": c2["fall_total"],
               "fall_near": c2["fall_near"],
               "n_zone": len(c2["zone"]),
               "scan": scan,
               "btns": sorted(set().union(
                   *[s["btns"] or set() for s in segs]))}
        jf.write(json.dumps(row) + "\n")
        if c % 10 == 0:
            png(p, f"{args.tag}_c{c:03d}.png")
        if hp1b == 0 or row["flags"] == 0x1:
            death = {"chunk": c, "px": round(pxb, 1),
                     "trigger": "hp_zero" if hp1b == 0
                     else "game_over_screen",
                     "geometry": scan_entities(m, px=px_of(m))}
            for _ in range(60):           # death animation tail
                p.core.run(1, set())
            break
    jf.close()
    rep = {"schema": "ps1play-ckpt-policy-pass/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "firmware_mode": fwmode, "checkpoint": CKPT,
           "tag": args.tag,
           "chunks_run": (death["chunk"] + 1) if death else c + 1,
           "died": death is not None, "death": death,
           "start_px": round(px0, 1), "max_px": round(max_px, 1),
           "hp_start": hp0, "hp_end": last_hp,
           "n_damage_events": len(damage), "damage": damage,
           "score_start": score0,
           "score_end": int(m.u32(A_SCORE)),
           "grenades_start": gren0,
           "mode_counts": mode_counts,
           "policy_stats": dict(pol.stats),
           "wall_s": round(time.time() - t0, 1),
           "emu_fps": round((p.core.frames_run - f0)
                            / max(time.time() - t0, 1), 1)}
    rpath = os.path.join(EVID, f"report_{args.tag}.json")
    with open(rpath, "w") as f:
        json.dump(rep, f, indent=1)
    png(p, f"{args.tag}_end.png")
    log("report:", rpath)
    log(f"RESULT died={rep['died']} chunks={rep['chunks_run']} "
        f"px {rep['start_px']}->{rep['max_px']} "
        f"hp {hp0}->{last_hp} score {score0}->{rep['score_end']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
