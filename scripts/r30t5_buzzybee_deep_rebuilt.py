#!/usr/bin/env python3
"""r30t5_buzzybee_deep_rebuilt.py — Round 30: BuzzyBee deep systems on the
REBUILT beetle core.

Environment repair (disclosed, zero boots): the 5th filesystem rollback
reverted ps1-test/cores/mednafen_psx_libretro.so to the Oct-19 binary
(md5 79f8fac0...) and destroyed the documented self-built core (md5
f3b4a4be..., *.orig.so gone). On 79f8fac0, BuzzyBee's input.c driver
(InitPAD/StartPAD + ChangeClearPAD(0)) receives NO button bits while
(a) the kernel padbuf IS polled (input_pad=0x0000 released-state, not
stuck 0xFFFF), (b) Tetrade's BIOS-pad path DOES receive buttons on the
same binary (r30t4: padbuff 0041ffbf during a CROSS hold), and (c) a
direct-SIO game (MSPSX r29) works. ReARMed also delivers nothing to
BuzzyBee (r30t3). The core was REBUILT from the vendored df2b53b source
tree (md5 447b7ebf..., GIT_VERSION " 83b8cfc"; the f3b4a4be binary is
unreproducible - build nondeterminism) and swapped in; the rollback
binary is retained as mednafen_psx_libretro_79f8fac0_rollback.so.

Fresh per-core ledger (r26 per-backend convention), cap 2, boot 2 =
script-bug retry only.

Deep program (identical to the r30t1 design):
  A settle 900f -> START -> gameState 1
  B run 1: health trajectory classification (-3/f drain, <=-1500 enemy
    edge, >=+500 flower edge), CROSS flap bursts
  C death: gameState 5, bestScore == final score, PNG
  D auto-return: gameState 0, score 0, bestScore persisted
  E run 2: death again -> bestScore == max() verified
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
BOOTS = os.path.join(OUT, "boots_used_beetle_rebuilt.json")

GS, BEST, SCORE, HEALTH = 0x80058830, 0x80058838, 0x8005883C, 0x8005EF48
IN_PAD = 0x8005881C

R = {"task": "r30t5 BuzzyBee deep on rebuilt beetle core (447b7ebf)",
     "core": "mednafen_psx_libretro.so md5 447b7ebf9e0805d0ebb222256ed62958 "
             "(rebuilt from vendored df2b53b source; rollback binary "
             "79f8fac0 retained alongside)",
     "cap_policy": "cap 2 (fresh per-core ledger); boot 2 = script-bug "
                   "retry only",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r30t5.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r30t5] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"rb_{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


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
assert not os.path.exists(BOOTS), "rebuilt-core ledger exists - abort"
json.dump({"count": 1, "cap": 2, "cap_policy": R["cap_policy"],
           "core_note": R["core"],
           "log": [{"boot": 1, "script": "r30t5_buzzybee_deep_rebuilt.py",
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws_rb")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

# ---- A: settle -> START -> gameState 1 ---------------------------------------
for _ in range(900):
    core.run(1, set())
st = sym()
log("settle", sym=st)
snap("title")
core.run(3, {"START"})
core.run(60, set())
for _ in range(600):
    core.run(1, set())
    if i32(GS) == 1:
        break
gs1 = i32(GS)
log("play_start", gs=gs1, pad=u16(IN_PAD))
snap("play")

if gs1 != 1:
    R["verdict"] = ("rebuilt core ALSO delivers no input to BuzzyBee - "
                    "the variable is NOT the core binary; park R30 "
                    "buzzybee with the full investigation")
    log("verdict", verdict=R["verdict"])
    R["frames_total"] = core.frames_run
    R["finished"] = time.strftime("%FT%TZ", time.gmtime())
    dump()
    led = json.load(open(BOOTS))
    led["log"][0]["outcome"] = R["verdict"]
    json.dump(led, open(BOOTS, "w"), indent=1)
    print("[r30t5] DONE (negative)", flush=True)
    sys.exit(0)

# ---- B: run 1 -------------------------------------------------------------------
s1 = run_play(2400)
c1 = classify(s1)
R["run1"] = {"class": c1, "score_end": s1[-1][1]}
log("run1_done", **R["run1"])

# ---- C: death --------------------------------------------------------------------
st_death = sym()
snap("gameover")
R["death1"] = {"state": st_death,
               "best_eq_score": st_death["best"] == st_death["score"]}
log("death1", **R["death1"])
assert st_death["gameState"] == 5, f"expected 5: {st_death}"
S1 = st_death["score"]

# ---- D: auto-return ----------------------------------------------------------------
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

# ---- E: run 2 + max() ----------------------------------------------------------------
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
R["verdict"] = ("DEEP_SYSTEMS_OK on rebuilt core (drain classified x2, "
                "death->bestScore causality, auto-return, bestScore=max)"
                if ok else "PARTIAL - see logs")
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
led = json.load(open(BOOTS))
led["log"][0]["outcome"] = R["verdict"]
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t5] DONE", R["verdict"], flush=True)
