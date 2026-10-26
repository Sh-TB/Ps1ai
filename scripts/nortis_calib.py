#!/usr/bin/env python3
"""nortis_calib.py — empirical geometry calibration for the release
binary (the cloned source may differ from the built release.zip).

Method: fresh boot -> START -> drop the FIRST piece with NO input ->
snapshot.  On an otherwise-empty board the settled piece is a tiny
cluster of small values; log every u32 in [1..7] with its address
(the piece cells + HUD/preview), plus raw bytes around the two known
state candidates.  Geometry (cell width, row stride, base) falls out
algebraically from the 4 addresses + the known spawn shape."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from nortis_lineclear import CUE, EVID, WS, wait_playing          # noqa


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "calib.jsonl"), "w")

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
    # the first piece falls on its own; wait for it to LAND (byte 2
    # region unknown -> detect landing by RAM stability instead):
    prev = None
    stable = 0
    for _ in range(200):
        ram = bytes(p.mem.snapshot())
        if prev is not None and ram == prev:
            stable += 1
            if stable >= 12:            # ~0.5s of identical RAM
                break
        else:
            stable = 0
        prev = ram
        p.core.run(10, set())
    J({"ev": "settled", "stable_frames": stable})
    ram = bytes(p.mem.snapshot())
    arr = np.frombuffer(ram, dtype="<u4")
    hits = [(int(v), int(off)) for off, v in enumerate(arr)
            if 1 <= int(v) <= 7]
    # u32 view
    J({"ev": "u32_hits", "n": len(hits),
       "hits": [(v, hex(o * 4)) for v, o in hits[:80]]})
    # byte view: every byte in [1..7] (noisy but bounded in empty RAM)
    bhits = [(int(b), i) for i, b in enumerate(ram) if 1 <= b <= 7]
    J({"ev": "byte_hits", "n": len(bhits),
       "hits": [(v, hex(i)) for v, i in bhits[:200]]})
    # raw dumps around known state candidates
    for name, off in (("candA", 0x15f5c), ("candB", 0x15fb0)):
        J({"ev": "raw_state", "which": name, "off": hex(off),
           "u32": [int(x) for x in arr[off // 4:off // 4 + 8]],
           "bytes": list(ram[off:off + 32])})
    # screenshot for the human
    rgb = p.core.frame_rgb()
    if rgb is not None:
        from PIL import Image
        Image.fromarray(rgb).save(os.path.join(EVID,
                                               "calib_board.png"))
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
