#!/usr/bin/env python3
"""r20t3_zenmai_input.py — focused input-causality on the zenmai title screen.

One boot: settle 3600f on title -> PNG -> census A -> DOWN 15f -> 90f ->
census B + PNG (cursor should move 日本語->ENGLISH) -> UP 15f -> 90f -> PNG
(cursor back) -> START 15f -> 600f -> census C + PNG (game should start).
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)
from ps1play.core.host import LibretroCore  # noqa: E402
from ps1play.core.inputmap import JP_UP, JP_DOWN, JP_START  # noqa: E402

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled",
             b"beetle_psx_override_bios": b"openbios"}
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/zenmai_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
OUT = "/home/z/my-project/scratch/r20t3_zenmai"

os.makedirs(OUT, exist_ok=True)
ws_sys = os.path.join(OUT, "ws_system2")
os.makedirs(ws_sys, exist_ok=True)
shutil.copyfile("/home/z/my-project/ps1ai/third_party/openbios/openbios.bin",
                os.path.join(ws_sys, "openbios.bin"))

core = LibretroCore(CORE, ws_sys, os.path.join(OUT, "ws_saves2"),
                    var_overrides=dict(OVERRIDES))
core.load_game(CONTENT)
core.run(3600)
Image.fromarray(core.frame_rgb()).save(os.path.join(OUT, "title.png"))

R = {"boot_frames": 3600}


def snap(tag):
    r = core.ram.copy()
    np.save(os.path.join(OUT, f"inp_{tag}.npy"), r)
    arr = core.frame_rgb()
    if arr is not None:
        Image.fromarray(arr).save(os.path.join(OUT, f"inp_{tag}.png"))
    return r


def gray(a):
    return np.asarray(Image.fromarray(a).convert("L"), np.float32)


def press(btn, hold=15, wait=90):
    pre = core.frame_rgb()
    core.run(hold, {btn})
    core.run(wait, set())
    post = core.frame_rgb()
    d = float(np.abs(gray(post) - gray(pre)).mean()) if pre is not None else None
    return d, post


A = snap("a")
d_down, _ = press(JP_DOWN)
B = snap("b")
d_up, _ = press(JP_UP)
d_start = None
core.run(15, {JP_START})
core.run(600, set())
C = snap("c")

dAB = int((np.frombuffer(A.tobytes(), np.uint8) !=
           np.frombuffer(B.tobytes(), np.uint8)).sum())
dBC = int((np.frombuffer(B.tobytes(), np.uint8) !=
           np.frombuffer(C.tobytes(), np.uint8)).sum())
R.update({"down_frame_diff": d_down, "up_frame_diff": d_up,
          "ram_AB_down": dAB, "ram_BC_start": dBC})
print(json.dumps(R), flush=True)
json.dump(R, open(os.path.join(OUT, "input_focus.json"), "w"), indent=1)
core.shutdown()
print("done")
