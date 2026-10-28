#!/usr/bin/env python3
"""r30t4_tetrade_input_probe.py — Round 30 class-separation probe.

Question: is the BIOS-pad class (kernel InitPAD/StartPAD padbuf fill)
broken across the board in the post-rollback environment, or is BuzzyBee
special?

Tetrade = the cleanest BIOS-pad reference on the ladder: r6/r7 proved
padbuff 00 41 FF FF @0xBB120 (port0) / 0xBB142 (port1) and START/ CROSS
transitions through the SAME LibretroCore. Boot is fast (title ~f600).

One boot: settle -> require padbuff id bytes (00 41 FF FF) -> hold CROSS
5f -> the button u16 (bytes 2-3, active-low) MUST change; release ->
revert. Also START tap -> menu transition observed via padbuff + screen
diff. Cap 1 (disclosed: this is a class probe, not a rung attempt).
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

OUT = os.path.join(REPO, "scratch", "r30", "tetrade_probe")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/TETRADE_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

PAD0 = 0xBB120

R = {"task": "r30t4 Tetrade BIOS-pad class probe",
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
    print(f"[r30t4] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def pb():
    return bytes(core.ram[PAD0:PAD0 + 4])


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
if os.path.exists(BOOTS):
    led0 = json.load(open(BOOTS))
    assert led0["log"][0].get("outcome", "").startswith(
        "retro_load_game FAILED"), "ledger mismatch"
    print("[r30t4] retrying after disclosed non-boot load failure")
else:
    json.dump({"count": 1, "cap": 1, "cap_policy": R["cap_policy"],
               "log": [{"boot": 1, "script": "r30t4_tetrade_input_probe.py",
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

# settle until the kernel padbuff shows the digital-pad id
live = False
for _ in range(2400):
    core.run(1, set())
    if pb() == b"\x00\x41\xff\xff":
        live = True
        break
log("padbuff_live", live=live, pb=pb().hex())
snap("idle")

# CROSS hold probe: bytes 2-3 (active-low u16) must change
core.set_buttons("B")
h_series = []
for _ in range(5):
    core.run_frame()
    h_series.append(pb().hex())
core.set_buttons(set())
r_series = []
for _ in range(30):
    core.run_frame()
    r_series.append(pb().hex())
changed_during = any(x != "0041ffff" for x in h_series)
reverted_after = all(x == "0041ffff" for x in r_series)
R["cross_probe"] = {"during": h_series, "after": r_series[:5],
                    "changed_during": changed_during,
                    "reverted_after": reverted_after}
log("cross_probe", changed=changed_during, reverted=reverted_after,
    during=h_series)

# START tap: padbuff + vis diff (menu entry is the r7-proven transition)
pre = snap("pre_start")
mean_pre = float(pre.mean()) if pre is not None else -1
core.set_buttons("START")
for _ in range(3):
    core.run_frame()
core.set_buttons(set())
for _ in range(120):
    core.run(1, set())
post = snap("post_start")
mean_post = float(post.mean()) if post is not None else -1
R["start_probe"] = {"mean_pre": round(mean_pre, 2),
                    "mean_post": round(mean_post, 2),
                    "vis": round(float(np.abs(
                        post.astype(int) - pre.astype(int)).mean()), 2)
                    if pre is not None and post is not None else -1}
log("start_probe", **R["start_probe"])

verdict = ("BIOS-PAD CLASS ALIVE on this core build (Tetrade padbuff "
           "responds)" if changed_during and reverted_after else
           "BIOS-PAD CLASS DEAD on this core build (both classes now "
           "implicated; environment-level input regression)")
R["verdict"] = verdict
log("verdict", verdict=verdict)
led = json.load(open(BOOTS))
led["log"][0]["outcome"] = verdict
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t4] DONE", verdict, flush=True)
