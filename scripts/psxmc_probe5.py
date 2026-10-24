#!/usr/bin/env python3
"""psxmc_probe5.py — digital-mode button-byte delivery matrix read at
the GAME'S OWN pad buffer (Input global `input` @0x3C73C, BSS; layout:
pad_buffer[2][34] first — port0 buttons at input+2/+3, active-low).

Question: does the beetle digital pad (id 0x41) still set L2/R2/L3/R3
button bits when held? If yes, dig/place/hotbar work on the digital
pad and the DualShock switch is unnecessary. One boot per process (H5).
"""
import json
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from ps1play.plugins import psxmc_play                            # noqa

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
A_INPUT = 0x3C73C
ONE_BLOCK = 286720

TESTS = [("none", set()), ("up", {"UP"}), ("l1", {"L1"}), ("r1", {"R1"}),
         ("l2", {"L2"}), ("r2", {"R2"}), ("l3", {"L3"}), ("r3", {"R3"}),
         ("cross", {"X"}), ("start", {"START"}), ("select", {"SELECT"})]


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    # force the digital pad: no INPUT_DEVICE capability
    psxmc_play.PSXMCPlayPlugin.INPUT_DEVICE = None
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_psxmc_probe5")
    info = p.boot()
    out["input_device"] = info.get("input_device")
    P = None
    for _ in range(240):
        v = p.mem.u32(0x3C608)
        if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
            y = p.mem.u32((v & 0x1FFFFF) + 4)
            if 0 < y < 10 * ONE_BLOCK * 4:
                P = v & 0x1FFFFF
                break
        p.wait(30)
    if not P:
        out["verdict"] = "NO_WORLD"
        print(json.dumps(out, indent=1))
        return 1
    p.wait(120)
    res = {}
    for label, btns in TESTS:
        if btns:
            p.core.run(8, btns)
        w = p.mem.u16(A_INPUT + 2)                    # port0 button word
        idb = p.mem.u8(A_INPUT + 1)
        st = p.mem.u8(A_INPUT)
        res[label] = {"stat": st, "pad_id": hex(idb),
                      "held": hex((~w) & 0xFFFF)}
        p.core.run(10, set())
    out["matrix"] = res
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open("/home/z/my-project/emu/games_psx/evidence/"
              "psxmc_probe5_pad_matrix.json", "w") as f:
        json.dump(out, f, indent=1)
    for k, v in res.items():
        print(f"{k:7s} stat={v['stat']} id={v['pad_id']} held={v['held']}")
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
