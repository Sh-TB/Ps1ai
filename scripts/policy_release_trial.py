#!/usr/bin/env python3
"""policy_release_trial.py — the paired live trial of the session-3
policy fix (Issue #5 Phase 5).

One arm = load `pin_ckpt` (the D7 pin: px 1164, 10 grenades, the
section's soldiers pending) and drive ONLY the shipped CombatPolicy
(observe/observe_section/decide each chunk — no manual chain, no
cheats) for up to 120 chunks.

PASS (FIX arm): the policy clears the section's pending entities and
the game RELEASES the pin — walker state leaves {0xA,0xB} into 0xC /
mission-end (px < 200 with sec 0xC) — then the MISSION 1 screen PNG.
BASE arm (pre-fix policy, run under `git stash`): expected to stall
in the pin/death loop (the session-2/c40-c42 record).

Usage: python3 scripts/policy_release_trial.py --tag base|fix
"""
import argparse
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
    print("[pt]", *a, file=sys.stderr, flush=True)


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
    return [{"s": s, "st": int(tv[s, 0]),
             "x": round(((int(tv[s, 61]) << 16) | int(tv[s, 60]))
                        / 65536.0, 1), "h": int(tv[s, 63]),
             "hpA4": int(tv[s, 82])}
            for s in range(1, 24)
            if int(tv[s, 0]) or ((int(tv[s, 61]) << 16)
                                 | int(tv[s, 60]))]


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(
            os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--chunks", type=int, default=120)
    args = ap.parse_args()
    tag = f"trial_{args.tag}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    p.load_state("pin_ckpt")
    pol = combat.CombatPolicy()
    J({"ev": "start", **snap(m)})
    last_px, last_segs = None, None
    deaths = 0
    released = False
    mission_screen = False
    max_px = snap(m)["px"]
    for c in range(args.chunks):
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0:
            deaths += 1
            J({"ev": "death", "chunk": c, **s, "slots": raw_slots(m)})
            log(f"death c{c} px={s['px']} (deaths={deaths})")
            # wait for the F6-style respawn (control-proven: ~540f)
            got = False
            for k in range(30):
                p.core.run(30, set())
                s2 = snap(m)
                if s2["flags"] == 0xFF and s2["px"] != 0.0:
                    J({"ev": "respawn", "chunk": c, **s2})
                    got = True
                    break
            if not got:
                J({"ev": "no_respawn", "chunk": c})
                log("no respawn — stop")
                break
            continue
        px = px_of(m)
        max_px = max(max_px, px)
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
        s2 = snap(m)
        if c % 5 == 0 or s2["sec"] != s["sec"]:
            J({"ev": "chunk", "chunk": c, "mode": pol.mode, **s2,
               "scan": [(e["slot"], hex(e["st"]), e["dx_px"], e["hp"])
                        for e in scan]})
        # release detection: state leaves the pin family into 0xC
        st = s2["sec"][0]
        if st == 0xC:
            released = True
            J({"ev": "RELEASE", "chunk": c, **s2})
            log(f"RELEASE c{c} sec={s2['sec']} px={s2['px']}")
            png(p, "release", tag)
            # mission-end screen: px walks back below 200 in state 0xC
            for k in range(80):
                s3 = snap(m)
                if s3["px"] < 200.0 and s3["sec"][0] == 0xC:
                    mission_screen = True
                    J({"ev": "MISSION_SCREEN", "chunk": c, **s3})
                    png(p, "mission_screen", tag)
                    log(f"MISSION SCREEN c{c}+{k} px={s3['px']}")
                    break
                if s3["flags"] != 0xFF or s3["px"] == 0.0:
                    break
                p.core.run(30, set())
            break
    fin = snap(m)
    rep = {"tag": args.tag, "deaths": deaths, "released": released,
           "mission_screen": mission_screen, "max_px": max_px,
           "final": fin,
           "stats": {k: v for k, v in pol.stats.items()},
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    J({"ev": "done", **rep})
    log("DONE", json.dumps({k: rep[k] for k in
                            ("deaths", "released", "mission_screen",
                             "max_px")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
