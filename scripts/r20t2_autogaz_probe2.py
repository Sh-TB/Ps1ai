#!/usr/bin/env python3
"""r20-t2 autogaz boot #2 (final): input-sweep + pad scan + RAM dump.
ONE process, ONE boot. Screenshots + button-by-button visual/RAM deltas."""
import json
import os
import shutil
import sys
import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402
from PIL import Image  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r20t2_autogaz")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/autogaz_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"

ws = os.path.join(OUT, "ws2")
shutil.rmtree(ws, ignore_errors=True)
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))

core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
core.load_game(CONTENT)
log = {"shots": [], "buttons": []}


def shot(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}.png")
        Image.fromarray(arr).save(p)
        log["shots"].append({"tag": tag, "png": os.path.relpath(p, OUT),
                             "mean": float(arr.mean())})
    return arr


def ram_u32():
    return core.ram.view(np.uint32).copy()


def shot_diff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return float(np.abs(a.astype(int) - b.astype(int)).mean())


# settle 6000 frames (~100 s), screenshot every 1500
base = None
for i in range(6000):
    core.run_frame()
    if i % 1500 == 0:
        base = shot(f"b2_f{i:05d}")
        print(f"f{i} mean={base.mean():.1f}", flush=True)
print("padbuff 0xBB120:", bytes(core.ram[0xBB120:0xBB130]).hex(), flush=True)
hits = [hex(i) for i in range(0, 2 * 1024 * 1024 - 4)
        if core.ram[i] == 0x00 and core.ram[i + 1] == 0x41
        and core.ram[i + 2] == 0xFF and core.ram[i + 3] == 0xFF]
print("padpattern 00 41 ff ff hits:", hits[:20], flush=True)
log["padpattern_hits"] = hits[:50]

pre = shot("b2_pre_input")
pre_ram = ram_u32()

# sequential button sweep
for btn in ("START", "X", "O", "SQ", "TR", "SELECT", "START+SELECT"):
    core.set_buttons(btn)
    for _ in range(15):
        core.run_frame()
    core.set_buttons(set())
    for _ in range(75):
        core.run_frame()
    arr = shot(f"b2_btn_{btn}")
    post = ram_u32()
    chg = int(np.count_nonzero(post != pre_ram))
    log["buttons"].append({"btn": btn, "frame": core.frames_run,
                           "vis_diff": shot_diff(pre, arr), "ram_changed": chg})
    print(f"{btn}: vis_diff={shot_diff(pre, arr):.2f} ram_changed={chg}",
          flush=True)
    pre, pre_ram = arr, post

# 'gaz' hold: hold X 600f watching visual
core.set_buttons("X")
for _ in range(600):
    core.run_frame()
core.set_buttons(set())
hold = shot("b2_hold_x_600")
print("after 600f X hold mean:", hold.mean() if hold is not None else None,
      flush=True)
log["hold_x_vis_diff"] = shot_diff(pre, hold)

np.save(os.path.join(OUT, "ram_b2.npy"), core.ram.copy())
with open(os.path.join(OUT, "boot2_log.json"), "w") as f:
    json.dump(log, f, indent=1)
print("DONE frames=", core.frames_run, flush=True)
