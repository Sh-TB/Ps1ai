#!/usr/bin/env python3
"""r19t1_run3_slots.py — Round 19 Poy Poy, Run 3: pin RAM screen-position
slots for all 4 characters + full-dress aimed charged throw.

Ground truth (VLM grid read of t_start = r19_f600 + 30f settle):
  1P blue ~(16,144), 2P yellow ~(208,48), 3P red ~(336,80), 4P green ~(464,80)

Steps:
  1. restore r19_f600, settle 30f, RAM snap idle
  2. scan all i32 "position-like pairs" (x in [0,512] with y-twin in [0,232]
     within +-32 bytes); match to ground truth (tolerance 48px)
  3. LEFT/RIGHT/UP/DOWN 30f holds (restore each time): per-pair deltas
     -> identify HARRY pair (moves strongly on L/R, others only camera-shift)
  4. dress rehearsal: walk to nearest white rock, B tap, hold B + aim keys
     (sign of HARRY->nearest-opponent delta from slots), release, capture
     PNG every 4f x220 + RAM every 20f; HUD logged per capture.
Artifacts: scratch/r19t1_poypoy/run3/ + slots npz for offline checks.
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

OUT = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy/run3"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r19_f600.ckpt")
GT = {"1P": (16, 144), "2P": (208, 48), "3P": (336, 80), "4P": (464, 80)}
T0W = time.time()
BUDGET = 320


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(OUT, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.core.ram[:]), dtype=np.uint8).copy()


def i32(a, off):
    return int(np.frombuffer(a[off:off + 4].tobytes(), dtype="<i4")[0])


def i16(a, off):
    return int(np.frombuffer(a[off:off + 2].tobytes(), dtype="<i2")[0])


def position_pairs(a):
    """i32 x in [0,512] with i32 y in [0,232] at o+4 or o+8; also i16 pairs.
    Returns list of dicts."""
    n = len(a)
    out = []
    for o in range(0, n - 24, 4):
        x = i32(a, o)
        if not (0 <= x <= 512):
            continue
        for dy_off in (4, 8):
            y = i32(a, o + dy_off)
            if 0 <= y <= 232:
                out.append({"kind": "i32", "xo": o, "yo": o + dy_off,
                            "x": x, "y": y})
    return out


def match_pairs(pairs, gt, tol=48):
    m = {}
    for name, (gx, gy) in gt.items():
        best = None
        for pr in pairs:
            d2 = (pr["x"] - gx) ** 2 + (pr["y"] - gy) ** 2
            if d2 <= tol * tol and (best is None or d2 < best[0]):
                best = (d2, pr)
        if best:
            m[name] = best[1]
    return m


def orb_target(img):
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    H, W = r.shape
    band = np.zeros((H, W), bool)
    band[int(H * 0.25):int(H * 0.80), :] = True
    m = (r > 205) & (g > 205) & (b > 205) & (np.abs(r - b) < 30) & band
    ys, xs = np.nonzero(m)
    if len(xs) < 15:
        return None
    from collections import Counter
    c = Counter(zip(xs // 24, ys // 24))
    (gx, gy), _ = c.most_common(1)[0]
    sel = (xs // 24 == gx) & (ys // 24 == gy)
    return (float(xs[sel].mean()), float(ys[sel].mean()))


def hud(img):
    a = np.asarray(img, dtype=np.int16)
    H, W = a.shape[:2]
    strip = a[int(H * 0.80):, :, :]
    rs, gs, bs = strip[..., 0], strip[..., 1], strip[..., 2]
    qw = W // 4
    out = []
    for q in range(4):
        rsq, gsq, bsq = (rs[:, q * qw:(q + 1) * qw],
                         gs[:, q * qw:(q + 1) * qw],
                         bs[:, q * qw:(q + 1) * qw])
        red = int(((rsq > 150) & (gsq < 95) & (bsq < 95)).sum())
        mag = int(((rsq > 160) & (bsq > 120) & (gsq < 110) &
                   (bsq <= rsq + 40)).sum())
        out.append({"hearts": red, "mag": mag})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    p.load_state(MATCH)
    p.core.run(30, set())
    idle = ram(p)
    snap(p, "s_idle.png")
    pairs = position_pairs(idle)
    rep["pairs_n"] = len(pairs)
    m = match_pairs(pairs, GT)
    rep["matched"] = {k: {"xo": v["xo"], "yo": v["yo"], "x": v["x"],
                          "y": v["y"]} for k, v in m.items()}
    print("matched:", json.dumps(rep["matched"]))

    holds = {}
    for name, btn in (("L", {"LEFT"}), ("R", {"RIGHT"}),
                      ("U", {"UP"}), ("D", {"DOWN"})):
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(30, btn)
        holds[name] = ram(p)
        snap(p, f"s_{name}.png")
    rep["pair_moves"] = {}
    for name, pr in m.items():
        row = {"idle": (pr["x"], pr["y"])}
        for hn, st in holds.items():
            row[hn] = (i32(st, pr["xo"]), i32(st, pr["yo"]))
        rep["pair_moves"][name] = row
    print(json.dumps(rep["pair_moves"], indent=1))
    np.savez_compressed(os.path.join(OUT, "slots.npz"),
                        idle=idle, **{f"hold_{k}": v for k, v in holds.items()})

    if time.time() - T0W > BUDGET:
        rep["cut"] = "budget"
    else:
        # ---- dress rehearsal: grab + aim + charged throw ----
        p.load_state(MATCH)
        p.core.run(30, set())
        harry = m.get("1P")
        img = snap(p, "d_start.png")
        grabbed = False
        for step in range(30):
            tgt = orb_target(img)
            act = set()
            if tgt is not None:
                cx, cy = tgt
                bx = harry["x"] if harry else 256
                by = harry["y"] if harry else 120
                dx, dy = cx - bx, cy - by
                if abs(dx) > 12:
                    act.add("RIGHT" if dx > 0 else "LEFT")
                if abs(dy) > 10:
                    act.add("DOWN" if dy > 0 else "UP")
                if abs(dx) <= 12 and abs(dy) <= 10:
                    p.core.run(2, {"B"})
                    grabbed = True
                    break
            else:
                act = {"DOWN"}
            p.core.run(20, act)
            img = p.core.frame_rgb()
        rep["grabbed"] = grabbed
        if grabbed:
            # aim at nearest opponent by slots
            aims = set()
            if harry and len(m) > 1:
                bx, by = harry["x"], harry["y"]
                best = None
                for k, pr in m.items():
                    if k == "1P":
                        continue
                    d2 = (pr["x"] - bx) ** 2 + (pr["y"] - by) ** 2
                    if best is None or d2 < best[0]:
                        best = (d2, pr)
                if best:
                    tx, ty = best[1]["x"], best[1]["y"]
                    dx, dy = tx - bx, ty - by
                    rep["aim_target"] = {"slot": (best[1]["xo"], best[1]["yo"]),
                                         "d": (dx, dy)}
                    if dx > 16:
                        aims.add("RIGHT")
                    elif dx < -16:
                        aims.add("LEFT")
                    if dy > 14:
                        aims.add("DOWN")
                    elif dy < -14:
                        aims.add("UP")
            rep["aims"] = sorted(aims)
            p.core.run(10, set())
            p.core.run(55, {"B"} | aims)     # charge + aim
            snap(p, "d_charged.png")
            p.core.run(2, set())              # release
            trace = []
            for k in range(14):               # 280f
                p.core.run(20, set())
                img = p.core.frame_rgb()
                if img is not None and k % 2 == 0:
                    Image.fromarray(img).save(
                        os.path.join(OUT, f"d_fly_{(k+1)*20:03d}.png"))
                trace.append({"f": p.core.frames_run, "hud": hud(img)})
                if time.time() - T0W > BUDGET:
                    break
            rep["trace"] = trace
    rep["wall_s"] = round(time.time() - T0W, 1)
    rep["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(OUT, "run3.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    print("wall_s:", rep["wall_s"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
