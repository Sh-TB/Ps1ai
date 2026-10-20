#!/usr/bin/env python3
"""issue4_visual_debug.py — capture frames during a controller-style run
to SEE what state the gate+policy actually reaches (rope intro? demo?
death loop?).  Saves numbered PNGs + a compact telemetry table."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PIL import Image                                     # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.telemetry import TelemetryAdapter            # noqa: E402
from issue4_controller import boot                        # noqa: E402

OUT = "/home/z/my-project/work/msx_recomp/evidence/issue4_controller/frames2"
CHUNKS = 18


def main():
    os.makedirs(OUT, exist_ok=True)
    p, fwmode = boot()
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    prev = tel.snapshot()
    rows = []
    for c in range(CHUNKS):
        segs = policy.decide(60, det)
        for s in segs:
            p.core.run(s["frames"], s["btns"] if s["btns"] else None)
        cur = tel.snapshot(frame=p.core.frames_run)
        rows.append({"chunk": c, "frame": cur["frame"],
                     "score": cur["score"], "gren": cur["grenades"],
                     "cam": hex(cur["camera_fx"]),
                     "pad": hex(cur["pad_mirror"]),
                     "btns": sorted(set().union(
                         *[s["btns"] or set() for s in segs]))})
        rgb = p.core.frame_rgb()
        if rgb is not None and c % 2 == 0:
            Image.fromarray(rgb).save(os.path.join(OUT, f"c{c:02d}.png"))
        prev = cur
    print(json.dumps(rows, indent=0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
