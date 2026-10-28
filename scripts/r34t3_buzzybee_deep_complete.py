#!/usr/bin/env python3
"""r34t3_buzzybee_deep_complete.py — Round 34: BuzzyBee DEEP SYSTEMS
completion pass (the "کامل کامل" run) — r30t1's plan executed with
correct addressing after the r34 artifact correction.

Source ground truth (github.com/NDR008/BuzzyBee @ master, via
engine/input.c + main.c, per r30t1 header):
  mainHealth.level i32: init 5999, cap 5999, PASSIVE DRAIN -3/frame
  in gameMode; enemy contact -1500 EDGE-triggered; flower contact
  +1000 (edge); level<0 -> clamp 0, bestScore = max(bestScore, score),
  gameState = 5; gs 5 renders "Your Last attempt: %d / Your Best
  score: %d" and AUTO-RETURNS to gs 0 (score=0, full re-init) after
  time2-time3 > 6s (bestScore NOT reset); score += 1/frame in
  gameMode; gameState 99 = debugMode (SELECT).
r23 live-verified anchors: gameState 0x80058830, bestScore
0x80058838, score 0x8005883C, mainHealth 0x8005EF48.
r34t2 re-verified: input ALIVE (gs 0->1 on START, score rises on
CROSS), kernel padbuf bytes land — the r30 regression premise is
refuted as an observation artifact.

Phases (event-driven waits, frame ceilings as honesty bounds):
  A settle -> gs 0 -> START -> gs 1 (run 1 begins, health 5999)
  B run 1 IDLE death: sample health/score every 30f until gs 5
    (ceiling 2600f); classify health deltas (-3 drain dominant;
    -1500 enemy / +1000 flower events recorded if they occur);
    bestScore == S1 at death
  C gs 5 screen PNG ("Your Last attempt")
  D auto-return: wait until gs 0 (ceiling 500f), score == 0,
    bestScore == S1 retained
  E run 2: START -> gs 1; flap bursts (CROSS 6f every 30f) to push
    S2 > S1; then idle to death (ceiling 2600f)
  F death 2: bestScore == max(S1, S2); PNG; final verdict
    ALL_PHASES_OK iff every assertion above held.

Cap amendment 3->4 DISCLOSED PRE-RUN (r34 ledger): boot 4 = the deep
systems completion pass. Verdict ladder: this pass, if green,
completes buzzybee's systems closure (input -> gameplay -> scoring ->
death -> game-over -> auto-return -> bestScore persistence across
runs) — on top of r23's GAMEPLAY_CONFIRMED and r29's mspSX bot, per
the user's complete-the-two-games directive.
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

GS, BEST, SCORE, HEALTH = 0x80058830, 0x80058838, 0x8005883C, 0x8005EF48

R = {"task": "r34t3 BuzzyBee deep systems completion pass",
     "cap_policy": "amendment 3->4 DISCLOSED PRE-RUN: boot 4 = deep "
                   "systems completion pass",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r34t3.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r34t3] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def i32(va):
    off = va - 0x80000000
    return int.from_bytes(bytes(core.ram[off:off + 4]), "little",
                          signed=True)


def state():
    return {"gs": i32(GS), "best": i32(BEST), "score": i32(SCORE),
            "health": i32(HEALTH)}


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)

led = json.load(open(BOOTS))
assert led["count"] == 3, "expected r34t2 to have consumed 3"
led["amendments"].append({"from": 3, "to": 4,
                          "reason": "r34t3 deep systems completion pass, "
                                    "disclosed pre-run"})
led["count"] = 4
led["log"].append({"boot": 4, "script": "r34t3_buzzybee_deep_complete.py",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws_deep")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(BUZZ)
log("boot", core=core.core_name, av=av)

OK = {}

# ---- A: settle -> title -> START -> run 1 -----------------------------
for _ in range(900):
    core.run(1, set())
st = state()
OK["A_title_gs0"] = bool(st["gs"] == 0)
log("A_title", **st)
snap("A_title")

core.set_buttons("START")
for _ in range(40):
    core.run_frame()
core.set_buttons(set())
st = state()
OK["A_run1_started"] = bool(st["gs"] == 1)
OK["A_health_5999"] = bool(st["health"] == 5999)
log("A_run1_start", **st)
snap("A_run1")

# ---- B: run 1 idle death (passive drain) ------------------------------
traj = []
deltas = []
last_h, last_s = st["health"], st["score"]
death_f = None
for i in range(2600):
    core.run(1, set())
    if i % 30 == 0:
        s = state()
        traj.append({"f": core.frames_run, **s})
        dh, ds = s["health"] - last_h, s["score"] - last_s
        if dh != 0 or ds != 0:
            deltas.append({"f": core.frames_run, "dh": dh, "ds": ds})
        last_h, last_s = s["health"], s["score"]
    if i32(GS) == 5:
        death_f = core.frames_run
        break
st = state()
S1 = st["best"]
OK["B_run1_death"] = bool(st["gs"] == 5)
OK["B_best_eq_S1"] = bool(st["best"] == st["score"]) if death_f else False
drains = [d for d in deltas if d["dh"] == -3]
enemies = [d for d in deltas if d["dh"] <= -1500]
flowers = [d for d in deltas if d["dh"] >= +1000]
R["B_traj"] = traj[::4]
R["B_deltas_head"] = deltas[:40]
log("B_run1_death", death_f=death_f, **st,
    drain_samples=len(drains), enemy_hits=len(enemies),
    flower_hits=len(flowers),
    dh_classified=len(deltas), S1=S1,
    score_at_death=st["score"])
snap("B_death_screen")

# ---- D: auto-return to title ------------------------------------------
ret_f = None
for i in range(600):
    core.run(1, set())
    if i32(GS) == 0:
        ret_f = core.frames_run
        break
st = state()
OK["D_auto_return"] = bool(st["gs"] == 0)
OK["D_score_reset"] = bool(st["score"] == 0)
OK["D_best_retained"] = bool(st["best"] == S1)
log("D_auto_return", ret_f=ret_f, waited=ret_f - death_f if ret_f and
    death_f else None, **st)
snap("D_returned_title")

# ---- E: run 2 with flap bursts ----------------------------------------
core.set_buttons("START")
for _ in range(40):
    core.run_frame()
core.set_buttons(set())
st = state()
OK["E_run2_started"] = bool(st["gs"] == 1)
log("E_run2_start", **st)

flaps = 0
for i in range(2600):
    core.run(1, set())
    if i % 30 == 0 and i32(GS) == 1:
        core.set_buttons("B")
        for _k in range(6):
            core.run_frame()
        core.set_buttons(set())
        flaps += 1
    if i32(GS) == 5:
        break
st = state()
S2 = st["score"]
OK["E_run2_death"] = bool(st["gs"] == 5)
log("E_run2_death", flaps=flaps, **st, S2=S2)
snap("E_death2_screen")

# ---- F: bestScore == max(S1, S2) --------------------------------------
OK["F_best_max"] = bool(st["best"] == max(S1, S2))
log("F_best_max", S1=S1, S2=S2, best=st["best"],
    expected=int(max(S1, S2)), ok=bool(st["best"] == max(S1, S2)))

verdict = {"ALL_PHASES_OK": bool(all(OK.values())), "phases": OK,
           "S1": S1, "S2": S2, "best_final": st["best"]}
R["verdict"] = verdict
log("verdict", **verdict)

json.dump(R, open(os.path.join(OUT, "boot_log_r34t3.json"), "w"),
          indent=1, default=str)
print("[r34t3] DONE", flush=True)
