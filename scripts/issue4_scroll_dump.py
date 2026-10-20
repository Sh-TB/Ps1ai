#!/usr/bin/env python3
"""issue4_scroll_dump.py — reconstruct the scroll/world-x variable layout.

Evidence so far: bytes 0xEB85A and 0xEB862 (8 bytes apart, identical
series = double-buffered) increment ~+59.75 per 40 frames during RIGHT
(= 1.494/frame, Marco's run speed in px/frame) and freeze at the left
boundary.  The u16 read at those addresses wraps at 256 without the
high byte growing there, so the integer part lives elsewhere.  This
dump records the full 0xEB850..0xEB87F window every 40 frames on
RIGHT / LEFT / idle legs so the true multi-byte layout can be
reconstructed offline.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_progress_probe import boot, SCORE_OFF         # noqa: E402

LO, HI = 0xEB850, 0xEB880


def _log(*a):
    print("[scrolldump]", *a, file=sys.stderr, flush=True)


def leg_dump(p, btns, frames=240, step=40):
    p.load_state("caus0")
    rows = []
    for i in range(0, frames, step):
        p.core.run(step, btns)
        ram = p.mem.ram
        rows.append({"t": i + step,
                     "hex": ram[LO:HI].tobytes().hex(),
                     "u16_eb85a": int(p.mem.u16(0xEB85A)),
                     "u16_eb862": int(p.mem.u16(0xEB862)),
                     "score": int(p.mem.u32(SCORE_OFF))})
    p._advance()
    return rows


def main():
    p = boot()
    p.core.run(90, {"RIGHT"})
    p.core.run(45, {"Y"})
    p.core.run(15, set())
    p._advance()
    p.save_state("caus0")
    out = {"schema": "ps1play-scroll-dump/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "watch": [hex(LO), hex(HI)],
           "legs": {
               "idle": leg_dump(p, set()),
               "right": leg_dump(p, {"RIGHT"}),
               "left": leg_dump(p, {"LEFT"}),
           }}
    # diff reconstruction: which byte offsets carry the +59..60 wrap
    r = out["legs"]["right"]
    series = {}
    for k in range(0, HI - LO - 1):
        vals = []
        for row in r:
            h = bytes.fromhex(row["hex"])
            vals.append(h[k] | (h[k + 1] << 8))
        series[hex(LO + k)] = vals
    out["u16_series"] = series
    # wrap-safe forward diffs per address
    fwd = {}
    for a, v in series.items():
        d = [(b - a2) % 65536 for a2, b in zip(v, v[1:])]
        small = all(x <= 128 for x in d)
        if small and sum(d) > 100:
            fwd[a] = {"diffs": d, "net": sum(d)}
    out["forward_candidates"] = fwd
    _log("forward candidates:", json.dumps(fwd, indent=1))
    outdir = os.path.join(labconfig.resolve_path("evidence_dir"),
                          "issue4_progress")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "scroll_dump.json"), "w") as f:
        json.dump(out, f, indent=1)
    _log("saved scroll_dump.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
