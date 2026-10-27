#!/usr/bin/env python3
"""r19t1_run1_entry.py — Round 19 Poy Poy, Run 1: fresh match entry + probes.

One beetle boot. Sequence:
  1. boot -> load m23_b0 (STAGE SELECT) -> UP x2 + B -> 1500f entry,
     PNG every 100f, save fresh checkpoints at f600/f1200/f1500
  2. census (left_vs_right RAM diff) on f1500 ckpt  -> REAL_MATCH evidence
  3. direction holds LEFT/RIGHT/UP/DOWN (30f) from the SAME ckpt:
     RAM i32 deltas + PNGs (verify calib3 candidates 746776/649276)
  4. scripted grab attempt: nearest white orb by vision -> walk -> B tap ->
     PNG every 2f x120 (ball overhead ~+90f) -> hold B 60f -> release ->
     PNG every 2f x160 (charged throw flight)
All artifacts under scratch/r19t1_poypoy/run1/ + checkpoints under the
home workspace (never /tmp).
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

OUT = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy/run1"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
B0 = os.path.join(WS, "m23_b0.ckpt")
T0W = time.time()
BUDGET = 330  # seconds hard cap for the emulator phase


def snap(p, name, frm):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(OUT, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.core.ram[:]), dtype=np.uint8).copy()


def i32(a, off):
    return int(np.frombuffer(a[off:off + 4].tobytes(), dtype="<i4")[0])


def orb_centroid(img):
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    H, W = r.shape
    band = np.zeros((H, W), bool)
    band[int(H * 0.25):int(H * 0.80), :] = True
    m = (r > 205) & (g > 205) & (b > 205) & (np.abs(r - b) < 30) & band
    ys, xs = np.nonzero(m)
    if len(xs) < 12:
        return None, int(m.sum())
    # biggest white cluster approx: take median of pixels (orb-dominant)
    return (float(np.median(xs)), float(np.median(ys))), int(m.sum())


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    p.load_state(B0)
    p.core.run(120, set())
    snap(p, "e_b0.png", p.core.frames_run)

    # ---- 1. entry ladder ----
    for _ in range(2):
        p.core.run(20, set())
        p.core.run(30, {"UP"})
        p.core.run(120, set())
    snap(p, "e_preconfirm.png", p.core.frames_run)
    p.core.run(60, {"B"})
    ckpts = {}
    for f in range(100, 1501, 100):
        p.core.run(100, set())
        snap(p, f"e_f{f:04d}.png", p.core.frames_run)
        if f in (600, 1200, 1500):
            ck = os.path.join(WS, f"r19_f{f}.ckpt")
            p.save_state(ck)
            ckpts[f] = ck
        if time.time() - T0W > BUDGET:
            break
    rep["checkpoints"] = ckpts

    MATCH = ckpts.get(1500) or ckpts.get(1200)
    rep["match_ckpt"] = MATCH

    # ---- 2. census ----
    s = {}
    for name, btns in (("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(MATCH)
        p.core.run(120, set())
        p.core.run(90, btns)
        s[name] = ram(p)
    p.load_state(MATCH)
    p.core.run(120, set())
    p.core.run(90, set())
    n2 = ram(p)
    rep["census"] = {"det_none": int((n2 != s["left"]).sum()),
                     "left_vs_right": int((s["left"] != s["right"]).sum()),
                     "left_vs_none": int((s["left"] != n2).sum())}
    rep["census"]["verdict"] = ("REAL_MATCH" if rep["census"]["left_vs_right"]
                                > max(500, 5 * rep["census"]["det_none"])
                                else "not_yet")

    # ---- 3. direction holds (i32 candidates) ----
    p.load_state(MATCH)
    p.core.run(30, set())
    idle = ram(p)
    snap(p, "d_idle.png", p.core.frames_run)
    holds = {}
    for name, btn in (("left", {"LEFT"}), ("right", {"RIGHT"}),
                      ("up", {"UP"}), ("down", {"DOWN"})):
        if time.time() - T0W > BUDGET:
            break
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(30, btn)
        holds[name] = ram(p)
        snap(p, f"d_{name}.png", p.core.frames_run)
    rep["dir"] = {}
    for name, st in holds.items():
        d = (st != idle)
        both = d
        cands = []
        for off in np.flatnonzero(both):
            o4 = int(off - (off % 4))
            dv = i32(st, o4) - i32(idle, o4)
            if abs(dv) >= 8:
                cands.append((o4, dv))
        # dedupe by offset, sort by |dv| desc
        seen = {}
        for o4, dv in cands:
            seen[o4] = dv
        top = sorted(seen.items(), key=lambda t: -abs(t[1]))[:40]
        rep["dir"][name] = {"diff_bytes": int(d.sum()), "top_i32": top}
    # verify calib3 candidates explicitly
    rep["calib3_check"] = {}
    for off in (746776, 649276, 844968, 2096760):
        row = {"idle": i32(idle, off)}
        for name, st in holds.items():
            row[name] = i32(st, off)
        rep["calib3_check"][off] = row

    # ---- 4. scripted grab + charge ----
    p.load_state(MATCH)
    p.core.run(30, set())
    img = snap(p, "g_start.png", p.core.frames_run)
    grabbed = False
    log = []
    for step in range(24):  # up to 480f of walking
        c, n = orb_centroid(img)
        act = set()
        if c is None:
            log.append({"f": p.core.frames_run, "orb": None, "n": n})
            act = {"DOWN"}
        else:
            cx, cy = c
            # HARRY approx center; walk toward orb
            dx, dy = cx - 256, cy - 110
            if abs(dx) > 14:
                act.add("RIGHT" if dx > 0 else "LEFT")
            if abs(dy) > 12:
                act.add("DOWN" if dy > 0 else "UP")
            if abs(dx) <= 14 and abs(dy) <= 12:
                p.core.run(2, {"B"})
                grabbed = True
                log.append({"f": p.core.frames_run, "ev": "B_tap", "orb": [cx, cy]})
                img = p.core.frame_rgb()
                break
            log.append({"f": p.core.frames_run, "orb": [round(cx), round(cy)],
                        "act": sorted(act)})
        p.core.run(20, act)
        img = p.core.frame_rgb()
        if time.time() - T0W > BUDGET:
            break
    rep["grab"] = {"grabbed": grabbed, "log": log[-8:]}
    if grabbed:
        # ball-overhead watch
        for k in range(60):  # 120f, PNG every 2
            p.core.run(2, set())
            if k % 2 == 0:
                snap(p, f"g_carry_{k*2:03d}.png", p.core.frames_run)
        # charge hold 60f then release
        p.core.run(60, {"B"})
        snap(p, "g_charged.png", p.core.frames_run)
        for k in range(80):  # 160f after release
            p.core.run(2, set())
            if k % 2 == 0:
                snap(p, f"g_throw_{k*2:03d}.png", p.core.frames_run)
    snap(p, "g_end.png", p.core.frames_run)

    rep["frames_run"] = p.core.frames_run
    rep["wall_s"] = round(time.time() - T0W, 1)
    rep["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(OUT, "run1.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ("census", "calib3_check", "grab",
                                          "wall_s")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
