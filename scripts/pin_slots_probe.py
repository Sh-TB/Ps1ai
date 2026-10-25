#!/usr/bin/env python3
"""pin_slots_probe.py — full raw-slot census at the pin_ckpt anchor,
60f cadence for 1800f: WHO is at the D7 pin, who one-shots, and is
the chopper (0xAA94/0xABDC) or the truck (0x9E88) ever resident?
READ-ONLY. Usage: python3 scripts/pin_slots_probe.py
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
                    "issue5_chopper_hunt")


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def raw_slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    out = []
    for s in range(1, 24):
        st = int(tv[s, 0])
        xw = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        h = int(tv[s, 63])
        hpA4 = int(tv[s, 82])
        if not st and not xw:
            continue
        out.append((s, st, round(xw, 1), h, hpA4))
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    out = os.path.join(EVID, f"pin_slots_{tag}.jsonl")
    p, fw = boot()
    m = p.mem
    p.load_state("pin_ckpt")
    with open(out, "w") as jf:
        for k in range(30):
            px = px_of(m)
            rec = {"k": k, "f": p.core.frames_run,
                   "px": round(px, 1),
                   "score": int(m.u32(A_SCORE)),
                   "gren": int(m.u8(GRENADES)),
                   "sec": (int(m.u16(combat.SECTION_STATE)),
                           int(m.u16(combat.SECTION_FLAGS))),
                   "slots": raw_slots(m)}
            jf.write(json.dumps(rec, default=str) + "\n")
            jf.flush()
            print(f"k{k:02d} px={px:7.1f} score={rec['score']} "
                  f"sec={rec['sec']} slots={rec['slots']}",
                  file=sys.stderr, flush=True)
            p.core.run(60, set())
    print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main()
