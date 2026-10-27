#!/usr/bin/env python3
"""poypoy_r18_colormap.py — ASCII map of dominant colors (file 512x232)."""
import numpy as np
from PIL import Image

a = np.asarray(Image.open("/home/z/my-project/emu/games_psx/evidence/poypoy_r18_viscal/v_f1.png")).astype(int)
H, W = a.shape[:2]
# downsample 8x -> 64 x 29 cells, classify each cell by its mean color
step = 8
legend = {}
order = []


def classify(c):
    r, g, b = c
    if r > 200 and g > 200 and b > 200: return "W"   # white
    if b > 150 and b > r + 50 and g < b - 20 and r < 110: return "B"  # strong blue
    if b > 180 and r > 120 and g > 160: return "s"   # pale blue/sky
    if r > 140 and g > 90 and b < 90: return "Y"     # yellow/orange
    if r > 160 and g < 110 and b < 110: return "R"   # red
    if r < 70 and g < 70 and b < 70: return "K"      # dark
    if g > 120 and g > r + 20 and g > b - 40: return "G"
    if r > 120 and g > 100 and b < 100: return "o"   # tan/orange
    return "."


rows = []
for y in range(0, H - step + 1, step):
    row = ""
    for x in range(0, W - step + 1, step):
        c = a[y:y + step, x:x + step].reshape(-1, 3).mean(axis=0)
        ch = classify(c)
        row += ch
    rows.append(f"{y:3d} {row}")
print("cols: x*8 (0..504)")
print("\n".join(rows))
print("\nLegend: W=white B=strong-blue s=pale-blue Y=yellow/orange R=red K=dark G=green o=tan .=other")
