#!/usr/bin/env python3
"""r31t2_psxmc_place_craftui.py — Round 31 boot 2: place + crafting-UI
open attempt on the CCP(1)-patched minecraft (probe passed in boot 1:
pitch ring + movement alive).

Deep program (r19t5 helpers reused verbatim via import):
  world ready -> control -> hotbar dump (CRAFTING_TABLE id 58)
  -> select table slot -> walk off the spawn platform (r19 lesson)
  -> pitch ladder 34/42/50 deg -> L2 3f-tap bursts with stack+world_px
  gates -> on CONFIRMED place: one more L2 tap at the same aim -> the
  r7 accidental crafting-modal becomes deliberate (PNG + vis spike).

Cap 3 pre-run: this IS boot 2 (deep program on probe pass); boot 3 =
script-bug retry only.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from ps1play.api import PS1Play  # noqa: E402
from psxmc_r7_lib import Evid, madiff  # noqa: E402
from psxmc_r10_lib import DEG, ONE_BLOCK, ring_diff  # noqa: E402
import psxmc_r10_lib as L  # noqa: E402
from psxmc_r10_oracle import (player_ptr, pitch_now, pos_of,  # noqa: E402
                              ensure_world_control)
import r19t5_psxmc_place as R19  # noqa: E402
from r19t5_psxmc_place import (ID_TABLE, ITEM_STACK, UI_BTN,  # noqa: E402
                               aim_to_ring, center_stats, hotbar_slots,
                               measure_look_rate, selected_hotbar,
                               sense_hit, stable_frame, tap_r3_select,
                               walk_off_platform, world_diff, yaw_now)

OUT = os.path.join(REPO, "scratch", "r31", "psxmc")
BOOTS = os.path.join(OUT, "boots_used.json")
PATCHED_CUE = ("/home/z/my-project/emu/games_homebrew/patched/"
               "PSXMC_lic_ccp1.cue")
PLACE_BTN = "L2"

T0 = time.time()
os.makedirs(OUT, exist_ok=True)
led = json.load(open(BOOTS))
assert led["count"] == 1 and led["cap"] == 3
led["count"] = 2
led["log"].append({"boot": 2, "script": "r31t2_psxmc_place_craftui.py",
                   "cue": PATCHED_CUE,
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

ev = Evid(OUT, "r31t2")
ev.jpath = os.path.join(OUT, "r31t2.jsonl")
ev.j({"ev": "start", "cue": PATCHED_CUE, "boot": 2,
      "task": "place + deliberate crafting-UI open on CCP(1) image"})

p = PS1Play(PATCHED_CUE, workspace="/home/z/my-project/emu/games_homebrew/"
            "ws_psxmc_r31")
p.boot()
core, m = p.core, p.mem
grab = core.frame_rgb
log = lambda e, **kw: ev.j({"ev": e, **kw})

P = None
for _ in range(240):
    P = player_ptr(m)
    if P:
        break
    p.wait(30)
assert P, "world never came up"
p.wait(120)
log("world_ready", P=hex(P), pos=[round(v / ONE_BLOCK, 2)
                                  for v in pos_of(m, P)])
ev.png("r31t2_world", grab())

ensure_world_control(core, m, P, ev, "r31t2")
for _k in range(3):
    core.run(2, set())
    if int(m.u8(R19.phys(m.u32(P + R19.INV_OFF)) + 8)) == 0:
        break
    core.run(1, {UI_BTN})
    core.run(24, set())

slots = hotbar_slots(m, P)
table = next((it for it in slots.values()
              if it and not it.get("unresolved") and it["id"] == ID_TABLE
              and it["stack"] > 0), None)
log("hotbar", table=table,
    ids={s: (it or {}).get("id") for s, it in slots.items()})
assert table, "no crafting table in hotbar"
table_slot = next(s for s, it in slots.items()
                  if it and it.get("addr") == table["addr"])
sel_ok, _tr = tap_r3_select(m, P, core, table_slot)
sel, sel_item = selected_hotbar(m, P)
stack_addr = int(sel_item["addr"], 16) + ITEM_STACK
log("selected", ok=sel_ok, sel=sel, item=sel_item,
    stack_addr=hex(stack_addr), stack_now=int(m.u8(stack_addr)))

# walk off the spawn platform (r19 lesson: place cell out-of-world there)
walk_rec = walk_off_platform(core, m, P, ev)
core.run(10, set())
pos1 = pos_of(m, P)
log("walked", rec=walk_rec, pos=[round(v / ONE_BLOCK, 2)
                                 for v in pos1])

spawn_ring = pitch_now(m, P)
rate_down, rate_up = measure_look_rate(core, m, P)
yaw0 = yaw_now(m, P)

# place attempts: pitch ladder, stack+vis gates
place_ok = None
for pdeg in (34.0, 42.0, 50.0, 26.0, 58.0):
    ring = (spawn_ring + int(round(pdeg * DEG))) % L.PITCH_MOD
    aim_to_ring(core, m, P, ring, rate_down, rate_up, "p%g" % pdeg)
    core.run(6, set())
    f_pre, _w = stable_frame(core, grab, n=3)
    st0 = int(m.u8(stack_addr))
    for _b in range(2):
        core.run(3, {PLACE_BTN})
        core.run(40, set())
    st1 = int(m.u8(stack_addr))
    f_post = grab()
    wd = world_diff(f_pre, f_post)
    ev.png(f"r31t2_place_p{int(pdeg)}_post", f_post)
    rec = {"pdeg": pdeg, "stack": [st0, st1],
           "consumed": st1 == st0 - 1, **wd}
    log("place_attempt", **rec)
    if rec["consumed"] and wd.get("world_px", 0) > 0:
        place_ok = {"pdeg": pdeg, "ring": ring, "f_pre": f_pre,
                    "f_post": f_post, "st0": st0}
        break

R = {"place": None, "craft_ui": None}
if place_ok:
    log("PLACE_CONFIRMED", pdeg=place_ok["pdeg"],
        stack=[place_ok["st0"], place_ok["st0"] - 1])
    R["place"] = {"pdeg": place_ok["pdeg"],
                  "stack": [place_ok["st0"], place_ok["st0"] - 1]}
    # deliberate crafting-UI attempt: same aim, one more L2 tap
    core.run(4, set())
    f0 = grab()
    core.run(3, {PLACE_BTN})
    core.run(60, set())
    f1 = grab()
    vis = madiff(f0, f1)
    ev.png("r31t2_after_use_tap", f1)
    ui_px = int((np.abs(f1.astype(int) - f0.astype(int)).sum(axis=2)
                 > 40).sum())
    R["craft_ui"] = {"vis": vis, "ui_px": ui_px,
                     "modal_likely": ui_px > 20000}
    log("craft_ui_attempt", **R["craft_ui"])
    ev.png("r31t2_craft_modal", f1)
else:
    log("no_place_confirmed")

p.save_state("r31t2_end")
R["frames"] = core.frames_run
ev.j({"ev": "final", **R})
ev.finish("done: " + json.dumps(R)[:200])
led["log"][-1]["outcome"] = json.dumps(R)[:200]
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r31t2] DONE", json.dumps(R), flush=True)
