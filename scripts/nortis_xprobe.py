#!/usr/bin/env python3
"""nortis_xprobe.py — pin the REAL GameState: two candidate structs
respond to steering; per-frame word dumps + landings tell which x
predicts where the piece actually lands."""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import (CUE, EVID, WS, WIDTH, HEIGHT, HIDDEN,
                              SHAPES, cells_at, read_state, read_field,
                              wait_playing)                        # noqa

def log(*a):
    print("[nxp]", *a, file=sys.stderr, flush=True)


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "xprobe.jsonl"), "w")

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
    log("playing:", ok)
    # candidates: same signature scan
    cands = []
    for poll in range(6):
        p.core.run(30 if poll else 0, set())
        ram0 = bytes(p.mem.snapshot())
        arr0 = np.frombuffer(ram0, dtype="<u4")
        for off in range(0, len(ram0) - 28, 4):
            b, rot, ln, pt, x, y, pl = arr0[off // 4:off // 4 + 7]
            if (1 <= b <= 7 and rot <= 3 and ln == 0 and pt == 0
                    and 2 <= x <= 7 and 0 <= y <= 12 and pl == 0):
                cands.append(off)
        if cands:
            break
    cands = sorted(set(cands))
    J({"ev": "cands", "offs": [hex(c) for c in cands]})
    # verify ALL with L/R (collect every responder)
    live = []
    for off in cands[:16]:
        r0 = bytes(p.mem.snapshot())
        a0 = np.frombuffer(r0, dtype="<u4")
        x0 = int(a0[off // 4 + 4])
        if not (2 <= x0 <= 7):
            continue
        p.core.run(1, {"LEFT"})
        p.core.run(5, set())
        a1 = np.frombuffer(bytes(p.mem.snapshot()), dtype="<u4")
        if int(a1[off // 4 + 4]) != x0 - 1:
            continue
        p.core.run(1, {"RIGHT"})
        p.core.run(5, set())
        a2 = np.frombuffer(bytes(p.mem.snapshot()), dtype="<u4")
        if int(a2[off // 4 + 4]) == x0:
            live.append(off)
    J({"ev": "live", "offs": [hex(c) for c in live]})
    log("live:", [hex(c) for c in live])
    # trace 6 pieces: per-frame dumps of all live structs + landing
    for piece in range(6):
        # wait for a fresh spawn (y small) on the FIRST live struct
        for _ in range(60):
            st0 = read_state(bytes(p.mem.snapshot()), live[0])
            if st0["play"] == 0 and st0["y"] <= 3:
                break
            p.core.run(10, set())
        trace = []
        pre = None
        landed = None
        for f in range(600):
            ram = bytes(p.mem.snapshot())
            words = {hex(o): read_state(ram, o) for o in live}
            trace.append({"f": f, **{k: v["x"] for k, v in
                                     words.items()},
                          "y0": words[hex(live[0])]["y"],
                          "play0": words[hex(live[0])]["play"]})
            if f == 0:
                fld0 = read_field(ram, 0x16378)
            if pre is not None:
                fld = read_field(ram, 0x16378)
                d = np.nonzero(fld != pre)
                if len(d[0]):
                    landed = sorted((int(r), int(c))
                                    for r, c in zip(*d))
                    J({"ev": "landing", "piece": piece, "f": f,
                       "landed": landed,
                       "words_at_landing": words})
                    break
            pre = read_field(ram, 0x16378).copy()
            # one neutral frame (no input) — pure gravity
            p.core.run(1, set())
        J({"ev": "piece_trace", "piece": piece, "n": len(trace),
           "xs": {k: [t[k] for t in trace[::10]] for k in
                  [hex(o) for o in live]}})
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
