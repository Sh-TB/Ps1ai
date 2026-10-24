#!/usr/bin/env python3
"""poypoy_flow2.py — patient EXHIBITION flow walker.

flow1 evidence: X on highlighted EXHIBITION -> Konami cinematic ->
"WAIT A MOMENT" load -> (c) splash — the post-confirm flow
SELF-PROGRESSES through long animations; button presses during those
are consumed/irrelevant and the flow1 "stable_300f" arena heuristic
misfired on the cinematic tail.

This walker:
  - never presses during motion (diff-over-90f > 20 = animating);
    tries ONE X-skip per animation block (Konami cinematics usually
    accept X/START skip)
  - at static screens: X (confirm) -> START (fallback), screenshot
    every distinct screen
  - hard caps: 45 screens / ~180k frames, one beetle boot (H5)
Output: poypoy_flow2/*.png + flow2.json (screens classified).
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow2"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"screens": [], "started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_flow2")
    p.boot()
    p.wait(420)
    p.core.run(90, {"START"})
    p.core.run(30, set())
    p.core.run(60, {"START"})
    p.core.run(240, set())
    p.core.run(10, {"DOWN"})
    p.core.run(20, set())
    p.core.run(20, {"X"})                      # confirmed EXHIBITION entry
    out["screens"].append({"n": 0, "event": "exhibition_confirmed",
                           "frame": p.core.frames_run})
    print(json.dumps(out["screens"][-1]))

    n = 1
    while n <= 45 and p.core.frames_run < 180000:
        p.core.run(90, set())
        s0 = p.core.frame_rgb()
        p.core.run(90, set())
        motion = diff(s0, p.core.frame_rgb()) or 0
        if motion > 20.0:
            # animating: one X-skip attempt per block
            p.core.run(15, {"X"})
            p.core.run(120, set())
            skipped = diff(s0, p.core.frame_rgb()) or 0
            row = {"n": n, "kind": "anim", "motion": round(motion, 1),
                   "x_skip_diff": round(skipped, 1),
                   "frame": p.core.frames_run}
            if skipped > 40:                   # skip changed everything
                snap(p, f"f2_{n:02d}_postskip.png")
            out["screens"].append(row)
            print(json.dumps(row))
        else:
            snap(p, f"f2_{n:02d}_static.png")
            p.core.run(20, {"X"})
            p.core.run(150, set())
            d_x = diff(s0, p.core.frame_rgb()) or 0
            row = {"n": n, "kind": "static", "x_diff": round(d_x, 1),
                   "frame": p.core.frames_run}
            if d_x <= 12.0:                    # X did nothing -> START
                p.core.run(20, {"START"})
                p.core.run(150, set())
                d_s = diff(s0, p.core.frame_rgb()) or 0
                row["start_diff"] = round(d_s, 1)
                if d_s > 12.0:
                    row["progressed_by"] = "START"
            else:
                row["progressed_by"] = "X"
            out["screens"].append(row)
            print(json.dumps(row))
        n += 1
    snap(p, "f2_final.png")
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "flow2.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
