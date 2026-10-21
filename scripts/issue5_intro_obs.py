#!/usr/bin/env python3
"""issue5_intro_obs.py — OBSERVE the first 900 frames after the gate:
screenshots every 60 frames + per-window mirror/churn/score, with
alternating idle and RIGHT-hold windows.  No cheats, no anchor.
Question: is there a scripted intro (Marco auto-walks), when does
input control actually start, and does the world respond to RIGHT?"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402


def _log(*a):
    print("[obs]", *a, file=sys.stderr, flush=True)


def main():
    outdir = os.path.join(
        labconfig.resolve_path("evidence_dir"), "issue5_intro_obs")
    os.makedirs(outdir, exist_ok=True)
    p, fwmode = boot()
    g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
    _log("gate:", g.get("in_mission"))
    Image.fromarray(p.core.frame_rgb()).save(
        os.path.join(outdir, "t000_gate.png"))
    for w in range(15):                      # 15 windows x 60f = 900f
        btns = {"RIGHT"} if w % 2 == 1 else set()
        s0 = p.mem.snapshot()
        m_end = None
        # run 60 frames in 20f slices, reading the mirror after a
        # fresh settle each slice
        for _ in range(3):
            p.core.run(20, btns)
        m_end = int(p.mem.u16(0x0D4948))
        # settle 10f idle then read the mirror cleanly
        p.core.run(10, set())
        m_settled = int(p.mem.u16(0x0D4948))
        churn = int(np.count_nonzero(s0 != p.mem.snapshot()))
        score = int(p.mem.u32(0x0EE318))
        flags = int(p.mem.u32(0x0EE518))
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(os.path.join(
                outdir, f"t{w * 60 + 60:04d}_{'R' if btns else 'i'}.png"))
        _log(f"w{w:02d} btn={'RIGHT' if btns else 'idle':5s} "
             f"mirror={m_end:#06x} settled={m_settled:#06x} "
             f"churn={churn:6d} score={score} flags={flags:#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
