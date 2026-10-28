#!/usr/bin/env python3
"""r25t2_doukutsu_start.py — Round 25 boot 2: reach the Start Point room.

Boot-1 finding (r25t1, disclosed): 26 dialog-advance CROSS pulses are
NOT enough to leave the intro cutscene chain (PNGs show the terminal
scene 'Connecting to network...'); the RAM movers seen there are
cutscene timer/animation words, hence NO_MOVE_ANCHOR honestly recorded.

Boot cap amendment 4 -> 5 (disclosed pre-run). Program:
  intro --CROSS batches (6 pulses each, PNG trail)-->
  after EVERY batch run the in-game detector:
      idle watch 60f  ->  words that tick with time (cutscene timers)
      LEFT hold 8f    ->  words that respond to input
      RIGHT hold 8f   ->  confirmation
  in-game := exists words changed by BOTH move probes but by NONE of
  the idle watch (input-driven position class, not timers).
  When detected: full 30f movement anchors + visual scroll + GIF.
Honest failure mode: 15 batches exhausted -> NO_INGAME with full trail.
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

OUT = os.path.join(REPO, "scratch", "r25", "doukutsu")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/doukutsu_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

R = {"task": "r25t2 doukutsu Start Point + movement anchors",
     "boot_amendment": "cap 5->6 disclosed pre-run (boot 5 consumed by "
                       "a NameError crash in the idle-ablation line "
                       "A1->A_idle1 after full data collection; batch-0 "
                       "detector false positive also fixed: typewriter "
                       "dialog noise is transient, so the detector now "
                       "requires two consecutive agreeing rounds)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "gif_frames": 0}


def boots_used():
    if os.path.exists(BOOTS):
        return json.load(open(BOOTS)).get("count", 0)
    return 0


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r25t2] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag, gif=False):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
        if gif:
            GIF.append(arr.copy())
            R["gif_frames"] += 1
    return arr


def mad(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 3)


def ram_arr():
    return np.frombuffer(bytes(core.ram), dtype=np.uint8)


def diff_idx(a, b):
    return set(int(i) for i in np.nonzero(a != b)[0])


T0 = time.time()
GIF = []
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 5, f"boot counter {n0} != 5"
json.dump({"count": 6,
           "amendments": [
               {"from": 1, "to": 2, "reason": "boot-1 settle heuristic bug"},
               {"from": 2, "to": 3, "reason": "boot-2 probes hit intro "
                                             "cutscene; 0x9098 retracted"},
               {"from": 3, "to": 4, "reason": "r24 ledger 3/3; r25 needs "
                                              "fresh boot"},
               {"from": 4, "to": 5,
                "reason": "r25t1: 26 dialog pulses insufficient (intro "
                          "chain longer); batch+detector approach",
                "disclosed": "pre-run of r25t2"},
               {"from": 5, "to": 6,
                "reason": "boot 5: script NameError crash in idle-"
                          "ablation line after data collection; batch-0 "
                          "detector false positive (typewriter noise) "
                          "fixed with two-round agreement",
                "disclosed": "pre-run of r25t2 (fixed)"}],
           "log": [
               {"boot": 1, "script": "r24t1", "outcome": "FAILED (settle bug)"},
               {"boot": 2, "script": "r24t1", "outcome": "cutscene->menu"},
               {"boot": 3, "script": "r24t2",
                "outcome": "menu + New Game -> intro (3 rungs)"},
               {"boot": 4, "script": "r25t1",
                "outcome": "NO_MOVE_ANCHOR (still in intro chain, 26 "
                           "pulses insufficient; PNG'd terminal scene)"},
               {"boot": 5, "script": "r25t2_doukutsu_start.py",
                "outcome": "CRASHED (NameError in idle ablation, after "
                           "data collection; batch-0 detector false "
                           "positive diagnosed from its events)"},
               {"boot": 6, "script": "r25t2_doukutsu_start.py (fixed)",
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

# ---- phase 1: menu -> New -> intro --------------------------------------
while core.frames_run < 1200:
    core.run_frame()
core.run(4, {"B"})
core.run(90, set())
for k in range(20):
    core.run(60, set())
    a = core.frame_rgb()
    b = core.frame_rgb()
    core.run(60, set())
    c = core.frame_rgb()
    if mad(a, b) < 1.0 and mad(b, c) < 1.0 and 25 < float(b.mean()) < 45:
        break
snap("menu")
core.run(4, {"B"})
core.run(120, set())
snap("intro_start")
log("intro_reached")

# ---- phase 2: CROSS batches with the in-game detector -------------------
def detector_once():
    """idle watch vs LEFT/RIGHT probes -> input-driven byte set."""
    A0 = ram_arr().copy()
    core.run(60, set())                       # idle watch
    A1 = ram_arr().copy()
    idle = diff_idx(A0, A1)
    core.run(8, {"LEFT"})
    core.run(22, set())
    A2 = ram_arr().copy()
    left = diff_idx(A1, A2) - idle
    core.run(8, {"RIGHT"})
    core.run(22, set())
    A3 = ram_arr().copy()
    right = diff_idx(A2, A3) - idle
    return left & right, len(idle), len(left), len(right)


def detector():
    """Two consecutive rounds must agree: transient noise (typewriter
    dialog reveal) settles by round 2; player movement reproduces."""
    c1, i1, l1, r1 = detector_once()
    c2, i2, l2, r2 = detector_once()
    agree = c1 & c2
    return agree, (len(c1), len(c2), i1, i2, l1, l2, r1, r2)


ingame_f = None
cand = set()
batches = []
for b in range(20):
    for _ in range(6):
        core.run(3, {"B"})
        core.run(40, set())
    cand, det = detector()
    f = snap(f"batch_{b:02d}")
    rec = {"batch": b, "f": core.frames_run, "det": det,
           "cand": len(cand),
           "mean": round(float(f.mean()), 2) if f is not None else None}
    batches.append(rec)
    log("batch", **rec)
    if len(cand) >= 2:
        ingame_f = core.frames_run
        break
snap("ingame_candidate")

# ---- phase 3: full movement anchors (only if in-game) -------------------
GIF_ON = ingame_f is not None
persistent, idle_only, vd_l, vd_r, ctrl2 = [], set(), -1.0, -1.0, []
if GIF_ON:
    M0 = ram_arr().copy()
    pre = core.frame_rgb()
    core.run(30, {"LEFT"})
    for _ in range(12):
        core.run_frame()
        snap("mv", gif=True)
    core.run(40, set())
    M1 = ram_arr().copy()
    post_l = core.frame_rgb()
    vd_l = mad(pre, post_l)
    core.run(20, set())
    core.run(30, {"RIGHT"})
    for _ in range(12):
        core.run_frame()
        snap("mv", gif=True)
    core.run(40, set())
    M2 = ram_arr().copy()
    post_r = core.frame_rgb()
    vd_r = mad(post_l, post_r)
    core.run(20, set())
    M3 = ram_arr().copy()
    snap("after_moves")
    persistent = sorted(i for i in range(len(M1))
                        if M0[i] != M1[i] and M1[i] != M2[i]
                        and M2[i] != M3[i] and M0[i] != M3[i])
    log("moves", vd_l=vd_l, vd_r=vd_r, persistent=len(persistent),
        head=[hex(i) for i in persistent[:16]])

    # idle ablation control: NO input for 90f -> how many of the
    # persistent movers also move with time alone (timers)?
    A_idle0 = ram_arr().copy()
    core.run(90, set())
    A_idle1 = ram_arr().copy()
    idle_only = diff_idx(A_idle0, A_idle1) & set(persistent)
    log("idle_ablation", idle_overlap=len(idle_only))
    for _ in range(4):
        a = core.frame_rgb()
        core.run(30, set())
        ctrl2.append(mad(a, core.frame_rgb()))
snap("final_state")

# ---- verdicts -------------------------------------------------------------
anchor_ok = len(persistent) >= 4 and len(idle_only) < len(persistent) // 2
vis_ok = vd_l > 2 * max(max(ctrl2), 0.05) or vd_r > 2 * max(max(ctrl2), 0.05)
R["verdicts"] = {
    "START_POINT_REACHED": bool(ingame_f is not None),
    "GAMEPLAY_CONFIRMED": bool(ingame_f is not None and anchor_ok
                               and (vis_ok or len(persistent) >= 16)),
}
R["verdict"] = ("GAMEPLAY_CONFIRMED" if R["verdicts"]["GAMEPLAY_CONFIRMED"]
                else "START_POINT_REACHED" if ingame_f is not None
                else "STILL_INTRO")
R["final"] = {"ingame_f": ingame_f, "batches": batches,
              "cand": [hex(i) for i in sorted(cand)[:16]],
              "vd_l": vd_l, "vd_r": vd_r, "persistent": len(persistent),
              "idle_overlap": len(idle_only), "ctrl2": ctrl2}

if GIF:
    out = os.path.join(REPO, "docs", "evidence_gifs",
                       "r25_doukutsu_movement.gif")
    ims = [Image.fromarray(a) for a in GIF[::2]]
    ims[0].save(out, save_all=True, append_images=ims[1:],
                duration=50, loop=0, optimize=True)
    R["gif"] = out
    print("[r25t2] gif:", out, os.path.getsize(out), "bytes")

R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r25t2] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
