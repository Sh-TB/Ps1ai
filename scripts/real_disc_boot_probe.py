#!/usr/bin/env python3
"""real_disc_boot_probe.py — first real-content boot observation, SLUS-01212.

Boots the verified Metal Slug X (USA) disc through the OFFICIAL OpenBIOS
override path (beetle_psx_override_bios=openbios) and records, strictly
observationally, what the screen does over time:

  * per-interval RGB frame snapshots saved as PNG
  * per-interval screen-change metric (mean abs diff vs previous snapshot)
  * the exact core log lines that mark the boot path

No cheats, no RAM writes, no state editing. Evidence level: OBSERVED.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WORKSPACE = "/home/z/my-project/ps1-test/emu"
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_disc_boot"
TOTAL_FRAMES = 1800
SNAP_EVERY = 60

os.makedirs(OUT, exist_ok=True)


def diff_metric(a, b):
    """Mean abs diff; handles resolution changes by resizing the
    previous frame (a resolution switch is itself a real event and is
    reported via the resized_prev flag)."""
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b_img = Image.fromarray(b).resize(
            (a.shape[1], a.shape[0]))
        b = np.asarray(b_img)
    return float(np.mean(np.abs(
        a.astype(np.int16) - b.astype(np.int16))))


def main():
    p = PS1Play(GAME, core=CORE, workspace=WORKSPACE,
                var_overrides={b"beetle_psx_override_bios": b"openbios"},
                verbose=False)
    info = p.boot()
    print("boot:", json.dumps(info, default=str))

    logs = getattr(p.core, "log_history", [])
    boot_path_lines = [ln for ln in logs if
                       "Override" in ln or "Firmware" in ln]
    print("boot-path log lines:", boot_path_lines)

    prev = None
    timeline = []
    t0 = time.time()
    for f in range(1, TOTAL_FRAMES + 1):
        p.core.run_frame()
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                arr = np.asarray(rgb)
                png = os.path.join(OUT, f"f{f:05d}.png")
                Image.fromarray(arr).save(png)
                m = diff_metric(arr, prev)
                timeline.append({
                    "frame": f,
                    "png": os.path.basename(png),
                    "mean_abs_diff_vs_prev": m,
                    "shape": list(arr.shape),
                    "mean_rgb": [round(float(arr[..., i].mean()), 1)
                                 for i in range(3)],
                })
                prev = arr
            else:
                timeline.append({"frame": f, "png": None,
                                 "mean_abs_diff_vs_prev": None})
    elapsed = time.time() - t0

    # summarize: which snapshots changed the screen the most
    events = [t for t in timeline
              if t["mean_abs_diff_vs_prev"] is not None
              and t["mean_abs_diff_vs_prev"] > 3.0]
    report = {
        "game": os.path.basename(GAME),
        "core": f"{p.core.core_name} {p.core.core_ver}",
        "boot_path": "official OpenBIOS override",
        "boot_log_lines": boot_path_lines,
        "frames": TOTAL_FRAMES,
        "snap_every": SNAP_EVERY,
        "elapsed_s": round(elapsed, 1),
        "big_changes": events[:40],
        "timeline": timeline,
    }
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps({k: report[k] for k in
                      ("core", "boot_path", "elapsed_s",
                       "boot_log_lines")}, indent=1))
    print("big_changes (frame, diff):",
          [(e["frame"], round(e["mean_abs_diff_vs_prev"], 1))
           for e in events][:30])
    print("report:", os.path.join(OUT, "report.json"))


if __name__ == "__main__":
    main()
