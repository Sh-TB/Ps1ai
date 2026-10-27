#!/usr/bin/env python3
"""r19t1_viscal.py — offline sensor calibration on r18 agent frames.

No emulator. Analyzes /home/z/my-project/emu/games_psx/evidence/
poypoy_r18_agent/frames/*.png (saved every 2 ticks = 40 frames) to design:
  1. a better HARRY (1P blue) mask  — r18 missed 38% of ticks
  2. a RETIRE!/banner detector
  3. ball (white orb) + carry detection
  4. opponent (non-blue character) masks
Outputs scratch/r19t1_poypoy/viscal.json + annotated PNGs.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

FR = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_agent/frames"
OUT = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy"
os.makedirs(OUT, exist_ok=True)

files = sorted(os.listdir(FR))
print("frames:", len(files))


def blobs(mask, minpx, maxpx):
    m = mask.astype(np.int8)
    H, W = m.shape
    seen = np.zeros_like(m)
    out = []
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = 1
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = 1
                    stack.append((ny, nx))
        n = len(pts)
        if minpx <= n <= maxpx:
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            out.append((n, float(np.mean(xs)), float(np.mean(ys)),
                        min(xs), max(xs), min(ys), max(ys)))
    return out


def old_harry(img):
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    H, W = r.shape
    floor = np.zeros((H, W), bool)
    floor[int(H * 0.28):int(H * 0.66), :] = True
    m = (np.abs(r - g) < 45) & (b > g) & (g >= r) & (b >= 115) & (b <= 190) \
        & (r >= 45) & (r <= 115) & floor
    return m


def blue_all(img):
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (b > 120) & (b > r + 40) & (b > g + 30) & (r < 110)


report = {"per_frame": []}
# sample some frames in detail
detail = {0: "start", 20: "t20", 60: "RETIRE-t60-r18", 150: "newround",
          200: "mid", 300: "mid2", 400: "late"}
for i, fn in enumerate(files):
    tick = int(fn[1:5])
    img = Image.open(os.path.join(FR, fn))
    oh = old_harry(img)
    ob = blobs(oh, 20, 500)
    ba = blue_all(img)
    bab = blobs(ba, 20, 60000)
    row = {"t": tick, "old_harry_blobs": [(b[0], round(b[1]), round(b[2]))
                                          for b in ob[:4]],
           "blue_all_n": int(ba.sum()),
           "blue_all_blobs": [(b[0], round(b[1]), round(b[2]))
                              for b in sorted(bab, reverse=True)[:4]]}
    report["per_frame"].append(row)
    if i in detail:
        img.save(os.path.join(OUT, f"visc_t{tick:04d}.png"))
        # save masks as images for inspection
        Image.fromarray((old_harry(img) * 255).astype(np.uint8)).save(
            os.path.join(OUT, f"visc_t{tick:04d}_oldmask.png"))
        Image.fromarray((blue_all(img) * 255).astype(np.uint8)).save(
            os.path.join(OUT, f"visc_t{tick:04d}_bluemask.png"))

found = sum(1 for r in report["per_frame"] if r["old_harry_blobs"])
print("old-harry found on", found, "/", len(files), "frames =",
      round(100 * found / len(files)), "%")
# biggest blue_all blob per frame (likely arena or HARRY)
n_big = sum(1 for r in report["per_frame"]
            if r["blue_all_blobs"] and r["blue_all_blobs"][0][0] > 3000)
print("blue_all blob >3000px on", n_big, "frames (arena-sized?)")

with open(os.path.join(OUT, "viscal_scan.json"), "w") as f:
    json.dump(report, f, indent=1)
print("wrote viscal_scan.json")
