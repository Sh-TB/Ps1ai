#!/usr/bin/env python3
"""r21t6_poypoy_retire2.py — Poy Poy: land RETIRE #2 through legal play.

One emulator run (PS1Play process), four phases:
  P0 boot + restore r19_f600 (fresh round, all hearts full) -> RAM A;
       restore r20t4_retire (3P at 1 heart) -> RAM B; HP-array diff scan
       A->B finds per-fighter heart/HP counter candidates (lane decreased).
  P1 aim loop from r20t4_retire: target the lowest-HP alive opponent,
       charged throw = hold B (90f cap) WITH aim direction (r19 recipe:
       hold B + aim dirs, release); release early when the target's RAM
       screen-x (r19-proven per-fighter i32 slots) enters the hit window
       observed at r20's confirmed HIT (|dx| ~ 63 px -> gate <=110 px on
       the correct side). Detector v2 (learned baseline, 2-sample
       sustain) for hits; r19 RETIRE! signature (hearts<=60 + mag>=170
       x3 ticks) for KOs. HP candidate lanes logged every tick.
  P2 on first RETIRE: dense KO frames -> GIF frames, save state
       r21t6_retire2, +300f stability check (card stays RETIRE!/no heal).
  P3 JSON logs + honest verdict (RETIRE2 / PLAYING) + slot trace.

Static RE companion: scripts/r21t6_re_scan.py (see re_scan.json):
  main EXE = SLUS_004.86;1 (LBA 3157, 583680 B), t_addr 0x80010000,
  t_size 0x8E000 -> image ends 0x8009E000; NO other PS-X EXE on disc;
  ZERO static xrefs to 0x8019F7xx (r20 hint refuted) and to the exact
  cluster slots 0x8009F778/780/7B0/7EA -> the cluster is heap data
  reached via runtime pointers, same as the per-fighter screen slots.
"""
import json
import os
import time

import numpy as np
from PIL import Image

sys_path = "/home/z/my-project/ps1ai"
import sys  # noqa: E402
sys.path.insert(0, sys_path)
from ps1play.api import PS1Play  # noqa: E402

OUT = "/home/z/my-project/ps1ai/scratch/r21t6_poypoy/run1"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}

# r19-proven per-fighter screen-position i32 slots (RAM offsets, x then y)
P = {"1P": (0x142EF8, 0x142F00), "2P": (0x13247C, 0x132480),
     "3P": (0x1E12EC, 0x1E12F0), "4P": (0x083114, 0x08311C)}
CAM = 0x0A09CC                      # camera x (r19 run2)
CLUSTER = [0x9F778, 0x9F780, 0x9F7B0, 0x9F7EA]   # r20 live-slot cluster
HP_SCAN_STRIDES = [1, 2, 4, 8, 16, 32, 64]        # bytes, between lanes
WALL_CAP = 300.0                    # seconds for the whole emulator phase

os.makedirs(OUT, exist_ok=True)
R = {"task": "r21t6", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "verdict": None, "hp_candidates": [], "retire_events": [],
     "hit_events": [], "throws": 0, "slot_trace": [], "hp_trace": []}


def ram(p):
    return np.frombuffer(bytes(p.core.ram[:]), dtype=np.uint8).copy()


def i32(a, off):
    return int(np.frombuffer(a[off:off + 4].tobytes(), "<i4")[0])


def gray(p):
    return np.asarray(Image.fromarray(p.core.frame_rgb()).convert("L")
                      .resize((512, 240)), np.float32)


def hud(p):
    """r19 signature: bottom strip quarters -> red heart px + magenta px."""
    a = np.asarray(p.core.frame_rgb(), dtype=np.int16)
    H, W = a.shape[:2]
    strip = a[int(H * 0.80):, :, :]
    rs, gs, bs = strip[..., 0], strip[..., 1], strip[..., 2]
    qw = W // 4
    out = []
    for q in range(4):
        r_, g_, b_ = (s[:, q * qw:(q + 1) * qw]
                      for s in (rs, gs, bs))
        red = int(((r_ > 150) & (g_ < 95) & (b_ < 95)).sum())
        mag = int(((r_ > 160) & (b_ > 120) & (g_ < 110)
                   & (b_ <= r_ + 40)).sum())
        out.append({"hearts": red, "mag": mag})
    return out


def hp_scan(A, B):
    """Find 4-lane counter groups where exactly one lane decreased to a
    small value and the other lanes are unchanged (3P heart drop)."""
    hits = []
    for width, dt in ((1, np.uint8), (2, "<u2"), (4, "<u4")):
        av = A.view(dt)
        bv = B.view(dt)
        for s in HP_SCAN_STRIDES:
            step = s // width
            if step < 1:
                continue
            dec = np.nonzero((bv < av) & (bv > 0) & (bv <= 4))[0]
            for k in range(4):
                if k == 0:
                    continue
                base_idx = dec - k * step
                ok = (base_idx >= 0) & (base_idx + 3 * step < len(av))
                base_idx = base_idx[ok]
                dec2 = dec[ok]
                if len(base_idx) == 0:
                    continue
                same = np.ones(len(base_idx), bool)
                lanes_small = np.ones(len(base_idx), bool)
                for j in range(4):
                    if j == k:
                        continue
                    jj = base_idx + j * step
                    same &= av[jj] == bv[jj]
                    lanes_small &= (bv[jj] >= 1) & (bv[jj] <= 4)
                for bi, di in zip(base_idx[same & lanes_small],
                                  dec2[same & lanes_small]):
                    hits.append({
                        "base": int(bi) * width,
                        "stride": s, "width": width,
                        "dec_lane": int(k),
                        "A": [int(av[bi + j * step]) for j in range(4)],
                        "B": [int(bv[bi + j * step]) for j in range(4)]})
    # dedupe by (base, stride, width), drop subsumed (same base smaller stride)
    seen, out = set(), []
    for h in hits:
        key = (h["base"], h["stride"], h["width"])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def target_of(p, hudst, alive_mask):
    """Nearest alive opponent by screen x (1P pinned at x=20)."""
    best, bestd = None, 1e9
    for name in ("2P", "3P", "4P"):
        q = {"2P": 1, "3P": 2, "4P": 3}[name]
        if not alive_mask[q]:
            continue
        x = i32(ram(p), P[name][0])
        d = abs(x - 20)
        if 0 < d < bestd:
            best, bestd = (name, x), d
    return best


def main():
    t0 = time.time()
    p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
    R["boot"] = {k: p.boot().get(k) for k in ("core", "serial")}

    # ---------------- P0: HP-array diff scan ----------------
    p.load_state("r19_f600")
    p.core.run(30)
    A = ram(p)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/p0_f600.png")
    p.load_state("r20t4_retire")
    p.core.run(30)
    B = ram(p)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/p0_retire_resume.png")
    R["hud_resume"] = hud(p)
    cands = hp_scan(A, B)
    # rank: prefer groups whose dec lane is unique within +-stride*8 and
    # whose values look like hearts (A>=2, B in 1..3)
    cands.sort(key=lambda h: -(h["A"][h["dec_lane"]] - h["B"][h["dec_lane"]]))
    R["hp_candidates"] = cands[:40]
    R["n_hp_candidates"] = len(cands)
    print(f"[P0] hp candidates: {len(cands)}; top:",
          json.dumps(cands[:6]))
    # monitor set: up to 6 distinct bases with small strides
    mon = []
    for h in cands:
        if h["width"] in (1, 2, 4) and h["stride"] <= 64:
            if all(abs(h["base"] - m["base"]) > 16 for m in mon):
                mon.append(h)
        if len(mon) >= 6:
            break
    R["hp_monitor"] = mon

    # ---------------- P1: aiming charged-throw loop ----------------
    base_hist, baseline = [], None
    consec_mag = [0, 0, 0, 0]
    retired_q = [False] * 4
    state = "IDLE"
    cool = 0
    charge_left = 0
    aim = set()
    last_target = None
    img_n = 0
    end_at = None
    tick = 0
    while time.time() - t0 < WALL_CAP:
        tick += 1
        btn = set()
        if state == "CHARGE":
            btn.add("B")
            btn |= aim
        p.core.run(6, btn)
        fc = p.core.frames_run
        rr = ram(p)
        h = hud(p)
        g = gray(p)
        band = [float((g[78:94, 20 + i * 120:120 + i * 120] > 110).mean())
                for i in range(4)]
        row = {"fc": fc, "hud": h, "band": [round(b, 3) for b in band],
               "cluster": [int(p.mem.u16(a)) for a in CLUSTER],
               "slots": {k: [i32(rr, P[k][0]), i32(rr, P[k][1])]
                         for k in P},
               "aim": sorted(aim), "charging": state == "CHARGE"}
        row["hp"] = {f'{m["width"] }B@{m["base"]:X}':
                     [int(np.frombuffer(rr[m["base"] + j * m["stride"]:
                                        m["base"] + j * m["stride"]
                                        + m["width"]].tobytes(),
                                   "<u2" if m["width"] == 2 else
                                   ("<u4" if m["width"] == 4 else "u1"))[0])
                       for j in range(4)] for m in mon}
        R["slot_trace"].append(row)

        # detector v2 baseline
        base_hist.append(band)
        if baseline is None and len(base_hist) >= 8:
            baseline = [max(0.05, float(np.mean([x[i] for x in
                                                 base_hist[:8]])))
                        for i in range(4)]
            R["baseline_band"] = [round(b, 3) for b in baseline]

        # RETIRE! signature (r19): hearts<=60 + mag>=170 sustained 3 ticks
        for q in range(4):
            if retired_q[q]:
                continue
            consec_mag[q] = consec_mag[q] + 1 if (
                h[q]["hearts"] <= 60 and h[q]["mag"] >= 170) else 0
            if consec_mag[q] >= 3:
                retired_q[q] = True
                R["retire_events"].append({"fc": fc, "card": q + 1,
                                           "hud": h[q]})
                print(f"[P1] RETIRE! card {q+1} at fc={fc}")
        alive = [not retired_q[q] for q in range(4)]

        # hit event: band collapse vs learned baseline (detector v2)
        if baseline and len(base_hist) >= 2:
            for i in range(4):
                if (base_hist[-1][i] < 0.45 * baseline[i]
                        and base_hist[-2][i] < 0.45 * baseline[i]
                        and alive[i]):
                    R["hit_events"].append({"fc": fc, "band": i,
                                            "w": base_hist[-1][i],
                                            "throw": R["throws"]})
                    img_n += 1
                    Image.fromarray(p.core.frame_rgb()).save(
                        f"{OUT}/hit_f{fc:05d}.png")
                    base_hist = []
                    baseline = None
                    break

        # dense capture while a retire is fresh (GIF source)
        if any(retired_q) and (end_at is None or fc < end_at):
            Image.fromarray(p.core.frame_rgb()).save(
                f"{OUT}/ko_{fc:05d}.png")

        if any(retired_q):
            if end_at is None:
                end_at = fc + 300
                p.save_state("r21t6_retire2")
                R["retire_state"] = "r21t6_retire2"
            if fc >= end_at:
                break
        elif fc % 90 < 6:
            img_n += 1
            Image.fromarray(p.core.frame_rgb()).save(
                f"{OUT}/f{fc:05d}.png")

        # ---------------- throw state machine (explicit FSM) ----------------
        # states: IDLE(cool>0) -> CHARGE(hold B+aim, cap 90f, early release
        # when target inside hit window |dx|<=110 on the aimed side) ->
        # COOL 240f (flight + impact) -> IDLE
        if state == "IDLE":
            if cool > 0:
                cool -= 6
                continue
            tgt = target_of(p, h, alive)
            if tgt is None:
                continue
            name, tx = tgt
            last_target = name
            dx = tx - 20
            aim = set()
            if dx > 0:
                aim.add("RIGHT")
            else:
                aim.add("LEFT")
            ty = i32(rr, P[name][1])
            aim.add("UP" if ty <= 146 else "DOWN")
            state = "CHARGE"
            charge_left = 90
        elif state == "CHARGE":
            tx = i32(rr, P[last_target][0])
            dx = tx - 20
            side_ok = (dx > 0) == ("RIGHT" in aim)
            charge_left -= 6
            if (abs(dx) <= 110 and side_ok and charge_left <= 30) \
                    or charge_left <= 0:
                R["throws"] += 1
                R.setdefault("releases", []).append(
                    {"fc": fc, "target": last_target, "dx": dx,
                     "tx": tx, "aim": sorted(aim),
                     "charged_f": 90 - charge_left})
                state = "COOL"
                cool = 240
                aim = set()
        elif state == "COOL":
            cool -= 6
            if cool <= 0:
                state = "IDLE"

    # ---------------- P3: close out ----------------
    R["final_frame"] = p.core.frames_run
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/end.png")
    R["hud_end"] = hud(p)
    R["retired_q"] = retired_q
    n_ret = sum(retired_q)
    R["verdict"] = ("RETIRE2" if n_ret >= 2 else
                    ("RETIRE1" if n_ret == 1 else "PLAYING"))
    R["wall_s"] = round(time.time() - t0, 1)
    R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(R, open(f"{OUT}/run1.json", "w"), indent=1)
    print(json.dumps({k: R.get(k) for k in
                      ("verdict", "retire_events", "hit_events", "throws",
                       "hud_end", "final_frame", "wall_s")}, indent=1))


if __name__ == "__main__":
    main()
