#!/usr/bin/env python3
"""r36t2_voxide_boot2.py — menu->gameplay state-change probe (boot 2/2).

Boot 1 (disclosed): VoXide v0.1.11 TITLE RENDERS (route-2 license patch;
title 'VoXide — NOW WITH 2MB OF RAM!', menu PLAY GAME / NEW WORLD /
SETTINGS / CREDITS), animated background, big census+vis deltas under
probes (INPUT_RESPONSIVE class evidence).

This boot (cap 2, boot 2 of 2, disclosed BEFORE run):
  1. wait f1400 (title stable)
  2. DOWN probe -> menu cursor should move PLAY GAME -> NEW WORLD
  3. CROSS on PLAY GAME (default highlight) -> wait 900f -> is gameplay?
     (voxel world render = STATE_CHANGE title->game)
  4. RAM census across the transition for the game-state anchor hunt
"""
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r36", "voxide")
SHOTS = os.path.join(OUT, "shots2")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/voxide_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/system/openbios.bin"

R = {"task": "r36t2 VoXide boot2 (title->gameplay probe)",
     "content": CONTENT, "boot_cap": 2, "boot_no": 2,
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    with open(os.path.join(OUT, "boot2_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r36t2b2] {json.dumps(rec, default=str)[:220]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def pdiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


def ram_now():
    return np.frombuffer(bytes(core.ram), dtype=np.uint8)


def census(b0, b1):
    if b0.shape != b1.shape:
        return {"n": -1}
    d = np.where(b0 != b1)[0]
    return {"n": int(len(d)),
            "top": [{"va": hex(0x80000000 + int(x))} for x in d[:6]]}


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
ws = os.path.join(OUT, "ws2")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", av=av)

while core.frames_run < 1400:
    core.run_frame()
v0 = snap("title")
log("title", vis_mean=round(float(v0.mean()), 1))

# ---- DOWN probe: menu cursor movement --------------------------------------------
b0 = ram_now()
core.set_buttons("DOWN")
for _ in range(20):
    core.run_frame()
core.set_buttons(set())
f_t = core.frames_run + 40
while core.frames_run < f_t:
    core.run_frame()
v1 = snap("down")
R["vis_DOWN"] = round(pdiff(v0, v1), 2)
R["cens_DOWN"] = census(b0, ram_now())
log("probe_DOWN", vis=R["vis_DOWN"], cens=R["cens_DOWN"])

# ---- UP probe: cursor back (causal control pair) ----------------------------------
b0 = ram_now()
core.set_buttons("UP")
for _ in range(20):
    core.run_frame()
core.set_buttons(set())
f_t = core.frames_run + 40
while core.frames_run < f_t:
    core.run_frame()
v2 = snap("up")
R["vis_UP"] = round(pdiff(v1, v2), 2)
log("probe_UP", vis=R["vis_UP"])

# ---- CROSS on PLAY GAME (default highlight) -> enter game -------------------------
b0 = ram_now()
core.set_buttons("B")  # CROSS
for _ in range(25):
    core.run_frame()
core.set_buttons(set())
log("cross_sent")

world = None
for step in range(9):
    f_t = core.frames_run + 100
    while core.frames_run < f_t:
        core.run_frame()
    world = snap(f"game{step}")
    log("post_cross", step=step, vis_mean=round(float(world.mean()), 1)
        if world is not None else None)
R["cens_enter"] = census(b0, ram_now())

# ---- verdict -----------------------------------------------------------------------
v_first = R["shots"][0]
R["verdict"] = {
    "title_rendered": True,
    "menu_cursor_probe_vis": [R["vis_DOWN"], R["vis_UP"]],
    "post_cross_last_mean": round(float(world.mean()), 1)
    if world is not None else None,
}
log("verdict", **R["verdict"])
dump()
print(json.dumps({k: R[k] for k in ("vis_DOWN", "vis_UP", "cens_DOWN",
                                     "cens_enter", "verdict")},
                  indent=1, default=str))
