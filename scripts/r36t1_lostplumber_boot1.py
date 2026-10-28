#!/usr/bin/env python3
"""r36t1_lostplumber_boot1.py — first boot probe for LostPlumber (train A).

Task r36t1. New-game intake on the honest ladder:
  BOOTED -> INPUT_RESPONSIVE -> STATE_CHANGE -> GAMEPLAY.

Game: NDR008/LostPlumber (MIT-in-header, flagged; jam prototype,
scroll-right world walker). Same engine/input.c driver as BuzzyBee
(InitPAD => BIOS pad class), so the `41 5A FF FF` padbuf scan is the
first sensor to try.

Image: lostplumber_lic.bin (r36t1_lostplumber_wrap.py; local MSX license
sectors, disclosed route 2; EXE unpatched).

Boot accounting: train cap 2 boots, disclosed BEFORE run (new game,
fresh ledger). 1 boot budgeted for this probe.
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
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/lostplumber_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/system/openbios.bin"

R = {"task": "r36t1 LostPlumber boot1 (intake probe)",
     "content": CONTENT, "image": "lostplumber_lic.bin (route 2, disclosed)",
     "boot_cap": 2, "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    with open(os.path.join(OUT, "boot1_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r36t1] {json.dumps(rec, default=str)[:220]}", flush=True)
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


def census(b0, b1, buckets=64):
    """changed-byte count + top-8 bucket regions between two RAM snapshots."""
    if b0 is None or b1 is None or b0.shape != b1.shape:
        return {"n": -1}
    d = np.where(b0 != b1)[0]
    if len(d) == 0:
        return {"n": 0, "buckets": []}
    hist = np.histogram(d, bins=buckets, range=(0, len(b0)))[0]
    top = sorted(enumerate(hist.tolist()), key=lambda kv: -kv[1])[:8]
    bk = [{"kva": hex(0x80000000 + int(i * len(b0) / buckets)),
           "n": int(n)} for i, n in top if n > 0]
    return {"n": int(len(d)), "buckets": bk}


def scan_padbuf(ram):
    """BIOS padbuf signature scan: '41 5A FF FF' (pad1 digital, idle buttons)
    and '00 41 5A FF FF' (the 0x00 is the received-status byte)."""
    tb = ram
    out = {}
    for p in (bytes.fromhex("415affff"), bytes.fromhex("00415affff")):
        w = np.frombuffer(p, dtype=np.uint8)
        hits = np.where((tb[:-len(w)] == w[0]) &
                        (tb[1:len(tb)-len(w)+1] == w[1]) &
                        (tb[2:len(tb)-len(w)+2] == w[2]) &
                        (tb[3:len(tb)-len(w)+3] == w[3]))[0]
        out[p.hex()] = [int(x) for x in hits[:8]]
    return out


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", av=av)

# ---- phase A: boot wait + padbuf scan -------------------------------------------
while core.frames_run < 60:
    core.run_frame()  # 2f-warmup lesson from r35: brief, then first snap late
snap("boot60")
while core.frames_run < 400:
    core.run_frame()
a400 = snap("b400")
ram = ram_now()
R["padbuf_400"] = scan_padbuf(ram)
log("padbuf_scan", hits=R["padbuf_400"], vis_mean=round(float(a400.mean()), 1)
    if a400 is not None else None)

# ---- phase B: idle strip (animation + baseline) ---------------------------------
idle = [a400]
for k, f_t in enumerate((520, 640)):
    while core.frames_run < f_t:
        core.run_frame()
    idle.append(snap(f"idle{k}"))
R["idle_vis"] = [round(pdiff(a400, x), 2) for x in idle[1:]]
base = ram_now()
log("idle_strip", vis=R["idle_vis"])

# ---- phase C: START hold (title gate?) ------------------------------------------
core.set_buttons("START")
for _ in range(60):
    core.run_frame()
core.set_buttons(set())
while core.frames_run < 400 + 60 + 90:
    core.run_frame()
a_start = snap("start")
after = ram_now()
R["cens_start"] = census(base, after)
R["vis_start"] = round(pdiff(a400, a_start), 2)
log("probe_START", vis=R["vis_start"], cens=R["cens_start"])

# ---- phase D: gameplay probes (RIGHT = world-walker scroll; CROSS) ---------------
base2 = ram_now()
core.set_buttons("RIGHT")
for _ in range(60):
    core.run_frame()
core.set_buttons(set())
f_t = core.frames_run + 30
while core.frames_run < f_t:
    core.run_frame()
a_r = snap("right")
R["cens_right"] = census(base2, ram_now())
R["vis_right"] = round(pdiff(a_start, a_r), 2)

base3 = ram_now()
core.set_buttons("B")  # CROSS per project map
for _ in range(30):
    core.run_frame()
core.set_buttons(set())
f_t = core.frames_run + 60
while core.frames_run < f_t:
    core.run_frame()
a_b = snap("cross")
R["cens_cross"] = census(base3, ram_now())
R["vis_cross"] = round(pdiff(a_r, a_b), 2)

# padbuf re-scan (does input land in the driver buffer?)
R["padbuf_after"] = scan_padbuf(ram_now())
log("probes_done", cens_right=R["cens_right"], cens_cross=R["cens_cross"],
     padbuf_after=R["padbuf_after"])

# ---- verdict (honest ladder) -----------------------------------------------------
vis_ok = R["vis_start"] > 1.0 or any(v > 1.0 for v in R["idle_vis"])
inp = R["cens_start"]["n"] > 200 or R["cens_right"]["n"] > 200 or \
    R["cens_cross"]["n"] > 200
pad_ok = any(len(v) > 0 for v in R["padbuf_400"].values())
if not vis_ok:
    verdict = "BLACK_OR_STATIC (BOOTED-unproven)"
elif pad_ok and inp:
    verdict = "INPUT_RESPONSIVE+"
elif inp:
    verdict = "INPUT_RESPONSIVE (census only)"
else:
    verdict = "BOOTED (no input causality yet)"
R["verdict"] = verdict
log("verdict", verdict=verdict)
dump()
print(json.dumps({k: R[k] for k in ("verdict", "padbuf_400", "padbuf_after",
                                     "vis_start", "vis_right", "vis_cross",
                                     "idle_vis")},
                  indent=1, default=str))
