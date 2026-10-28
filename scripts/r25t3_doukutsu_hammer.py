#!/usr/bin/env python3
"""r25t3_doukutsu_hammer.py — Round 25 boot 7: hammer the intro.

Lessons so far (all disclosed in boots_used.json):
  - boot 4: 26 dialog pulses insufficient (terminal scene PNG'd)
  - boot 5: crashed (NameError) after diagnosing detector noise
  - boot 6: two-round detector agreement still passes typewriter noise
    (idle_overlap 81/84 -> movers were time-driven; verdict honestly
    did NOT claim gameplay)

New approach for boot 7 (cap 6 -> 7, disclosed pre-run): press CROSS
100 times (fast 2f holds), PNG every 10 pulses, NO mid-run detection.
Then at the END:
  - double-detector (idle vs LEFT vs RIGHT, two agreeing rounds)
  - revert test: cand bytes that return to their pre-hold value after
    the opposite-direction hold (position class, not typewriter)
  - full 30f movement anchors + visual scroll + idle ablation
  - dialog-box region stats (bottom strip) recorded for offline review
Verdicts stay conservative; the PNG trail is the ground truth for
offline attribution.
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

R = {"task": "r25t3 doukutsu intro hammer (100 CROSS) + end detector",
     "boot_amendment": "cap 6->7 disclosed pre-run (boot 6: detector "
                       "false positive at batch 0, idle_overlap 81/84 "
                       "proved movers time-driven; no gameplay claim)",
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
    print(f"[r25t3] {json.dumps(rec, default=str)[:230]}", flush=True)
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


T0 = time.time()
GIF = []
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 6, f"boot counter {n0} != 6"
json.dump({"count": 7,
           "amendments": [
               {"from": 1, "to": 2, "reason": "boot-1 settle bug"},
               {"from": 2, "to": 3, "reason": "boot-2 probes hit intro "
                                             "cutscene"},
               {"from": 3, "to": 4, "reason": "r24 ledger 3/3"},
               {"from": 4, "to": 5, "reason": "r25t1 26 pulses insufficient"},
               {"from": 5, "to": 6, "reason": "boot 5 NameError crash"},
               {"from": 6, "to": 7,
                "reason": "boot 6 detector false positive (typewriter "
                          "noise reproduces across rounds); hammer "
                          "approach: no mid-run detection",
                "disclosed": "pre-run of r25t3"}],
           "log": [
               {"boot": 1, "script": "r24t1", "outcome": "FAILED (settle)"},
               {"boot": 2, "script": "r24t1", "outcome": "cutscene->menu"},
               {"boot": 3, "script": "r24t2", "outcome": "3 rungs (r24)"},
               {"boot": 4, "script": "r25t1", "outcome": "NO_MOVE_ANCHOR"},
               {"boot": 5, "script": "r25t2", "outcome": "CRASHED"},
               {"boot": 6, "script": "r25t2 fixed",
                "outcome": "detector FP, honest NO gameplay claim"},
               {"boot": 7, "script": "r25t3_doukutsu_hammer.py",
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

# ---- phase 2: hammer 100 CROSS pulses, PNG every 10 ---------------------
for i in range(100):
    core.run(2, {"B"})
    core.run(25, set())
    if (i + 1) % 10 == 0:
        f = snap(f"hammer_{i + 1:03d}")
        log("hammer", n=i + 1, mean=round(float(f.mean()), 2)
            if f is not None else None)
snap("after_hammer")

# ---- phase 3: end detectors ---------------------------------------------
def det_once():
    A0 = ram_arr().copy()
    core.run(90, set())
    A1 = ram_arr().copy()
    idle = set(int(i) for i in np.nonzero(A0 != A1)[0])
    core.run(12, {"LEFT"})
    core.run(18, set())
    A2 = ram_arr().copy()
    left = set(int(i) for i in np.nonzero(A1 != A2)[0]) - idle
    core.run(12, {"RIGHT"})
    core.run(18, set())
    A3 = ram_arr().copy()
    right = set(int(i) for i in np.nonzero(A2 != A3)[0]) - idle
    return A1, A2, A3, idle, left & right


B1, _, _, _, c1 = det_once()
B2, _, _, _, c2 = det_once()
cand = c1 & c2
log("detector", c1=len(c1), c2=len(c2), cand=len(cand),
    head=[hex(i) for i in sorted(cand)[:16]])

# revert test: LEFT hold then RIGHT hold -> bytes returning to base
base = ram_arr().copy()
core.run(20, {"LEFT"})
core.run(20, set())
after_l = ram_arr().copy()
core.run(20, {"RIGHT"})
core.run(20, set())
after_r = ram_arr().copy()
reverted = sorted(i for i in cand
                  if base[i] != after_l[i] and after_r[i] == base[i])
log("revert_test", reverted=len(reverted),
    head=[hex(i) for i in reverted[:16]])

# dialog-box region stats (bottom strip) for offline review
fr = core.frame_rgb()
if fr is not None:
    strip = fr[175:235, 40:280].astype(int)
    R["bottom_strip"] = {"mean": round(float(strip.mean()), 2),
                         "std": round(float(strip.std()), 2)}

# ---- phase 4: full movement anchors -------------------------------------
persistent, idle_only, vd_l, vd_r, ctrl2 = [], set(), -1.0, -1.0, []
if len(cand) >= 4:
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
    A0 = ram_arr().copy()
    core.run(90, set())
    A1 = ram_arr().copy()
    idle_only = set(int(i) for i in np.nonzero(A0 != A1)[0]) & set(persistent)
    log("idle_ablation", idle_overlap=len(idle_only))
    for _ in range(4):
        a = core.frame_rgb()
        core.run(30, set())
        ctrl2.append(mad(a, core.frame_rgb()))
snap("final_state")

# ---- verdicts -------------------------------------------------------------
anchor_ok = (len(persistent) >= 8
             and len(idle_only) < len(persistent) // 2)
vis_ok = (vd_l > 2 * max(ctrl2 or [0.05]) or
          vd_r > 2 * max(ctrl2 or [0.05]))
R["verdicts"] = {
    "CAND_DETECTED": bool(len(cand) >= 4),
    "REVERT_CLASS": bool(len(reverted) >= 2),
    "GAMEPLAY_CONFIRMED": bool(anchor_ok and (vis_ok or len(persistent) >= 24)),
}
R["verdict"] = ("GAMEPLAY_CONFIRMED" if R["verdicts"]["GAMEPLAY_CONFIRMED"]
                else "CAND_DETECTED" if R["verdicts"]["CAND_DETECTED"]
                else "STILL_INTRO")
R["final"] = {"cand": len(cand), "reverted": len(reverted),
              "persistent": len(persistent), "idle_overlap": len(idle_only),
              "vd_l": vd_l, "vd_r": vd_r, "ctrl2": ctrl2}

if GIF:
    out = os.path.join(REPO, "docs", "evidence_gifs",
                       "r25_doukutsu_movement.gif")
    ims = [Image.fromarray(a) for a in GIF[::2]]
    ims[0].save(out, save_all=True, append_images=ims[1:],
                duration=50, loop=0, optimize=True)
    R["gif"] = out
    print("[r25t3] gif:", out, os.path.getsize(out), "bytes")

R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r25t3] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
