#!/usr/bin/env python3
"""chopper_kill.py — THE session-3 highest-value experiment: kill the
chopper (the last live section-queue entity at the D7 pin).

Trial data (policy_release_trial.py trial_fix): at the pin the
chopper IS active — slots cycling st 0xAA94/0xABDC with hpA4=300,
h readings 176-286, tracking the player and dropping the 0xB4E4
fallers that kill the pinned player (c23 death census).  Session-2
could not connect with UP+Y bullets or ground UP-lobs at h~210.

Arms (each from the `chopper_live` anchor, chopper overhead):
  C    no-input control — chopper/bomb cadence baseline
  J1   hop -> UP+A lob at apex   (the untried delivery; apex ~+2
       player heights + the UP-lob arc may reach h~250-300)
  J2   hop -> flat A lob at apex (arc at head height)
  J3   hop -> UP+Y air burst
  G    standing UP+A ground lob (session-2 negative control)
  YB   standing UP+Y sustained burst (session-2 re-check)

Connect = the chopper slot's hpA4 drops OR a score event while the
chopper is the only plausible target.  Every throw logs dx/h/hpA4.
READ-ONLY instrumentation; deaths are real.
Usage: python3 scripts/chopper_kill.py --anchor live --arm J1
       python3 scripts/chopper_kill.py --anchor make   (build anchor)
"""
import argparse
import json
import os
import sys
import time
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
                    "issue5_chopper_hunt")
DEAD_ST = (0x4BE4, 0x5CC8)
CHOPPER_ST = (0xAA94, 0xABDC)


def log(*a):
    print("[ck]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS)))}


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


def make_anchor(p, m, J):
    """From pin_ckpt: run the policy until the chopper is live and
    close, then save `chopper_live`."""
    p.load_state("pin_ckpt")
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    for c in range(80):
        s = snap(m)
        if not alive(m):
            # wait out the respawn (control-proven quiet at 992)
            for k in range(30):
                p.core.run(30, set())
                if alive(m):
                    break
            else:
                log("no respawn while building anchor")
                return 1
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
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        ch = chopper(m, px_of(m))
        if ch is not None and abs(ch["x"] - px) < 160 and \
                not alive(m) is False:
            p.core.run(6, set())
            if alive(m):
                p.save_state("chopper_live")
                J({"ev": "ANCHOR_SAVED", "chunk": c, "chopper": ch,
                   **snap(m), "slots": raw_slots(m)})
                log(f"ANCHOR chopper_live c{c}: chopper x={ch['x']} "
                    f"h={ch['h']} hp={ch['hpA4']} px={px:.0f}")
                return 0
    log("no live-close chopper window found")
    return 1


def run_arm(p, m, J, arm, cycles=60):
    s0 = snap(m)
    ch0 = chopper(m, px_of(m))
    J({"ev": "arm_start", "arm": arm, "snap": s0, "chopper": ch0})
    log(f"arm {arm}: chopper={ch0} px={s0['px']} gren={s0['gren']}")
    score0 = s0["score"]
    connects, events = 0, []
    for k in range(cycles):
        if not alive(m):
            J({"ev": "death", "cycle": k, **snap(m)})
            log(f"death cycle {k}")
            break
        px = px_of(m)
        ch = chopper(m, px)
        sn = snap(m)
        sc = sn["score"]
        if ch is not None:
            dx = round(ch["x"] - px, 1)
        else:
            dx = None
        if arm == "C":
            p.core.run(60, set())
        elif arm == "G":
            if int(m.u8(GRENADES)) > 0:
                d = ("RIGHT" if ch and ch["x"] >= px else "LEFT") \
                    if ch else "RIGHT"
                p.core.run(6, {"UP", "A", d})
                p.core.run(34, set())
            else:
                p.core.run(30, set())
        elif arm == "YB":
            d = ("RIGHT" if ch and ch["x"] >= px else "LEFT") \
                if ch else "RIGHT"
            p.core.run(24, {"UP", "Y", d})
            p.core.run(16, set())
        elif arm in ("J1", "J2", "J3"):
            if k % 2 == 0:
                d = ("RIGHT" if ch and ch["x"] >= px else "LEFT") \
                    if ch else "RIGHT"
                p.core.run(3, {"B"})
                p.core.run(8, set())
                if arm == "J1":
                    if int(m.u8(GRENADES)) > 0:
                        p.core.run(8, {"UP", "A", d})
                    else:
                        p.core.run(8, set())
                elif arm == "J2":
                    if int(m.u8(GRENADES)) > 0:
                        p.core.run(8, {"A", d})
                    else:
                        p.core.run(8, set())
                else:
                    p.core.run(16, {"UP", "Y", d})
                p.core.run(25, set())
            else:
                p.core.run(30, set())
        sn2 = snap(m)
        ev = {"cycle": k, "dx": dx,
              "ch": ch, "score": sn2["score"],
              "d_score": sn2["score"] - sc, "gren": sn2["gren"]}
        if sn2["score"] > sn["score"]:
            connects += 1
            ev["CONNECT"] = True
            events.append(ev)
            J({"ev": "SCORE_EVENT", "arm": arm, **ev})
        if k % 3 == 0:
            J({"ev": "census", "arm": arm, **ev, **sn2})
        chn = chopper(m, px_of(m))
        if ch0 is not None and chn is not None and \
                chn["hpA4"] < ch0["hpA4"]:
            J({"ev": "CHOPPER_HP_DROP", "arm": arm, "cycle": k,
               "from": ch0["hpA4"], "to": chn["hpA4"], **sn2})
            log(f"CHOPPER HP DROP {ch0['hpA4']}->{chn['hpA4']}")
            ch0 = chn
        if ch0 is not None and chn is None:
            J({"ev": "CHOPPER_GONE", "arm": arm, "cycle": k, **sn2,
               "slots": raw_slots(m)})
            log(f"CHOPPER GONE cycle {k} score={sn2['score']}")
            break
    fin = snap(m)
    rep = {"arm": arm, "start": s0, "final": fin,
           "score_delta": fin["score"] - score0,
           "score_events": connects, "events": events,
           "chopper_final": chopper(m, px_of(m))}
    J({"ev": "arm_done", **rep})
    log(f"arm {arm} done: dScore={rep['score_delta']} "
        f"events={connects}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", required=True, choices=["make", "live"])
    ap.add_argument("--arm", default="C",
                    choices=["C", "G", "YB", "J1", "J2", "J3"])
    ap.add_argument("--cycles", type=int, default=60)
    args = ap.parse_args()
    tag = f"chk_{args.arm}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    p, fw = boot()
    m = p.mem
    if args.anchor == "make":
        rc = make_anchor(p, m, J)
        jf.close()
        return rc
    p.load_state("chopper_live")
    rep = run_arm(p, m, J, args.arm, args.cycles)
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
