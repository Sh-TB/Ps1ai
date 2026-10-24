#!/usr/bin/env python3
"""truck_uplob7.py — THE decisive campaign: 3 grenade hits kill the truck
(HP u16 @+0xA4: 300, grenade = 100 dmg), then the D7 pin-release test.

Per rep (fresh process):
  boot -> load truck_engage ->
  3x cycle: walk LEFT to dx ~ -58 (the proven hit geometry), face LEFT,
            flat lob, escape RIGHT ~90f, watch slot 14 +0xA4 while moving
            (kite: alternate RIGHT/LEFT bursts so the rear mortar cannot
            lock on) ->
  on +0xA4 == 0 or record gone: walk RIGHT hard up to 2400f, record
  px / sec-walker state every 30f -> did the pin release (px > 1170)?

Usage: python3 scripts/truck_uplob7.py --rep 1
Evidence: evidence/issue5_truck/uplob7_rep<N>/
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
    print("[t7]", *a, file=sys.stderr, flush=True)


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
    tag = f"uplob7_rep{args.rep}"
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

    hits = []
    killed = False
    for t in range(5):
        if alive(truck(m)) is False:
            break
        # approach to the proven hit geometry
        threw = False
        for k in range(150):
            px = px_of(m)
            dx = truck_x0 - px
            if -62 <= dx <= -50:
                # face left + throw
                p.core.run(2, {"LEFT"})
                pre = snap(m)
                trk_pre = truck(m)
                p.core.run(8, {"A"})
                p.core.run(2, set())
                threw = True
                break
            if dx < -62:
                p.core.run(6, {"LEFT"})
            else:
                p.core.run(6, {"RIGHT"})
        if not threw:
            J({"ev": "no_throw", "t": t})
            break
        # escape + moving watch
        p.core.run(80, {"RIGHT"})
        events = []
        hit_seen = None
        gone = False
        for w in range(9):
            btns = {"RIGHT"} if w % 2 == 0 else set()
            p.core.run(30, btns)
            trk = truck(m)
            s = snap(m)
            events.append({**s, "hpA4": trk["hpA4"], "st": trk["st"]})
            J({"ev": "watch", "t": t, "w": w, **s, "truck": trk})
            if trk["hpA4"] < trk_pre["hpA4"] and hit_seen is None:
                hit_seen = trk_pre["hpA4"] - trk["hpA4"]
            if not alive(trk):
                gone = True
                break
            if s["flags"] != 0xFF or s["px"] == 0.0:
                J({"ev": "player_died", "t": t, "w": w, "snap": s})
                png(p, "died", tag)
                break
        trk = truck(m)
        hits.append({"t": t, "hp_before": trk_pre["hpA4"],
                     "hp_after": trk["hpA4"], "dmg": hit_seen,
                     "gone": gone, "events": events})
        J({"ev": "lob", "t": t, "hp_before": trk_pre["hpA4"],
           "hp_after": trk["hpA4"], "dmg": hit_seen, "gone": gone})
        log(f"rep{args.rep} lob{t}: hp {trk_pre['hpA4']}->"
            f"{trk['hpA4']} (dmg={hit_seen}) gone={gone} "
            f"score={snap(m)['score']}")
        if gone:
            killed = True
            png(p, "truck_dead", tag)
            break
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            break

    # pin-release test: walk right hard with kiting
    walk = []
    max_px, passed = px_of(m), False
    if snap(m)["flags"] == 0xFF and px_of(m) > 0:
        png(p, "pre_walk", tag)
        f0 = p.core.frames_run
        while p.core.frames_run - f0 < 2400:
            btns = {"RIGHT"} if True else set()
            p.core.run(30, btns)
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

    res = {"rep": args.rep, "truck_start": tr0, "hits": hits,
           "killed": killed, "max_px": round(max_px, 1),
           "passed_1170": passed, "walk_len": len(walk),
           "walk_tail": walk[-8:], "final": snap(m),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, tag, "report.json"), "w") as f:
        json.dump(res, f, indent=1)
    jf.close()
    png(p, "end", tag)
    log(f"rep{args.rep} DONE killed={killed} max_px={max_px:.1f} "
        f"passed_1170={passed}")


if __name__ == "__main__":
    main()
