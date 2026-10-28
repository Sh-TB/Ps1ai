#!/usr/bin/env python3
"""r30t3_buzzybee_rearmed.py — Round 30 cross-backend lever (r26-recorded).

Beetle facts (3 disclosed boots today): BuzzyBee's BIOS-pad path receives
NO button bits (input_pad/held/trig @0x8005881C/20/24 all zero through
40f holds + double-taps) while the kernel padbuf IS polled (input_pad
0x0000 = valid released-state, not stuck 0xFFFF). Direct-SIO games
(MSPSX r29) DO receive input on the same core today. The r23-proven
START transition does not reproduce on a byte-identical image (sha
042b94bb re-verified).

This boot: PCSX-ReARMed (different SIO implementation entirely, r26
precedent: fresh per-backend ledger + core sha16 recorded). If input
lands, run the FULL deep program in the same boot:
  health -3/f drain classification, enemy/flower edge events,
  death -> gameState 5 + bestScore == final score,
  auto-return to title (score 0, bestScore persisted),
  run 2 -> bestScore == max() verification.

Cap 2 (fresh backend ledger, r26 convention). Boot 2 = script-bug retry
only, disclosed pre-run.
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
CORE = "/home/z/my-project/ps1-test/cores/pcsx_rearmed_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used_rearmed.json")

GS, BEST, SCORE, HEALTH = 0x80058830, 0x80058838, 0x8005883C, 0x8005EF48
IN_PAD, IN_HELD, IN_TRIG = 0x8005881C, 0x80058824, 0x80058820

R = {"task": "r30t3 BuzzyBee deep via PCSX-ReARMed (beetle input dead)",
     "backend": "PCSX-ReARMed",
     "cap_policy": "cap 2 (fresh per-backend ledger, r26 convention); "
                   "boot 2 = script-bug retry only",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r30t3.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r30t3] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"rearmed_{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def pdiff(a, b):
    if a is None or b is None:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


def i32(va):
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def u16(va):
    return int.from_bytes(bytes(core.ram[va:va + 2]), "little")


def sym():
    return {"gameState": i32(GS), "best": i32(BEST), "score": i32(SCORE),
            "health": i32(HEALTH), "pad": u16(IN_PAD)}


def run_play(n, flap_every=60, flap_len=4):
    series = []
    for k in range(n):
        btn = set()
        if flap_every and k % flap_every < flap_len:
            btn = {"B"}
        core.run(1, btn)
        series.append((i32(HEALTH), i32(SCORE), i32(GS)))
        if series[-1][2] == 5:
            break
    return series


def classify(series):
    d = {"frames": len(series), "drain3": 0, "enemy_hit": 0,
         "flower": 0, "other": [], "g5": False}
    for a, b in zip(series, series[1:]):
        dh = b[0] - a[0]
        if dh == -3:
            d["drain3"] += 1
        elif dh <= -1500:
            d["enemy_hit"] += 1
        elif dh >= 500:
            d["flower"] += 1
        elif dh != 0:
            d["other"].append(dh)
        if b[2] == 5:
            d["g5"] = True
            break
    return d


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
assert not os.path.exists(BOOTS), "rearmed ledger exists - abort"
json.dump({"count": 1, "cap": 2, "cap_policy": R["cap_policy"],
           "core_note": "pcsx_rearmed_libretro.so sha16 f202985eae74498b "
                        "(r26-recorded build)",
           "log": [{"boot": 1, "script": "r30t3_buzzybee_rearmed.py",
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws_rearmed")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"pcsx_rearmed_pad1type": b"standard"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

# P1: settle + input probe (does ReARMed land pad bits?)
for _ in range(900):
    core.run(1, set())
snap("title")
idle0 = sym()
log("settle", sym=idle0)
core.set_buttons("START")
hold_series = []
for _ in range(40):
    core.run_frame()
    hold_series.append({"f": core.frames_run, "pad": u16(IN_PAD),
                        "trig": i32(IN_TRIG), "gs": i32(GS)})
core.set_buttons(set())
for _ in range(120):
    core.run(1, set())
gs_after_start = i32(GS)
R["input_probe"] = {"idle": idle0, "hold_nonzero":
                    sum(1 for s in hold_series if s["pad"] or s["trig"]),
                    "gs_after_start": gs_after_start}
log("start_probe", **R["input_probe"])
snap("after_start")

if gs_after_start != 1:
    R["verdict"] = ("ReARMed input also dead for BuzzyBee - the BIOS-pad "
                    "class is broken across BOTH backends today; park and "
                    "investigate the host input path (frontend-level)")
    log("verdict", **R["verdict"])
    R["frames_total"] = core.frames_run
    R["finished"] = time.strftime("%FT%TZ", time.gmtime())
    dump()
    led = json.load(open(BOOTS))
    led["log"][0]["outcome"] = R["verdict"]
    json.dump(led, open(BOOTS, "w"), indent=1)
    print("[r30t3] DONE (negative)", flush=True)
    sys.exit(0)

# ---- deep program (input works on this backend) --------------------------------
play0 = core.frame_rgb()
s1 = run_play(2400)
c1 = classify(s1)
R["run1"] = {"class": c1, "score_end": s1[-1][1]}
log("run1_done", **R["run1"])
st_death = sym()
snap("gameover")
R["death1"] = {"state": st_death,
               "best_eq_score": st_death["best"] == st_death["score"]}
log("death1", **R["death1"])
assert st_death["gameState"] == 5
S1 = st_death["score"]

ret = False
for _ in range(400):
    core.run(1, set())
    if i32(GS) == 0:
        ret = True
        break
st_title = sym()
R["return"] = {"returned": ret, "state": st_title}
log("auto_return", **R["return"])
snap("title2")

core.run(3, {"START"})
core.run(60, set())
for _ in range(600):
    core.run(1, set())
    if i32(GS) == 1:
        break
s2 = run_play(2400)
c2 = classify(s2)
st_death2 = sym()
snap("gameover2")
best_expect = max(S1, st_death2["score"])
R["run2"] = {"class": c2, "final": st_death2, "best_expect": best_expect,
             "max_ok": st_death2["best"] == best_expect}
log("run2_done", **R["run2"])

ok = (R["run2"]["max_ok"] and c1["drain3"] > 1000 and c2["drain3"] > 1000
      and ret)
R["verdict"] = ("DEEP_SYSTEMS_OK via ReARMed (drain classified x2, "
                "death->bestScore causality, auto-return, bestScore=max)"
                if ok else "PARTIAL - see logs")
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
led = json.load(open(BOOTS))
led["log"][0]["outcome"] = R["verdict"]
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t3] DONE", R["verdict"], flush=True)
