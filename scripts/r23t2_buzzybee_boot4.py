#!/usr/bin/env python3
"""r23t2_buzzybee_boot4.py — decisive NTSC-forced boot (BuzzyBee v1.0 HEAD).

Hypothesis under test (from boots 1-3 + static RE): the game forces PAL
(setScreenMode compiled PAL-only; SetVideoMode(1)) and the PAL display
path yields a permanent black screen on beetle+OpenBIOS while the game
logic itself runs (input state machine proven in boot 3).

This boot runs the TWO-INSTRUCTION NTSC patch (SCREEN_HEIGHT 256->240,
SetVideoMode 1->0 — byte-verified in-disc, sha256 042b94bb...b093 image)
and expects the game to RENDER. Exact BSS symbols from the upstream map
(same build as the EXE):
  SCREEN_WIDTH 0x80058810  SCREEN_HEIGHT 0x80058814 currentBuffer ...18
  input_pad ...81C  input_trig ...820  input_held ...824
  gameState ...830  bestScore ...838  score ...83C
  mainPlayer 0x8005EDC0  mainHealth 0x8005EF48  mainTimer 0x8005F548

Boot accounting (disclosed): train cap amended 3 -> 4 BEFORE this run
(same artifact family, decisive display-path experiment; logged).
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

OUT = os.path.join(REPO, "scratch", "r23", "buzzybee")
SHOTS = os.path.join(OUT, "shots_b4")
CONTENT = ("/home/z/my-project/emu/games_homebrew/patched/"
           "buzzybee_ntsc_lic.cue")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

SW, SH = 0x80058810, 0x80058814
INP_PAD, INP_TRIG, INP_HELD = 0x8005881C, 0x80058820, 0x80058824
STATE, BEST, SCORE = 0x80058830, 0x80058838, 0x8005883C
PLAYER, HEALTH, TIMER = 0x8005EDC0, 0x8005EF48, 0x8005F548

R = {"task": "r23t2 BuzzyBee boot4 (NTSC-forced decisive)",
     "content": CONTENT,
     "image_sha": "042b94bb29907e75... (2-instruction NTSC patch, disclosed)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "anchors": {}}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def dump():
    with open(os.path.join(OUT, "boot4_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r23t2b4] {json.dumps(rec, default=str)[:240]}", flush=True)
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


def i32(va):
    return int.from_bytes(bytes(core.ram[va - 0x80000000:va - 0x80000000 + 4]),
                          "little", signed=True)


def u32(va):
    return int.from_bytes(bytes(core.ram[va - 0x80000000:va - 0x80000000 + 4]),
                          "little")


def syms():
    return {"SCREEN_W": i32(SW), "SCREEN_H": i32(SH),
            "input_held": u32(INP_HELD) & 0xFFFFFFFF,
            "gameState": i32(STATE), "score": i32(SCORE),
            "bestScore": i32(BEST)}


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
n0 = boots_used()
assert n0 == 4, f"boot counter {n0} != 4 (boot 4 crashed post-boot; " \
    "cap amended 4->5, disclosed)"
with open(BOOTS) as f:
    prev = json.load(f)
with open(BOOTS, "w") as f:
    json.dump({"count": 5, "log": prev.get("log", []) +
               [{"boot": 5, "script": "r23t2_buzzybee_boot4.py (retry)",
                 "image": "buzzybee_ntsc_lic.bin (2-instr NTSC patch, "
                          "disclosed)",
                 "cap_note": "train cap amended 4->5 BEFORE this run "
                             "(boot 4 consumed by a script crash after "
                             "400 real frames)",
                 "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

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

# ---- phase 1: boot wait + patch-live check --------------------------------------
for f_target in (400, 700):
    while core.frames_run < f_target:
        core.run_frame()
    snap(f"b{f_target}")
    R["anchors"][f"sym_at_f{f_target}"] = syms()
    log("sym_check", at=f_target, **R["anchors"][f"sym_at_f{f_target}"])
# SCREEN_HEIGHT must read 240 (patched) once initialize() has run —
# the unpatched game writes 256.

# ---- phase 2: VRAM census (is anything drawn?) -----------------------------------
vram = core.vram
if vram is not None:
    v1d = np.asarray(vram).ravel()
    nz = int(np.count_nonzero(v1d))
    R["anchors"]["vram"] = {"shape": str(np.asarray(vram).shape),
                            "dtype": str(np.asarray(vram).dtype),
                            "nonzero": nz}
    log("vram_census", **R["anchors"]["vram"])

# ---- phase 3: START -> play (exact symbol) ---------------------------------------
st0 = i32(STATE)
vis_before = core.frame_rgb()
core.set_buttons("START")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(150):
    core.run_frame()
vis_after = core.frame_rgb()
st1 = i32(STATE)
start_diff = pdiff(vis_before, vis_after)
snap("after_START")
R["anchors"]["gameState"] = {"before": st0, "after": st1}
log("pulse_START", vis_diff=start_diff, state_0=st0, state_1=st1,
    syms=syms())

# ---- phase 4: SELECT pause toggle (exact symbol) ----------------------------------
core.set_buttons("SELECT")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
st2 = i32(STATE)
snap("paused")
log("pulse_SELECT", state=st2, is_99=(st2 == 99))
core.set_buttons("SELECT")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
st3 = i32(STATE)
log("resume", state=st3)

# ---- phase 5: CROSS flap + score climb --------------------------------------------
sc0 = i32(SCORE)
vis_before = core.frame_rgb()
core.set_buttons("B")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
vis_after = core.frame_rgb()
sc1 = i32(SCORE)
flap_diff = pdiff(vis_before, vis_after)
snap("after_flap")
R["anchors"]["score"] = {"before": sc0, "after": sc1}
log("pulse_CROSS", vis_diff=flap_diff, score_0=sc0, score_1=sc1)

# ---- verdicts ---------------------------------------------------------------------
vram_ok = R["anchors"].get("vram", {}).get("nonzero", 0) > 10000
R["verdicts"] = {
    "BOOTED": bool(vis_after is not None and
                   (start_diff > 2.0 or vram_ok)),
    "INPUT_RESPONSIVE": bool(st1 == 1 and st0 == 0),
    "STATE_CHANGE_CONFIRMED": bool(st2 == 99 and st3 == 1),
    "GAMEPLAY_CONFIRMED": bool(sc1 > sc0 and flap_diff > 1.0),
}
R["verdict"] = ("GAMEPLAY_CONFIRMED" if R["verdicts"]["GAMEPLAY_CONFIRMED"]
                else "STATE_CHANGE_CONFIRMED"
                if R["verdicts"]["STATE_CHANGE_CONFIRMED"]
                else "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED" if R["verdicts"]["BOOTED"] else "FAILED")
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r23t2b4] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), "anchors=", json.dumps(R["anchors"]),
      flush=True)
