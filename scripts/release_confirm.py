#!/usr/bin/env python3
"""release_confirm.py — final D7 confirmation: after the proven
release chain, the MISSION 1 complete screen appears (PNG evidence:
"MISSION 1" banner + PRESS START).  This run:
  1. replays the chain (pin_ckpt -> respawn -> clear 2 soldiers ->
     release (0xC,0x8)),
  2. waits on the mission screen, PNGs it,
  3. PRESSES START (the screen's own instruction),
  4. observes what follows for ~30s of frames (census + PNGs).

PASS = an observable transition past the mission screen (new HUD /
new section state / px movement / score reset for the next mission).
READ-ONLY instrumentation.  Usage: python3 scripts/release_confirm.py
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
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_chopper_hunt")
DEAD_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[cf]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(0x0CA2E0)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1),
            "score": int(m.u32(0x0EE318)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(0x0EDCF4)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def raw_slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    return [{"s": s, "st": int(tv[s, 0]),
             "x": round(((int(tv[s, 61]) << 16) | int(tv[s, 60]))
                        / 65536.0, 1), "h": int(tv[s, 63]),
             "hpA4": int(tv[s, 82])}
            for s in range(1, 24)
            if int(tv[s, 0]) or ((int(tv[s, 61]) << 16)
                                 | int(tv[s, 60]))]


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
    tag = time.strftime("cfm_%H%M%S")
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    p, fw = boot()
    m = p.mem
    p.load_state("pin_ckpt")
    J({"ev": "start", **snap(m)})

    # 1) respawn
    ok = False
    for k in range(40):
        if not alive(m):
            break
        if snap(m)["px"] < 1100.0:
            ok = True
            J({"ev": "RESPAWN", "k": k, **snap(m)})
            break
        p.core.run(30, set())
    if not ok:
        log("no respawn"); return 1

    # 2) clear the zone
    for k in range(40):
        s = snap(m)
        if not alive(m):
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

    # 3) wait for the release
    released = False
    for k in range(60):
        s = snap(m)
        if s["sec"][0] not in (0xA, 0xB) and s["sec"] != (0, 0):
            released = True
            J({"ev": "RELEASE", "k": k, **s})
            log(f"RELEASE k={k} sec={s['sec']}")
            break
        p.core.run(30, set())
    if not released:
        log("no release"); return 1

    # 4) the mission screen: wait for px to settle / PRESS START state
    mission_screen = False
    for k in range(80):
        s = snap(m)
        J({"ev": "mission_wait", "k": k, **s})
        if s["px"] < 200.0 and s["sec"][0] == 0xC:
            mission_screen = True
            break
        if s["sec"] == (0xB, 1) and s["px"] == 0.0:
            # walker reverted without the mission screen
            log("walker reverted — no mission screen")
            break
        p.core.run(30, set())
    png(p, "mission_screen", tag)
    J({"ev": "MISSION_SCREEN", "seen": bool(mission_screen),
       **snap(m)})
    log("mission screen seen:", mission_screen,
        "px=", snap(m)["px"])

    # 5) START sequence: the first START pauses (observed); toggle
    #    unpause, then press again to advance past the mission screen
    p.core.run(20, {"START"})
    p.core.run(30, set())
    J({"ev": "START_1_pause", **snap(m)})
    p.core.run(20, {"START"})          # unpause
    p.core.run(60, set())
    J({"ev": "START_2_unpause", **snap(m)})
    seen = []
    advanced = False
    for k in range(60):                # 1800f: watch for auto-tally
        s = snap(m)
        if k % 10 == 0:
            J({"ev": "tally_wait", "k": k, **s})
            seen.append((k, s["px"], s["sec"], s["score"]))
        # the screen changed away from the mission-end state?
        if s["px"] != 26.4 or s["sec"] not in ((0xC, 0x8), (0xC, 0x9)):
            advanced = True
            J({"ev": "SCREEN_CHANGED", "k": k, **s})
            log(f"screen changed k={k} px={s['px']} sec={s['sec']}")
            break
        p.core.run(30, set())
    if not advanced:
        p.core.run(20, {"START"})      # the advancing START
        p.core.run(30, set())
        J({"ev": "START_3_advance", **snap(m)})
    for k in range(100):               # 3000f observation
        s = snap(m)
        if k % 5 == 0:
            J({"ev": "post_start", "k": k, **s,
               "slots": raw_slots(m)})
            seen.append((k, s["px"], s["sec"], s["score"]))
        if k in (10, 30, 60, 99):
            png(p, f"post{k:03d}", tag)
        p.core.run(30, set())
    fin = snap(m)
    rep = {"tag": tag, "released": released,
           "mission_screen": bool(mission_screen),
           "seen": seen, "final": fin}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    J({"ev": "done", **rep})
    log("DONE", json.dumps({"mission_screen": mission_screen,
                            "final": {k: fin[k] for k in
                                      ("px", "score", "sec")}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
