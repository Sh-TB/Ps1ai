#!/usr/bin/env python3
"""r55h_trace_lab.py — dissect the law-on-v7 death trace (k=6)."""
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r55")

z = np.load(os.path.join(OUT, "trace_v7b_k6.npz"))
fr = z["frames"]; act = z["action"]; oy = z["obs_y"]; ov = z["obs_vy"]
st = z["since_trust"]; by = z["beak_y"]; gc = z["gap_gc"]; bx = z["gap_bx"]
n = len(fr)
print(f"steps={n}")
for b0 in range(0, n, 50):
    b1 = min(n, b0 + 50)
    print(f"[{b0:4d}:{b1:4d}] flaps={int((act[b0:b1]=='FLAP').sum()):3d} "
          f"obs_y[-1]={oy[b1-1]:7.1f} vy={ov[b1-1]:5.1f} "
          f"st={st[b1-1]:3d} beak={by[b1-1]:7.1f} gc={gc[b1-1]:6.1f}")
print("--- last 60 steps:")
for i in range(max(0, n - 60), n):
    print(f" {i:4d} {act[i]:5s} oy={oy[i]:7.1f} vy={ov[i]:5.1f} "
          f"st={st[i]:3d} beak={by[i]:7.1f} gc={gc[i]:6.1f}")
# blind stats
blind = st > 0
print(f" blind steps: {int(blind.sum())}/{n}")
# where does obs diverge from beak? (both valid)
ok = (oy > 0) & (by > 0)
if ok.sum():
    err = np.abs(oy[ok] - by[ok])
    print(f" |obs-beak| med={np.median(err):.1f} p90={np.percentile(err,90):.1f} "
          f"max={err.max():.1f}; >10px: {100*(err>10).mean():.1f}%")
