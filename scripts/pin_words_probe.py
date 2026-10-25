#!/usr/bin/env python3
"""pin_words_probe.py — dump the FULL 32-bit walker words at the D7
pinned state (the u16-only snaps left the signed-compare question
open: is PROGRESS positive-saturated (pin = the 0x800232f4 gate) or
negative (the gate would pass and the block is elsewhere)?)

Load truck_engage -> proven truck kill -> walk right into the clamp
-> hex-dump 0x800EB5B0..0x800EB600 + the walker words.

READ-ONLY. Usage: python3 scripts/pin_words_probe.py
"""
import json, os, sys
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
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_truck_release")
WALKER_LO, WALKER_HI = 0x0EB5B0, 0x0EB600


def log(*a):
    print("[pw]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def dump_words(m, tag):
    blob = m.ram[WALKER_LO:WALKER_HI]
    words = blob.view("<u4")
    out = {}
    for i in range(0, len(words), 4):
        va = WALKER_LO + i * 4
        out[hex(va)] = [hex(int(w)) for w in words[i:i + 4]]
    log(f"[{tag}] walker words:")
    for k, v in out.items():
        log(f"  {k}: {' '.join(v)}")
    return out


def main():
    p, fw = boot()
    m = p.mem
    p.load_state("truck_engage")
    for _ in range(3):
        p.core.run_frame()
    dump_words(m, "anchor")
    # kill the truck: it is parked at 1126.5, player 1061.7 -> dx -65,
    # walk into the band then lobs (the proven recipe, mirrored)
    for k in range(200):
        dx = 1126.5 - px_of(m)
        if -62 <= dx <= -50:
            break
        p.core.run(6, {"LEFT"} if dx < -50 else {"RIGHT"})
    p.core.run(2, {"LEFT"}); p.core.run(8, {"LEFT", "A"})
    p.core.run(2, set()); p.core.run(35, set())
    # alternate lobs until the truck record is gone (max 8)
    for i in range(8):
        tv = m.ram[TABLE + 19 * STRIDE:TABLE + 20 * STRIDE].view("<u2")
        st = int(tv[0])
        if st != 0x9E88:
            break
        face = {"LEFT"}
        if i % 2 == 0:
            p.core.run(2, face); p.core.run(8, face | {"A"})
        else:
            p.core.run(3, face | {"UP"})
            p.core.run(6, face | {"UP", "A"})
        p.core.run(2, set()); p.core.run(35, set())
    log(f"truck state now: {hex(st)}")
    dump_words(m, "post_kill")
    # walk right into the clamp
    f0 = p.core.frames_run
    frozen = 0
    while p.core.frames_run - f0 < 1800:
        px0 = px_of(m)
        p.core.run(30, {"RIGHT"})
        px1 = px_of(m)
        frozen = frozen + 1 if abs(px1 - px0) < 0.5 else 0
        if frozen >= 3:
            break
        if int(m.u32(0x0EE518)) & 0xFF != 0xFF:
            log("died walking"); break
    log(f"pinned at px={px_of(m):.1f} "
        f"(flags={int(m.u32(0x0EE518)) & 0xFF:#x})")
    full = dump_words(m, "PINNED")
    st = int(m.u16(0x0EB5F4)); fl = int(m.u16(0x0EB5D0))
    prog32 = int(m.u32(0x0EB5D4)); sectid = int(m.u16(0x0EB5C8))
    import ctypes
    prog_signed = ctypes.c_int32(prog32).value
    res = {"state": st, "flags": fl, "sectid": sectid,
           "progress_u32": prog32, "progress_signed": prog_signed,
           "px": round(px_of(m), 1)}
    log("PIN SUMMARY:", json.dumps(res))
    log(f"advance gate test: PROGRESS(signed)={prog_signed} "
        f"< a0(small positive)? -> {prog_signed < 8}")
    with open(os.path.join(EVID, "pin_words.json"), "w") as f:
        json.dump({"summary": res, "dump": full}, f, indent=1)
    return 0


if __name__ == "__main__":
    main()
