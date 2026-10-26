#!/usr/bin/env python3
"""nortis_calib6.py — dump the TRUE settled field (array Q @0x1615C)
at gameplay start, before any bot piece lands; verify Q == R."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import (CUE, EVID, WS, wait_playing)         # noqa

Q = 0x1615C
R = 0x16570


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "calib6.jsonl"), "w")

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
        return 1
    ram = bytes(p.mem.snapshot())
    q = np.frombuffer(ram, dtype="<u4", count=26 * 10, offset=Q)
    r = np.frombuffer(ram, dtype="<u4", count=26 * 10, offset=R)
    J({"ev": "QR_equal", "equal": bool((q == r).all())})
    qf = q.reshape(26, 10)
    rows = ["".join(str(int(v)) if v else "." for v in row)
            for row in qf]
    J({"ev": "field_Q", "rows": rows,
       "nonzero_by_row": [int((qf[i] != 0).sum()) for i in range(26)]})
    print("Q==R:", bool((q == r).all()), file=sys.stderr)
    for i, row in enumerate(rows):
        print("%2d %s" % (i, row), file=sys.stderr)
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
