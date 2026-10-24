#!/usr/bin/env python3
"""truck_uplob9.py — clamp-stand grenade spam at the chasing truck.

Sequence per rep:
  1. approach -> hit #1 at the proven geometry (hp 300->200)
  2. escape RIGHT to the clamp (px ~1164)
  3. face LEFT and SPAM grenades at the chasing truck, alternating
     UP-lobs (short arc, for close range) and flat lobs, one grenade
     per ~35f, until +0xA4 hits 0 or the record dies (ammo permits:
     9 left after hit #1)
  4. on kill: walk RIGHT hard -> pin release test

Usage: python3 scripts/truck_uplob9.py --rep 1
"""
import argparse, json, os, sys, time
import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
ENGAGE = "truck_engage"
EVID = os.path.join(labconfig.resolve_path("evidence_dir"), "issue5_truck")


def log(*a):
    print("[t9]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS)),
            "sec_prog": int(m.u16(combat.SECTION_PROGRESS))}


def truck(m):
    tv = m.ram[TABLE + 14 * STRIDE:TABLE + 15 * STRIDE].view("<u2")
    return {"st": int(tv[0]), "x": ((int(tv[61]) << 16) |
                                    int(tv[60])) / 65536.0,
            "h": int(tv[63]), "sx": int(tv[71]), "hpA4": int(tv[82])}


def alive(t):
    return t["st"] != 0x4BE4 and t["x"] != 0.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", type=int, default=1)
    args = ap.parse_args()
    tag = f"uplob9_rep{args.rep}"
    os.makedirs(os.path.join(EVID, tag), exist_ok=True)
    jf = open(os.path.join(EVID, tag, "trace.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    p.load_state(ENGAGE)
    for _ in range(3):
        p.core.run_frame()
    s0 = snap(m)
    tr0 = truck(m)
    truck_x0 = tr0["x"]
    J({"ev": "start", "snap": s0, "truck": tr0})
    log(f"rep{args.rep} start truck={tr0}")
    png(p, "start", tag)

    dead, killed = False, False
    hp_track = [tr0["hpA4"]]

    # ---- hit #1 at the proven geometry ----
    threw = False
    for k in range(200):
        if snap(m)["flags"] != 0xFF or px_of(m) == 0.0:
            dead = True
            break
        dx = truck_x0 - px_of(m)
        if -62 <= dx <= -50:
            p.core.run(2, {"LEFT"})
            trk_pre = truck(m)
            p.core.run(8, {"A"})
            p.core.run(2, set())
            threw = True
            break
        p.core.run(6, {"LEFT"} if dx < -50 else {"RIGHT"})
    if not threw or dead:
        J({"ev": "abort_hit1"})
        res = {"rep": args.rep, "abort": True, "final": snap(m)}
        with open(os.path.join(EVID, tag, "report.json"), "w") as f:
            json.dump(res, f, indent=1)
        return
    p.core.run(110, {"RIGHT"})            # escape toward the clamp
    log(f"rep{args.rep} hit1 hp {trk_pre['hpA4']}->{truck(m)['hpA4']}")

    # ---- spam phase at the clamp ----
    spam = []
    for i in range(14):
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            dead = True
            J({"ev": "player_died", "i": i, "snap": s})
            png(p, "died", tag)
            break
        trk = truck(m)
        if not alive(trk) or trk["hpA4"] <= 0:
            killed = True
            png(p, "truck_dead", tag)
            break
        # face left, then throw: alternate UP-lob / flat
        p.core.run(2, {"LEFT"})
        if i % 2 == 0:
            p.core.run(3, {"UP"})
            p.core.run(6, {"UP", "A"})
        else:
            p.core.run(6, {"A"})
        p.core.run(2, set())
        # watch 30f
        p.core.run(22, set())
        trk2 = truck(m)
        spam.append({"i": i, "hp": trk2["hpA4"], "truck_x": trk2["x"],
                     "px": round(px_of(m), 1), "score": snap(m)["score"]})
        J({"ev": "spam", "i": i, "truck": trk2, "snap": snap(m)})
        hp_track.append(trk2["hpA4"])
        log(f"rep{args.rep} spam{i}: hp={trk2['hpA4']} "
            f"truck_x={trk2['x']:.1f} px={px_of(m):.1f}")

    # ---- pin-release walk ----
    walk, max_px, passed = [], px_of(m), False
    if not dead and snap(m)["flags"] == 0xFF and px_of(m) > 0:
        png(p, "pre_walk", tag)
        f0 = p.core.frames_run
        while p.core.frames_run - f0 < 2400:
            p.core.run(30, {"RIGHT"})
            s = snap(m)
            max_px = max(max_px, s["px"])
            if s["px"] > 1170.0:
                passed = True
            walk.append(s)
            J({"ev": "walk", **s})
            if s["flags"] != 0xFF:
                J({"ev": "walk_interrupted", **s})
                png(p, "walk_interrupt", tag)
                break

    res = {"rep": args.rep, "truck_start": tr0,
           "hp_track": hp_track, "killed": killed, "player_died": dead,
           "spam": spam, "max_px": round(max_px, 1),
           "passed_1170": passed, "walk_len": len(walk),
           "walk_tail": walk[-8:], "final": snap(m),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, tag, "report.json"), "w") as f:
        json.dump(res, f, indent=1)
    jf.close()
    png(p, "end", tag)
    log(f"rep{args.rep} DONE killed={killed} dead={dead} "
        f"max_px={max_px:.1f} passed_1170={passed}")


if __name__ == "__main__":
    main()
