#!/usr/bin/env python3
"""truck_reach2.py — revive the lost `truck_engage` savestate after the
sandbox reset (Issue #5 truck campaign continuation).

The truck kill (hp u16 @+0xA4, 4 grenades) is GAMEPLAY_VERIFIED 8/8 at
commit 73c172d, but the savestate lived in the reset workspace. This
script re-creates it HONESTLY: no assist, no cheats, the proven
CombatPolicy walks the route from a fresh boot; when the parked truck
(st 0x9E88, hp_a4 == 300) is alive and the player is in/near the proven
hit band, the state is saved as `truck_engage`.

Stop condition (raw table read, robust to screen position):
  slot with st == 0x9E88 and hp_a4 == 300  AND
  player px in [truck_x + 40, truck_x + 90]  (past the truck, before
  the clamp at ~1164; the 8/8 kill campaign started from this zone)
If the player overshoots to the clamp (px frozen ~1164), walk LEFT back
into the band first.

Death (flags != 0xFF or px == 0) -> abort this attempt (retry = fresh
boot, done by the caller loop --rep). Grenades are preserved: the
policy is called with grenades=0 so it never spends ammo on the route.

Usage: python3 scripts/truck_reach2.py
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
TRUCK_ST, TRUCK_HP = 0x9E88, 300


def log(*a):
    print("[tr2]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS)),
            "sec_prog": int(m.u16(combat.SECTION_PROGRESS))}


def raw_truck(m):
    """Raw slot scan for the parked truck (independent of on-screen)."""
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    for s in range(1, 24):
        st = int(tv[s, 0])
        if st != TRUCK_ST:
            continue
        hpA4 = int(tv[s, 82])
        if hpA4 != TRUCK_HP:
            continue
        x = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        return {"slot": s, "x": round(x, 1), "hp_a4": hpA4}
    return None


def main():
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(EVID, f"reach_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n"); jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    log(f"boot ok fw={fw}")
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    saved = False
    f0 = p.core.frames_run
    for c in range(200):
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death", "chunk": c, **s})
            log(f"DIED at chunk {c} {s}")
            break
        trk = raw_truck(m)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        pol.observe_section(combat.scan_section(m))
        # band check BEFORE deciding (player may already be in the zone)
        if trk is not None:
            d = px - trk["x"]
            if 40 <= d <= 90:
                p.core.run(3, set())
                s2 = snap(m)
                if s2["flags"] == 0xFF and s2["px"] != 0.0:
                    p.save_state("truck_engage")
                    J({"ev": "SAVED", "chunk": c, "truck": trk,
                       "snap": s2})
                    log(f"SAVED truck_engage chunk={c} truck={trk} "
                        f"px={s2['px']} gren={s2['gren']}")
                    saved = True
                    break
            elif d > 90 and px >= 1150:
                # overshot to the clamp: walk LEFT into the band
                segs = [{"frames": 20, "btns": {"LEFT"}}]
            else:
                scan = combat.scan_entities(m, px=px)
                segs = pol.decide(60, px, scan, grenades=0,
                                  hp=int(m.u16(0x0CA2F6)))
        else:
            scan = combat.scan_entities(m, px=px)
            segs = pol.decide(60, px, scan, grenades=0,
                              hp=int(m.u16(0x0CA2F6)))
        last_px, last_segs = px, segs
        f_start = p.core.frames_run
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        J({"ev": "chunk", "chunk": c, "mode": pol.mode,
           "px": s["px"], "truck": trk, "segs": segs,
           "frames": p.core.frames_run - f_start,
           "snap": snap(m)})
        if c % 10 == 0:
            log(f"c{c} px={s['px']} truck={trk} gren={s['gren']} "
                f"score={s['score']}")
    jf.close()
    res = {"saved": saved, "final": snap(m),
           "chunks": c + 1, "frames": p.core.frames_run - f0,
           "policy_stats": dict(pol.stats),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"reach_{tag}_report.json"), "w") as f:
        json.dump(res, f, indent=1)
    log("DONE", json.dumps(res))
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
