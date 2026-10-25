#!/usr/bin/env python3
"""truck_zone_probe.py — READ-ONLY raw entity census through the D7
zone (Issue #5 truck reach revival).

Question: what states does the armored truck take during the approach,
what does CombatPolicy's armor_hold actually lock (hp>=200 now keys the
SCREEN-X field post-semantics-correction), and what kills the player
when holding around px 900-1030?

Method: fresh boot -> CombatPolicy walk (grenades=0, unchanged) ->
from px>=850 dump EVERY raw slot (st, world x, h, hp_a4, sx) every 15f
plus a px/score/section snapshot. No memory writes, no cheats.

Usage: python3 scripts/truck_zone_probe.py
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


def log(*a):
    print("[zp]", *a, file=sys.stderr, flush=True)


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
        hp8E = int(tv[s, 71])
        hpA4 = int(tv[s, 82])
        h = int(tv[s, 63])
        if not st and not xw:
            continue
        out.append({"s": s, "st": st, "x": round(xw, 1), "h": h,
                    "hp8E": hp8E, "hpA4": hpA4})
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(EVID, f"zone_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n"); jf.flush()

    p, fw = boot()
    m = p.mem
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    dumping = False
    f0 = p.core.frames_run
    for c in range(200):
        px = px_of(m)
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            J({"ev": "death", "chunk": c, **s,
               "slots": raw_slots(m)})
            log(f"DIED c{c} px={s['px']}")
            break
        if px >= 850:
            dumping = True
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
        if dumping and c % 2 == 0:      # every ~2 policy chunks
            J({"ev": "census", "chunk": c, "mode": pol.mode,
               **snap(m), "slots": raw_slots(m),
               "scan_hp8E": [(e["slot"], e["st"], e["dx_px"], e["hp"])
                             for e in scan]})
        if c % 10 == 0:
            log(f"c{c} px={s['px']} mode={pol.mode} gren={s['gren']} "
                f"score={s['score']}")
    jf.close()
    log("probe done", round(time.time() - p.core.frames_run / 60, 1))


if __name__ == "__main__":
    main()
