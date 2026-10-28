#!/usr/bin/env python3
"""r34t4_buzzybee_deathshot.py — Round 34: visual capture of the BuzzyBee
game-over screen + auto-return loop (evidence boot).

r34t3 proved the deep systems chain in RAM (ALL_PHASES_OK): drain
-3/f, enemy -1500 edge, score +1/f (apparent cap 1000), death -> gs5,
bestScore==score, auto-return ~381f with score reset + best retained,
second run bestScore retention. The r34t3 snapshots fired ON the
gs5-detection frame, which still renders the last gameplay frame —
the "Your Last attempt" screen draws later.

This boot (cap amendment 4->5 DISCLOSED PRE-RUN, evidence-only, no
new systems claims): one idle death, capture the gs5 screen ~90f
after detection, then a frame series covering the 6.4s hold and the
auto-return to title for the evidence GIF.
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

OUT = os.path.join(REPO, "scratch", "r34")
SHOTS = os.path.join(OUT, "shots")
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro_psxbus_r34.so"
BUZZ = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"
BOOTS = os.path.join(OUT, "boots_used.json")
GIF_FRAMES = os.path.join(OUT, "gif_frames")

GS, BEST, SCORE, HEALTH = 0x80058830, 0x80058838, 0x8005883C, 0x8005EF48

R = {"task": "r34t4 BuzzyBee death-screen visual capture + GIF series",
     "cap_policy": "amendment 4->5 DISCLOSED PRE-RUN: boot 5 = "
                   "evidence-only visual capture",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r34t4.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r34t4] {json.dumps(rec, default=str)[:200]}", flush=True)
    dump()


def i32(va):
    off = va - 0x80000000
    return int.from_bytes(bytes(core.ram[off:off + 4]), "little",
                          signed=True)


def state():
    return {"gs": i32(GS), "best": i32(BEST), "score": i32(SCORE),
            "health": i32(HEALTH)}


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(GIF_FRAMES, exist_ok=True)

led = json.load(open(BOOTS))
assert led["count"] == 4
led["amendments"].append({"from": 4, "to": 5,
                          "reason": "r34t4 death-screen visual capture, "
                                    "evidence-only, disclosed pre-run"})
led["count"] = 5
led["log"].append({"boot": 5, "script": "r34t4_buzzybee_deathshot.py",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws_shot")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(BUZZ)
log("boot", core=core.core_name, av=av)

for _ in range(900):
    core.run(1, set())
log("title", **state())

core.set_buttons("START")
for _ in range(40):
    core.run_frame()
core.set_buttons(set())
log("run_started", **state())

death_f = None
for i in range(2600):
    core.run(1, set())
    if i32(GS) == 5:
        death_f = core.frames_run
        break
st = state()
log("death_detected", death_f=death_f, **st)

# hold ~90f after detection, then capture the drawn game-over screen
for _ in range(90):
    core.run_frame()
st = state()
p = os.path.join(SHOTS, f"death_screen_f{core.frames_run:05d}.png")
Image.fromarray(core.frame_rgb()).save(p)
R["shots"].append({"tag": "death_screen", "frame": core.frames_run,
                   "png": p, **st})
log("death_screen_captured", png=p, **st)

# frame series for the GIF: death screen -> auto-return -> title
gf = 0
ret_f = None
while core.frames_run - death_f < 700:
    core.run(1, set())
    if (core.frames_run % 6) == 0:
        Image.fromarray(core.frame_rgb()).save(
            os.path.join(GIF_FRAMES, f"loop_{gf:04d}.png"))
        gf += 1
    if ret_f is None and i32(GS) == 0:
        ret_f = core.frames_run
        Image.fromarray(core.frame_rgb()).save(
            os.path.join(SHOTS, f"returned_title_f{ret_f:05d}.png"))
log("series_done", gif_frames=gf, ret_f=ret_f,
    final=state())
R["verdict"] = {"death_f": death_f, "ret_f": ret_f,
                "gif_frames": gf,
                "best_final": i32(BEST)}
dump()
print("[r34t4] DONE", flush=True)
