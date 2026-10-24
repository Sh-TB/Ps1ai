#!/usr/bin/env python3
"""truck_uplob10.py — after the proven truck kill, walk right and CATCH
THE KILLER at the 1164 clamp: PNG every 30f + full entity presence rows
every 30f, so the death frame shows exactly what kills the player.

Usage: python3 scripts/truck_uplob10.py --rep 1
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
    print("[ta]", *a, file=sys.stderr, flush=True)


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
            "h": int(tv[63]), "hpA4": int(tv[82])}


def presence(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    rows = []
    for s in range(24):
        xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
        st = int(tv[s, 0])
        if not xw and st in (0, 0x4BE4):
            continue
        rows.append({"s": s, "x": round(xw / 65536.0, 1), "st": st,
                     "h": int(tv[s, 63]), "hpA4": int(tv[s, 82])})
    return rows


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", type=int, default=1)
    args = ap.parse_args()
    tag = f"uplob10_rep{args.rep}"
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

    # hit #1
    threw = False
    for k in range(200):
        if snap(m)["flags"] != 0xFF or px_of(m) == 0.0:
            log("died before hit1")
            return
        dx = truck_x0 - px_of(m)
        if -62 <= dx <= -50:
            p.core.run(2, {"LEFT"})
            p.core.run(8, {"A"})
            p.core.run(2, set())
            threw = True
            break
        p.core.run(6, {"LEFT"} if dx < -50 else {"RIGHT"})
    if not threw:
        log("no hit1")
        return
    p.core.run(110, {"RIGHT"})
    log(f"hit1 hp {truck(m)['hpA4']}")

    # spam to kill the truck (uplob9-proven)
    for i in range(14):
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            log("died during spam")
            return
        trk = truck(m)
        if trk["hpA4"] <= 0:
            log(f"truck dead at spam{i} hp={trk['hpA4']} st={trk['st']:#x}")
            J({"ev": "truck_dead", "i": i, "truck": trk})
            break
        p.core.run(2, {"LEFT"})
        if i % 2 == 0:
            p.core.run(3, {"UP"})
            p.core.run(6, {"UP", "A"})
        else:
            p.core.run(6, {"A"})
        p.core.run(2, set())
        p.core.run(22, set())
    trk = truck(m)
    J({"ev": "post_spam", "truck": trk, "snap": snap(m)})

    # THE WALK: png + presence every 30f
    png(p, "walk_0000", tag)
    f0 = p.core.frames_run
    i = 0
    while p.core.frames_run - f0 < 2400:
        p.core.run(30, {"RIGHT"})
        i += 1
        s = snap(m)
        rows = presence(m)
        J({"ev": "walk", "i": i, **s, "ents": rows})
        if i % 3 == 0:
            png(p, f"walk_{i:04d}", tag)
        if s["px"] > 1170.0:
            J({"ev": "PASSED_1170", "i": i, **s})
            log(f"PASSED 1170 at walk{i} px={s['px']}")
            png(p, f"PASSED_{i:04d}", tag)
        if s["flags"] != 0xFF:
            J({"ev": "walk_interrupted", "i": i, **s})
            png(p, f"interrupt_{i:04d}", tag)
            log(f"interrupted at walk{i}: {s}")
            break

    rep = {"rep": args.rep, "final": snap(m),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, tag, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    jf.close()
    log("DONE", json.dumps(rep))


if __name__ == "__main__":
    main()
