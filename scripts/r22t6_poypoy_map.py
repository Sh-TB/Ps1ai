#!/usr/bin/env python3
"""r22t6_poypoy_map.py — boot 1/3: per-fighter heart-cell map + position re-test.

Read-only phase (no game-altering inputs; legal-input discipline kept).

Loads four same-lineage states in ONE PS1Play process and snapshots RAM:
  C = r19_f600         fresh round, all fighters full hearts (cells = 4)
  A = r20t4_retire     3P at 1 heart (r20 VLM-verified), others full
  L = r21t6_ablation_end  r20t4_retire + 1200f AI-only (3P still 1; others unknown)
  B = r21t6_retire2    1P/2P/3P retired (0), 4P alive at 1 heart

Outputs (scratch/r22t6_poypoy/run1/):
  <tag>.npz / <tag>.png / hud_<tag> in map.json
  heart-cell candidates: u8/u16/u32 words in [0..4] with ==4 at C, ==0 at B,
  classified against the per-fighter heart vector hypothesis.
  live trace: from A, 24 ticks x 8f of the r19 i32 slots + r20 u16 cluster +
  camera + i32/i16 fields near each candidate heart cell (struct walk).
Verdict helper: prints proposed cell<->fighter map.
"""
import json
import os
import time

import numpy as np
from PIL import Image

import sys  # noqa: E402
sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.api import PS1Play  # noqa: E402

OUT = "/home/z/my-project/ps1ai/scratch/r22t6_poypoy/run1"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}

# r19-proven (r21-used) per-fighter screen-position i32 slots (RAM offsets)
P = {"1P": (0x142EF8, 0x142F00), "2P": (0x13247C, 0x132480),
     "3P": (0x1E12EC, 0x1E12F0), "4P": (0x083114, 0x08311C)}
CAM = 0x0A09CC
CLUSTER = [0x9F778, 0x9F780, 0x9F7B0, 0x9F7EA]
HEART_KNOWN = 0x9DF00            # r21: one fighter's u32 heart counter (3P)

os.makedirs(OUT, exist_ok=True)
R = {"task": "r22t6 boot1", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "states": {}, "live": [], "cells": {}, "verdict": None}


def ram(p):
    return np.frombuffer(bytes(p.core.ram[:]), dtype=np.uint8).copy()


def hud(p):
    a = np.asarray(p.core.frame_rgb(), dtype=np.int16)
    H, W = a.shape[:2]
    strip = a[int(H * 0.80):, :, :]
    rs, gs, bs = strip[..., 0], strip[..., 1], strip[..., 2]
    qw = W // 4
    out = []
    for q in range(4):
        r_, g_, b_ = (s[:, q * qw:(q + 1) * qw] for s in (rs, gs, bs))
        out.append({"hearts": int(((r_ > 150) & (g_ < 95) & (b_ < 95)).sum()),
                    "mag": int(((r_ > 160) & (b_ > 120) & (g_ < 110)
                                & (b_ <= r_ + 40)).sum())})
    return out


def load_snap(p, tag, state, settle=10, extra=()):
    p.load_state(state)
    p.core.run(settle)
    snap = ram(p)
    np.savez_compressed(f"{OUT}/{tag}.npz", ram=snap)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/{tag}.png")
    R["states"][tag] = {"state": state, "hud": hud(p)}
    out = {tag: snap}
    for add, tag2 in extra:
        p.core.run(add)
        s2 = ram(p)
        np.savez_compressed(f"{OUT}/{tag2}.npz", ram=s2)
        Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/{tag2}.png")
        R["states"][tag2] = {"state": state, "hud": hud(p), "settle": add}
        out[tag2] = s2
    return out


def scan_cells(snaps, tags):
    """Words with value in [0..4] everywhere, ==4 at C(fresh), ==0 at B
    (retired), width u8/u16/u32. 4-byte aligned for u32, 2-byte for u16."""
    C = snaps["C_fresh"]
    B = snaps["B_retire2"]
    out = []
    for width, dt, align in ((1, np.uint8, 1), (2, "<u2", 2), (4, "<u4", 4)):
        views = {}
        for t, s in snaps.items():
            v = s.view(dt)
            views[t] = v[: (len(v) // align) * align]
        cv, bv = views["C_fresh"], views["B_retire2"]
        c_ok = (cv == 4)
        b_ok = (bv == 0)
        in4 = np.ones(len(cv), bool)
        for t, v in views.items():
            in4 &= (v <= 4)
        mask = c_ok & b_ok & in4
        for t, v in views.items():
            if t.startswith("B") or t == "C_fresh":
                continue
            mask &= (v == 4) | (t == "A_3p1") | (v != 4)
        # A: a heart cell may be 4 (full) or 1 (3P) at A
        mask &= (views["A_3p1"] == 4) | (views["A_3p1"] == 1)
        idxs = np.nonzero(mask)[0]
        for i in idxs:
            off = i * align
            vec = {t: int(views[t][i]) for t in tags}
            out.append({"off": off, "va": hex(0x80000000 + off),
                        "width": width, "vec": vec})
    # dedupe: prefer widest width at same address
    best = {}
    for c in out:
        k = c["off"]
        if k not in best or c["width"] > best[k]["width"]:
            best[k] = c
    res = sorted(best.values(), key=lambda c: c["off"])
    return res


def struct_dump(rr, off, span=0x40):
    lo = max(0, off - span)
    hi = min(len(rr), off + span)
    chunk = rr[lo:hi]
    words32 = [(lo + i, int.from_bytes(chunk[i:i + 4], "little", signed=True))
               for i in range(0, len(chunk) - 3, 4)]
    coords = [(hex(0x80000000 + o), v) for o, v in words32
              if -32768 <= v <= 32768 and abs(v) > 3]
    return coords[:24]


def main():
    t0 = time.time()
    p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
    R["boot"] = {k: p.boot().get(k) for k in ("core", "serial")}

    snaps = {}
    snaps.update(load_snap(p, "C_fresh", "r19_f600"))
    snaps.update(load_snap(p, "A_3p1", "r20t4_retire"))
    snaps.update(load_snap(p, "L_abl", "r21t6_ablation_end"))
    snaps.update(load_snap(p, "B_retire2", "r21t6_retire2",
                           settle=10, extra=((120, "B_retire2_t130"),)))

    tags = ["C_fresh", "A_3p1", "L_abl", "B_retire2", "B_retire2_t130"]
    cands = scan_cells(snaps, tags)
    print(f"[cells] candidates: {len(cands)}")
    known = [c for c in cands if c["off"] == HEART_KNOWN]
    print("[cells] known 0x9DF00 vector:", known)
    for c in cands[:60]:
        print(f"    u{c['width']*8} @0x{c['off']:05X} ({c['va']}): {c['vec']}")

    # ---- live trace from A (all fighters alive at A) ----
    p.load_state("r20t4_retire")
    p.core.run(10)
    trace = []
    for i in range(24):
        p.core.run(8)
        rr = ram(p)
        row = {"fc": p.core.frames_run}
        for k, (x, y) in P.items():
            row[f"{k}_x"] = int(np.frombuffer(rr[x:x + 4].tobytes(), "<i4")[0])
            row[f"{k}_y"] = int(np.frombuffer(rr[y:y + 4].tobytes(), "<i4")[0])
        row["cam"] = int(np.frombuffer(rr[CAM:CAM + 4].tobytes(), "<i4")[0])
        row["cluster"] = [int(np.frombuffer(rr[a:a + 2].tobytes(), "<u2")[0])
                          for a in CLUSTER]
        # fields near the known heart cell
        row["near_DF00"] = {
            hex(o): int(np.frombuffer(rr[o:o + 4].tobytes(), "<i4")[0])
            for o in (0x9DEB0, 0x9DEB4, 0x9DEC4, 0x9DED0, 0x9DEE4, 0x9DEEC,
                      0x9DF00, 0x9DF04, 0x9DF08)}
        trace.append(row)
        R["live"].append(row)
    var = {k: (min(r[k] for r in trace), max(r[k] for r in trace))
           for k in trace[0] if k.endswith(("_x", "_y"))}
    print("[live] slot min/max:", json.dumps(var))
    R["live_slot_range"] = {k: [v[0], v[1]] for k, v in var.items()}

    # struct walk around candidate cells using the LAST live frame
    rr = ram(p)
    for c in cands[:20]:
        c["nearby_coords"] = struct_dump(rr, c["off"])
    R["cells"] = cands
    R["wall_s"] = round(time.time() - t0, 1)
    json.dump(R, open(f"{OUT}/map.json", "w"), indent=1)
    print(json.dumps({k: R.get(k) for k in
                      ("boot", "states", "live_slot_range", "wall_s")}, indent=1)[:2000])


if __name__ == "__main__":
    main()
