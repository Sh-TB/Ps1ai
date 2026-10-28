#!/usr/bin/env python3
"""r28t3_airhockey_endgame.py — Round 28 boot 6: decisive chase with
boot-5 pre-seeded word pins.

Boot-5 (interrupted, no verdict, disclosed) left partial pins before the
session cutoff:
  0x8009be3e corr -0.859 range [239,384]
  0x8009be40 corr -0.900 range [4434,4706]
  0x8009be56 corr -0.839 range [3813,4450]
  0x801ffe** corr +0.85..0.88 (timer class - EXCLUDED this boot)

Boot cap 5 -> 6 (disclosed pre-run). Boot 6 plan:
  P1 entry (r21-proven path, byte-identical timings)
  P2 live re-verification of the 3 seeded pins under a short-hold
     L/R plan (no discovery phase - seeds only), pick the live one
  P3 puck word via idle red-ring correlation (excluding >=0x801ff000
     and the paddle word itself)
  P4 5400-step word-space chase + top-RIGHT score-box watch + PNG trail

Success = >=1 score-box change with PNGs while the chase tracks; honest
negative otherwise -> air_hockey PARKED at RUNNING (r22 rung) per the
"user directive: do not get stuck".
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

OUT = os.path.join(REPO, "scratch", "r28", "airhockey")
SHOTS = os.path.join(OUT, "shots")
CONTENT = ("/home/z/my-project/emu/games_small/extracted/"
           "air_hockey_norm/Air Hockey (USA) 2352.cue")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

SEEDS = [0x8009BE3E, 0x8009BE40, 0x8009BE56]

R = {"task": "r28t3 air hockey endgame: seeded-pin chase + score watch",
     "boot_amendment": "cap 5->6 disclosed pre-run: boot 5 (wordspace) was "
                       "interrupted by session cutoff BEFORE any verdict; "
                       "its partial paddle_pins are logged in boot_log.json "
                       "and reused as seeds here",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r28t3.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r28t3] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def u16():
    return np.frombuffer(bytes(core.ram), dtype="<u2").astype(np.int32)


def widx(addr):
    return (addr - 0x80000000) // 2


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)

# ---- honest ledger ---------------------------------------------------------
led = json.load(open(BOOTS))
assert led["count"] == 5 and led["log"][-1]["boot"] == 5
led["amendments"].append({
    "from": 5, "to": 6,
    "reason": "boot 6 = decisive seeded-pin chase (seeds from boot-5 "
              "partial data); if inconclusive air_hockey PARKS at RUNNING",
    "disclosed": "pre-run"})
led["log"][-1]["outcome"] = ("INTERRUPTED by session cutoff, no verdict; "
                             "partial pins logged (0x8009be3e/40/56 corr "
                             "-0.84..-0.9; 0x801ffe* timer class)")
led["log"].append({"boot": 6, "script": "r28t3_airhockey_endgame.py",
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

# ---- P1: entry (r21-proven path) -------------------------------------------
core.run(2000, set())
core.run(3, {"START"})
core.run(300, set())
core.run(3, {"B"})
core.run(500, set())
core.run(3, {"O"})
core.run(300, set())
for _ in range(40):
    core.run(60, set())
game = snap("live_match")
log("entry", mean=round(float(game.mean()), 2))
core.run(120, set())


def blue_cx_loose(fr):
    if fr is None:
        return np.nan
    bot = fr[100:235, 20:300]
    m = (bot[:, :, 2].astype(int) - bot[:, :, 0] > 25) & \
        (bot[:, :, 2].astype(int) - bot[:, :, 1] > 15)
    ys, xs = np.nonzero(m)
    if 15 < len(xs) < 8000:
        return float(xs.mean()) + 20
    return np.nan


def red_cx(fr):
    if fr is None:
        return np.nan
    tbl = fr[40:215, 60:262]
    m = (tbl[:, :, 0] > 140) & (tbl[:, :, 1] < 110) & (tbl[:, :, 2] < 110)
    ys, xs = np.nonzero(m)
    if 20 < len(xs) < 4000:
        return float(xs.mean()) + 60
    return np.nan


# ---- P2: re-verify the 3 seeded pins ---------------------------------------
plan = [("LEFT", 14), ("IDLE", 10), ("RIGHT", 14), ("IDLE", 10),
        ("LEFT", 14), ("IDLE", 10), ("RIGHT", 14), ("IDLE", 10)]
u16_series, blues = [], []
for btn, n in plan:
    for _ in range(n):
        core.run(2, {btn} if btn != "IDLE" else set())
        blues.append(blue_cx_loose(core.frame_rgb()))
        u16_series.append(u16())
A = np.stack(u16_series)
bx = np.array(blues)
v = ~np.isnan(bx)
log("probe_done", n_frames=A.shape[0], blue_valid=int(v.sum()),
    mean=round(float(np.nanmean(bx)), 1) if v.any() else None)

pin_scores = []
for addr in SEEDS:
    i = widx(addr)
    vv = A[:, i]
    if vv[v].std() < 1:
        pin_scores.append({"addr": hex(addr), "corr": None,
                           "note": "no variance"})
        continue
    a = bx[v] - bx[v].mean()
    b = vv[v] - vv[v].mean()
    d = a.std() * b.std()
    c = float((a * b).mean() / d) if d > 0 else 0.0
    pin_scores.append({"addr": hex(addr), "corr": round(c, 3),
                       "range": [int(vv[v].min()), int(vv[v].max())]})
log("seed_verify", seeds=pin_scores)

pin_i, pin_addr = None, None
for rec in pin_scores:
    if rec["corr"] is not None and abs(rec["corr"]) > 0.75:
        pin_i = widx(int(rec["addr"], 16))
        pin_addr = rec["addr"]
        break
log("pin_choice", pin=pin_addr)
snap("after_paddle_probes")

# ---- P3: puck word via red-ring idle correlation ----------------------------
u16_series2, reds = [], []
for _ in range(150):
    core.run(2, set())
    reds.append(red_cx(core.frame_rgb()))
    u16_series2.append(u16())
B2 = np.stack(u16_series2)
rx = np.array(reds)
v2 = ~np.isnan(rx)
log("red_valid", n=int(v2.sum()),
    mean=round(float(np.nanmean(rx)), 1) if v2.any() else None)
best2 = []
busy2 = np.nonzero((np.abs(np.diff(B2, axis=0)) > 0).sum(axis=0)
                   > 75)[0]
for i in busy2:
    if pin_i is not None and i == pin_i:
        continue
    if 0x801FF000 <= 0x80000000 + i * 2:      # timer cluster excluded
        continue
    vv = B2[:, i]
    if vv[v2].std() < 1:
        continue
    a = rx[v2] - rx[v2].mean()
    b = vv[v2] - vv[v2].mean()
    d = a.std() * b.std()
    if d > 0:
        c = float((a * b).mean() / d)
        if abs(c) > 0.6:
            best2.append((abs(c), int(i), int(vv[v2].min()),
                          int(vv[v2].max())))
best2.sort(reverse=True)
puck_i = best2[0][1] if best2 else None
log("puck_word",
    addr=hex(0x80000000 + puck_i * 2) if puck_i is not None else None,
    n=len(best2), top=[(round(c, 3), hex(0x80000000 + i * 2), [lo, hi])
                       for c, i, lo, hi in best2[:5]])

# ---- P4: chase + score watch -------------------------------------------------
res = {"attempted": bool(pin_i is not None and puck_i is not None),
       "paddle": pin_addr,
       "puck": hex(0x80000000 + puck_i * 2) if puck_i is not None else None}
if res["attempted"]:
    w0 = int(u16()[pin_i])
    core.run(6, {"RIGHT"})
    core.run(6, set())
    w1 = int(u16()[pin_i])
    right_dir = 1 if w1 > w0 else -1
    res["calib"] = {"w0": w0, "w1": w1, "right_dir": right_dir}
    snap("calibrated")

    prev_score = None
    events = []
    pushes = 0
    for step in range(1, 5401):
        pw = int(u16()[pin_i])
        px = int(u16()[puck_i])
        diff = px - pw
        btn = set()
        if abs(diff) > 24:
            if (diff > 0) == (right_dir > 0):
                btn = {"RIGHT"}
            else:
                btn = {"LEFT"}
        elif diff < -24:
            btn = {"RIGHT"} if right_dir > 0 else {"LEFT"}
        core.run(2, btn)
        if btn:
            pushes += 1
        if step % 10 == 0:
            f2 = core.frame_rgb()
            if f2 is not None:
                box = f2[6:36, 205:318].tobytes()
                if prev_score is not None and box != prev_score:
                    events.append({"f": core.frames_run, "step": step,
                                   "pw": pw, "px": px})
                    snap(f"score_change_{len(events)}")
                prev_score = box
        if step % 900 == 0:
            snap(f"rally_{step}")
            log("rally", step=step, pw=pw, px=px,
                score_changes=len(events))
    res["steps"] = 5400
    res["pushes"] = pushes
    res["score_changes"] = len(events)
    res["events_head"] = events[:12]
    snap("post_rally")
log("goal_campaign", **res)

R["final"] = {"seed_verify": pin_scores, "goal": res}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()

# honest verdict helper
verdict = "INCONCLUSIVE"
if res.get("attempted") and res.get("score_changes", 0) >= 1:
    verdict = ("SCORE_EVENTS_OBSERVED with chase live (paddle %s corr "
               "> 0.75) - PNGs decide our-goal vs CPU-goal" % pin_addr)
elif res.get("attempted"):
    verdict = "chase ran, no score change observed - honest negative"
R["verdict"] = verdict
dump()
led["log"][-1]["outcome"] = verdict
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r28t3] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", verdict, flush=True)
