#!/usr/bin/env python3
"""chopper_chain.py — THE full session-3 chain, one run:

  pin_ckpt -> policy walk -> chopper_live anchor (auto) ->
  J1 jump-lobs until the chopper dies ->
  POST-KILL WATCH: section-walker transitions for 2400f ->
  release (state 0xC) + MISSION-1 screen detection + PNGs.

This closes the loop: chopper dead = last section-queue entity ->
the walker advances -> mission end.  READ-ONLY; deaths are real.
Usage: python3 scripts/chopper_chain.py
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
CHOPPER_ST = (0xAA94, 0xABDC)


def log(*a):
    print("[cc]", *a, file=sys.stderr, flush=True)


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


def raw_slots(m, n=36):
    tv = m.ram[TABLE:TABLE + n * STRIDE].view("<u2").astype(
        np.int32).reshape(n, STRIDE // 2)
    return [{"s": s, "st": int(tv[s, 0]),
             "x": round(((int(tv[s, 61]) << 16) | int(tv[s, 60]))
                        / 65536.0, 1), "h": int(tv[s, 63]),
             "hpA4": int(tv[s, 82])}
            for s in range(1, n)
            if int(tv[s, 0]) or ((int(tv[s, 61]) << 16)
                                 | int(tv[s, 60]))]


def chopper(m, px):
    best = None
    for sl in raw_slots(m):
        if sl["st"] in CHOPPER_ST and sl["hpA4"] > 0:
            d = abs(sl["x"] - px)
            if best is None or d < best[0]:
                best = (d, sl)
    return best[1] if best else None


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(
            os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    tag = time.strftime("chain_%H%M%S")
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    p, fw = boot()
    m = p.mem
    p.load_state("chopper_live")
    J({"ev": "start", **snap(m), "chopper": chopper(m, px_of(m))})

    # -- phase K: J1 the chopper until dead ---------------------------
    ch0 = chopper(m, px_of(m))
    throws, lives = 0, 4
    for k in range(150):
        if not alive(m):
            lives -= 1
            J({"ev": "death_kill", "k": k, **snap(m)})
            if lives <= 0:
                break
            got = False
            for w in range(40):      # respawn refills grenades (k11)
                p.core.run(30, set())
                if alive(m):
                    got = True
                    break
            if not got:
                break
            J({"ev": "respawn_kill", "k": k, **snap(m)})
            continue
        px = px_of(m)
        ch = chopper(m, px)
        if ch is None:
            J({"ev": "CHOPPER_DEAD", "k": k, **snap(m),
               "slots": raw_slots(m)})
            log(f"CHOPPER DEAD k={k} throws={throws} "
                f"score={snap(m)['score']}")
            break
        dx = ch["x"] - px
        if int(m.u8(GRENADES)) == 0:
            p.core.run(30, set())    # wait for the respawn refill
            continue
        if abs(dx) > 34:
            # reposition: walk toward the hover x minus ~15px lead
            target = ch["x"] - (15 if ch["x"] >= px else -15)
            d = "RIGHT" if target > px else "LEFT"
            p.core.run(8, {d})
            p.core.run(6, set())
            continue
        d = "RIGHT" if dx >= 0 else "LEFT"
        p.core.run(3, {"B"})
        p.core.run(8, set())
        p.core.run(8, {"UP", "A", d})
        p.core.run(25, set())
        throws += 1
        J({"ev": "throw", "k": k, "dx": round(dx, 1),
           "ch": ch, **snap(m)})
    s1 = snap(m)
    J({"ev": "kill_phase_end", **s1, "throws": throws})

    # -- phase W: post-kill watch + soldier clear + release -----------
    released = False
    mission = False
    seen_states = []
    for k in range(120):
        s = snap(m)
        if s["sec"] not in seen_states:
            seen_states.append(s["sec"])
            J({"ev": "SEC_CHANGE", "k": k, **s, "slots": raw_slots(m)})
            log(f"sec change k={k}: {s['sec']} px={s['px']}")
            png(p, f"sec{s['sec'][0]:02x}_{s['sec'][1]:02x}", tag)
        if s["sec"][0] == 0xC:
            released = True
            if s["px"] < 200.0:
                mission = True
                J({"ev": "MISSION_SCREEN", "k": k, **s})
                png(p, "mission_screen", tag)
                log(f"MISSION SCREEN k={k} px={s['px']}")
                break
        if not alive(m):
            J({"ev": "death_watch", "k": k, **s})
            got = False
            for w in range(40):
                p.core.run(30, set())
                if alive(m):
                    got = True
                    break
            if not got:
                break
            continue
        # clear any remaining ground foes (the release_test recipe)
        px = px_of(m)
        foes = [sl for sl in raw_slots(m)
                if sl["h"] == 64 and sl["hpA4"] == 0 and
                sl["st"] not in (19428, 0x4BE4, 0x5CC8) and
                abs(sl["x"] - px) < 230]
        if foes:
            near = min(foes, key=lambda e: abs(e["x"] - px))
            d = "RIGHT" if near["x"] >= px else "LEFT"
            p.core.run(6, {d})
            p.core.run(24, {"Y"})
            p.core.run(10, set())
        else:
            # nothing pending: the release_test released while the
            # player WALKED the section (zone clear at px 1034) —
            # walk RIGHT through the clamp zone
            p.core.run(40, {"RIGHT"})
            p.core.run(10, set())
    fin = snap(m)
    rep = {"tag": tag, "throws": throws,
           "chopper_dead": chopper(m, px_of(m)) is None,
           "released": released, "mission_screen": mission,
           "seen_states": [list(x) for x in seen_states],
           "final": fin}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    J({"ev": "done", **rep})
    png(p, "final", tag)
    log("DONE", json.dumps({k: rep[k] for k in
                            ("throws", "chopper_dead", "released",
                             "mission_screen")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
