#!/usr/bin/env python3
"""r30t2_buzzybee_inputdiag.py — Round 30 diagnostic boot (cap 2->3,
DISCLOSED PRE-RUN): why did the r23-proven START->gameState-1 transition
not reproduce?

Today's facts: the rebuilt image is byte-identical to r23's (sha
042b94bb...), the title renders (PNG "Buzzy Bee ... Press Start"), but a
3f START hold at f900 left gameState==0 (boot 2, disclosed). Beetle pad
delivery works TODAY in general (r29 MSPSX START->board-init at f605
through the same core+BIOS).

Source: engine/input.c (stolen from doukutsupsx): InitPAD/StartPAD +
ChangeClearPAD(0); in_update(): input_pad = ~pad->btn; input_held =
input_pad (RAW u16 pad bits, zero-extended); input_trig = ~input_old &
input_held (rising edge); input_suppress_trig never set TRUE anywhere.
main.c line 617: if (input_trig & PAD_START) { if (gameState == 0 &
(time2 >= 2)) { gameState = 1; } } — time2 = mainTimer.totalsec.

Probe plan (one boot):
  P1 settle 900f; sample input_pad/held/trig (0x8005881C/20/24) idle
  P2 hold START 40f (covers slow poll classes), sample EVERY frame
  P3 release 90f, sample; then double-tap START (5f on/off x3)
  P4 read mainTimer struct (0x8005F548, 64B) for a seconds-like field
  P5 verdict: pad-bits-land vs trig-vs-gate
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

OUT = os.path.join(REPO, "scratch", "r30", "buzzybee")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

IN_PAD, IN_HELD, IN_TRIG = 0x8005881C, 0x80058824, 0x80058820
GS, TIMER = 0x80058830, 0x8005F548

R = {"task": "r30t2 BuzzyBee input diagnostic",
     "boot_amendment": "cap 2->3 DISCLOSED PRE-RUN: r23-proven START "
                       "transition failed to reproduce on a byte-identical "
                       "image; this diagnostic observes the game's own "
                       "input words directly",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r30t2.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r30t2] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"diag_{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def i32(va):
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def u16(va):
    return int.from_bytes(bytes(core.ram[va:va + 2]), "little")


def inp():
    return {"pad": u16(IN_PAD), "held": i32(IN_HELD),
            "trig": i32(IN_TRIG), "gs": i32(GS)}


T0 = time.time()
led = json.load(open(BOOTS))
assert led["count"] == 2 and led["cap"] == 2
led["amendments"] = [{"from": 2, "to": 3,
                      "reason": R["boot_amendment"],
                      "disclosed": "pre-run"}]
led["count"] = 3
led["log"].append({"boot": 3, "script": "r30t2_buzzybee_inputdiag.py",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

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

# P1: settle + idle input words
for _ in range(900):
    core.run(1, set())
idle = [inp() for _ in range(30)]
R["idle"] = idle[:5]
log("idle_sample", head=idle[:5],
    all_zero=bool(all(x["pad"] == 0 and x["held"] == 0 for x in idle)))
snap("idle")

# P2: hold START 40f, sample every frame
core.set_buttons("START")
series = []
for _ in range(40):
    core.run_frame()
    series.append({"f": core.frames_run, **inp()})
core.set_buttons(set())
R["start_hold"] = series
nz = [s for s in series if s["pad"] or s["held"] or s["trig"]]
log("start_hold_40f", nonzero_frames=len(nz), first=nz[:3] if nz else None,
    last=series[-1], gs_after=i32(GS))
snap("after_hold")

# P3: release 90f + double-tap
rel = [inp() for _ in range(90)]
R["release"] = {"nonzero": sum(1 for x in rel
                               if x["pad"] or x["held"] or x["trig"]),
                "gs_after": i32(GS)}
log("release_90f", **R["release"])
taps = []
for k in range(3):
    core.set_buttons("START")
    for _ in range(5):
        core.run_frame()
        taps.append({"f": core.frames_run, **inp()})
    core.set_buttons(set())
    for _ in range(90):
        core.run_frame()
        taps.append({"f": core.frames_run, **inp()})
R["double_tap"] = {"nonzero": sum(1 for x in taps
                                  if x["pad"] or x["held"] or x["trig"]),
                   "head": taps[:6], "gs_end": i32(GS)}
log("double_tap", **R["double_tap"])
snap("after_taps")

# P4: timer struct scan (seconds-like field ~ frames/60)
tm = bytes(core.ram[TIMER:TIMER + 64])
words = [int.from_bytes(tm[i:i + 4], "little", signed=True)
         for i in range(0, 64, 4)]
R["timer_words"] = words
log("timer_scan", words=words, frames=core.frames_run)

# verdict
pad_lands = any(s["pad"] for s in series) or any(s["pad"] for s in taps)
trig_fires = any(s["trig"] for s in series) or any(s["trig"] for s in taps)
gs_moved = i32(GS) != 0
R["verdict"] = {
    "pad_bits_land": bool(pad_lands),
    "trig_fires": bool(trig_fires),
    "gameState_moved": bool(gs_moved),
    "interpretation": (
        "pad bits never reach the game (kernel padbuf fill dead this "
        "session) - input-suppression issue class"
        if not pad_lands else
        "pad bits land but no transition - gate/state issue class"),
}
log("verdict", **R["verdict"])
led["log"][-1]["outcome"] = json.dumps(R["verdict"])
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t2] DONE", json.dumps(R["verdict"]), flush=True)
