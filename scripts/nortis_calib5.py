#!/usr/bin/env python3
"""nortis_calib5.py — isolate the SETTLED-field array behaviorally.

Signature: it changes ONLY at piece commit (never between two frames
mid-fall), while the render array (0x15FCC region) repaints every
frame.  Sequence: mid-fall pair (2f apart) -> per-frame delta R;
commit pair (before/after hard drop) -> delta C; settled candidates =
C minus R, u32 in [1..7], stable stride."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import (CUE, EVID, WS, wait_playing,
                              read_state)                          # noqa


def diffs(a, b):
    ia = np.frombuffer(a, dtype="<u4")
    ib = np.frombuffer(b, dtype="<u4")
    d = np.nonzero(ia != ib)[0]
    return set(int(i * 4) for i in d)


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "calib5.jsonl"), "w")

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
    if not wait_playing(p, p.mem, J):
        log("no gameplay")
        return 1
    # mid-fall pair -> render delta
    p.core.run(200, set())
    A = bytes(p.mem.snapshot())
    p.core.run(2, set())
    B = bytes(p.mem.snapshot())
    R = diffs(A, B)
    # commit pair -> commit delta
    p.core.run(2, {"B"})
    p.core.run(30, set())
    C_ = bytes(p.mem.snapshot())
    Cset = diffs(A, C_)
    settled = Cset - R
    J({"ev": "sizes", "render_delta": len(R), "commit_delta": len(Cset),
       "settled_candidates": len(settled)})
    # describe candidates: value at C_, neighborhood stride check
    arrC = np.frombuffer(C_, dtype="<u4")
    cand = []
    for a in sorted(settled):
        v = int(arrC[a // 4])
        if 1 <= v <= 7:
            cand.append((hex(a), v))
    J({"ev": "candidates", "n": len(cand), "list": cand[:60]})
    print("render=%d commit=%d settled=%d cand=%d" %
          (len(R), len(Cset), len(settled), len(cand)),
          file=sys.stderr)
    # second commit for confirmation: next piece, drop again
    p.core.run(200, set())
    A2 = bytes(p.mem.snapshot())
    p.core.run(2, {"B"})
    p.core.run(30, set())
    C2 = bytes(p.mem.snapshot())
    settled2 = diffs(A2, C2) - R
    both = settled & settled2
    J({"ev": "second_commit", "settled2": len(settled2),
       "both": len(both),
       "both_list": [hex(a) for a in sorted(both)[:40]]})
    print("settled2=%d both=%d" % (len(settled2), len(both)),
          file=sys.stderr)
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
