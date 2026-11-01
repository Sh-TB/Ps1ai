#!/usr/bin/env python3
"""r63_tetrade_probe1.py — R63 round (Issue #8 re-delivery), phase 1.

The Oct-26 round-10 full-loop artifacts were lost to the repo rewrites
(v0.5/v0.6) and sandbox rollbacks; this round re-establishes the
evidence on the CURRENT stack (plugin contract v1, zero core edits).

Phase 1 (ONE boot, disclosed):
  1. boot the license-patched Tetrade image (sha-verified manifest chain)
  2. title -> START -> menu -> CROSS(B) on Marathon -> gameplay
  3. anchor hunt on live RAM:
     - monotonic counters during natural play (pieces/score/lines priors)
     - piece-ID words in 0..7 changing at spawn; test the struct+896 pair prior
     - isGameOver prior @0x1FF5A8
     - soft-drop diff experiment
Evidence: JSONL trace + PNGs (local) + a committable digest.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from ps1play.api import PS1Play  # noqa: E402
from ps1play.core.inputmap import parse_buttons  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_r63_tetrade"
EVID = "/home/z/my-project/scratch/r63_tetrade"
OV = {b"beetle_psx_override_bios": b"openbios"}
os.makedirs(EVID, exist_ok=True)

out = {"round": "R63", "phase": 1, "game": "tetrade_lic",
       "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "events": []}


def ev(**kw):
    kw["t"] = round(time.time() - T0, 2)
    out["events"].append(kw)
    print(json.dumps(kw)[:220])


T0 = time.time()


def shot(name):
    arr = np.asarray(p.core.frame_rgb())
    Image.fromarray(arr).save(f"{EVID}/{name}.png")
    return arr


def framediff(a, b):
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


p = PS1Play(CUE, workspace=WS, var_overrides=OV)
p.boot()
ev(op="booted", wall=round(time.time() - T0, 1))

# ---- 1. title settle -------------------------------------------------
p.core.run(900, set())
title = shot("r63_00_title")
snap_title = bytes(p.mem.snapshot())
ev(op="title_settled", sha_frame=round(framediff(title, title), 3),
   ram_nonzero=sum(1 for b in snap_title if b))

# ---- 2. START -> menu ------------------------------------------------
p.core.run(60, set())
p.core.run(120, {"START"})
p.core.run(90, set())
menu = shot("r63_01_menu_after_start")
ev(op="start_pressed", diff=round(framediff(menu, title), 2))
p.core.run(240, set())
menu2 = shot("r63_02_menu_settled")
ev(op="menu_settled", diff_vs_menu=round(framediff(menu2, menu), 2))

# ---- 3. menu navigation: confirm Marathon with CROSS (B), then START --
# Observed in R63 phase-0: B on ">Marathon Mode<" opens the gameplay HUD
# which then shows PRESS START — the game waits for START before the
# first piece spawns. Detect gameplay by ANY sustained frame churn
# (a falling piece changes >=1 cell per gravity step) after START.
entered = False
for attempt in range(2):
    p.core.run(30, set())
    p.core.run(12, {"B"})          # CROSS = ps1play name B (X/Y trap)
    p.core.run(60, set())
    hud = shot(f"r63_10_hud_att{attempt}")
    # short START taps only — a 60f hold triggers the game's key-repeat
    # and lands PAUSED (observed in phase-0 attempt 0). Gravity is SLOW
    # (~1 cell / 48 f): detect gameplay by the CUMULATIVE diff across a
    # 100-frame window, not by consecutive-frame churn.
    for tap in range(3):
        p.core.run(4, {"START"})
        fa = np.asarray(p.core.frame_rgb())
        p.core.run(100, set())
        fb = np.asarray(p.core.frame_rgb())
        moved = framediff(fb, fa)
        shot(f"r63_11_tap{tap}_att{attempt}")
        ev(op="start_tap", attempt=attempt, tap=tap, moved=round(moved, 3))
        if moved > 0.05:
            entered = True
            break
    if entered:
        ev(op="gameplay_entered", attempt=attempt, taps=tap + 1)
        break

if not entered:
    out["verdict"] = "BLOCKED_NO_GAMEPLAY_ENTRY"
    json.dump(out, open(f"{EVID}/r63_probe1_summary.json", "w"), indent=1)
    print("NO GAMEPLAY ENTRY — saved summary, exiting")
    sys.exit(2)

# ---- 4. anchor hunt ---------------------------------------------------
snap_g0 = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)

# 4a. natural play 360f, per-frame snapshots: find piece-ID words and
#     monotonic counters
NAT = 360
ids_cand = {}      # addr -> list of values
mono = {}          # addr -> [first, last, steps]
prev = snap_g0
s0 = snap_g0.view("<u4")
for i in range(NAT):
    p.core.run(1, set())
    cur = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
    d = np.flatnonzero(cur != prev)
    for a in d:
        v = int(cur[a])
        c = ids_cand.setdefault(int(a), [])
        if not c or c[-1] != v:
            c.append(v)
    # monotonic u32 candidates (+1 steps only, sampled every 6 frames)
    if i % 6 == 0:
        c4 = cur.view("<u4")
        inc = (c4.astype(np.int64) - s0.astype(np.int64))
        m = (inc > 0) & (inc < 4096)
        for a in np.flatnonzero(m)[:400]:
            mono[int(a) * 4] = mono.get(int(a) * 4, 0) + 1
    prev = cur
ev(op="natural_play_done", frames=NAT)

# piece-ID words: values stay within 0..7 and change >=2 times
piece_words = []
for a, vals in ids_cand.items():
    if len(vals) >= 2 and all(0 <= v <= 7 for v in vals):
        piece_words.append((a, vals[:8]))
piece_words.sort()
ev(op="piece_id_words", n=len(piece_words),
   sample=[(a, v) for a, v in piece_words[:40]])

# struct+896 pair prior: two piece-ID words exactly 896 bytes apart
pa = set(a for a, _ in piece_words)
pairs896 = []
for a, _ in piece_words:
    if (a + 896) in pa:
        pairs896.append((a, a + 896))
ev(op="pairs_at_896", pairs=pairs896[:20])

# monotonic counters (u32, rose in >=30 of 60 samples)
counters = sorted(((c, a) for a, c in mono.items() if c >= 30),
                  reverse=True)[:40]
ev(op="monotonic_u32_candidates", top=[(a, c) for c, a in counters])

# 4b. soft-drop 240f experiment
snap_pre = bytes(p.mem.snapshot())
p.core.run(240, {"DOWN"})
snap_post = bytes(p.mem.snapshot())
pre4 = np.frombuffer(snap_pre, dtype="<u4").astype(np.int64)
post4 = np.frombuffer(snap_post, dtype="<u4").astype(np.int64)
d4 = post4 - pre4
rose = np.flatnonzero((d4 > 0) & (d4 < 4096))
ev(op="softdrop_done", rose_u32=[(int(a) * 4, int(d4[a]))
                                 for a in rose[:40]])
shot("r63_11_after_softdrop")

# 4c. priors from the Oct-26 record
prio = {}
for addr, name in [(0x1FF5A8, "isGameOver_u8"), (0x1FF5A4, "nb4")]:
    prio[name] = int(snap_post[addr]) if addr < len(snap_post) else None
ev(op="priors", **prio)

# 4d. gameplay screenshot + a second natural window for ID stability
p.core.run(120, set())
shot("r63_12_gameplay_later")
p.core.shutdown()
out["verdict"] = "PHASE1_DONE"
out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
json.dump(out, open(f"{EVID}/r63_probe1_summary.json", "w"), indent=1)
print("PHASE1 DONE ->", f"{EVID}/r63_probe1_summary.json")
