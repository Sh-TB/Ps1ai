#!/usr/bin/env python3
"""r55b_lab.py — offline analysis of the r55a recordings.

Questions this answers (all from recorded small frames + full-res
occlusion captures, no emulator):
  1. WHERE does the sf teacher die per seed (frame index, silver y,
     gap geometry)?
  2. How often does the full-res vision lose the bird, and is the loss
     explained by pipe occlusion (green in the bird column)?
  3. Does the small-frame yellow feature (by_feat) latch (frozen values)
     during those windows, and on WHAT pixels (the yellow-mask hit map)?
  4. The gap features (gc_feat) during approach vs pass.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r55")


def yellow_small(s):
    r = s[:, :, 0].astype(int)
    g = s[:, :, 1].astype(int)
    b = s[:, :, 2].astype(int)
    y = (r > b + 25) & (g > b + 5) & (r > 120)
    y[:5, :] = False
    y[46:, :] = False
    y[:, :32] = False
    y[:, 50:] = False
    return y


def green_small(s):
    r = s[:, :, 0].astype(int)
    g = s[:, :, 1].astype(int)
    b = s[:, :, 2].astype(int)
    return (g > 110) & (g > r + 10) & (b < 175) & (r < g)


def analyze(k):
    z = np.load(os.path.join(OUT, f"life_k{k:03d}.npz"))
    fr = z["frames"]
    act = z["actions"]
    vy = z["vision_y"]
    vn = z["vision_n"]
    sy = z["silver_y"]
    oc = z["occl"]
    byf = z["by_feat"]
    gcf = z["gc_feat"]
    n = len(fr)
    print(f"=== k={k} steps={n} result_rows={n}")
    # vision loss stats
    vloss = vy < 0
    print(f" vision lost: {vloss.sum()}/{n} "
          f"({100.0*vloss.mean():.1f}%)  occl==1: {(oc==1).sum()}")
    # by_feat latch: frozen (>0, delta < 0.5) runs
    feats = byf[byf >= 0]
    if len(feats) > 2:
        d = np.abs(np.diff(feats))
        print(f" by_feat present {len(feats)}/{n}; frozen-delta(<0.5) "
              f"frac {100.0*(d<0.5).mean():.1f}%")
    # per-100-step blocks: vision loss + feature presence
    for b0 in range(0, n, 100):
        b1 = min(n, b0 + 100)
        blk_v = 100.0 * (vy[b0:b1] < 0).mean()
        blk_f = 100.0 * (byf[b0:b1] >= 0).mean()
        a_flaps = int((act[b0:b1] == "FLAP").sum())
        print(f"  [{b0:4d}:{b1:4d}] vloss%={blk_v:5.1f} byfeat%={blk_f:5.1f} "
              f"flaps={a_flaps:3d} sy[-1..]={sy[b1-1]:6.1f} "
              f"gc={gcf[b1-1]:6.1f}")
    # find death window: last 40 steps detail
    print(" -- last 40 steps (step, act, vision_y, by_feat, gc_feat, "
          "silver_y, occl):")
    for i in range(max(0, n - 40), n):
        print(f"   {i:4d} {act[i]:5s} v={vy[i]:6.1f}/{vn[i]:3d} "
              f"bf={byf[i]:6.1f} gc={gcf[i]:6.1f} sy={sy[i]:6.1f} "
              f"oc={oc[i]}")
    # the full-res occlusion captures: yellow-mask hit maps (small)
    ful = z["fullres"]
    if ful.ndim == 4 and len(ful):
        print(f" fullres occlusion captures: {len(ful)}")
        hits = []
        for i, s in enumerate(ful):
            ym = yellow_small(s)
            gm = green_small(s)
            n_y = int(ym.sum())
            n_g = int(gm[5:46, 32:50].sum())
            hits.append((i, n_y, n_g))
        arr = np.asarray(hits)
        print(f"  yellow-pixel count in occlusion frames: "
              f"min={arr[:,1].min()} med={int(np.median(arr[:,1]))} "
              f"max={arr[:,1].max()}; frames with >=2 yellow px: "
              f"{int((arr[:,1]>=2).sum())}/{len(arr)}")
        for i, ny, ng in hits[:15]:
            print(f"   cap{i:3d} yellow_px={ny:3d} green_in_band={ng:3d}")
        # where do the yellow hits sit when they exist during occlusion?
        ys, xs = [], []
        for s in ful:
            ym = yellow_small(s)
            yy, xx = np.nonzero(ym)
            if len(yy):
                ys.append(yy.mean())
                xs.append(xx.mean())
        if ys:
            print(f"  occlusion yellow centroid small-rows: "
                  f"min={min(ys):.1f} med={np.median(ys):.1f} "
                  f"max={max(ys):.1f}  (cols min={min(xs):.1f} "
                  f"med={np.median(xs):.1f} max={max(xs):.1f})")


def main():
    meta = json.load(open(os.path.join(OUT, "r55a_meta.json")))
    for life in meta["lives"]:
        print(json.dumps(life))
    for k in meta["seeds"]:
        analyze(k)


if __name__ == "__main__":
    main()
