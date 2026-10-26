#!/usr/bin/env python3
"""nortis_calib3.py — ground-truth geometry by per-frame tracking of
ONE falling piece (no statics, no game-over contamination).

Diffs over a controlled sequence: neutral fall (row stride), one LEFT
tap (cell width), another fall.  Also isolates positionY/positionX
words (u32s changing by exactly +/-1 at the right moments)."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import CUE, EVID, WS, wait_playing          # noqa


def log(*a):
    print("[nc3]", *a, file=sys.stderr, flush=True)


def diff_addrs(a, b):
    """u32-index addresses whose VALUE changed."""
    ia = np.frombuffer(a, dtype="<u4")
    ib = np.frombuffer(b, dtype="<u4")
    d = np.nonzero(ia != ib)[0]
    return [(int(i * 4), int(ia[i]), int(ib[i])) for i in d]


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "calib3.jsonl"), "w")

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
    log("playing:", ok)
    # let the first piece fall to mid-air
    p.core.run(400, set())
    S0 = bytes(p.mem.snapshot())
    # fall one gravity row (20f per source; use 24f margin)
    p.core.run(24, set())
    S1 = bytes(p.mem.snapshot())
    # one LEFT tap (piece moves 1 col left, if not at wall)
    p.core.run(2, {"LEFT"})
    p.core.run(4, set())
    S2 = bytes(p.mem.snapshot())
    # fall another row
    p.core.run(24, set())
    S3 = bytes(p.mem.snapshot())

    d_fall1 = diff_addrs(S0, S1)
    d_tap = diff_addrs(S1, S2)
    d_fall2 = diff_addrs(S2, S3)
    J({"ev": "fall1", "n": len(d_fall1),
       "diffs": [(hex(a), v0, v1) for a, v0, v1 in d_fall1[:60]]})
    J({"ev": "tap", "n": len(d_tap),
       "diffs": [(hex(a), v0, v1) for a, v0, v1 in d_tap[:60]]})
    J({"ev": "fall2", "n": len(d_fall2),
       "diffs": [(hex(a), v0, v1) for a, v0, v1 in d_fall2[:60]]})
    log("fall1:", [(hex(a), v0, v1) for a, v0, v1 in d_fall1[:20]])
    log("tap :", [(hex(a), v0, v1) for a, v0, v1 in d_tap[:20]])
    log("fall2:", [(hex(a), v0, v1) for a, v0, v1 in d_fall2[:20]])
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
