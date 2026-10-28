#!/usr/bin/env python3
"""r30t1_buzzybee_deep.py — Round 30: BuzzyBee deep systems pass.

Source ground truth (github.com/NDR008/BuzzyBee @ master, cloned today):
  Health mainHealth.level i32: init 5999, cap 5999, PASSIVE DRAIN -3/frame
  in gameMode; enemy contact -1500 EDGE-triggered (hitE && !oldHitE);
  flower contact +1000 (edge); level<0 -> clamp 0, bestScore = max(
  bestScore, score), gameState = 5; score += 1/frame in gameMode;
  gameState 5 renders "Your Last attempt: %d / Your Best score: %d" and
  AUTO-RETURNS to gameState 0 (score=0, full re-init) after time2-time3>6
  (bestScore NOT reset); gameState 99 = debugMode (r23's SELECT 1->99).
r23 live-verified: gameState 0x80058830, bestScore 0x80058838, score
0x8005883C, mainHealth 0x8005EF48; image = buzzybee_ntsc_lic.bin
(sha 042b94bb... rebuilt byte-identical today); ps1play B = PSX CROSS =
flap (input_trig & PAD_CROSS).

Boot cap 2 (disclosed pre-run: boot 2 = script-bug retry only; a
mechanics refutation parks honestly).

Phases:
  A boot -> title (gameState 0) -> START -> gameState 1
  B run 1: health/score trajectory classification (~2050f expected to
    death by drain; flap bursts for real play; hit events classified
    from deltas: -3 drain, <=-1500 enemy, >=+500 flower)
  C death: gameState 5, bestScore == final score, PNG game-over screen
  D auto-return to title (gameState 0, score 0, bestScore == S1)
  E run 2: START again, second death; bestScore = max() verified against
    whichever of S1/S2 is larger
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

GS, BEST, SCORE, HEALTH = 0x80058830, 0x80058838, 0x8005883C, 0x8005EF48

R = {"task": "r30t1 BuzzyBee deep systems (health/damage/death/bestScore)",
     "cap_policy": "cap 2 disclosed pre-run: boot 2 = script-bug retry "
                   "only; mechanics refutations park honestly",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r30t1] {json.dumps(rec, default=str)[:240]}", flush=True)
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
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def sym():
    return {"gameState": i32(GS), "best": i32(BEST), "score": i32(SCORE),
            "health": i32(HEALTH)}


def run_play(n, flap_every=60, flap_len=4):
    """Play n frames with periodic flap bursts; classify health deltas."""
    series = []
    for k in range(n):
        btn = set()
        if flap_every and k % flap_every < flap_len:
            btn = {"B"}
        core.run(1, btn)
        h, s, g = i32(HEALTH), i32(SCORE), i32(GS)
        series.append((h, s, g))
        if g == 5:
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
if os.path.exists(BOOTS):
    led0 = json.load(open(BOOTS))
    assert led0["count"] == 2 and led0["cap"] == 2, \
        f"ledger mismatch: {led0['count']}"
    print("[r30t1] running ARMED boot 2 (script-bug retry per policy)")
else:
    json.dump({"count": 1, "cap": 2, "cap_policy": R["cap_policy"],
               "note": "r23's 5 boots are recorded in manifest "
                       "accepted[buzzybee]; fresh per-round ledger",
               "log": [{"boot": 1, "script": "r30t1_buzzybee_deep.py",
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

# ---- A: title -> START -> play ----------------------------------------------
# NOTE: RAM is zero from frame 0, so gameState==0 alone is NOT a title
# signal - settle a fixed window first (r23 title lived ~f900), then
# require the title to be STABLE before pressing START.
for _ in range(900):
    core.run(1, set())
log("settle", sym=sym())
snap("title")
core.run(3, {"START"})
core.run(60, set())
for _ in range(600):
    core.run(1, set())
    if i32(GS) == 1:
        break
log("play_start", sym=sym())
snap("play")
assert i32(GS) == 1, f"START did not reach gameState 1: {sym()}"

# ---- B: run 1 with trajectory classification ---------------------------------
s1 = run_play(2400, flap_every=60, flap_len=4)
c1 = classify(s1)
h0, s0v, _ = s1[0]
R["run1"] = {"start": sym(), "class": c1,
             "health_range": [h0, s1[-1][0]],
             "score_end": s1[-1][1],
             "frames": len(s1)}
log("run1_done", **{k: v for k, v in R["run1"].items() if k != "start"})

# ---- C: death state ------------------------------------------------------------
st_death = sym()
snap("gameover")
R["death"] = {"state": st_death,
              "best_eq_score": st_death["best"] == st_death["score"]}
log("death", **R["death"])
assert st_death["gameState"] == 5, f"expected gameState 5: {st_death}"
assert st_death["best"] == st_death["score"], \
    f"bestScore != final score: {st_death}"
S1 = st_death["score"]

# ---- D: auto-return to title -----------------------------------------------------
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
assert ret and st_title["score"] == 0 and st_title["best"] == S1, \
    "auto-return state mismatch"

# ---- E: run 2 -> second death -> max() verification -------------------------------
core.run(3, {"START"})
core.run(60, set())
for _ in range(300):
    core.run(1, set())
    if i32(GS) == 1:
        break
s2 = run_play(2400, flap_every=60, flap_len=4)
c2 = classify(s2)
st_death2 = sym()
snap("gameover2")
best_expect = max(S1, st_death2["score"])
R["run2"] = {"class": c2, "final": st_death2,
             "best_expect": best_expect,
             "max_ok": st_death2["best"] == best_expect}
log("run2_done", **{k: v for k, v in R["run2"].items()
                    if k != "final"})
ok = (R["run2"]["max_ok"] and c1["drain3"] > 1000 and
      c2["drain3"] > 1000)
R["verdict"] = ("DEEP_SYSTEMS_OK (health drain -3/f classified, "
                "death->gameover->bestScore causality, auto-return, "
                "bestScore=max across two runs)" if ok else
                "PARTIAL - see run classifications")
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
led = json.load(open(BOOTS))
led["log"][0]["outcome"] = R["verdict"]
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t1] DONE", R["verdict"], "frames=", core.frames_run, flush=True)
