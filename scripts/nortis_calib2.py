#!/usr/bin/env python3
"""nortis_calib2.py — decisive field-geometry calibration.
Two landings at controlled tap-counts (LEFT x4, RIGHT x6), floor-
anchored, RAM-diff localized.  The two cell clusters' addresses solve
base/stride/cellwidth with zero assumptions about HEIGHT or enums."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import CUE, EVID, WS, wait_playing          # noqa


def log(*a):
    print("[nc2]", *a, file=sys.stderr, flush=True)


def tap(p, btn, n):
    for _ in range(n):
        p.core.run(2, {btn})
        p.core.run(4, set())


def wait_land(p):
    prev = None
    stable = 0
    for _ in range(240):
        ram = bytes(p.mem.snapshot())
        if prev is not None and ram == prev:
            stable += 1
            if stable >= 10:
                return ram
        else:
            stable = 0
        prev = ram
        p.core.run(10, set())
    return bytes(p.mem.snapshot())


def hits_u32(ram, lo=0x14000, hi=0x1A000):
    arr = np.frombuffer(ram, dtype="<u4")
    return [(int(v), off * 4) for off, v in enumerate(arr)
            if lo <= off * 4 < hi and 1 <= int(v) <= 7]


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "calib2.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(420)
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    ok = wait_playing(p, p.mem, J)
    J({"ev": "playing", "ok": ok})
    # piece 1: 4 LEFT taps -> lands near col 0
    tap(p, "LEFT", 4)
    ramA = wait_land(p)
    hA = hits_u32(ramA)
    J({"ev": "landingA", "hits": [(v, hex(a)) for v, a in hA]})
    log("landingA:", [(v, hex(a)) for v, a in hA])
    # piece 2: 6 RIGHT taps -> lands near col 9 (wall-clamped)
    tap(p, "RIGHT", 6)
    ramB = wait_land(p)
    hB = hits_u32(ramB)
    newB = [(v, a) for v, a in hB if (v, a) not in
            [(v, a) for v, a in hA]]
    J({"ev": "landingB", "hits": [(v, hex(a)) for v, a in hB],
       "new": [(v, hex(a)) for v, a in newB]})
    log("landingB new:", [(v, hex(a)) for v, a in newB])
    rgb = p.core.frame_rgb()
    if rgb is not None:
        from PIL import Image
        Image.fromarray(rgb).save(os.path.join(EVID,
                                               "calib2_board.png"))
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
