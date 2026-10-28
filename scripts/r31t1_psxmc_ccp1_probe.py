#!/usr/bin/env python3
"""r31t1_psxmc_ccp1_probe.py — Round 31 boot 1: does the disclosed
ChangeClearPAD(0)->(1) 1-instruction patch (r31t0) restore input to
PSX-Minecraft (a ChangeClearPAD(0)-class game per its source)?

R30 matrix: the whole CCP(0) class (doukutsu/buzzybee) lost button
delivery post-rollback; Tetrade (CCP(1)) still works. Minecraft's
inputInit @0x800104F0 patched move $a0,$zero -> addiu $a0,$zero,1
(ELF-symbol-located, byte-verified, image LOCAL: PSXMC_lic_ccp1.bin
sha 7b83b306..., unpatched PSXMC_lic.bin sha 5262f511 remains reference).

Probe (r4/r19-proven recipe, RAM anchors unchanged by the 4-byte patch):
  world ready (player_ptr) -> ensure_world_control (LOOK_DOWN pitch
  ring) -> LEFT 60f position delta -> RIGHT reversal -> PNG trail.
Cap 3: boot 2 = deep program if this passes; boot 3 = script-bug retry
only (disclosed pre-run).
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
from psxmc_r10_lib import (DEG, HEAP_HI, HEAP_LO, ONE_BLOCK, ring_diff,  # noqa
                           s32)
from psxmc_r10_oracle import (CUE, player_ptr, pitch_now, pos_of)  # noqa

OUT = os.path.join(REPO, "scratch", "r31", "psxmc")
BOOTS = os.path.join(OUT, "boots_used.json")
PATCHED_CUE = ("/home/z/my-project/emu/games_homebrew/patched/"
               "PSXMC_lic_ccp1.cue")

R = {"task": "r31t1 minecraft CCP(1) input probe",
     "patch": "ChangeClearPAD(0)->(1) @VA 0x800104F0 (r31t0, disclosed)",
     "cap_policy": "cap 3 pre-run: boot 2 = deep program on probe pass; "
                   "boot 3 = script-bug retry only",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": p.core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r31t1] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = p.core.frame_rgb()
    if arr is not None:
        import os.path
        path = os.path.join(OUT, "shots", f"{tag}_f{p.core.frames_run:05d}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        from PIL import Image
        Image.fromarray(arr).save(path)
        R["shots"].append({"tag": tag, "frame": p.core.frames_run,
                           "png": os.path.relpath(path, OUT)})
    return arr


def madiff(a, b):
    if a is None or b is None:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


T0 = time.time()
os.makedirs(os.path.join(OUT, "shots"), exist_ok=True)
assert not os.path.exists(BOOTS), "ledger exists - abort"
json.dump({"count": 1, "cap": 3, "cap_policy": R["cap_policy"],
           "log": [{"boot": 1, "script": "r31t1_psxmc_ccp1_probe.py",
                    "cue": PATCHED_CUE,
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

p = PS1Play(PATCHED_CUE, workspace="/home/z/my-project/emu/games_homebrew/"
            "ws_psxmc_r31")
p.boot()
log("boot", core=p.core.core_name)

P = None
for _ in range(240):
    P = player_ptr(p.mem)
    if P:
        break
    p.wait(30)
if not P:
    R["verdict"] = "FAILED: no player pointer (world never came up)"
    log("verdict", verdict=R["verdict"])
    dump()
    sys.exit(1)
p.wait(120)
snap("world")
log("world_ready", P=hex(P), pos=pos_of(p.mem, P))

# ---- input probe 1: LOOK_DOWN pitch ring (r4-proven) -----------------------
a = pitch_now(p.mem, P)
pre = snap("pre_look")
p.core.run(6, {"B"})            # LOOK_DOWN = CROSS = ps1play B
p.core.run(2, set())
b = pitch_now(p.mem, P)
post = snap("post_look")
pitch_moved = abs(ring_diff(a, b)) > 0.2 * DEG
log("look_down", a=a, b=b, moved=pitch_moved,
    vis=madiff(pre, post))

# ---- input probe 2: movement LEFT -> RIGHT reversal ------------------------
pos0 = pos_of(p.mem, P)
pre2 = snap("pre_move")
p.core.run(60, {"LEFT"})
pos1 = pos_of(p.mem, P)
p.core.run(60, {"RIGHT"})
pos2 = pos_of(p.mem, P)
snap("post_move")
dx_left = [s32(x - y) / ONE_BLOCK for x, y in zip(pos1, pos0)]
dx_back = [s32(x - y) / ONE_BLOCK for x, y in zip(pos2, pos1)]
log("movement", pos0=pos0, pos1=pos1, pos2=pos2,
    left_delta_blocks=[round(v, 3) for v in dx_left],
    right_delta_blocks=[round(v, 3) for v in dx_back])

alive = pitch_moved or any(abs(v) > 0.05 for v in dx_left)
R["verdict"] = {
    "input_alive": bool(alive),
    "pitch_moved": bool(pitch_moved),
    "left_moved": [round(v, 3) for v in dx_left],
}
log("verdict", **R["verdict"])
led = json.load(open(BOOTS))
led["log"][0]["outcome"] = ("CCP(1) PATCH WORKS - minecraft input ALIVE"
                            if alive else
                            "patch did not restore input - class still "
                            "dead for minecraft")
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r31t1] DONE", led["log"][0]["outcome"], flush=True)
