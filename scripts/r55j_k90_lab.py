#!/usr/bin/env python3
"""r55j_k90_lab.py — OFFLINE dissection of the law-on-v7 k90 death
(trace tv7g_k90.npz, recorded pre-r55j; the r55j lessons were baked in
AFTER this trace, so the death mode may differ today — but the
observer-level failure classes are the same objects).

Prints the death window + the observer-vs-beak error stats, then
REPLAYS the recorded (frames, actions) through the CURRENT BirdObserverV7
+ GapTrackerV7 and compares the fresh decisions against the recorded
law decisions (which produced this death) — an offline A/B of the
r55j fixes on the exact frames that killed the law.
"""
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, REPO)

from ps1play.learn import visual_only as VO                    # noqa: E402
from ps1play.learn.teacher import FlappyTeacher                # noqa: E402

OUT = os.path.join(REPO, "scratch", "r55")
NPZ = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT,
                                                         "tv7g_k90.npz")

z = np.load(NPZ)
fr = z["frames"]; act = z["action"]; oy = z["obs_y"]; ov = z["obs_vy"]
st = z["since_trust"]; by = z["beak_y"]; gc = z["gap_gc"]
bx = z["gap_bx"]
n = len(fr)
tgc = z["trk_gc"] if "trk_gc" in z.files \
    else np.full(n, -1.0, dtype=np.float32)
print(f"== {os.path.basename(NPZ)} steps={n} "
      f"flaps={int((act == 'FLAP').sum())}")
blind = int((st > 0).sum())
print(f" blind steps: {blind}/{n} ({100 * blind / n:.0f}%)")
ok = (oy > 0) & (by > 0)
if ok.sum():
    err = np.abs(oy[ok] - by[ok])
    print(f" |obs-beak| med={np.median(err):.1f} "
          f"p90={np.percentile(err, 90):.1f} max={err.max():.1f}; "
          f">10px: {100 * (err > 10).mean():.1f}%")

print("--- last 45 steps:")
for i in range(max(0, n - 45), n):
    print(f" {i:4d} {act[i]:5s} oy={oy[i]:7.1f} vy={ov[i]:5.1f} "
          f"st={st[i]:3d} beak={by[i]:7.1f} gc={gc[i]:6.1f} "
          f"trk={tgc[i]:6.1f} bx={bx[i]:6.1f}")

# --- replay through the CURRENT v7 stack ---
obs = VO.BirdObserverV7()
gtr = VO.GapTrackerV7()
t = FlappyTeacher(flap_below=16.0, emergency_below=28.0)
t.reset_history()
prev = None
fresh = []
for i in range(n):
    o_by, o_vy = obs.step(fr[i], prev)
    g_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(fr[i])
    g_c = gtr.step((g_raw, g0, g1, dx + 160.0))
    a = t.act(o_by if o_by >= 0 else None, o_vy, g_c)
    fresh.append((a, o_by, o_vy, g_c))
    prev = a
f_act = np.asarray([f[0] for f in fresh])
same = int((f_act == act).sum())
print(f"== REPLAY(current v7): decisions equal {same}/{n} "
      f"({100 * same / n:.0f}%)")
d0 = next((i for i in range(n) if f_act[i] != act[i]), None)
if d0 is not None:
    print(f" first divergence at step {d0}")
    for i in range(max(0, d0 - 8), min(n, d0 + 12)):
        print(f" {i:4d} rec={act[i]:5s} new={f_act[i]:5s} "
              f"oy_rec={oy[i]:7.1f} oy_new={fresh[i][1]:7.1f} "
              f"gc_rec={gc[i]:6.1f} gc_new={-1 if fresh[i][3] is None else fresh[i][3]:6.1f}")
