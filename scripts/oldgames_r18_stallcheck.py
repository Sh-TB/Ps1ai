#!/usr/bin/env python3
"""oldgames_r18_stallcheck.py — is the quad screen a slow init or a true stall?

4000 frames, PNG every 500f, per-frame mean-absolute luma + frame-to-frame
change counts. Verdict: STATIC_STALL if all frames identical; SLOW_INIT if
any visual progression appears.
"""
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_small/play_evidence/r18_probe"
CUE = "/home/z/my-project/emu/games_small/extracted/ballistic/Ballistic [U] [SLUS-00966]/Ballistic [U] [SLUS-00966].cue"


def main():
    p = PS1Play(CUE, workspace=os.path.join(EVID, "ws_ballistic2"))
    p.boot()
    p.wait(120)
    prev = None
    rows = []
    for i in range(9):
        p.core.run(500, set())
        img = p.core.frame_rgb()
        if img is None:
            rows.append((i, "no_frame"))
            continue
        arr = img if isinstance(img, np.ndarray) else np.asarray(img)
        a = np.asarray(Image.fromarray(arr).convert("L").resize((320, 240)), dtype=np.int16)
        Image.fromarray(arr).save(os.path.join(EVID, f"stall_{i * 500 + 620}.png"))
        ch = int(np.abs(a - prev).sum()) if prev is not None else -1
        rows.append((i * 500 + 620, float(a.mean()), ch))
        prev = a
    out = {"rows": [{"f": r[0], "luma": r[1], "delta": r[2]} for r in rows]}
    vals = {r[2] for r in rows if len(r) == 3 and r[2] >= 0}
    out["verdict"] = "STATIC_STALL" if not vals or max(vals) == 0 else "SLOW_INIT"
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
