#!/usr/bin/env python3
"""truck_reach3.py — revive `truck_engage` (attempt 3, evidence-driven).

Probe findings this session (evidence/issue5_truck_reach2/zone_*.jsonl):
  * the live truck during the approach is the hp_a4 == 300 slot cycling
    states 0xaa94 / 0xabdc (oscillating x 909..1186 around the player);
    the historical parked 0x9E88 @937.5 never appears before the
    faller-bomb death
  * CombatPolicy armor_hold mislocks the 0x4054 soldier (hp>=200 keys
    the +0x8E SCREEN-X field post-correction) and holds the player at
    ~900 — outside the proven safe-hold band 950-998 — where the
    wall-mortarman faller bombs (0xb4e4) kill

Strategy (no memory writes, no cheats):
  W) CombatPolicy walk (grenades=0) until px >= 950
  H) hold loop inside [950, 998] (the CLAMP-ROOT safe band, zero deaths
     in 5400f historically): reposition, hop-dodge verified fallers
     (ahead -> LEFT+B, behind -> RIGHT+B), poll raw slots every 6f for
     the hp_a4 == 300 truck; when the truck sits BEHIND the player at
     dx 45..90 (the proven hit geometry), settle and save truck_engage
  D) death (flags != 0xFF or px == 0) -> report, exit 1

Usage: python3 scripts/truck_reach3.py
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
HOLD_LO, HOLD_HI = 950.0, 998.0
BAND_LO, BAND_HI = 45.0, 90.0
HOLD_BUDGET_F = 7200            # 2 minutes at 60fps


def log(*a):
    print("[r3]", *a, file=sys.stderr, flush=True)


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


def find_truck300(m, px):
    """Any live slot with the truck's real HP (hp_a4 == 300)."""
    return [sl for sl in raw_slots(m)
            if sl["hpA4"] == 300 and sl["st"] not in (0x4BE4,)
            and abs(sl["x"] - px) < 400]


def faller_near(m, px):
    for sl in raw_slots(m):
        if sl["st"] == 0xB4E4 and 60 < sl["h"] < 200 \
                and abs(sl["x"] - px) < 150:
            return sl
    return None


def main():
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(EVID, f"reach3_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n"); jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    f0 = p.core.frames_run

    # ---- W) policy walk to the hold band ---------------------------
    walked = False
    for c in range(200):
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death_walk", "chunk": c, **s})
            log(f"DIED walking c{c}"); jf.close(); return 1
        if px >= HOLD_LO + 10:
            walked = True
            J({"ev": "walk_done", "chunk": c, **s})
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
    if not walked:
        log("never reached the hold band"); jf.close(); return 1

    # ---- H) hold loop ----------------------------------------------
    truck_seen = {}
    saved = False
    h0 = p.core.frames_run
    while p.core.frames_run - h0 < HOLD_BUDGET_F:
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death_hold", **s, "slots": raw_slots(m)})
            log(f"DIED holding px={s['px']}"); jf.close(); return 1
        trks = find_truck300(m, px)
        for t in trks:
            truck_seen.setdefault(t["st"], []).append(
                {"chunk_f": p.core.frames_run - h0, "x": t["x"],
                 "px": round(px, 1)})
        # band check: truck BEHIND the player at the proven geometry
        for t in trks:
            dx = px - t["x"]
            if BAND_LO <= dx <= BAND_HI:
                p.core.run(3, set())
                s2 = snap(m)
                if s2["flags"] == 0xFF and s2["px"] != 0.0:
                    p.save_state("truck_engage")
                    J({"ev": "SAVED", "truck": t, "dx": round(dx, 1),
                       "snap": s2, "truck_seen": truck_seen})
                    log(f"SAVED truck_engage: st={t['st']:#06x} "
                        f"x={t['x']} px={s2['px']} dx={dx:.0f} "
                        f"gren={s2['gren']}")
                    saved = True
                    break
        if saved:
            break
        fall = faller_near(m, px)
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(8, set())
            J({"ev": "dodge", "faller": fall, "px": round(px, 1)})
            continue
        # reposition inside the hold band
        if px < HOLD_LO + 4:
            p.core.run(10, {"RIGHT"})
        elif px > HOLD_HI - 4:
            p.core.run(10, {"LEFT"})
        else:
            p.core.run(6, set())
    res = {"saved": saved, "final": snap(m),
           "truck_seen": {f"{k:#06x}": v for k, v in
                          truck_seen.items()},
           "frames": p.core.frames_run - f0,
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"reach3_{tag}_report.json"),
              "w") as f:
        json.dump(res, f, indent=1)
    J({"ev": "done", **res})
    jf.close()
    log("DONE", json.dumps({"saved": saved,
                            "truck_states": list(truck_seen)}))
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
