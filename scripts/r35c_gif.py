#!/usr/bin/env python3
"""r35c_gif.py — build ONE GIF of the winning run and mirror it.

Frames: sampled in-run captures (gif_frames/*.png named by frames_run)
interleaved with key shot PNGs (game_start, full_clear, win screen).
No emulator needed.
"""
import json
import os
import re
import sys

from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35c_lib as L  # noqa: E402

OUTDIR = L.OUT
MIRROR = os.path.join(REPO, "docs", "evidence_gifs", "r35_mspsx_win.gif")


def shots_by_tag(tag):
    fs = sorted(f for f in os.listdir(L.SHOTS) if f.startswith(tag))
    return os.path.join(L.SHOTS, fs[-1]) if fs else None


items = []  # (sort_key, path, duration_ms)
for f in sorted(os.listdir(L.GIFD)):
    m = re.match(r"(\d+)\.png$", f)
    if m:
        items.append((int(m.group(1)), os.path.join(L.GIFD, f), 60))
for tag, dur in (("title", 500), ("game_start", 500),
                 ("full_clear", 900), ("full_clear_plus180f", 2500)):
    p = shots_by_tag(tag)
    if p:
        # derive frames_run from filename for correct interleave position
        m = re.search(r"_f(\d+)\.png$", p)
        k = int(m.group(1)) if m else 10**9
        items.append((k, p, dur))
items.sort(key=lambda it: it[0])
# drop duplicate keys (decoded_board == game_start frame)
seen = set()
uniq = []
for it in items:
    if it[0] in seen:
        continue
    seen.add(it[0])
    uniq.append(it)
items = uniq

frames = [Image.open(p).convert("RGB").quantize(colors=64, method=2)
          for _, p, _ in items]
durs = [d for _, _, d in items]
gif_path = os.path.join(OUTDIR, "r35c_mspsx_win.gif")
frames[0].save(gif_path, save_all=True, append_images=frames[1:],
               duration=durs, loop=0, optimize=True)
sz = os.path.getsize(gif_path)
print(f"[r35c] GIF {gif_path} frames={len(frames)} bytes={sz}")

os.makedirs(os.path.dirname(MIRROR), exist_ok=True)
import shutil  # noqa: E402
shutil.copyfile(gif_path, MIRROR)
print(f"[r35c] MIRRORED -> {MIRROR} bytes={os.path.getsize(MIRROR)}")

json.dump({"gif": gif_path, "mirror": MIRROR, "frames": len(frames),
           "bytes": sz,
           "sequence": [{"f": k, "png": os.path.relpath(p, OUTDIR),
                         "ms": d} for k, p, d in items]},
          open(os.path.join(OUTDIR, "gif_manifest.json"), "w"), indent=1)
