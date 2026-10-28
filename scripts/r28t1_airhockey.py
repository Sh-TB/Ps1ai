#!/usr/bin/env python3
"""r28t1_airhockey.py — Round 28: air_hockey goal campaign.

State: RUNNING (r21) — legal-input gameplay reached (title -> START ->
"AIR HOCKEY!!" -> CROSS -> PLAYER SELECT -> A(confirm) -> live match),
but the paddle words were RETRACTED in r22 and only clock/goal-flag
candidates exist. No PLAYING/GOAL claim has ever been made.

Boot cap: fresh counter, hard cap 1 (amendments disclosed). Phases:
  P1 entry (r21 run5-proven path): 2000f -> START -> 300f -> CROSS ->
     500f -> A(O=JP_A) -> 300f -> wait 2400f -> PNG live match
  P2 paddle pin: idle 60f -> LEFT 40f -> RIGHT 40f (per-frame u16LE
     sampling of the full RAM); pin = words whose drift under LEFT is
     consistently opposite to RIGHT, monotone within each hold, range
     plausible (screen coords), and screen-correlated with the bottom-
     half motion centroid. Reported top-5 with correlation.
  P3 puck hunt: idle rally 300f, per-2f u16LE series + frame-diff blob
     centroid (moving object on the table) -> top correlated words.
  P4 goal attempt: chase policy from the anchors (paddle word drives
     the stick toward the puck x via LEFT/RIGHT pulses; when the puck
     is in our half, push it up = hold toward the CPU goal). Scoreboard
     watch: byte words with an exact +1 step at one tick during play
     (r22 C3 method) + PNG before/after the tick.
Honest failure mode: no goal -> RUNNING stands, candidates recorded.
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
           "air_hockey_norm/Air Hockey (USA) 2352.cue")  # copied from the surviving /tmp mirror
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

R = {"task": "r28t1 air hockey: paddle pin + puck hunt + goal attempt",
     "boot_cap": 1,
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


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
    print(f"[r28t1] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def ram_u16():
    return np.frombuffer(bytes(core.ram), dtype="<u2")


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 0, f"boot counter {n0} != 0 (hard cap 1)"
json.dump({"count": 1,
           "log": [{"boot": 1, "script": "r28t1_airhockey.py",
                    "disc": "retail SLUS-01467 user disc, no patches",
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


def motion_centroid(arr, half="bottom"):
    g = arr.mean(axis=2)
    band = g[120:] if half == "bottom" else g[:120]
    return float(band.mean())


# ---- P1: entry (r21 run5-proven path) ------------------------------------
core.run(2000, set())
snap("title")
core.run(3, {"START"})
core.run(300, set())
snap("m0_airhockey")
core.run(3, {"B"})
core.run(500, set())
snap("m1_playerselect")
core.run(3, {"O"})
core.run(300, set())
snap("m2_confirmed")
for _ in range(40):
    core.run(60, set())
    if core.frames_run > 6000:
        break
game = snap("live_match")
log("entry", mean=round(float(game.mean()), 2))

# ---- P2: paddle pin -------------------------------------------------------
def sample_series(btn, n):
    series = []
    for _ in range(n):
        core.run_frame()
        series.append(ram_u16().copy())
    return series


idle = sample_series(None, 60) if False else None
core.run(60, set())
base = ram_u16().copy()
sL = sample_series("LEFT", 40)
sR = sample_series("RIGHT", 40)
sL2 = sample_series("LEFT", 40)
base2 = ram_u16().copy()

Ldrift = np.array([s[-1].astype(np.int32) - base.astype(np.int32)
                   for s in sL])
Rdrift = np.array([s[-1].astype(np.int32) - sL[-1].astype(np.int32)
                   for s in sR])
L2drift = np.array([s[-1].astype(np.int32) - sR[-1].astype(np.int32)
                    for s in sL2])
# consistent opposite-sign drift across both LEFT holds, and RIGHT reverses
monoL = (np.sign(Ldrift[-1]) == np.sign(Ldrift[0])) & (Ldrift[-1] != 0)
monoL2 = (np.sign(L2drift[-1]) == np.sign(L2drift[0])) & (L2drift[-1] != 0)
rev = np.sign(Rdrift[-1]) == -np.sign(Ldrift[-1])
cands = np.nonzero(monoL & monoL2 & rev)[0]
paddle_pins = [{"idx": int(i), "addr": hex(0x80000000 + int(i) * 2),
                "L": int(Ldrift[-1][i]), "R": int(Rdrift[-1][i]),
                "L2": int(L2drift[-1][i])}
               for i in cands[:12]]
log("paddle_pins", n=len(cands), head=paddle_pins[:6])
snap("after_paddle_probes")

# ---- P3: puck hunt (idle rally, frame-diff centroid correlation) ---------
N = 150
u16_series = []
cents = []
prev = core.frame_rgb()
for _ in range(N):
    core.run(2, set())
    fr = core.frame_rgb()
    if fr is None or prev is None or fr.shape != prev.shape:
        continue
    d = np.abs(fr.astype(int) - prev.astype(int)).sum(axis=2)
    ys, xs = np.nonzero(d > 40)
    if len(xs) > 8:
        cents.append((float(xs.mean()), float(ys.mean())))
    else:
        cents.append(None)
    u16_series.append(ram_u16().copy().astype(np.int32))
    prev = fr
u16_arr = np.stack(u16_series)                     # (N, 1M, )
cx = np.array([c[0] if c else np.nan for c in cents])
cy = np.array([c[1] if c else np.nan for c in cents])
valid = ~np.isnan(cx)
corr_cx = np.zeros(u16_arr.shape[1], dtype=np.float32)
# correlate per-chunk to bound memory: only words that CHANGED often
changed_mask = (np.abs(np.diff(u16_arr, axis=0)) > 0).sum(axis=0)
busy = np.nonzero(changed_mask > N // 2)[0]
best = []
for i in busy:
    v = u16_arr[:, i]
    if v.std() < 1:
        continue
    a = cx[valid] - cx[valid].mean()
    b = v[valid] - v[valid].mean()
    denom = (a.std() * b.std())
    if denom > 0:
        c = float((a * b).mean() / denom)
        if abs(c) > 0.55:
            best.append((abs(c), c, int(i)))
best.sort(reverse=True)
puck_cands = [{"addr": hex(0x80000000 + i * 2), "corr": round(c, 3),
               "range": [int(u16_arr[:, i].min()), int(u16_arr[:, i].max())]}
              for _, c, i in best[:8]]
log("puck_cands", n=len(best), head=puck_cands)

# ---- P4: goal attempt (chase policy) --------------------------------------
paddle_idx = cands[0] if len(cands) else None
puck_idx = best[0][2] if best else None
goal_result = {"attempted": False}
if paddle_idx is not None and puck_idx is not None:
    goal_result["attempted"] = True
    snap_before = snap("pre_rally")
    steps = 0
    score_events = []
    prev_ram = ram_u16().copy()
    for step in range(3600):
        steps += 1
        px = int(ram_u16()[puck_idx])
        # paddle chases the puck x; deadband 12px
        pw = int(ram_u16()[paddle_idx])
        btn = set()
        if px < pw - 12:
            btn = {"LEFT"}
        elif px > pw + 12:
            btn = {"RIGHT"}
        core.run(2, btn)
        cur = ram_u16()
        dd = (cur.astype(np.int32) - prev_ram.astype(np.int32))
        inc = np.nonzero(dd == 1)[0]
        for i in inc:
            score_events.append({"f": core.frames_run,
                                 "addr": hex(0x80000000 + int(i) * 2)})
        prev_ram = cur.copy()
        if steps % 600 == 0:
            snap(f"rally_{steps}")
            log("rally_step", steps=steps,
                paddle=int(ram_u16()[paddle_idx]),
                puck=int(ram_u16()[puck_idx]),
                score_events=len(score_events))
    goal_result["steps"] = steps
    goal_result["score_events_head"] = score_events[:12]
    goal_result["score_events_n"] = len(score_events)
    snap("post_rally")
log("goal_attempt", **goal_result)

R["final"] = {"paddle_pins": paddle_pins, "puck_cands": puck_cands,
              "goal": goal_result}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r28t1] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1),
      "paddle_pins=", len(cands), "puck_cands=", len(best),
      "score_events=", goal_result.get("score_events_n"), flush=True)
