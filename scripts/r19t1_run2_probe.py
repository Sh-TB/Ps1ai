#!/usr/bin/env python3
"""r19t1_run2_probe.py — Round 19 Poy Poy, Run 2: RAM position mining +
aimed charged throw.

One beetle boot. From the surviving fresh round-start checkpoint
(r19_f600 = timer 01:55, all hearts full):

  A. position mining (deterministic, calib2 ambient=0):
     idle snap A; restore; LEFT 60f -> L; restore; RIGHT 60f -> R;
     restore; UP 60f -> U; restore; DOWN 60f -> D.
     x-candidates: (A-L) >= 24 and (R-A) >= 24 ; y-candidates on U/D.
     Then linear-walk verification: LEFT 150f, RAM every 30f.
  B. 4-player struct hunt: for each x-cand offset, test strides 20..136:
     do ox+k*stride hold i32 in a similar value range at idle?
  C. aimed charged throw: restore; vision-walk to nearest white rock;
     B tap (grab); hold B 55f + hold aim direction (from mined HARRY vs
     opponent slots if available, else toward yellow blob); release;
     run 240f capturing PNG every 4f + RAM every 20f (ball-slot hunt).
All artifacts: scratch/r19t1_poypoy/run2/
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

OUT = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy/run2"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r19_f600.ckpt")
T0W = time.time()
BUDGET = 330


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(OUT, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.core.ram[:]), dtype=np.uint8).copy()


def i32(a, off):
    return int(np.frombuffer(a[off:off + 4].tobytes(), dtype="<i4")[0])


def orb_target(img, hx=None, hy=None):
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    H, W = r.shape
    band = np.zeros((H, W), bool)
    band[int(H * 0.25):int(H * 0.80), :] = True
    m = (r > 205) & (g > 205) & (b > 205) & (np.abs(r - b) < 30) & band
    # blob-ish: use column/row density around candidate points
    ys, xs = np.nonzero(m)
    if len(xs) < 15:
        return None
    # greedy biggest cluster via grid binning
    from collections import Counter
    c = Counter(zip(xs // 24, ys // 24))
    (gx, gy), _ = c.most_common(1)[0]
    sel = (xs // 24 == gx) & (ys // 24 == gy)
    return (float(xs[sel].mean()), float(ys[sel].mean()))


def mine():
    """Direction holds from MATCH; returns dict of RAM snapshots."""
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    snaps = {}
    p.load_state(MATCH)
    p.core.run(30, set())
    snaps["A"] = ram(p)
    snap(p, "m_idle.png")
    for name, btn in (("L", {"LEFT"}), ("R", {"RIGHT"}),
                      ("U", {"UP"}), ("D", {"DOWN"})):
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(60, btn)
        snaps[name] = ram(p)
        snap(p, f"m_{name}.png")
    # linear walk verification (LEFT 150f)
    p.load_state(MATCH)
    p.core.run(30, set())
    walk = [ram(p)]
    for _ in range(5):
        p.core.run(30, {"LEFT"})
        walk.append(ram(p))
    snap(p, "m_walk_end.png")
    return p, snaps, walk


def candidates(snaps, walk):
    A, L, R, U, D = (snaps[k].astype(np.int32) for k in "ALRUD")
    dL, dR, dU, dD = A - L, R - A, A - U, D - A
    xs = []
    for off in np.flatnonzero((dL >= 24) & (dR >= 24)):
        o4 = int(off - (off % 4))
        xs.append(o4)
    ys = []
    for off in np.flatnonzero((dU >= 24) & (dD >= 24)):
        o4 = int(off - (off % 4))
        ys.append(o4)
    # walk-verify x candidates: monotone decreasing, |total| >= 40
    wv = []
    if xs:
        W0 = np.stack([w.astype(np.int32) for w in walk])
        for o4 in xs:
            seq = W0[:, o4] + (W0[:, o4 + 1].astype(np.int32) << 8 if False else 0)
            seq = W0[:, o4:o4 + 4].copy()
            seq.flags.writeable = False
            vals = [int(np.frombuffer(seq[i].tobytes(), dtype="<i4")[0])
                    for i in range(len(walk))]
            diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
            if all(d < 0 for d in diffs) and abs(vals[-1] - vals[0]) >= 40 \
                    and abs(vals[-1] - vals[0]) <= 4000:
                wv.append((o4, vals))
    return xs, ys, wv


def struct_hunt(snaps, wv):
    """For verified x-slots, look for 3 sibling slots at regular strides
    holding similar-range i32 values at idle (4 players)."""
    A = snaps["A"]
    out = []
    for o4, vals in wv[:12]:
        v0 = vals[0]
        for stride in range(20, 137, 4):
            sibs = []
            ok = True
            for k in (1, 2, 3):
                o = o4 + k * stride
                if o + 4 > len(A):
                    ok = False
                    break
                v = i32(A, o)
                if not (-0x200000 <= v <= 0x400000) or \
                        abs(v - v0) > 0x180000:
                    ok = False
                    break
                sibs.append((o, v))
            if ok:
                out.append({"base": o4, "idle_vals": vals, "stride": stride,
                            "siblings": sibs})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p, snaps, walk = mine()
    xs, ys, wv = candidates(snaps, walk)
    rep["x_cand_n"] = len(xs)
    rep["x_verified"] = [(o, v) for o, v in wv[:20]]
    rep["y_cand_n"] = len(ys)
    rep["y_cand_head"] = ys[:30]
    rep["struct"] = struct_hunt(snaps, wv)[:12]
    print("x verified:", [(o, v[0], v[-1]) for o, v in rep["x_verified"][:10]])
    print("struct:", [(s["base"], s["stride"],
                       [sib[1] for sib in s["siblings"]])
                      for s in rep["struct"][:6]])

    if time.time() - T0W > BUDGET:
        rep["cut"] = "budget before throw probe"
    else:
        # ---- C. aimed charged throw ----
        p.load_state(MATCH)
        p.core.run(30, set())
        img = snap(p, "t_start.png")
        grabbed = False
        walklog = []
        aim = {"UP", "RIGHT"}
        for step in range(30):
            tgt = orb_target(img)
            act = set()
            if tgt is None:
                act = {"DOWN"}
                walklog.append({"f": p.core.frames_run, "orb": None})
            else:
                cx, cy = tgt
                dx, dy = cx - 256, cy - 115
                if abs(dx) > 12:
                    act.add("RIGHT" if dx > 0 else "LEFT")
                if abs(dy) > 10:
                    act.add("DOWN" if dy > 0 else "UP")
                walklog.append({"f": p.core.frames_run,
                                "orb": [round(cx), round(cy)],
                                "act": sorted(act)})
                if abs(dx) <= 12 and abs(dy) <= 10:
                    p.core.run(2, {"B"})
                    grabbed = True
                    walklog.append({"f": p.core.frames_run, "ev": "B_tap"})
                    img = p.core.frame_rgb()
                    break
            p.core.run(20, act)
            img = p.core.frame_rgb()
            if time.time() - T0W > BUDGET:
                break
        rep["grab"] = {"grabbed": grabbed, "last": walklog[-3:]}
        if grabbed:
            p.core.run(8, set())                 # settle into carry
            ram_carry = ram(p)
            snap(p, "t_carry.png")
            # aim during charge: hold B + direction; release at 55f
            p.core.run(55, {"B"} | aim)
            snap(p, "t_charged.png")
            ram_charged = ram(p)
            p.core.run(2, set())                 # release
            ball_snaps = []
            for k in range(12):                  # 240f after release
                p.core.run(20, set())
                ball_snaps.append((p.core.frames_run, ram(p)))
                snap(p, f"t_fly_{(k+1)*20:03d}.png")
            rep["release_frame"] = p.core.frames_run - 240
            # ball-slot hunt: carry vs charged vs flight endpoints
            fc = ram_carry.astype(np.int32)
            fd = ram_charged.astype(np.int32)
            fe = ball_snaps[-1][1].astype(np.int32)
            chg = np.flatnonzero((np.abs(fd - fc) > 4))[()]
            moved = []
            for off in np.flatnonzero(np.abs(fe - fc) > 100):
                o4 = int(off - (off % 4))
                moved.append((o4, i32(ram_carry, o4), i32(ram_charged, o4),
                              i32(ball_snaps[-1][1], o4)))
            moved = sorted(set(moved))[:40]
            rep["ball_slots_changed_carry_to_charged_n"] = int(len(set(
                int(o - o % 4) for o in chg)))
            rep["ball_slots"] = moved
            rep["hud_end"] = None
            img = snap(p, "t_end.png")
            a = np.asarray(img, dtype=np.int16)
            H, W = a.shape[:2]
            r, g, b = a[..., 0], a[..., 1], a[..., 2]
            strip = a[int(H * 0.80):, :, :]
            rs, gs, bs = strip[..., 0], strip[..., 1], strip[..., 2]
            qw = W // 4
            rep["hud_end"] = [int(((rs[:, q * qw:(q + 1) * qw] > 150) &
                                   (gs[:, q * qw:(q + 1) * qw] < 95) &
                                   (bs[:, q * qw:(q + 1) * qw] < 95)).sum())
                              for q in range(4)]

    rep["wall_s"] = round(time.time() - T0W, 1)
    rep["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(OUT, "run2.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    print("grab:", rep.get("grab"))
    print("hud_end:", rep.get("hud_end"))
    print("wall_s:", rep["wall_s"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
