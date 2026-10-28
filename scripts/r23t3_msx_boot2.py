#!/usr/bin/env python3
"""r23t3_msx_boot2.py — MSX stage-loader T3 boot 1 (r22 falsifiable plan).

Route (proven r17/r19 chain, legal inputs only):
  boot -> attract (5100f total) -> START -> main menu
  -> CROSS on ARCADE MISSION -> OK?YES -> CROSS (YES)
  -> SOLDIER SELECT -> CROSS -> OK dialog -> CROSS -> M1 live
  -> START (PAUSE) -> snapshot pause_k0
  -> DOWN census k=1..4 (PNG + cluster dump per k, from the pause
     savestate each time)

The r22 prime suspects: pause/menu BSS cluster 0x800D496C..0x800D4A80.
This boot measures it; the MISSION-2 selection + banner prediction is
boot 2 (savestate-restore, no new boot if the restore holds).

Boot cap: 2 for this train (hard, asserted). This script consumes boot 1.

Player anchors (r19): PLAYER_X 0xCA2E0, PLAYER_HP 0xCA2F6,
A_SCORE 0xEE318. Live-gate: HP in 0..200 and px sane.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.api import PS1Play  # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/r23/msx"
CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WS = "/home/z/my-project/ps1ai/scratch/r23/msx/ws"
BOOTS = os.path.join(EVID, "boots_used.json")
CUR_LO, CUR_HI = 0x957D8, 0x957F8
CLUSTER_LO, CLUSTER_HI = 0x800D496C - 0x80000000, 0x800D4A80 - 0x80000000
PLAYER_X, PLAYER_HP = 0x0CA2E0, 0x0CA2F6

R = {"task": "r23t3 MSX boot1 (ladder + pause cluster census)",
     "content": CUE, "disc_md5": "37d9e1179a32661800e74858009a4f8b "
     "(re-verified 2026-10-28)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "clusters": {}}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def dump():
    with open(os.path.join(EVID, "boot2_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": p.core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r23t3] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = p.core.frame_rgb()
    if arr is not None:
        path = os.path.join(EVID, f"{tag}.png")
        Image.fromarray(arr).save(path)
        R["shots"].append({"tag": tag, "f": p.core.frames_run})
    return arr


def words():
    return {"px": int.from_bytes(bytes(p.core.ram[PLAYER_X:PLAYER_X + 2]),
                                 "little", signed=True),
            "php": p.core.ram[PLAYER_HP],
            "frames": p.core.frames_run}


def cluster_bytes():
    return bytes(p.core.ram[CLUSTER_LO:CLUSTER_HI])


T0 = time.time()
os.makedirs(EVID, exist_ok=True)
n0 = boots_used()
assert n0 == 1, f"boot counter {n0} != 1 (boot 2 of hard cap 2)"
with open(BOOTS, "w") as f:
    json.dump({"count": 2, "log": [{"boot": 2, "script": "r23t3_msx_boot2",
                "disc_md5": "37d9e1179a32661800e74858009a4f8b",
                "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

p = PS1Play(CUE, workspace=WS,
            var_overrides={b"beetle_psx_renderer": b"software",
                           b"beetle_psx_frame_duping": b"disabled"})
p.boot()
p.wait(120)
log("boot", core=p.core.core_name)

# ---- attract -> main menu (r19 proven timings) -----------------------------------
p.core.run(300, set())
p.core.run(4800, set())
snap("attract")
p.core.run(60, {"START"})
p.core.run(900, set())
snap("main_menu")
p.save_state("menu2")

# ---- ARCADE MISSION -> OK?YES -> soldier -> M1 live -------------------------------
p.core.run(60, {"B"})            # CROSS on ARCADE MISSION
p.core.run(600, set())
snap("arcade_ok_dialog.png")
p.core.run(60, {"B"})            # YES
p.core.run(900, set())
snap("soldier_select.png")
p.save_state("soldier")
p.core.run(60, {"B"})
p.core.run(600, set())
snap("soldier_ok_dialog.png")
p.core.run(60, {"B"})

# ---- wait for live gameplay -------------------------------------------------------
live = None
for i in range(140):
    p.core.run(60, set())
    w = words()
    if 0 < w["php"] <= 200 and 0 <= w["px"] <= 4000:
        live = w
        break
snap("m1_live.png")
R["m1_live"] = live
log("M1 live", live=live)
if live:
    p.save_state("m1_live")

# ---- PAUSE + cluster census --------------------------------------------------------
if live:
    p.load_state("m1_live")
    p.core.run(120, set())
    p.core.run(60, {"START"})
    p.core.run(600, set())
    snap("pause_k0.png")
    p.save_state("pause")
    R["clusters"]["k0"] = cluster_bytes().hex()
    log("pause_opened", cluster0_sha=len(R["clusters"]["k0"]) // 2)

    for k in range(1, 5):
        p.load_state("pause")
        p.core.run(60, set())
        for _ in range(k):
            p.core.run(30, {"DOWN"})
            p.core.run(90, set())
        p.core.run(240, set())
        snap(f"pause_k{k}.png")
        R["clusters"][f"k{k}"] = cluster_bytes().hex()
        # cursor window diff
        cur = bytes(p.core.ram[CUR_LO:CUR_HI])
        R["clusters"][f"k{k}_cursor"] = cur.hex()
        log("pause_down", k=k)

# offline diff of the cluster between k0..k4
if len(R["clusters"]) >= 2:
    keys = [k for k in R["clusters"] if not k.endswith("_cursor")]
    base = bytes.fromhex(R["clusters"]["k0"])
    diffs = {}
    for k in keys[1:]:
        cur = bytes.fromhex(R["clusters"][k])
        d = [i for i in range(len(base))
             if base[i] != cur[i]]
        diffs[k] = {"n": len(d),
                    "offs": [hex(CLUSTER_LO + i) for i in d[:16]]}
    R["cluster_diffs"] = diffs
    log("cluster_diffs", **diffs)

R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r23t3] DONE frames=", p.core.frames_run,
      "wall=", round(time.time() - T0, 1),
      "live=", R.get("m1_live"), flush=True)
