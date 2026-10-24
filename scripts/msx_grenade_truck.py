#!/usr/bin/env python3
"""msx_grenade_truck.py — the OWED grenade-vs-armored-truck live run.

Session-4 disclosed debt: the armored truck (slot 14, hp 254, h 64)
resists standing Y fire (254->254 across all passes) and one-shots the
player (−291 ram) at the px-1164 clamp. The proven anti-armor kill
path is the grenade. This runner stands its ground at the truck
encounter and lobs grenades on a fixed cadence, watching:
  truck hp pair, truck presence (scan), score (+200 soft / +800
  mosque-class), grenade counter (0xEDCF4), player hp/death.

>=2 independent boots (H5: one boot per process) for reproducibility:
run with --tag gtruck1 / gtruck2 ...

Evidence: work/msx_recomp/evidence/heli_ladder/<tag>/ (local-only)
"""
import argparse
import json
import os
import sys
import time

from PIL import Image                                   # noqa

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                # noqa
from msx_helicopter_ladder import (                     # noqa
    CKPT, EVID, PLAYER_X, A_FLAGS, A_SCORE, A_PAIR0, A_PAIR1,
    GRENADES, flags_of, log, png, px_of)
from issue4_controller import boot                      # noqa


def scan(m, px):
    """Minimal local entity scan (same contract as combat.scan_entities
    fields used here: slot, x, dx, hp, h)."""
    import ps1play.agent.combat as combat
    return combat.scan_entities(m, px=px)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="gtruck1")
    ap.add_argument("--chunks", type=int, default=40)
    ap.add_argument("--lob-every", type=int, default=40,
                    help="grenade lob cadence (frames)")
    ap.add_argument("--retreat", action="store_true",
                    help="walk LEFT between lobs to keep the arc window")
    ap.add_argument("--topup", type=int, default=0,
                    help="DISCLOSED exploration assist: grenade top-up "
                         "at checkpoint load (0 = honest stock)")
    args = ap.parse_args()

    p, fwmode = boot()
    m = p.mem
    p.load_state(CKPT)
    for _ in range(2):
        p.core.run_frame()
    if flags_of(m) != 0xFF:
        log(f"checkpoint not in active gameplay (flags={flags_of(m):#x})")
        return 2

    outdir = os.path.join(EVID, args.tag)
    os.makedirs(outdir, exist_ok=True)
    jf = open(os.path.join(outdir, "trace.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")

    if args.topup:
        m.ram[GRENADES] = args.topup         # disclosed exploration arm
        log(f"DISCLOSED top-up grenades -> {args.topup}")
    gren0 = int(m.u8(GRENADES))
    score0 = int(m.u32(A_SCORE))
    hp0 = int(m.u16(A_PAIR0))
    px0 = px_of(m)
    log(f"start px={px0:.1f} hp={hp0} gren={gren0} score={score0}")
    J({"ev": "start", "px": px0, "hp": hp0, "gren": gren0,
       "score": score0, "topup": args.topup})

    lobs = 0
    truck_seen = {}
    death = None
    last_hp = hp0
    last_score = score0
    truck_kills = 0
    f0 = p.core.frames_run
    t0 = time.time()

    for c in range(args.chunks):
        px = px_of(m)
        ents = scan(m, px)
        truck = None
        for e in ents:
            if e.get("hp") and 200 <= e["hp"] <= 300 and \
                    abs(e.get("dx_px", 0)) < 300 and \
                    e.get("h", 0) == 64:
                truck = e
                break
        segs = []
        if truck is not None:
            truck_seen.setdefault("first_chunk", c)
            truck_seen["last_chunk"] = c
            truck_seen["last_hp"] = truck["hp"]
            truck_seen["last_dx"] = truck["dx_px"]
            # face the truck, lob on cadence; --retreat walks LEFT
            # between lobs so the lob arc keeps landing (close-range
            # lobs sail over — observed: damage freezes at close dx)
            rear = truck["dx_px"] < 0
            face = {"LEFT"} if rear else set()
            back = set() if rear else {"LEFT"}   # retreat = away
            frames = 60
            for i in range(0, frames, 8):
                if (i // 8) % max(1, args.lob_every // 8) == 0:
                    segs.append({"btns": face | {"A"}, "frames": 4})
                    lobs += 1
                    segs.append({"btns": face, "frames": 4})
                elif args.retreat:
                    segs.append({"btns": back, "frames": 8})
                else:
                    segs.append({"btns": face, "frames": 8})
        else:
            segs.append({"btns": set(), "frames": 60})
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())

        gren1 = int(m.u8(GRENADES))
        score1 = int(m.u32(A_SCORE))
        hp1 = int(m.u16(A_PAIR0))
        px1 = px_of(m)
        d_score = score1 - last_score
        if d_score >= 100:
            truck_kills += 1
        J({"ev": "chunk", "chunk": c, "px": round(px1, 1),
           "hp": hp1, "gren": gren1, "score": score1,
           "d_score": d_score, "lobs": lobs,
           "truck": truck, "n_ents": len(ents),
           "flags": flags_of(m)})
        last_score = score1
        if hp1 < last_hp:
            J({"ev": "damage", "chunk": c, "delta": last_hp - hp1,
               "px": round(px1, 1)})
        last_hp = hp1
        if c % 5 == 0:
            png(p, f"{args.tag}_c{c:03d}.png")
        if hp1 == 0 or flags_of(m) != 0xFF:
            death = {"chunk": c, "px": round(px1, 1),
                     "trigger": "hp_zero" if hp1 == 0
                     else f"flags_{flags_of(m):#x}"}
            for _ in range(60):
                p.core.run(1, set())
            break

    jf.close()
    rep = {"schema": "ps1play-gtruck/1",
           "tag": args.tag, "firmware_mode": fwmode,
           "chunks_run": (death["chunk"] + 1) if death else c + 1,
           "died": death is not None, "death": death,
           "lobs": lobs, "grenades_start": gren0,
           "grenades_end": int(m.u8(GRENADES)),
           "truck_seen": truck_seen,
           "score_start": score0, "score_end": int(m.u32(A_SCORE)),
           "hp_start": hp0, "hp_end": last_hp,
           "score_events_ge100": truck_kills,
           "wall_s": round(time.time() - t0, 1),
           "emu_fps": round((p.core.frames_run - f0)
                            / max(time.time() - t0, 1), 1)}
    with open(os.path.join(EVID, f"report_{args.tag}.json"), "w") as f:
        json.dump(rep, f, indent=1)
    png(p, f"{args.tag}_end.png")
    log("report:", json.dumps(rep)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
