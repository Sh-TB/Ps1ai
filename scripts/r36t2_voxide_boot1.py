#!/usr/bin/env python3
"""r36t2_voxide_boot1.py — first boot probe for VoXide v0.1.11 (train B).

Task r36t2. New-game intake on the honest ladder:
  BOOTED -> INPUT_RESPONSIVE -> STATE_CHANGE -> GAMEPLAY.

Game: EBonura/voxide (GPL-2.0-or-later; assets CC0 per the portal audit) —
Minecraft-style voxel survival sandbox, the PSX-Minecraft sibling.

Image: voxide_lic.bin (r36t2_voxide_lic.py; local MSX license sectors,
disclosed route 2; game bytes unpatched).

Pad driver class UNVERIFIED at source level (Rust psx-sdk-rs) — probes are
generic: padbuf scan + full-RAM census diffs under button holds.

Boot accounting: train cap 2 boots, disclosed BEFORE run (new game, fresh
ledger). 1 boot budgeted for this probe.
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
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/voxide_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/system/openbios.bin"

R = {"task": "r36t2 VoXide boot1 (intake probe)",
     "content": CONTENT, "image": "voxide_lic.bin (route 2, disclosed)",
     "boot_cap": 2, "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    with open(os.path.join(OUT, "boot1_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r36t2] {json.dumps(rec, default=str)[:220]}", flush=True)
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

# ---- phase A: boot wait (voxel games stream world data; give it time) -----------
while core.frames_run < 60:
    core.run_frame()
snap("boot60")
for f_t in (600, 1200):
    while core.frames_run < f_t:
        core.run_frame()
    a = snap(f"b{f_t}")
    log("frame_check", at=f_t, vis_mean=round(float(a.mean()), 1)
        if a is not None else None, padbuf=scan_padbuf(ram_now()))
ram = ram_now()
R["padbuf_1200"] = scan_padbuf(ram)

# ---- phase B: idle strip --------------------------------------------------------
a0 = snap("idle0")
idle = [a0]
for k in (1, 2):
    f_t = core.frames_run + 120
    while core.frames_run < f_t:
        core.run_frame()
    idle.append(snap(f"idle{k}"))
R["idle_vis"] = [round(pdiff(a0, x), 2) for x in idle[1:]]
base = ram_now()
log("idle_strip", vis=R["idle_vis"])

# ---- phase C: input probes -------------------------------------------------------
# START gate; then CROSS / RIGHT / UP for menu or world interaction
for name, btn, hold in (("START", "START", 60), ("CROSS", "B", 30),
                        ("RIGHT", "RIGHT", 60), ("UP", "UP", 30)):
    b0 = ram_now()
    v0 = snap(f"pre_{name}")
    core.set_buttons(btn)
    for _ in range(hold):
        core.run_frame()
    core.set_buttons(set())
    f_t = core.frames_run + 60
    while core.frames_run < f_t:
        core.run_frame()
    v1 = snap(f"post_{name}")
    R[f"cens_{name}"] = census(b0, ram_now())
    R[f"vis_{name}"] = round(pdiff(v0, v1), 2)
    log(f"probe_{name}", vis=R[f"vis_{name}"], cens=R[f"cens_{name}"])

R["padbuf_after"] = scan_padbuf(ram_now())
log("probes_done", padbuf_after=R["padbuf_after"])

# ---- verdict (honest ladder) -----------------------------------------------------
vis_ok = (R["vis_START"] > 1.0 or R["vis_CROSS"] > 1.0 or
          any(v > 1.0 for v in R["idle_vis"]))
inp = max(R["cens_START"]["n"], R["cens_CROSS"]["n"],
          R["cens_RIGHT"]["n"], R["cens_UP"]["n"]) > 200
pad_ok = any(len(v) > 0 for v in R["padbuf_1200"].values())
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
print(json.dumps({k: R[k] for k in ("verdict", "vis_START", "vis_CROSS",
                                     "vis_RIGHT", "vis_UP", "idle_vis",
                                     "padbuf_1200", "padbuf_after")},
                  indent=1, default=str))
