#!/usr/bin/env python3
"""r20t3_zenmai_boot.py — headless boot + input-causality for zenmai (r20-t3).

ONE boot (one beetle/LibretroCore process):
  A) boot timeline: 3600 frames, probe every 100 -> PNG + diff log
  B) input causality: RAM census A -> (60f drift) B -> hold btn 15f -> wait
     75f -> census C; also frame-diff around the press. Buttons tried
     sequentially: CROSS, START, UP.
Outputs into /home/z/my-project/scratch/r20t3_zenmai/.
"""
import json
import os
import shutil
import sys

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.core.host import LibretroCore  # noqa: E402
from ps1play.core.inputmap import JP_X, JP_START, JP_UP  # noqa: E402

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled",
             b"beetle_psx_override_bios": b"openbios"}

CONTENT = "/home/z/my-project/emu/games_homebrew/patched/zenmai_lic.cue"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
OUT = "/home/z/my-project/scratch/r20t3_zenmai"

BOOT_FRAMES = 3600
PROBE = 100

os.makedirs(OUT, exist_ok=True)
ws_sys = os.path.join(OUT, "ws_system")
os.makedirs(ws_sys, exist_ok=True)
shutil.copyfile("/home/z/my-project/ps1ai/third_party/openbios/openbios.bin",
                os.path.join(ws_sys, "openbios.bin"))
shots = os.path.join(OUT, "shots")
shutil.rmtree(shots, ignore_errors=True)
os.makedirs(shots, exist_ok=True)

from PIL import Image  # noqa: E402

core = LibretroCore(CORE, os.path.join(OUT, "ws_system"),
                    os.path.join(OUT, "ws_saves"), var_overrides=dict(OVERRIDES))
core.load_game(CONTENT)

timeline = []
last = None
for i in range(BOOT_FRAMES):
    core.run_frame()
    if i % PROBE == 0:
        arr = core.frame_rgb()
        if arr is None:
            continue
        d = -2.0 if last is None or arr.shape != last.shape else \
            float(np.abs(arr.astype(int) - last.astype(int)).mean())
        mean = float(arr.mean())
        timeline.append({"f": i, "diff": d, "mean": round(mean, 2)})
        Image.fromarray(arr).save(os.path.join(shots, f"f{i:05d}.png"))
        print(f"f{i:5d} diff={d:7.2f} mean={mean:6.1f}"
              f"{' BLACK' if mean < 6.0 else ''}", flush=True)
        last = arr

# ---- input causality ---------------------------------------------------
def census(tag):
    r = core.ram.tobytes()
    np.save(os.path.join(OUT, f"ram_{tag}.npy"), core.ram.copy())
    return r


def ramdiff(a, b):
    A, B = np.frombuffer(a, np.uint8), np.frombuffer(b, np.uint8)
    d = np.flatnonzero(A != B)
    return {"bytes_changed": int(len(d)),
            "first_offs": [int(x) for x in d[:8]]}


def framediff(n=10):
    """mean abs diff between consecutive captured frames while pressing."""
    vals = []
    prev = core.frame_rgb()
    for _ in range(n):
        core.run_frame()
        arr = core.frame_rgb()
        if arr is not None and prev is not None and arr.shape == prev.shape:
            vals.append(float(np.abs(arr.astype(int) - prev.astype(int)).mean()))
        prev = arr
    return round(sum(vals) / max(len(vals), 1), 2), prev


results = []
BTN = {"cross": (JP_X, "X"), "start": (JP_START, "START"), "up": (JP_UP, "UP")}
for name, (btn_id, label) in BTN.items():
    A = census(f"{name}_a")
    core.run(60)
    B = census(f"{name}_b")
    drift = ramdiff(A, B)
    core.set_buttons({btn_id})
    fd, _ = framediff(15)
    core.set_buttons(set())
    core.run(75)
    C = census(f"{name}_c")
    resp = ramdiff(B, C)
    arr = core.frame_rgb()
    png = os.path.join(OUT, f"after_{name}.png")
    if arr is not None:
        Image.fromarray(arr).save(png)
    results.append({"btn": name, "drift_60f": drift,
                    "resp_75f": resp, "frame_diff_press": fd,
                    "ratio": (resp["bytes_changed"] /
                              max(drift["bytes_changed"], 1))})
    print(f"[{name}] drift={drift['bytes_changed']}B "
          f"resp={resp['bytes_changed']}B ratio="
          f"{resp['bytes_changed']/max(drift['bytes_changed'],1):.2f} "
          f"frame_diff={fd}", flush=True)

with open(os.path.join(OUT, "boot_input.json"), "w") as f:
    json.dump({"timeline": timeline, "input": results}, f, indent=1)
core.shutdown()
print("done")
