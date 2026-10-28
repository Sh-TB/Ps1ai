#!/usr/bin/env python3
"""r36t2_voxide_boot4.py — decisive input battery on the PROVEN core (boot 4).

Evidence so far (disclosed): boot1-2 (beetle) and boot3 (rearmed
interpreter) all render the VoXide title but NO menu reaction to
DOWN/UP/CROSS. Today's LostPlumber boots on the SAME mednafen core with
the SAME host input path proved input lands for BIOS-pad games — so the
difference is the game's pad driver class, not the backend plumbing.

This boot (cap amended 3 -> 4 BEFORE run, disclosed; last boot of the
train): full-button battery on mednafen, with a MENU-REGION-ONLY visual
diff (y 140..220 of 320x240 — the button rows) to isolate cursor movement
from the ambient rotating-world background. Battery: DOWN, UP, CROSS,
CIRCLE, START, SELECT, TRIANGLE.

Outcome: any menu-region reaction = INPUT_RESPONSIVE+; none = INPUT_
UNPROVEN with the TX-only/direct-SIO hypothesis recorded as the lever
(same class as zenmai; fix = standalone mednafen or PCSX-Redux backend
per docs/homebrew_sources_r21.md 22.3(e)).
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
SHOTS = os.path.join(OUT, "shots4")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/voxide_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/system/openbios.bin"

# menu rows band in the 320x240 presentation
MENU = (slice(138, 222), slice(90, 230))

R = {"task": "r36t2 VoXide boot4 (decisive input battery, menu-region diff)",
     "content": CONTENT, "boot_cap": "3 -> 4 (amended before run, disclosed)",
     "boot_no": 4, "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    with open(os.path.join(OUT, "boot4_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r36t2b4] {json.dumps(rec, default=str)[:200]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def menu_band(a):
    return None if a is None else a[MENU[0], MENU[1]].astype(int)


def band_diff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return round(float(np.abs(a - b).mean()), 2)


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
ws = os.path.join(OUT, "ws4")
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
mb0 = menu_band(v0)
log("title", mean=round(float(v0.mean()), 1))

results = {}
for name, btn in (("DOWN", "DOWN"), ("UP", "UP"), ("CROSS", "B"),
                  ("CIRCLE", "A"), ("START", "START"), ("SELECT", "SELECT"),
                  ("TRIANGLE", "X"), ("SQ", "SQ")):
    core.set_buttons(btn)
    for _ in range(20):
        core.run_frame()
    core.set_buttons(set())
    f_t = core.frames_run + 30
    while core.frames_run < f_t:
        core.run_frame()
    v1 = snap(f"after_{name}")
    results[name] = band_diff(mb0, menu_band(v1))
    mb0 = menu_band(v1)
    log("probe", btn=name, menu_diff=results[name])

R["results"] = results
mx = max(v for v in results.values() if v >= 0)
R["verdict"] = ("INPUT_RESPONSIVE (menu reacts)"
                if mx > 3.0 else
                "INPUT_UNPROVEN (menu inert to all 8 buttons; TX-only "
                "hypothesis stands; backend lever = standalone mednafen / "
                "PCSX-Redux per r22 22.3(e))")
log("verdict", max_menu_diff=mx, verdict=R["verdict"])
dump()
print(json.dumps({"results": results, "verdict": R["verdict"]},
                 indent=1, default=str))
