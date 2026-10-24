#!/usr/bin/env python3
"""psxmc_probe3.py — pad-bit delivery matrix at the kernel pad buffer.

Session-4 ground truth: the kernel _pad_buff lives at 0xBB120 (port0:
0xBB120, layout: +0 status 0x00, +1 id 0x41, +2..3 button word,
active-low). This probe holds each button 30 frames and records the
button word — proving exactly which of L1/R1/L2/R2/L3/R3 reach the
console. One boot per process (H5).
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/psxmc_probe"
CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
PAD_BTN = 0xBB122          # u16 button word, active-low, port 0

TESTS = [("none", set()), ("L1", {"L1"}), ("R1", {"R1"}),
         ("L2", {"L2"}), ("R2", {"R2"}), ("L3", {"L3"}), ("R3", {"R3"}),
         ("TR", {"X"}), ("start", {"START"})]


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_psxmc_probe3")
    p.boot()
    for _ in range(240):
        v = p.mem.u32(0x3C608)
        if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
            break
        p.wait(30)
    p.wait(60)
    res = {}
    for label, btns in TESTS:
        if btns:
            p.core.run(10, btns)                 # pre-hold
        w = p.mem.u16(PAD_BTN)
        res[label] = {"word": w, "bits": hex((~w) & 0xFFFF)}
        p.core.run(30, btns)
        w2 = p.mem.u16(PAD_BTN)
        res[label] = {"word_held": w2,
                      "bits_held": hex((~w2) & 0xFFFF)}
        p.core.run(20, set())
    out["pad_matrix"] = res
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/probe3_pad_matrix.json", "w") as f:
        json.dump(out, f, indent=1)
    for k, v in res.items():
        print(f"{k:6s} held={v['bits_held']}")
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
