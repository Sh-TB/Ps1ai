#!/usr/bin/env python3
"""r19t1_sensors.py — Round 19 Poy Poy: offline sensor calibration + shared lib.

Calibrated on r19 run1 fresh frames (full-health round start). Exports
Sensors class used by the agent:
  - HARRY (1P blue suit) tight gate + tracking-by-motion
  - opponents: yellow(2P), red(3P), green(4P) suit gates
  - rocks: white blocks (ground/overhead/flight)
  - HUD: hearts per slot, DANGER!/RETIRE! text detection
Run standalone to print a calibration table.
"""
import json
import os

import numpy as np
from PIL import Image

RUN1 = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy/run1"
OUT = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy"

# ---------------- masks ----------------
# floor teal ~ (112-176,144-208,144-192); HARRY suit ~ (56-108,72-140,128-190)
M_HARRY = dict(r=(56, 110), g=(72, 142), b=(128, 195),
               br=40, gr=2, bg=10)          # b>r+40, g>r+2, b>=g+10
M_YELLOW = dict(r=(170, 256), g=(100, 185), b=(0, 120))
M_RED = dict(r=(140, 256), g=(0, 105), b=(0, 105))
M_GREEN = dict(r=(0, 130), g=(120, 220), b=(0, 140))
M_WHITE = dict(r=(200, 256), g=(200, 256), b=(200, 256))


def gate(a, m, band=(0.22, 0.82)):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    H, W = r.shape
    out = np.ones((H, W), bool)
    for ch, lo, hi in ((r, m["r"][0], m["r"][1]), (g, m["g"][0], m["g"][1]),
                       (b, m["b"][0], m["b"][1])):
        out &= (ch >= lo) & (ch <= hi)
    if "br" in m:
        out &= (b > r + m["br"]) & (g > r + m["gr"]) & (b >= g + m["bg"])
    if m is M_WHITE:
        out &= (np.abs(r - b) < 30)
    if band:
        y0, y1 = int(H * band[0]), int(H * band[1])
        keep = np.zeros((H, W), bool)
        keep[y0:y1] = True
        out &= keep
    return out


def blobs(mask, minpx, maxpx):
    m = mask.astype(np.int8)
    H, W = m.shape
    seen = np.zeros_like(m)
    out = []
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        st = [(y0, x0)]
        seen[y0, x0] = 1
        pts = []
        while st:
            y, x = st.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = 1
                    st.append((ny, nx))
        n = len(pts)
        if minpx <= n <= maxpx:
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            out.append({"n": n, "cx": float(np.mean(xs)),
                        "cy": float(np.mean(ys)),
                        "x0": int(min(xs)), "x1": int(max(xs)),
                        "y0": int(min(ys)), "y1": int(max(ys))})
    return out


class Sensors:
    """Per-frame sensor suite. Tracks HARRY by motion between calls."""

    def __init__(self):
        self.harry = None          # (cx, cy)
        self.tick = 0

    def frame(self, img):
        a = np.asarray(img, dtype=np.int16)
        H, W = a.shape[:2]
        s = {"W": W, "H": H}
        hb = blobs(gate(a, M_HARRY), 30, 1200)
        yb = blobs(gate(a, M_YELLOW), 30, 1200)
        rb = blobs(gate(a, M_RED), 30, 1200)
        gb = blobs(gate(a, M_GREEN), 30, 1200)
        wb = blobs(gate(a, M_WHITE), 40, 1600)
        s["harry_cands"] = hb
        s["yellow"] = yb
        s["red"] = rb
        s["green"] = gb
        s["white"] = wb
        # HARRY tracking: nearest to previous within 60px else biggest
        pick = None
        if hb:
            if self.harry is not None:
                near = [b for b in hb
                        if (b["cx"] - self.harry[0]) ** 2 +
                        (b["cy"] - self.harry[1]) ** 2 < 70 ** 2]
                pick = (min(near, key=lambda b: (b["cx"] - self.harry[0]) ** 2 +
                            (b["cy"] - self.harry[1]) ** 2) if near else
                        max(hb, key=lambda b: b["n"]))
            else:
                pick = max(hb, key=lambda b: b["n"])
        if pick:
            self.harry = (pick["cx"], pick["cy"])
            s["harry"] = (pick["cx"], pick["cy"], pick["n"])
        s["hud"] = hud(a)
        return s


def hud(a):
    """Bottom HUD: heart red px per slot, DANGER (red text) and RETIRE
    (magenta text) presence per slot."""
    H, W = a.shape[:2]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    strip = a[int(H * 0.80):, :, :]
    rs, gs, bs = strip[..., 0], strip[..., 1], strip[..., 2]
    qw = W // 4
    out = []
    for q in range(4):
        cell_s = slice(q * qw, (q + 1) * qw)
        rsq, gsq, bsq = rs[:, cell_s], gs[:, cell_s], bs[:, cell_s]
        red = (rsq > 150) & (gsq < 95) & (bsq < 95)
        magenta = (rsq > 160) & (bsq > 120) & (gsq < 110) & (bsq < rsq)
        out.append({"hearts": int(red.sum()),
                    "danger": int(red.sum()) > 400,
                    "retire": int(magenta.sum()) > 60,
                    "mag_px": int(magenta.sum())})
    return out


def main():
    rep = {}
    files = sorted(fn for fn in os.listdir(RUN1)
                   if fn.startswith(("e_f", "g_start", "g_carry", "g_charged",
                                     "g_throw", "g_end")) and fn.endswith(".png"))
    for fn in files:
        img = Image.open(os.path.join(RUN1, fn))
        s = Sensors().frame(img) if "start" in fn or "carry" in fn or "charged" in fn or "throw" in fn or "end" in fn \
            else None
        # one-shot scan for entry frames
        a = np.asarray(img, dtype=np.int16)
        row = {
            "harry": blobs(gate(a, M_HARRY), 30, 1200),
            "yellow": blobs(gate(a, M_YELLOW), 30, 1200),
            "red": blobs(gate(a, M_RED), 30, 1200),
            "green": blobs(gate(a, M_GREEN), 30, 1200),
            "white": blobs(gate(a, M_WHITE), 40, 1600),
            "hud": hud(a),
        }
        keep = {}
        for k in ("harry", "yellow", "red", "green", "white"):
            keep[k] = [(b["n"], round(b["cx"]), round(b["cy"]))
                       for b in sorted(row[k], key=lambda x: -x["n"])[:4]]
        keep["hud"] = [(h["hearts"], h["danger"], h["retire"], h["mag_px"])
                       for h in row["hud"]]
        rep[fn] = keep
    with open(os.path.join(OUT, "sensor_calib.json"), "w") as f:
        json.dump(rep, f, indent=1)
    for fn in files:
        row = rep[fn]
        print(fn, "HARRY:", row["harry"][:2], "| Y:", row["yellow"][:1],
              "R:", row["red"][:1], "G:", row["green"][:1],
              "W:", row["white"][:2], "| hud:", row["hud"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
