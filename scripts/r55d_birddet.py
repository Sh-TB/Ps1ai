#!/usr/bin/env python3
"""r55d_birddet.py — design a ROBUST full-res bird detector (silver
truth v2) from the recorded occlusion captures + small frames.

The bird sprite: WHITE body + ORANGE face/wing + dark outline. The r15
'yellow' sensor reads only the orange patch (~27px) — weak. Hypothesis:
a joint white-body + orange-face test in the bird column tracks the
bird through pipe passes.

This lab measures, per capture:
  * white mask stats in the bird column band (cols 130..200)
  * orange mask stats
  * joint blob centroid vs the recorded beak reading
and prints a per-frame table for manual validation against the PNGs.
"""
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r55")


def masks_full(fr):
    r = fr[:, :, 0].astype(int)
    g = fr[:, :, 1].astype(int)
    b = fr[:, :, 2].astype(int)
    white = (r > 185) & (g > 185) & (b > 165)
    orange = (r > 180) & (g > 100) & (g < 190) & (b < 110)
    return white, orange


def analyze(k, max_show=40):
    z = np.load(os.path.join(OUT, f"life_k{k:03d}.npz"))
    ful = z["fullres"]
    occl = np.nonzero(z["occl"] == 1)[0]
    if ful.ndim != 4 or not len(ful):
        print(f"k={k}: no captures")
        return
    print(f"=== k={k} captures={len(ful)}")
    rows = []
    for i, fr in enumerate(ful):
        white, orange = masks_full(fr)
        wband = white[:188, 130:200]
        oband = orange[:188, 130:200]
        wn = int(wband.sum())
        on = int(oband.sum())
        wc_y = wc_x = oy_y = oy_x = -1
        if wn >= 6:
            ys, xs = np.nonzero(wband)
            wc_y, wc_x = ys.mean(), xs.mean() + 130
        if on >= 4:
            ys, xs = np.nonzero(oband)
            oy_y, oy_x = ys.mean(), xs.mean() + 130
        rows.append((i, int(occl[i]) if i < len(occl) else -1, wn, on,
                     wc_y, oy_y))
    arr = np.asarray([(r[2], r[3]) for r in rows], dtype=float)
    print(f" white-in-band: min={arr[:,0].min():.0f} "
          f"med={np.median(arr[:,0]):.0f} max={arr[:,0].max():.0f}; "
          f">=12px: {100.0*(arr[:,0]>=12).mean():.1f}%")
    print(f" orange-in-band: min={arr[:,1].min():.0f} "
          f"med={np.median(arr[:,1]):.0f} max={arr[:,1].max():.0f}; "
          f">=4px: {100.0*(arr[:,1]>=4).mean():.1f}%")
    # white centroid stability: is the white blob a coherent moving
    # object (deltas small) or split across clouds/pipes?
    wy = np.asarray([r[4] for r in rows], dtype=float)
    ok = wy >= 0
    if ok.sum() > 3:
        d = np.abs(np.diff(wy[ok]))
        print(f" white centroid present {ok.sum()}/{len(rows)}; "
              f"delta med={np.median(d):.1f} p90={np.percentile(d,90):.1f}")
    for i, oc, wn, on, wy_, oy_ in rows[:max_show]:
        print(f"  cap{i:3d} step~{oc if oc>=0 else -1:4d} white={wn:3d}"
              f"@y={wy_:6.1f}  orange={on:3d}@y={oy_:6.1f}")


if __name__ == "__main__":
    for k in [int(x) for x in (sys.argv[1].split(",")
                               if len(sys.argv) > 1 else ["6", "30"])]:
        analyze(k)
