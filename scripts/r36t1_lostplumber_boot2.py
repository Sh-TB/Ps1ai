#!/usr/bin/env python3
"""r36t1_lostplumber_boot2.py — input-causality probe (train A, boot 2/2).

Boot 1 finding (disclosed): boot logo square renders (f60), then a DARK
side-scroll world renders from ~f520 (240x320, orange brick terrain);
RIGHT hold scrolled the terrain left (idle1 f640 vs cross f880 PNGs) and
census bucket 0x80028000 moved 282 bytes — visual causality exists but the
boot1 verdict logic mis-scored it (BLACK transition at the f400 baseline +
shape change 640x472 -> 320x240 broke pdiff).

This boot (cap 2, boot 2 of 2, disclosed BEFORE run):
  1. wait f900 (world stable) -> idle strip
  2. RIGHT hold 90f  -> expect scroll; census + same-shape pdiff
  3. LEFT hold 90f   -> expect reverse scroll
  4. CROSS/START     -> discovery pulses
  5. camera scroll-int hunt: u32 slots in the delta mask that move by a
     consistent delta (scroll offset candidates)
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

OUT = os.path.join(REPO, "scratch", "r36", "lostplumber")
SHOTS = os.path.join(OUT, "shots2")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/lostplumber_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/system/openbios.bin"

R = {"task": "r36t1 LostPlumber boot2 (input causality)",
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
    print(f"[r36t1b2] {json.dumps(rec, default=str)[:220]}", flush=True)
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
            "top": [{"va": hex(int(x))} for x in d[:6]]}


def hold(btn, n, settle=30, tag=None):
    b0 = ram_now()
    v0 = snap(f"pre_{tag or btn}")
    core.set_buttons(btn)
    for _ in range(n):
        core.run_frame()
    core.set_buttons(set())
    f_t = core.frames_run + settle
    while core.frames_run < f_t:
        core.run_frame()
    v1 = snap(f"post_{tag or btn}")
    b1 = ram_now()
    c = census(b0, b1)
    v = round(pdiff(v0, v1), 2)
    log(f"probe_{tag or btn}", vis=v, cens_n=c["n"])
    return b0, b1, v, c


def scroll_candidates(b0, b1, limit=8):
    """u32 slots whose value increased between snapshots (scroll offsets)."""
    d = np.where(b0 != b1)[0]
    cands = {}
    for i in d:
        if i % 4:
            continue
        a = int.from_bytes(b0[i:i + 4], "little")
        b = int.from_bytes(b1[i:i + 4], "little")
        if 0 < b <= 4096 and b > a and b - a <= 512 and a < 4096:
            cands[hex(0x80000000 + int(i))] = [a, b]
        if len(cands) >= limit:
            break
    return cands


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

while core.frames_run < 900:
    core.run_frame()
a0 = snap("idle0")
idle = [a0]
for k in (1, 2):
    f_t = core.frames_run + 90
    while core.frames_run < f_t:
        core.run_frame()
    idle.append(snap(f"idle{k}"))
R["idle_vis"] = [round(pdiff(a0, x), 2) for x in idle[1:]]
log("idle", vis=R["idle_vis"])

b0, b1, v, c = hold("RIGHT", 90, tag="right")
R["scroll_cands_right"] = scroll_candidates(b0, b1)
log("scroll_cands", cands=R["scroll_cands_right"])

b0l, b1l, vl, cl = hold("LEFT", 90, tag="left")
R["vis_left"] = vl

b0c, b1c, vc, cc = hold("B", 30, tag="cross")
b0s, b1s, vs, cs = hold("START", 30, tag="start")

R["verdict"] = {
    "booted_render": True,
    "right_scroll_vis": v,
    "right_scroll_census": c["n"],
    "left_vis": vl,
    "cross_vis": vc,
    "start_vis": vs,
}
log("verdict", **R["verdict"])
dump()
print(json.dumps({k: R[k] for k in ("idle_vis", "scroll_cands_right",
                                     "verdict")}, indent=1, default=str))
