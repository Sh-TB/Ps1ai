#!/usr/bin/env python3
"""r30t8_doukutsu_input_probe.py — Round 30 matrix-completion probe.

The last untested cell: doukutsupsx uses BYTE-EQUIVALENT input.c with
BuzzyBee (InitPAD/StartPAD/ChangeClearPAD(0), diff-verified today against
upstream master). It received input fine THIS MORNING (r24/r25, pre-5th-
rollback). If doukutsu input is ALSO dead now, the whole ChangeClearPAD
(0) class broke at the rollback (environment-level, core-independent -
both core binaries + ReARMed already ruled out for BuzzyBee); if it is
alive, the failure is BuzzyBee-specific (its prebuilt EXE differs from
its repo source - the compiled ChangeClearPAD sites are a mode-switch,
not the simple (0) call).

One boot, r24-proven entry: settle -> cutscene CROSS-skip -> menu gate
(PNG) -> DOWN hold -> cursor vis-diff decides. Cap 1, disclosed class
probe (not a rung attempt).
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

OUT = os.path.join(REPO, "scratch", "r30", "doukutsu_probe")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/doukutsu_r7_us.iso"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

R = {"task": "r30t8 doukutsu input class probe (ChangeClearPAD(0) family)",
     "cap_policy": "cap 1, disclosed: class probe, not a rung attempt",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r30t8] {json.dumps(rec, default=str)[:230]}", flush=True)
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
assert not os.path.exists(BOOTS), "probe ledger exists - abort"
json.dump({"count": 1, "cap": 1, "cap_policy": R["cap_policy"],
           "log": [{"boot": 1, "script": "r30t8_doukutsu_input_probe.py",
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

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

# r24 timeline: bright cutscene ~f1860, CROSS skips -> menu ~f2760
for _ in range(1900):
    core.run(1, set())
snap("cutscene_phase")
core.run(3, {"B"})
core.run(900, set())
snap("menu_check")
mean = core.frame_rgb().mean()
log("menu_wait", mean=round(float(mean), 2), f=core.frames_run)
# idle control: menu must be near-static
idle_frames = [core.frame_rgb() for _ in range(0)]
ctrl = []
for _ in range(40):
    fr = core.frame_rgb()
    core.run(1, set())
    ctrl.append(fr)
vis_ctrl = max(pdiff(ctrl[i], ctrl[i + 1]) for i in range(len(ctrl) - 1)) \
    if len(ctrl) > 1 else -1
menu = snap("menu")
log("menu_gate", idle_vis=vis_ctrl, mean=round(float(menu.mean()), 2))

# DOWN hold -> cursor vis-diff (New -> Load)
pre = snap("pre_down")
core.run(5, {"DOWN"})
core.run(60, set())
post = snap("post_down")
vis = pdiff(pre, post)
log("down_probe", vis=vis)
R["verdict"] = {
    "doukutsu_input_alive": vis > 1.0 and vis_ctrl <= 0.3,
    "down_vis": vis, "idle_vis": vis_ctrl,
}
log("verdict", **R["verdict"])
led = json.load(open(BOOTS))
led["log"][0]["outcome"] = (
    "doukutsu input ALIVE (class healthy)" if R["verdict"][
        "doukutsu_input_alive"] else
    "doukutsu input DEAD now - whole ChangeClearPAD(0) class broke at the "
    "rollback (environment-level)")
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t8] DONE", led["log"][0]["outcome"], flush=True)
