#!/usr/bin/env python3
"""game_boot_timeline.py — map the real-game boot timeline.

Boots SLUS-01212 with OpenBIOS, screenshots every N frames, and reports
per-probe mean frame change so we can pick the correct branch point for
the causality A/B (past NOW LOADING, at the title screen).
"""
import argparse
import os
import shutil
import sys

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.core.host import LibretroCore  # noqa: E402

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled"}

ap = argparse.ArgumentParser()
ap.add_argument("--content", required=True)
ap.add_argument("--bios", default="/home/z/my-project/ps1-test/emu/system/openbios.bin")
ap.add_argument("--core", default="/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")
ap.add_argument("--out", default="/tmp/game_timeline")
ap.add_argument("--frames", type=int, default=6000)
ap.add_argument("--probe-every", type=int, default=100)
a = ap.parse_args()

os.makedirs(a.out, exist_ok=True)
shots = os.path.join(a.out, "shots")
os.makedirs(shots, exist_ok=True)
ws = os.path.join(a.out, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
shutil.copyfile(a.bios, os.path.join(ws, "system", "openbios.bin"))
savedir = os.path.join(ws, "saves")
os.makedirs(savedir, exist_ok=True)

from PIL import Image

core = LibretroCore(a.core, os.path.join(ws, "system"), savedir,
                    var_overrides=dict(OVERRIDES))
core.load_game(a.content)

last = None
for i in range(a.frames):
    core.run_frame()
    if i % a.probe_every == 0:
        arr = core.frame_rgb()
        if arr is None:
            continue
        d = -2.0
        if last is not None:
            if arr.shape == last.shape:
                d = float(np.abs(arr.astype(int) - last.astype(int)).mean())
            else:
                print(f"  (resolution changed {last.shape} -> {arr.shape})",
                      flush=True)
        mean = float(arr.mean())
        black = mean < 6.0
        print(f"f{i:5d} diff={d:7.2f} mean={mean:6.1f}{' BLACK' if black else ''}",
              flush=True)
        Image.fromarray(arr).save(os.path.join(shots, f"f{i:05d}.png"))
        last = arr
