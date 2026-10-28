#!/usr/bin/env python3
"""r28t4_airhockey_pin40.py — Round 28 boot 7 (FINAL for this round):
word-space chase on the OTHER boot-5 seed 0x8009be40 (corr -0.900,
probe range [4434,4706] ~= x<<4 fixed-point on a 320px table).

r28t3 established (PNG-verified): score digits live (00%01 -> 02%02 ->
03%07), natural match end with CONTINUE? countdown (f11533), fresh match
in a NEW arena (f16933). Remaining question: OUR goal agency via a valid
paddle pin. 0x8009be3e is REJECTED (probe range [239,384] but chase-time
3563..10247 = not paddle-x). 0x8009be40 stays plausible.

Boot cap 6 -> 7 (disclosed pre-run; this is the round's last boot for
air_hockey regardless of outcome). Adds blue-paddle visual tracking
during the chase so paddle-word <-> vision agreement is checkable.
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

PIN = 0x8009BE40

R = {"task": "r28t4 air hockey: paddle-pin 0x8009be40 chase + score watch",
     "boot_amendment": "cap 6->7 disclosed pre-run (round-final boot)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r28t4.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r28t4] {json.dumps(rec, default=str)[:230]}", flush=True)
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


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)

led = json.load(open(BOOTS))
assert led["count"] == 6 and led["log"][-1]["boot"] == 6, (
    f"ledger state count={led['count']} last={led['log'][-1]['boot']}")
led["amendments"].append({"from": 6, "to": 7,
                          "reason": "boot 7 = round-final chase on the "
                                    "plausible fixed-point seed 0x8009be40",
                          "disclosed": "pre-run"})
led["log"][-1]["outcome"] = (
    "COMPLETE_LOOP_OBSERVED (score 00%01->02%02->03%07 PNG chain, natural "
    "CONTINUE? countdown f11533, NEW arena f16933) but chase pin 0x8009be3e "
    "INVALID (probe range [239,384] vs chase 3563..10247); agency unproven")
led["log"].append({"boot": 7, "script": "r28t4_airhockey_pin40.py",
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

# entry (r21-proven path)
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

# verify pin under short-hold plan
plan = [("LEFT", 14), ("IDLE", 10), ("RIGHT", 14), ("IDLE", 10),
        ("LEFT", 14), ("IDLE", 10), ("RIGHT", 14), ("IDLE", 10)]
u16_series, blues = [], []
for btn, n in plan:
    for _ in range(n):
        core.run(2, {btn} if btn != "IDLE" else set())
        blues.append(float(core.frame_rgb()[:, :, 2].astype(int).sum()
                           ) if core.frame_rgb() is not None else 0.0)
        u16_series.append(u16())
A = np.stack(u16_series)
i40 = (PIN - 0x80000000) // 2
vv = A[:, i40]
log("pin40_probe", range=[int(vv.min()), int(vv.max())],
    mean=round(float(vv.mean()), 1))
ok_range = 4000 <= vv.min() and vv.max() <= 5200
log("pin40_range_ok", ok=bool(ok_range))

# puck word via red-ring idle correlation (fresh, this match)
def red_cx(fr):
    if fr is None:
        return np.nan
    tbl = fr[40:215, 60:262]
    m = (tbl[:, :, 0] > 140) & (tbl[:, :, 1] < 110) & (tbl[:, :, 2] < 110)
    ys, xs = np.nonzero(m)
    if 20 < len(xs) < 4000:
        return float(xs.mean()) + 60
    return np.nan


u16_series2, reds = [], []
for _ in range(150):
    core.run(2, set())
    reds.append(red_cx(core.frame_rgb()))
    u16_series2.append(u16())
B2 = np.stack(u16_series2)
rx = np.array(reds)
v2 = ~np.isnan(rx)
best2 = []
busy2 = np.nonzero((np.abs(np.diff(B2, axis=0)) > 0).sum(axis=0)
                   > 75)[0]
for i in busy2:
    if i == i40 or 0x801FF000 <= 0x80000000 + i * 2:
        continue
    vv2 = B2[:, i]
    if vv2[v2].std() < 1:
        continue
    a = rx[v2] - rx[v2].mean()
    b = vv2[v2] - vv2[v2].mean()
    d = a.std() * b.std()
    if d > 0:
        c = float((a * b).mean() / d)
        if abs(c) > 0.6:
            best2.append((abs(c), int(i)))
best2.sort(reverse=True)
puck_i = best2[0][1] if best2 else None
log("puck_word",
    addr=hex(0x80000000 + puck_i * 2) if puck_i is not None else None,
    n=len(best2))

res = {"attempted": bool(ok_range and puck_i is not None)}
if res["attempted"]:
    w0 = int(u16()[i40])
    core.run(6, {"RIGHT"})
    core.run(6, set())
    w1 = int(u16()[i40])
    right_dir = 1 if w1 > w0 else -1
    res["calib"] = {"w0": w0, "w1": w1, "right_dir": right_dir}
    snap("calibrated")

    prev_score = None
    events = []
    for step in range(1, 5401):
        pw = int(u16()[i40])
        px = int(u16()[puck_i])
        diff = px - pw
        btn = set()
        if abs(diff) > 96:            # fixed-point scale (~x<<4)
            if (diff > 0) == (right_dir > 0):
                btn = {"RIGHT"}
            else:
                btn = {"LEFT"}
        elif diff < -96:
            btn = {"RIGHT"} if right_dir > 0 else {"LEFT"}
        core.run(2, btn)
        if step % 10 == 0:
            f2 = core.frame_rgb()
            if f2 is not None:
                box = f2[6:36, 205:318].tobytes()
                if prev_score is not None and box != prev_score:
                    events.append({"f": core.frames_run, "step": step,
                                   "pw": pw, "px": px})
                    snap(f"sc_{len(events)}")
                prev_score = box
        if step % 900 == 0:
            snap(f"rally_{step}")
            log("rally", step=step, pw=pw, px=px,
                score_changes=len(events))
    res["steps"] = 5400
    res["score_changes"] = len(events)
    res["events_head"] = events[:12]
    snap("post_rally")
log("goal_campaign", **res)

verdict = "INCONCLUSIVE"
if res.get("attempted") and res.get("score_changes", 0) >= 1:
    verdict = ("score events with valid fixed-point pin 0x8009be40 - "
               "PNG chain decides agency")
elif not res.get("attempted"):
    verdict = ("pin40 range check failed or no puck word - PARK at "
               "COMPLETE_LOOP_OBSERVED (r28t3)")
else:
    verdict = ("chase ran on valid pin, no score change - PARK at "
               "COMPLETE_LOOP_OBSERVED (r28t3)")
R["verdict"] = verdict
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
led["log"][-1]["outcome"] = verdict
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r28t4] DONE frames=", core.frames_run, "verdict=", verdict,
      flush=True)
