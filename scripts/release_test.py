#!/usr/bin/env python3
"""release_test.py — THE D7 pin-release discriminating experiment.

Hypothesis (session-3 static chain, scripts/pin_release_disasm.py +
walker_writers_scan.py + dispatcher_full.asm):
  * the section VM (fn 0x80020444 + the 13-opcode dispatcher
    0x80021128) consumes a QUEUE of section-entity nodes
    (head pointer 0x800EB5F8) and per tick maps each node's state to
    a REQUEST byte;
  * request != 8  -> flags |= 0x42 (the live pin signature 0x43);
  * request == 8 / empty queue -> flags |= 0x12 arm -> the walker
    produces the next section state -> px unfreezes.
  * the frozen 0x4054 soldiers at px 1064-1103 at the pin ARE the
    pending queue nodes (control arm C: they persist >1260f with no
    input and the pin never releases).

Treatment: from `pin_ckpt` (a) let the expected one-shot land and the
F6-style respawn put us at px 992 where the control arm proved quiet;
(b) standing-fire the soldiers ahead (RIGHT); (c) poll the walker
words every 15f; (d) when no live entity remains within 220px, walk
RIGHT in 60f chunks up to 60 chunks.

PASS = the pin releases: sustained px > 1170 OR a walker state/flag
transition away from the (0xB/0xA, 0x42|0x1) pin signature with px
movement.  Control = arm C (already recorded: no release, soldiers
persist).

READ-ONLY instrumentation; deaths are real.
Usage: python3 scripts/release_test.py --rep N
"""
import argparse
import json
import os
import sys
import time
import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_chopper_hunt")
DEAD_ST = (0x4BE4, 0x5CC8)
WW = [0x800EB588, 0x800EB5CE, 0x800EB5D0, 0x800EB5D4, 0x800EB5F4,
      0x800EB5F8, 0x800EB5E8]


def log(*a):
    print("[rt]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "walker": {hex(v): int.from_bytes(
                m.ram[v - 0x80000000:v - 0x80000000 + 4].tobytes(),
                "little") for v in WW}}


def raw_slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    out = []
    for s in range(1, 24):
        st = int(tv[s, 0])
        xw = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        h = int(tv[s, 63])
        if not st and not xw:
            continue
        out.append({"s": s, "st": st, "x": round(xw, 1), "h": h,
                    "hpA4": int(tv[s, 82])})
    return out


def live_enemies(m, px, win=220.0):
    out = []
    for sl in raw_slots(m):
        if sl["st"] in DEAD_ST or sl["st"] == 19428:
            continue
        if sl["h"] == 64 and abs(sl["x"] - px) < win:
            out.append(sl)
    return out


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--max-chunks", type=int, default=60)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"rel{args.rep}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    p.load_state("pin_ckpt")
    J({"ev": "start", "snap": snap(m), "slots": raw_slots(m)})

    # -- phase 1: wait for the expected one-shot + respawn to 992 -----
    respawned = False
    for k in range(40):          # 40 x 30f = 1200f budget
        s = snap(m)
        if not alive(m):
            J({"ev": "full_death", "k": k, **s})
            log("full death instead of respawn"); break
        if s["px"] < 1100.0:
            respawned = True
            J({"ev": "RESPAWN", "k": k, **s, "slots": raw_slots(m)})
            log(f"respawn at px={s['px']} k={k}")
            break
        p.core.run(30, set())
    if not respawned:
        log("no respawn observed — aborting (anchor still pinned?)")
        J({"ev": "no_respawn"})
        jf.close()
        return 1

    # -- phase 2: standing-fire the soldiers ahead --------------------
    killed = 0
    score0 = snap(m)["score"]
    for k in range(40):          # 40 bursts
        s = snap(m)
        if not alive(m):
            J({"ev": "death_phase2", "k": k, **s})
            break
        foes = live_enemies(m, s["px"])
        if not foes:
            J({"ev": "ZONE_CLEAR", "k": k, **s, "slots": raw_slots(m),
               "killed": killed})
            log(f"zone clear k={k} killed={killed}")
            break
        # face the nearest foe and fire
        near = min(foes, key=lambda e: abs(e["x"] - s["px"]))
        d = "RIGHT" if near["x"] >= s["px"] else "LEFT"
        p.core.run(6, {d})
        p.core.run(24, {"Y"})
        p.core.run(10, set())
        sc = int(m.u32(A_SCORE))
        if sc > s["score"]:
            killed += 1
            J({"ev": "kill", "k": k, "foe": near, "score": sc,
               **snap(m)})
        if k % 5 == 0:
            J({"ev": "fire", "k": k, "foes": foes, **snap(m)})
    s2 = snap(m)
    J({"ev": "phase2_end", "killed": killed, "score_gain":
       s2["score"] - score0, **s2, "slots": raw_slots(m)})

    # -- phase 3: poll for the release --------------------------------
    released = False
    base_flags = None
    for k in range(60):          # 60 x 30f
        s = snap(m)
        fl = s["sec"][1]
        if base_flags is None and s["sec"][0] in (0xA, 0xB):
            base_flags = fl
        if not alive(m):
            J({"ev": "death_phase3", "k": k, **s})
            break
        J({"ev": "poll", "k": k, **s, "slots": raw_slots(m)})
        # release signature: pin flags 0x42/0x43 drop the 0x40 bit
        # or the state leaves 0xA/0xB, or px moves past 1170
        if s["px"] > 1170.0 or \
                (base_flags is not None and s["sec"][0] not in (0xA, 0xB)
                 and s["sec"] != (0, 0)):
            released = True
            J({"ev": "RELEASE", "k": k, **s})
            log(f"RELEASE signal k={k} sec={s['sec']} px={s['px']}")
            break
        p.core.run(30, set())

    # -- phase 4: walk right ------------------------------------------
    max_px = s2["px"]
    if alive(m):
        for c in range(args.max_chunks):
            if not alive(m):
                J({"ev": "death_walk", "chunk": c})
                break
            p.core.run(50, {"RIGHT"})
            p.core.run(10, set())
            s = snap(m)
            max_px = max(max_px, s["px"])
            if c % 2 == 0:
                J({"ev": "walk", "chunk": c, **s,
                   "slots": raw_slots(m)})
            if not alive(m):
                break
    fin = snap(m)
    rep = {"tag": tag, "rep": args.rep,
           "respawned": respawned, "killed": killed,
           "released": bool(released),
           "max_px": max_px, "final": fin,
           "score_total": fin["score"],
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    J({"ev": "done", **rep})
    log("DONE", json.dumps({k: rep[k] for k in
                            ("respawned", "killed", "released",
                             "max_px")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
