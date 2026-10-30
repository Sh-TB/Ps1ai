#!/usr/bin/env python3
"""r55f_cues.py — calibrate the small-frame bird cues on real data.

For recorded steps where the FULL-RES orange patch (beak) is confident,
print the small-frame 7x7 block RGB around the bird's small position +
the score-digit box + a cloud-row strip. This gives the exact thresholds
for the v7 observer's orange/white/dark cues.
"""
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r55")


def fullres_orange(fr):
    r = fr[:, :, 0].astype(int)
    g = fr[:, :, 1].astype(int)
    b = fr[:, :, 2].astype(int)
    m = (r > 180) & (g > 100) & (g < 190) & (b < 110)
    m[:20, :] = False
    m[186:, :] = False
    m[:, :130] = False
    m[:, 200:] = False
    ys, xs = np.nonzero(m)
    if len(ys) < 4:
        return None, 0
    return float(ys.mean()), len(ys)


def main():
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    z = np.load(os.path.join(OUT, f"life_k{k:03d}.npz"))
    fr = z["frames"]
    ful = z["fullres"]
    occl = np.nonzero(z["occl"] == 1)[0]
    n_show = 0
    print("step | bird_small(rc) | patch RGB (7x7 blocks r,g,b)")
    for j in range(0, len(ful), 25):
        fr_full = ful[j]
        step = int(occl[j]) if j < len(occl) else -1
        fy, n = fullres_orange(fr_full)
        if fy is None or step < 0 or step >= len(fr):
            continue
        sr, sc = int(round(fy / 4.0)), 40
        if not (6 <= sr <= 44):
            continue
        small = fr[step]
        r0, r1 = max(0, sr - 2), min(60, sr + 3)
        c0, c1 = max(0, sc - 3), min(80, sc + 4)
        patch = small[r0:r1, c0:c1]
        print(f"--- step {step} bird_small=({sr},{sc}) orange_n={n}")
        for ch, name in ((0, "R"), (1, "G"), (2, "B")):
            rows = ["".join(f"{px:4d}" for px in row[:, ch])
                    for row in patch]
            print(f"  {name}: " + " | ".join(rows))
        n_show += 1
        if n_show >= 8:
            break
    # the digit box + cloud strip from a clean frame (no bird near)
    small = fr[400]
    print("=== digit box rows 9..17, cols 36..46 (frame 400):")
    patch = small[9:18, 36:46]
    for ch, name in ((0, "R"), (1, "G"), (2, "B")):
        rows = ["".join(f"{px:4d}" for px in row[:, ch]) for row in patch]
        print(f"  {name}: " + " | ".join(rows))
    print("=== cloud strip rows 36..47, cols 32..50 (frame 400):")
    patch = small[36:48, 32:50]
    for ch, name in ((0, "R"), (1, "G"), (2, "B")):
        rows = ["".join(f"{px:4d}" for px in row[:, ch]) for row in patch]
        print(f"  {name}: " + " | ".join(rows))


if __name__ == "__main__":
    main()
