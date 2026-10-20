#!/usr/bin/env python3
"""debug_causality.py — diagnose frozen-frame / input-path in causality lab."""
import sys, os
import numpy as np
_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    sys.path.insert(0, _p)
from ps1play import labconfig
from ps1play.api import PS1Play
from mission import ensure_mission, responsive
from PIL import Image

p = PS1Play(labconfig.resolve_path("game"))
info = p.boot()
p._advance()
r = ensure_mission(p, log=print)
print("gate:", r["in_mission"], "pad:", r["idle"], r["run"])

p.save_state("dbg0")
for label, spec in (("idle", set()), ("right", {"RIGHT"}),
                    ("cross", {"B"}), ("fire", {"Y"})):
    p.load_state("dbg0")
    # sample pad mirror + frame mid-leg
    mirrors, diffs = [], []
    prev_rgb = p.core.frame_rgb()
    p.core.set_buttons(spec)
    for i in range(60):
        p.core.run_frame()
        if i in (10, 30, 50):
            mirrors.append(hex(p.mem.u16(0x0D4948)))
            rgb = p.core.frame_rgb()
            if prev_rgb is not None and rgb is not None:
                diffs.append(round(float(
                    np.abs(rgb.astype(int) - prev_rgb.astype(int)).mean()), 2))
            prev_rgb = rgb
    p._advance()
    rgb_end = p.core.frame_rgb()
    Image.fromarray(rgb_end).save(
        f"/home/z/my-project/work/msx_recomp/evidence/issue4_causality/dbg_{label}.png")
    churn = None
    p.load_state("dbg0")
    s0 = p.mem.snapshot()
    p.core.run(60, spec)
    p._advance()
    churn = int(np.count_nonzero(s0 != p.mem.snapshot()))
    print(f"{label:6s} mirror={mirrors} midframe_diffs={diffs} churn60={churn}")
