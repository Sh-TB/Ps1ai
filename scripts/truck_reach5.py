#!/usr/bin/env python3
"""truck_reach5.py — revive `truck_engage`, final geometry (v5).

reach4 evidence: the ground truck parks at 1126.5 (st 0x9E88, h 64,
hp_a4 240 in this route) while the player holds 950-1055 — the
historical BEHIND-band (player = truck_x + 45..90) is unreachable past
the clamp, BUT the proven spam phase kills from the clamp at up to
~227px lob range (uplob9: truck 937.5 <- clamp 1164). So the anchor no
longer needs the behind-band: save as soon as the truck is parked
(ground, 0x9E88) and the player is alive — before the faller-bomb
death that ended reach4 (f~4521).

No memory writes, no cheats. Usage: python3 scripts/truck_reach5.py
"""
import json, os, sys, time
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
                    "issue5_truck_reach2")
HOLD_LO, HOLD_HI = 950.0, 1000.0
HOLD_BUDGET_F = 9000
DEAD_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[r5]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS)),
            "sec_prog": int(m.u16(combat.SECTION_PROGRESS))}


def raw_slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    out = []
    for s in range(1, 24):
        st = int(tv[s, 0])
        xw = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        if not st and not xw:
            continue
        out.append({"s": s, "st": st, "x": round(xw, 1),
                    "h": int(tv[s, 63]), "hp8E": int(tv[s, 71]),
                    "hpA4": int(tv[s, 82])})
    return out


def parked_truck(m, px):
    for sl in raw_slots(m):
        if sl["st"] == 0x9E88 and sl["h"] == 64 \
                and abs(sl["x"] - px) < 400:
            return sl
    return None


def faller_near(m, px):
    for sl in raw_slots(m):
        if sl["st"] == 0xB4E4 and 60 < sl["h"] < 260 \
                and abs(sl["x"] - px) < 150:
            return sl
    return None


def soldier_ahead(m, px):
    for sl in raw_slots(m):
        if sl["h"] == 64 and sl["hpA4"] == 0 and \
                sl["st"] not in DEAD_ST and 0 < sl["x"] - px < 160:
            return sl
    return None


def main():
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(EVID, f"reach5_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n"); jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    f0 = p.core.frames_run

    # ---- W) policy walk to px>=900 ---------------------------------
    for c in range(200):
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death_walk", "chunk": c, **s})
            log(f"DIED walking c{c}"); jf.close(); return 1
        if px >= 900:
            J({"ev": "walk_done", "chunk": c, **s})
            log(f"W done c{c} px={px:.0f}")
            break
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        pol.observe_section(combat.scan_section(m))
        scan = combat.scan_entities(m, px=px)
        segs = pol.decide(60, px, scan, grenades=0,
                          hp=int(m.u16(0x0CA2F6)))
        last_px, last_segs = px, segs
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        if c % 10 == 0:
            log(f"W c{c} px={px:.0f} mode={pol.mode}")

    # ---- H) hold + save on first parked truck ----------------------
    saved = False
    h0 = p.core.frames_run
    last_hop = h0
    while p.core.frames_run - h0 < HOLD_BUDGET_F:
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death_hold", **s, "slots": raw_slots(m)})
            log(f"DIED holding px={s['px']}")
            break
        trk = parked_truck(m, px)
        if trk is not None:
            p.core.run(3, set())
            s2 = snap(m)
            if s2["flags"] == 0xFF and s2["px"] != 0.0:
                p.save_state("truck_engage")
                J({"ev": "SAVED", "truck": trk, "snap": s2,
                   "slots": raw_slots(m)})
                log(f"SAVED truck_engage: truck x={trk['x']} "
                    f"hpA4={trk['hpA4']} px={s2['px']} "
                    f"gren={s2['gren']} score={s2['score']}")
                saved = True
                break
        fall = faller_near(m, px)
        now = p.core.frames_run
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(8, set())
            J({"ev": "dodge", "faller": fall, "px": round(px, 1)})
            last_hop = now
        elif now - last_hop >= 200 and px < HOLD_LO + 40:
            p.core.run(3, {"B"}); p.core.run(10, {"B"})
            p.core.run(8, set())
            last_hop = now
        else:
            sol = soldier_ahead(m, px)
            if sol is not None:
                p.core.run(8, {"RIGHT", "Y"})
                p.core.run(6, set())
            elif px > HOLD_HI:
                p.core.run(10, {"LEFT"})   # long recovery left
            elif px < HOLD_LO:
                p.core.run(6, {"RIGHT"})
            else:
                p.core.run(6, set())
    res = {"saved": saved, "final": snap(m),
           "frames": p.core.frames_run - f0,
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"reach5_{tag}_report.json"),
              "w") as f:
        json.dump(res, f, indent=1)
    J({"ev": "done", **res})
    jf.close()
    log("DONE", json.dumps({"saved": saved}))
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
