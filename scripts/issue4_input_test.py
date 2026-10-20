#!/usr/bin/env python3
"""issue4_input_test.py — DECISIVE test: does OUR pad move the real
Marco after the START taps?  Captures before/after frames + mirror
rhythm + world churn.  This separates 'banner cosmetic' from
'demo still owns the pad'."""
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
from issue4_real_start import (                           # noqa: E402
    boot_to_demo, banner_visible, OUTDIR, SCORE_OFF)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    p = boot_to_demo()
    for attempt in range(5):
        p.core.run(12, {"START"})
        p.core.run(150, set())
        if attempt >= 1 and not banner_visible(p):
            break
    # idle state: mirror must be 0 if we own the pad
    idles = []
    for _ in range(5):
        p.core.run(10, set())
        idles.append(int(p.mem.u16(0x0D4948)))
    # frame BEFORE movement
    p.core.run(10, set())
    rgb0 = p.core.frame_rgb()
    Image.fromarray(rgb0).save(os.path.join(OUTDIR, "inputtest_before.png"))
    s0 = p.mem.snapshot()
    # hold RIGHT 90 frames
    p.core.run(90, {"RIGHT"})
    p._advance()
    rgb1 = p.core.frame_rgb()
    Image.fromarray(rgb1).save(os.path.join(OUTDIR, "inputtest_after.png"))
    churn = int(np.flatnonzero(s0 != p.mem.snapshot()).size)
    px = round(float(np.abs(rgb0.astype(np.int16) -
                           rgb1.astype(np.int16)).mean()), 3)
    # player sprite region (Marco near the sign, left part of screen)
    box = (40, 120, 200, 224)
    a0 = np.asarray(rgb0, dtype=np.int32)[box[1]:box[3], box[0]:box[2]]
    a1 = np.asarray(rgb1, dtype=np.int32)[box[1]:box[3], box[0]:box[2]]
    sprite_px = round(float(np.abs(a0 - a1).mean()), 3)
    out = {"idle_mirror": idles, "idle_all_zero": all(v == 0 for v in idles),
           "churn": churn, "pixel_diff": px,
           "sprite_region_diff": sprite_px,
           "score": int(p.mem.u32(SCORE_OFF)),
           "verdict": ("OWN_PAD" if all(v == 0 for v in idles) and
                       (sprite_px > 1.0 or px > 0.5) else
                       "DEMO_OR_NO_PAD")}
    print(json.dumps(out, indent=1))
    with open(os.path.join(OUTDIR, "input_test.json"), "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
