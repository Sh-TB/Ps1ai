#!/usr/bin/env python3
"""truck_uplob12.py — full section-clear campaign:
  1. kill the truck (proven: hit1 geometry + clamp spam)
  2. sweep EVERY remaining alive entity in world [850, 1200]:
     ground foes -> flat lob at dx -50..-62; wall foes (h>70) -> UP-lob
     from below at dx -15..-45
  3. verify the section table is clean -> walk right -> release test

Usage: python3 scripts/truck_uplob12.py --rep 1
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
DEAD_ST = {0, 0x4BE4}


def log(*a):
    print("[tc]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS)),
            "sec_prog": int(m.u16(combat.SECTION_PROGRESS))}


def slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    out = []
    for s in range(1, 24):
        xw = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        st = int(tv[s, 0])
        if st in DEAD_ST or (not xw and not st):
            continue
        out.append({"s": s, "x": round(xw, 1), "st": st,
                    "h": int(tv[s, 63]), "hpA4": int(tv[s, 82])})
    return out


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", type=int, default=1)
    args = ap.parse_args()
    tag = f"uplob12_rep{args.rep}"
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
    tr0 = {"x": ((int(m.ram[TABLE + 14 * STRIDE + 122:][0]) << 16))}  # noop
    tv = m.ram[TABLE + 14 * STRIDE:TABLE + 15 * STRIDE].view("<u2")
    truck_x0 = ((int(tv[61]) << 16) | int(tv[60])) / 65536.0
    hpA4_off = 82 * 2
    J({"ev": "start", "snap": snap(m)})

    def truck_hp():
        return int(m.ram[TABLE + 14 * STRIDE + hpA4_off:
                         TABLE + 14 * STRIDE + hpA4_off + 2]
                   .view("<u2")[0])

    # 1) hit #1
    threw = False
    for k in range(200):
        if snap(m)["flags"] != 0xFF or px_of(m) == 0.0:
            log("died pre-hit1"); return
        dx = truck_x0 - px_of(m)
        if -62 <= dx <= -50:
            p.core.run(2, {"LEFT"}); p.core.run(8, {"A"})
            p.core.run(2, set()); threw = True; break
        p.core.run(6, {"LEFT"} if dx < -50 else {"RIGHT"})
    if not threw:
        log("no hit1"); return
    p.core.run(110, {"RIGHT"})
    log(f"hit1 hp={truck_hp()}")

    # 2) spam the truck down
    for i in range(14):
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            log("died during spam"); return
        if truck_hp() <= 0:
            log(f"truck dead at spam{i}")
            J({"ev": "truck_dead", "i": i})
            break
        p.core.run(2, {"LEFT"})
        if i % 2 == 0:
            p.core.run(3, {"UP"}); p.core.run(6, {"UP", "A"})
        else:
            p.core.run(6, {"A"})
        p.core.run(2, set()); p.core.run(22, set())
    png(p, "truck_dead", tag)

    # 3) sweep remaining entities
    sweeps = []
    for rnd in range(6):
        ents = [e for e in slots(m)
                if 830 <= e["x"] <= 1220 and e["hpA4"] == 0
                and e["st"] not in (0xB4E4, 0x5CC8)
                and 55 <= e["h"] <= 100]
        J({"ev": "sweep_scan", "rnd": rnd, "ents": ents,
           "snap": snap(m)})
        log(f"sweep{rnd}: {[(e['s'], e['x'], e['h'], e['hpA4']) for e in ents]}")
        if not ents:
            break
        tgt = ents[0]
        # approach: stand at tgt.x + 55 (ground) or tgt.x + 30 (wall)
        want = tgt["x"] + (30 if tgt["h"] > 70 else 55)
        for k in range(200):
            s = snap(m)
            if s["flags"] != 0xFF or s["px"] == 0.0:
                log("died during sweep approach")
                res = {"rep": args.rep, "died": True, "final": s}
                with open(os.path.join(EVID, tag, "report.json"),
                          "w") as f:
                    json.dump(res, f, indent=1)
                return
            d = want - px_of(m)
            if abs(d) <= 6:
                break
            bomb = [e for e in slots(m) if e["st"] == 0xB4E4
                    and 60 < e["h"] < 200 and abs(e["x"] - px_of(m)) < 150]
            if bomb:
                p.core.run(12, {"RIGHT"})
                p.core.run(6, set())
                continue
            p.core.run(6, {"LEFT"} if d < 0 else {"RIGHT"})
        # face the target and throw
        face = {"LEFT"} if tgt["x"] < px_of(m) else set()
        p.core.run(2, face)
        if tgt["h"] > 70:
            p.core.run(3, {"UP"}); p.core.run(6, {"UP", "A"})
        else:
            p.core.run(8, {"A"} | face)
        p.core.run(2, set())
        p.core.run(60, set())
        sweeps.append({"rnd": rnd, "target": tgt})
        J({"ev": "sweep_throw", "rnd": rnd, "target": tgt,
           "snap": snap(m)})
    png(p, "swept", tag)

    # 4) release walk
    ents_left = [e for e in slots(m) if 830 <= e["x"] <= 1220
                 and e["hpA4"] == 0 and e["st"] not in (0xB4E4, 0x5CC8)
                 and 55 <= e["h"] <= 100]
    J({"ev": "pre_walk", "ents_left": ents_left, "snap": snap(m)})
    walk, max_px, passed = [], px_of(m), False
    f0 = p.core.frames_run
    while p.core.frames_run - f0 < 2400:
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death", **s})
            png(p, "walk_death", tag)
            break
        p.core.run(30, {"RIGHT"})
        s = snap(m)
        max_px = max(max_px, s["px"])
        if s["px"] > 1170.0:
            passed = True
            J({"ev": "PASSED_1170", **s})
            png(p, "RELEASED", tag)
            p.core.run(300, {"RIGHT"})
            break
        walk.append(s)
        J({"ev": "walk", **s})

    res = {"rep": args.rep, "sweeps": sweeps,
           "ents_left": ents_left, "released": passed,
           "max_px": round(max_px, 1), "walk_len": len(walk),
           "walk_tail": walk[-8:], "final": snap(m),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, tag, "report.json"), "w") as f:
        json.dump(res, f, indent=1)
    jf.close()
    log("DONE", json.dumps({k: res[k] for k in
        ("released", "max_px", "walk_len")}))


if __name__ == "__main__":
    main()
