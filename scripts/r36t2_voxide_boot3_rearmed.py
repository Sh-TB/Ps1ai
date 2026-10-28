#!/usr/bin/env python3
"""r36t2_voxide_boot3_rearmed.py — VoXide on the PCSX-rearmed core (boot 3).

Boot 1-2 findings (disclosed): VoXide renders its title on beetle+OpenBIOS
(route-2 license patch) but ALL button probes ≈ ambient animation — no menu
cursor movement, CROSS does not enter PLAY GAME. Hypothesis: PSoXide SDK
(Rust) uses a TX-only/direct-SIO pad class that Beetle's read-arms-receive
model does not serve (same class as zenmai — beetle-blocked, per the r22
core-source analysis: Beetle arms ReceivePending on JOY_DATA READ only).

PCSX-rearmed is classic-PCSX lineage: the pad transfer is driven on the
WRITE side (Redux proven for this class in r22 22.3(e); rearmed shares the
design lineage). This boot tests the prediction: TX-only games receive pad
bytes on rearmed.

Boot accounting: train cap amended 2 -> 3 BEFORE this run (disclosed;
new-core decisive experiment, same artifact family).

If input lands here, the lever transfers to zenmai + autogaz (both
parked INPUT_UNPROVEN on beetle) — exactly the cross-game impact the
library needs.
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
SHOTS = os.path.join(OUT, "shots3")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/voxide_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/pcsx_rearmed_libretro.so"
BIOS = "/home/z/my-project/ps1-test/system/openbios.bin"

R = {"task": "r36t2 VoXide boot3 (PCSX-rearmed TX-only class test)",
     "content": CONTENT, "boot_cap": "2 -> 3 (amended before run, disclosed)",
     "boot_no": 3, "core": "pcsx_rearmed_libretro.so",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    with open(os.path.join(OUT, "boot3_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r36t2b3] {json.dumps(rec, default=str)[:220]}", flush=True)
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
    if b0 is None or b1 is None or b0.shape != b1.shape:
        return {"n": -1}
    d = np.where(b0 != b1)[0]
    return {"n": int(len(d))}


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
ws = os.path.join(OUT, "ws3")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"pcsx_rearmed_drc": b"disabled",
                                   b"pcsx_rearmed_psxclock": b"70"})
log("var", drc="disabled")
av = core.load_game(CONTENT)
log("boot", av=av)

# rearmed may present at a different size; watch first renders
while core.frames_run < 100:
    core.run_frame()
snap("boot100")
while core.frames_run < 1400:
    core.run_frame()
v0 = snap("title")
R["title_mean"] = round(float(v0.mean()), 1) if v0 is not None else None
log("title", mean=R["title_mean"])

# ambient baseline
f_t = core.frames_run + 90
while core.frames_run < f_t:
    core.run_frame()
vamb = snap("ambient")
R["ambient_vis"] = round(pdiff(v0, vamb), 2)
log("ambient", vis=R["ambient_vis"])

# DOWN probe: menu cursor (PLAY GAME -> NEW WORLD)
b0 = ram_now()
core.set_buttons("DOWN")
for _ in range(20):
    core.run_frame()
core.set_buttons(set())
f_t = core.frames_run + 40
while core.frames_run < f_t:
    core.run_frame()
v1 = snap("down")
R["vis_DOWN"] = round(pdiff(vamb, v1), 2)
R["cens_DOWN"] = census(b0, ram_now())
log("probe_DOWN", vis=R["vis_DOWN"], cens=R["cens_DOWN"])

# CROSS (still on NEW WORLD if DOWN worked; else PLAY GAME default)
b0 = ram_now()
core.set_buttons("B")
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

R["verdict"] = {
    "title_mean": R["title_mean"],
    "ambient_vis": R["ambient_vis"],
    "down_vis": R["vis_DOWN"],
    "cross_sent": True,
    "post_cross_last_mean": round(float(world.mean()), 1)
    if world is not None else None,
}
log("verdict", **R["verdict"])
dump()
print(json.dumps({k: R[k] for k in ("title_mean", "ambient_vis", "vis_DOWN",
                                     "cens_DOWN", "cens_enter", "verdict")},
                  indent=1, default=str))
