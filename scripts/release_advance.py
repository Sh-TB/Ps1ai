#!/usr/bin/env python3
"""release_advance.py — post-release progression test (D7 follow-up).

release_test.py 3/3 proved: clearing the section's pending entities
(the frozen 0x4054 soldiers) releases the D7 pin — walker state
0xB -> 0xC, flags 0x42/0x43 -> 0x8, progress leaves -1.

This script continues past the release: after the proven release
chain, hand control to the CombatPolicy (the shipped rule-based
policy, no cheats) and measure REAL progression in whatever follows
(new section / rebased coordinates).  PNG evidence at the release and
every 10th chunk.

Success = sustained live progression (score/kill/px movement) in the
post-release world; honest BLOCKED with the death census otherwise.
READ-ONLY instrumentation.  Usage: python3 scripts/release_advance.py
"""
import json
import os
import sys
import time
import numpy as np
from PIL import Image

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


def log(*a):
    print("[ra]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


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
    return [sl for sl in raw_slots(m)
            if sl["st"] not in DEAD_ST and sl["st"] != 19428
            and sl["h"] == 64 and abs(sl["x"] - px) < win]


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(
            os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    tag = time.strftime("adv_%H%M%S")
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    p.load_state("pin_ckpt")
    J({"ev": "start", **snap(m)})

    # -- phase 1: wait for the respawn to 992 (proven: k=18) ----------
    ok = False
    for k in range(40):
        s = snap(m)
        if not alive(m):
            break
        if s["px"] < 1100.0:
            ok = True
            J({"ev": "RESPAWN", "k": k, **s})
            break
        p.core.run(30, set())
    if not ok:
        log("no respawn"); return 1

    # -- phase 2: clear the zone (proven: 2 kills) --------------------
    for k in range(40):
        s = snap(m)
        if not alive(m):
            J({"ev": "death_clear", "k": k, **s})
            return 1
        foes = live_enemies(m, s["px"])
        if not foes:
            J({"ev": "ZONE_CLEAR", "k": k, **s})
            break
        near = min(foes, key=lambda e: abs(e["x"] - s["px"]))
        d = "RIGHT" if near["x"] >= s["px"] else "LEFT"
        p.core.run(6, {d})
        p.core.run(24, {"Y"})
        p.core.run(10, set())

    # -- phase 3: wait for the release (state 0xC / px jump) ----------
    released = False
    for k in range(60):
        s = snap(m)
        if not alive(m):
            J({"ev": "death_wait", "k": k, **s})
            return 1
        if s["sec"][0] not in (0xA, 0xB) and s["sec"] != (0, 0) or \
                s["prog"] not in (0xFFFFFFFF, 0x80000000,
                                  2147483648, 4294967295):
            released = True
            J({"ev": "RELEASE", "k": k, **s, "slots": raw_slots(m)})
            png(p, "release", tag)
            log(f"RELEASE k={k} sec={s['sec']} prog={s['prog']:#x} "
                f"px={s['px']}")
            break
        p.core.run(30, set())
    if not released:
        log("no release observed"); return 1

    # -- phase 4: policy walk in the post-release world ----------------
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    max_px, kills = snap(m)["px"], 0
    score0 = snap(m)["score"]
    deaths = 0
    for c in range(80):
        s = snap(m)
        if not alive(m):
            deaths += 1
            J({"ev": "death_post", "chunk": c, **s,
               "slots": raw_slots(m)})
            log(f"death c{c} px={s['px']} — waiting respawn")
            for k in range(40):
                p.core.run(30, set())
                if alive(m):
                    s = snap(m)
                    J({"ev": "respawn_post", "chunk": c, **s})
                    break
            else:
                log("no respawn after death — stop")
                break
            continue
        px = px_of(m)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        pol.observe_section(combat.scan_section(m))
        scan = combat.scan_entities(m, px=px)
        segs = pol.decide(60, px, scan,
                          grenades=int(m.u8(GRENADES)),
                          hp=int(m.u16(0x0CA2F6)))
        last_px, last_segs = px, segs
        sc0 = int(m.u32(A_SCORE))
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        if int(m.u32(A_SCORE)) > sc0:
            kills += 1
        max_px = max(max_px, px_of(m))
        if c % 10 == 0:
            png(p, f"c{c:03d}", tag)
            J({"ev": "walk", "chunk": c, "mode": pol.mode, **snap(m),
               "slots": raw_slots(m),
               "scan": [(e["slot"], hex(e["st"]), e["dx_px"],
                         e["hp"]) for e in scan]})
    fin = snap(m)
    rep = {"tag": tag, "released": released, "deaths": deaths,
           "kills": kills, "max_px": max_px,
           "score_gain": fin["score"] - score0, "final": fin,
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    J({"ev": "done", **rep})
    png(p, "final", tag)
    log("DONE", json.dumps({k: rep[k] for k in
                            ("deaths", "kills", "max_px",
                             "score_gain")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
