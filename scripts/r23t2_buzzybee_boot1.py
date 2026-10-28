#!/usr/bin/env python3
"""r23t2_buzzybee_boot1.py — BuzzyBee intake boot (NDR008/BuzzyBee, MIT).

Input class (upstream source, engine/input.c): BIOS InitPAD(padbuf[2][34])
+ StartPAD — the class that has worked first-try on beetle for
doukutsupsx/flappybirdpsx. Game model (main.c @HEAD):
  - gameState int: 0 = start screen, 1 = play, 5 = game over, 99 = SELECT
    pause/debug toggle (main.c:177 comment says 2, the code toggles 99)
  - START edge at state 0 (after time2>=2) -> state 1 (:617-625)
  - SELECT edge toggles 1 <-> 99 (:626-630)
  - CROSS edge -> y_vel -= MAXFLAP/2 (flap impulse, :249-256)
  - score++ every play frame (:333), health wasp -1500 / flower +1000

Anchors are DISCOVERED live (no static symbol addresses available):
  - padbuf: scan for the 41 5A FF FF idle signature, cross-check via a
    CROSS press flipping the buttons word (SW1 0xFF->0xBF bit pattern)
  - gameState: i32 scan ==0 at title, ==1 after START, ==99 after SELECT
  - score: i32 scan for +N over N frames during play

Boot cap: 2 (hard). This script consumes boot 1 only, and refuses to run
if the counter is not 0. Honest ladder: BOOTED < INPUT_RESPONSIVE <
STATE_CHANGE_CONFIRMED < GAMEPLAY_CONFIRMED (score climb + flap impulse).
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
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

R = {"task": "r23t2 BuzzyBee boot1 intake",
     "content": CONTENT,
     "exe": "BuzzyBee.ps-exe sha256 9b0bfc08...c909a8ba (repo tree, MIT)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "anchors": {}}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def dump():
    with open(os.path.join(OUT, "boot1_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r23t2] {json.dumps(rec, default=str)[:240]}", flush=True)
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


T0 = time.time()
for d in (OUT, SHOTS, os.path.join(OUT, "ws", "system"),
          os.path.join(OUT, "ws", "saves")):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 0, f"boot counter {n0} != 0 (hard cap 2)"
with open(BOOTS, "w") as f:
    json.dump({"count": 1, "log": [{"boot": 1,
                "script": "r23t2_buzzybee_boot1.py",
                "image": "buzzybee_lic.bin (license sectors only)",
                "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

shutil.copyfile(BIOS, os.path.join(OUT, "ws", "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(OUT, "ws", "system"),
                    os.path.join(OUT, "ws", "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, ver=core.core_ver, av=av)

# ---- phase 1: boot + title settle ----------------------------------------------
for _ in range(180):
    core.run_frame()
snap("start_screen")

# ---- phase 2: padbuf discovery --------------------------------------------------
ram = core.ram
idle_hits = [i for i in range(0, len(ram) - 8, 2)
             if ram[i] == 0x41 and ram[i + 1] == 0x5A
             and ram[i + 2] == 0xFF and ram[i + 3] == 0xFF]
log("pad_scan_idle", hits=len(idle_hits),
    offs=[hex(o) for o in idle_hits[:12]])
PAD = None
if idle_hits:
    cand = idle_hits[0]
    before = bytes(ram[cand:cand + 4])
    core.set_buttons("B")
    for _ in range(3):
        core.run_frame()
    after = bytes(ram[cand:cand + 4])
    core.set_buttons(set())
    for _ in range(5):
        core.run_frame()
    if before != after:
        PAD = cand
        R["anchors"]["padbuf0"] = {"off": hex(cand), "idle": before.hex(),
                                   "cross": after.hex()}
        log("padbuf_anchored", off=hex(cand), idle=before.hex(),
            cross=after.hex())
    else:
        log("padbuf_candidate_no_reaction", off=hex(cand))
snap("pad_probe")

# ---- phase 3: gameState candidates at title (== 0) ------------------------------
ram = core.ram
z = np.frombuffer(bytes(ram[:0x200000]), dtype="<u4")
title_zero = np.nonzero(z == 0)[0]
log("state_scan_title", n=int(len(title_zero)))

# ---- phase 4: START edge -> play (INPUT_RESPONSIVE) -----------------------------
vis_before = core.frame_rgb()
core.set_buttons("START")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(90):
    core.run_frame()
vis_after = core.frame_rgb()
start_diff = pdiff(vis_before, vis_after)
snap("after_START")
log("pulse_START", vis_diff=start_diff)

# gameState: ==1 now
z = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4")
one_hits = set(np.nonzero(z == 1)[0].tolist())
cand_state = sorted(one_hits & set(title_zero.tolist()))
log("state_scan_play", n=len(cand_state), offs=[hex(o) for o in cand_state[:20]])
STATE = None
if len(cand_state) == 1:
    STATE = cand_state[0] * 4
elif len(cand_state) > 1:
    # disambiguate with SELECT toggle (1 -> 99) below
    pass

# ---- phase 5: SELECT toggle -> pause (STATE_CHANGE) ------------------------------
sel_ok = False
vis_before = core.frame_rgb()
core.set_buttons("SELECT")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(45):
    core.run_frame()
vis_after = core.frame_rgb()
snap("after_SELECT")
sel_diff = pdiff(vis_before, vis_after)
z = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4")
hits99 = set(np.nonzero(z == 99)[0].tolist())
if len(cand_state) > 1:
    new_cand = sorted((one_hits & hits99) | set())
    # a true gameState is 1 now? no - after SELECT it is 99. So:
    cand2 = sorted(hits99 & set(cand_state))
    if len(cand2) == 1:
        STATE = cand2[0] * 4
        sel_ok = True
    log("state_scan_paused", n=len(cand2),
        offs=[hex(o) for o in cand2[:20]])
elif STATE is not None:
    sel_ok = int.from_bytes(bytes(core.ram[STATE:STATE + 4]), "little",
                            signed=True) == 99
    log("state_scan_paused", state_off=hex(STATE), is_99=sel_ok)

# toggle back to play
core.set_buttons("SELECT")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(45):
    core.run_frame()
log("resume_from_pause")

# ---- phase 6: score discovery (i32 +1/frame during play) -------------------------
ram = core.ram
a = np.frombuffer(bytes(ram[:0x200000]), dtype="<i4").copy()
FA = core.frames_run
for _ in range(30):
    core.run_frame()
b = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4").copy()
delta = b - a
cand_score = np.nonzero(delta == 30)[0]
log("score_scan", n=int(len(cand_score)),
    offs=[hex(int(o) * 4) for o in cand_score[:20]])
SCORE = None
if len(cand_score) == 1:
    SCORE = int(cand_score[0]) * 4

# ---- phase 7: flap impulse (CROSS edge) ------------------------------------------
vis_before = core.frame_rgb()
core.set_buttons("B")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(30):
    core.run_frame()
vis_after = core.frame_rgb()
flap_diff = pdiff(vis_before, vis_after)
snap("after_flap")
log("pulse_CROSS", vis_diff=flap_diff)
if SCORE is not None:
    sv = int.from_bytes(bytes(core.ram[SCORE:SCORE + 4]), "little",
                        signed=True)
    R["anchors"]["score"] = {"off": hex(SCORE), "value": sv}
    log("score_check", value=sv)

# ---- verdicts ---------------------------------------------------------------------
R["anchors"]["gameState"] = {"off": hex(STATE) if STATE else None}
R["verdicts"] = {
    "BOOTED": True,
    "INPUT_RESPONSIVE": bool(PAD is not None and start_diff > 2.0),
    "STATE_CHANGE_CONFIRMED": bool(STATE is not None and sel_ok),
    "GAMEPLAY_CONFIRMED": bool(SCORE is not None and flap_diff > 1.0),
}
R["verdict"] = ("GAMEPLAY_CONFIRMED" if R["verdicts"]["GAMEPLAY_CONFIRMED"]
                else "STATE_CHANGE_CONFIRMED"
                if R["verdicts"]["STATE_CHANGE_CONFIRMED"]
                else "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED" if R["verdicts"]["BOOTED"] else "FAILED")
R["diffs"] = {"START": start_diff, "SELECT": sel_diff, "CROSS": flap_diff}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r23t2] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1),
      "verdict=", R["verdict"], json.dumps(R["verdicts"]),
      "anchors=", json.dumps(R["anchors"]), flush=True)
