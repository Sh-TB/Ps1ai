#!/usr/bin/env python3
"""r32t2_psxmc_unpatched_control.py — Round 32 control experiment.

The r31t1 "patch works" conclusion lacked its control: UNPATCHED
minecraft was never probed post-rollback. If unpatched minecraft is
ALSO alive, the CCP(1) patch was irrelevant to minecraft's input and the
R30 class split is doukutsu/buzzybee-specific (the CCP trail is a red
herring). If unpatched minecraft is dead, the r31 causality stands.

Boot the UNPATCHED PSXMC_lic.cue, same r31t1 probe recipe (player_ptr ->
LOOK_DOWN pitch ring -> LEFT/RIGHT movement). Cap amend 3->4 disclosed
pre-run (r31 ledger): boot 3 re-designated from script-bug-retry to this
control; boot 4 = script-bug retry.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from ps1play.api import PS1Play  # noqa: E402
from psxmc_r10_lib import DEG, ONE_BLOCK, ring_diff, s32  # noqa: E402
from psxmc_r10_oracle import player_ptr, pitch_now, pos_of  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r31", "psxmc")
BOOTS = os.path.join(OUT, "boots_used.json")
UNPATCHED_CUE = ("/home/z/my-project/emu/games_homebrew/patched/"
                 "PSXMC_lic.cue")

R = {"task": "r32t2 minecraft UNPATCHED control probe",
     "cap_amendment": "cap 3->4 disclosed pre-run: boot 3 re-designated "
                      "to this control (r31's patch conclusion lacked it); "
                      "boot 4 = script-bug retry only",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r32t2.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": p.core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r32t2] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = p.core.frame_rgb()
    if arr is not None:
        path = os.path.join(OUT, "shots",
                            f"ctl_{tag}_f{p.core.frames_run:05d}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        from PIL import Image
        Image.fromarray(arr).save(path)
        R["shots"].append({"tag": tag, "frame": p.core.frames_run,
                           "png": os.path.relpath(path, OUT)})
    return arr


T0 = time.time()
led = json.load(open(BOOTS))
assert led["count"] == 2 and led["cap"] == 3
led["cap"] = 4
led["amendments"] = led.get("amendments", []) + [{
    "from": 3, "to": 4, "reason": R["cap_amendment"],
    "disclosed": "pre-run"}]
led["count"] = 3
led["log"].append({"boot": 3, "script": "r32t2_psxmc_unpatched_control.py",
                   "cue": UNPATCHED_CUE,
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

p = PS1Play(UNPATCHED_CUE, workspace="/home/z/my-project/emu/games_homebrew/"
            "ws_psxmc_r32ctl")
p.boot()
log("boot", core=p.core.core_name)

P = None
for _ in range(240):
    P = player_ptr(p.mem)
    if P:
        break
    p.wait(30)
assert P, "world never came up"
p.wait(120)
snap("world")
log("world_ready", P=hex(P))

a = pitch_now(p.mem, P)
snap("pre_look")
p.core.run(6, {"B"})
p.core.run(2, set())
b = pitch_now(p.mem, P)
snap("post_look")
pitch_moved = abs(ring_diff(a, b)) > 0.2 * DEG

pos0 = pos_of(p.mem, P)
p.core.run(60, {"LEFT"})
pos1 = pos_of(p.mem, P)
p.core.run(60, {"RIGHT"})
pos2 = pos_of(p.mem, P)
snap("post_move")
dx_left = [s32(x - y) / ONE_BLOCK for x, y in zip(pos1, pos0)]

alive = pitch_moved or any(abs(v) > 0.05 for v in dx_left)
R["verdict"] = {"unpatched_input_alive": bool(alive),
                "pitch_moved": bool(pitch_moved),
                "left_moved": [round(v, 3) for v in dx_left]}
log("verdict", **R["verdict"])
led["log"][-1]["outcome"] = (
    "UNPATCHED minecraft input ALIVE -> r31 patch was NOT the cause; "
    "class split is game-specific (doukutsu/buzzybee dead, minecraft "
    "alive pre&post patch)" if alive else
    "UNPATCHED minecraft input DEAD -> r31 patch causality CONFIRMED")
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r32t2] DONE", led["log"][-1]["outcome"], flush=True)
