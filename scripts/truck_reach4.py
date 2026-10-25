#!/usr/bin/env python3
"""truck_reach4.py — revive `truck_engage`, evidence-driven v4.

Session evidence (evidence/issue5_truck_reach2/zone_*.jsonl, reach3):
  * the hp_a4==300 h~206-228 slot (st 0xaa94/0xabdc) oscillating above
    is the CHOPPER class, not the truck; the ground truck (h 64,
    parked st 0x9E88 @937.5, historical anchor) only appears once the
    player holds the safe band 950-998 (CLAMP-ROOT: 5400f zero deaths,
    "the armored wave approached into range")
  * reach3 died because the walk overshot to 1030 (policy 60f chunks
    run ~2.2px/f) and the hold loop had no anti-bomb cadence

v4: policy walk to px>=900 -> fine 5f steps into [950,985] -> hold:
    periodic hop (200f cadence), reactive faller dodge (h window
    widened to 260), Y-bursts at soldiers ahead, poll every 6f for the
    ground truck; save `truck_engage` when the truck is behind at the
    proven band dx 45..90. No memory writes, no cheats.

Usage: python3 scripts/truck_reach4.py
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
HOLD_LO, HOLD_HI = 950.0, 985.0
BAND_LO, BAND_HI = 45.0, 90.0
HOLD_BUDGET_F = 9000
DEAD_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[r4]", *a, file=sys.stderr, flush=True)


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


def truck_cands(m, px):
    """Ground-truck candidates: parked signature OR ground+hp300."""
    out = []
    for sl in raw_slots(m):
        if sl["st"] in DEAD_ST:
            continue
        if sl["st"] == 0x9E88 or (sl["h"] == 64 and sl["hpA4"] == 300):
            if abs(sl["x"] - px) < 400:
                out.append(sl)
    return out


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
    jf = open(os.path.join(EVID, f"reach4_{tag}.jsonl"), "w")

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

    # ---- W2) fine steps into the hold band -------------------------
    while True:
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death_fine", **s})
            log("DIED fine-stepping"); jf.close(); return 1
        if HOLD_LO <= px <= HOLD_HI:
            break
        fall = faller_near(m, px)
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(8, set())
            J({"ev": "dodge_fine", "faller": fall,
               "px": round(px, 1)})
            continue
        p.core.run(5, {"RIGHT"} if px < HOLD_LO else {"LEFT"})
        J({"ev": "fine", "px": round(px, 1)})

    # ---- H) hold loop ----------------------------------------------
    truck_seen = []
    saved = False
    h0 = p.core.frames_run
    last_hop = h0
    while p.core.frames_run - h0 < HOLD_BUDGET_F:
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death_hold", **s,
               "slots": raw_slots(m), "truck_seen": truck_seen[-8:]})
            log(f"DIED holding px={s['px']}")
            break
        cands = truck_cands(m, px)
        for t in cands:
            truck_seen.append({**t, "px": round(px, 1),
                               "f": p.core.frames_run - h0})
        for t in cands:
            if t["h"] != 64:
                continue
            dx = px - t["x"]
            if BAND_LO <= dx <= BAND_HI:
                p.core.run(3, set())
                s2 = snap(m)
                if s2["flags"] == 0xFF and s2["px"] != 0.0:
                    p.save_state("truck_engage")
                    J({"ev": "SAVED", "truck": t, "dx": round(dx, 1),
                       "snap": s2})
                    log(f"SAVED truck_engage st={t['st']:#06x} "
                        f"x={t['x']} px={s2['px']} dx={dx:.0f}")
                    saved = True
                    break
        if saved:
            break
        fall = faller_near(m, px)
        now = p.core.frames_run
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(8, set())
            J({"ev": "dodge", "faller": fall, "px": round(px, 1)})
            last_hop = now
        elif now - last_hop >= 200:
            p.core.run(3, {"B"}); p.core.run(10, {"B"})
            p.core.run(8, set())
            last_hop = now
            J({"ev": "hop", "px": round(px, 1)})
        else:
            sol = soldier_ahead(m, px)
            if sol is not None:
                p.core.run(8, {"RIGHT", "Y"})
                p.core.run(6, set())
            elif px < HOLD_LO + 4:
                p.core.run(6, {"RIGHT"})
            elif px > HOLD_HI - 4:
                p.core.run(6, {"LEFT"})
            else:
                p.core.run(6, set())
        if (now - h0) % 300 < 12:
            J({"ev": "hold", **snap(m),
               "cands": cands, "slots_n": len(raw_slots(m))})
    res = {"saved": saved, "final": snap(m),
           "truck_seen_tail": truck_seen[-12:],
           "n_truck_seen": len(truck_seen),
           "frames": p.core.frames_run - f0,
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"reach4_{tag}_report.json"),
              "w") as f:
        json.dump(res, f, indent=1)
    J({"ev": "done", **res})
    jf.close()
    log("DONE", json.dumps({"saved": saved,
                            "n_truck_seen": len(truck_seen)}))
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
