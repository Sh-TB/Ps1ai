#!/usr/bin/env python3
"""r32t1_doukutsu_ccp1_probe.py — Round 32 boot 1: does the CCP(0)->(1)
patch restore doukutsupsx input? (The r30t8 probe of the UNPATCHED image
failed exactly this test.)

Probe = the r24-proven recipe: boot -> cutscene CROSS-skip -> menu gate
(mean ~34.8) -> DOWN hold -> cursor vis-diff. Alive = vis > 1.0 with
idle <= 0.3.

Cap 3 (fresh r32 ledger): boot 1 = this probe; boot 2 = deep program on
pass (movement anchors -> weapon/level systems per the r25 next-steps);
boot 3 = script-bug retry only. Disclosed pre-run.
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

OUT = os.path.join(REPO, "scratch", "r32", "doukutsu")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/doukutsu_ccp1.iso"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

R = {"task": "r32t1 doukutsu CCP(1) input probe",
     "patch": "CCP(0)->(1) at 2 zero-arg sites (r32t0); image "
              "doukutsu_ccp1.iso sha ae96fcc8; original bf15559e intact",
     "cap_policy": "cap 3 pre-run: boot 2 = deep program on probe pass; "
                   "boot 3 = script-bug retry only",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r32t1] {json.dumps(rec, default=str)[:230]}", flush=True)
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
    if a is None or b is None:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
led0 = json.load(open(BOOTS))
assert led0["count"] == 2, f"ledger: {led0['count']}"
led0["count"] = 3
led0["log"].append({"boot": 3, "script": "r32t1_doukutsu_ccp1_probe.py "
                    "(9-site + dispatcher patch)",
                    "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led0, open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

for _ in range(1900):
    core.run(1, set())
snap("cutscene_phase")
core.run(3, {"B"})
core.run(900, set())
snap("menu_check")
menu = snap("menu")
log("menu_wait", mean=round(float(menu.mean()), 2))

ctrl = []
for _ in range(40):
    fr = core.frame_rgb()
    core.run(1, set())
    ctrl.append(fr)
vis_ctrl = max(pdiff(ctrl[i], ctrl[i + 1]) for i in range(len(ctrl) - 1))

pre = snap("pre_down")
core.run(5, {"DOWN"})
core.run(60, set())
post = snap("post_down")
vis = pdiff(pre, post)
log("down_probe", vis=vis, idle_vis=vis_ctrl)
alive = vis > 1.0 and vis_ctrl <= 0.3
R["verdict"] = {"input_alive": bool(alive), "down_vis": vis,
                "idle_vis": vis_ctrl}
log("verdict", **R["verdict"])
led = json.load(open(BOOTS))
led["log"][-1]["outcome"] = ("CCP(1) PATCH WORKS on doukutsu - input ALIVE"
                            if alive else
                            "9-site + dispatcher patch insufficient "
                            "(down_vis %.2f)" % vis)
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r32t1] DONE", led["log"][0]["outcome"], flush=True)
