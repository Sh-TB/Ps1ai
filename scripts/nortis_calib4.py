#!/usr/bin/env python3
"""nortis_calib4.py — minimal decisive geometry probe.
Snapshot at SPAWN (piece fresh at top), log every u32 in [0x15f00,
0x16400]; wait exactly ~1 gravity row; snapshot again.  The piece
cells shift +stride; positionY +1; base falls out with the state's
own positionX/Y as anchors."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import CUE, EVID, WS, wait_playing          # noqa


def snap_words(ram, lo=0x15F00, hi=0x16400):
    arr = np.frombuffer(ram, dtype="<u4")
    out = []
    for off in range(lo // 4, hi // 4):
        v = int(arr[off])
        if v:
            out.append((off * 4, v))
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "calib4.jsonl"), "w")

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
    # wait for a FRESH spawn: positionY (0x15fc4) <= 1
    for _ in range(300):
        arr = np.frombuffer(bytes(p.mem.snapshot()), dtype="<u4")
        y = int(arr[0x15fc4 // 4])
        x = int(arr[0x15fc0 // 4])
        blk = int(arr[0x15fb0 // 4])
        if y <= 1 and 1 <= blk <= 7:
            break
        p.core.run(2, set())
    J({"ev": "spawn", "blk": blk, "x": x, "y": y})
    S0 = bytes(p.mem.snapshot())
    w0 = snap_words(S0)
    J({"ev": "words0", "words": w0})
    # one gravity row
    p.core.run(21, set())
    S1 = bytes(p.mem.snapshot())
    arr1 = np.frombuffer(S1, dtype="<u4")
    w1 = snap_words(S1)
    J({"ev": "state1", "blk": int(arr1[0x15fb0 // 4]),
       "x": int(arr1[0x15fc0 // 4]), "y": int(arr1[0x15fc4 // 4]),
       "words": w1})
    jf.close()
    print("spawn blk=%d x=%d y=%d" % (blk, x, y), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
