#!/usr/bin/env python3
"""r21t6_poypoy_hparray.py — run 3: isolate the per-fighter heart array.

Three same-lineage states loaded in ONE process, RAM snapshots SAVED to
disk (npz) so the diff never needs an emulator again:
  C = r19_f600      (fresh round start, all fighters full hearts)
  A = r20t4_retire  (3P at 1 heart after r20's VLM-verified hit)
  B = r21t6_retire2 (1P/2P/3P retired, 4P alive at 1 heart)

Scans (u8/u16/u32 x strides 1..64):
  C->A: 3P-lane decreased by 1..3, other lanes UNCHANGED (r20 hit only
        touched 3P) — the r20-style signature, now on true RAM.
  A->B: lanes 1P/2P/3P decreased, 4P UNCHANGED (4P survived, DANGER).
  Intersection of both = high-confidence heart/HP array.
Settle after each load is only 6 frames (HUD animation incomplete but
RAM state valid; +30f settle in run 2 let card 1 animate to empty).
"""
import json
import os
import time

import numpy as np
from PIL import Image

import sys  # noqa: E402
sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.api import PS1Play  # noqa: E402

OUT = "/home/z/my-project/ps1ai/scratch/r21t6_poypoy/run3"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}
os.makedirs(OUT, exist_ok=True)
R = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
LANE = {0: "1P", 1: "2P", 2: "3P", 3: "4P"}   # working hypothesis


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
        out.append({"hearts": int(((r_ > 150) & (g_ < 95)
                                   & (b_ < 95)).sum()),
                    "mag": int(((r_ > 160) & (b_ > 120) & (g_ < 110)
                                & (b_ <= r_ + 40)).sum())})
    return out


def scan(A, B, dec_lanes, keep_lanes, dec_max=3):
    """Groups where lanes in dec_lanes decreased by 1..dec_max (B<A<=4)
    and lanes in keep_lanes unchanged. Returns dict keyed by width."""
    out = {}
    for width, dt in ((1, np.uint8), (2, "<u2"), (4, "<u4")):
        av, bv = A.view(dt), B.view(dt)
        hits = []
        for s in (1, 2, 4, 8, 16, 32, 64):
            step = s // width
            if step < 1:
                continue
            seed = np.nonzero((bv < av) & (av - bv <= dec_max)
                              & (av <= 4) & (bv <= 3))[0]
            for k in range(4):
                base_idx = seed - k * step
                ok = (base_idx >= 0) & (base_idx + 3 * step < len(av))
                base_idx = np.unique(base_idx[ok])
                if len(base_idx) == 0:
                    continue
                good = np.ones(len(base_idx), bool)
                for j in range(4):
                    jj = base_idx + j * step
                    if j in dec_lanes:
                        good &= (bv[jj] < av[jj]) & (av[jj] - bv[jj] <= dec_max) \
                            & (av[jj] <= 4) & (bv[jj] <= 3)
                    else:
                        good &= av[jj] == bv[jj]
                for bi in base_idx[good]:
                    hits.append({"base": int(bi) * width, "stride": s,
                                 "A": [int(av[bi + j * step])
                                       for j in range(4)],
                                 "B": [int(bv[bi + j * step])
                                       for j in range(4)]})
        seen, ded = set(), []
        for h in hits:
            key = (h["base"], h["stride"])
            if key not in seen:
                seen.add(key)
                ded.append(h)
        out[width] = ded
    return out


def main():
    t0 = time.time()
    p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
    R["boot"] = {k: p.boot().get(k) for k in ("core", "serial")}
    snaps = {}
    for tag, state in (("C_r19f600", "r19_f600"),
                       ("A_r20t4retire", "r20t4_retire"),
                       ("B_r21t6retire2", "r21t6_retire2")):
        p.load_state(state)
        p.core.run(6)
        snaps[tag] = ram(p)
        np.savez_compressed(f"{OUT}/{tag}.npz", ram=snaps[tag])
        R[f"hud_{tag}"] = hud(p)
        Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/{tag}.png")
        print(f"[load] {tag}: hud={R[f'hud_{tag}']}")

    C, A, B = snaps["C_r19f600"], snaps["A_r20t4retire"], \
        snaps["B_r21t6retire2"]

    # C->A: only the 3P lane should have dropped (r20 hit), others equal
    sCA = scan(C, A, dec_lanes={2}, keep_lanes={0, 1, 3})
    # A->B: 1P/2P/3P dropped (retired), 4P unchanged (survived @DANGER)
    sAB = scan(A, B, dec_lanes={0, 1, 2}, keep_lanes={3})
    for name, s in (("C_to_A_3p_only", sCA), ("A_to_B_retires", sAB)):
        R[name] = {str(w): v[:25] for w, v in s.items()}
        print(f"[scan {name}] " + ", ".join(
            f"w{w}:{len(v)}" for w, v in s.items()))

    # intersection on base address (any width/stride)
    basesCA = {h["base"] for v in sCA.values() for h in v}
    basesAB = {h["base"] for v in sAB.values() for h in v}
    inter = sorted(basesCA & basesAB)
    R["intersection_bases"] = [hex(b) for b in inter]
    print("[intersect] common bases:", [hex(b) for b in inter][:20])
    # detail rows for intersection
    detail = []
    for v in list(sCA.values()) + list(sAB.values()):
        for h in v:
            if h["base"] in basesAB and h["base"] in basesCA:
                detail.append(h)
    # dedupe by base
    seen, dd = set(), []
    for h in detail:
        if h["base"] not in seen:
            seen.add(h["base"])
            dd.append(h)
    R["intersection_detail"] = dd[:20]
    for h in dd[:20]:
        print("    ", h)

    R["wall_s"] = round(time.time() - t0, 1)
    R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(R, open(f"{OUT}/hparray.json", "w"), indent=1)
    print(json.dumps({k: R[k] for k in ("hud_C_r19f600", "hud_A_r20t4retire",
                                        "hud_B_r21t6retire2", "wall_s")},
                     indent=1))


if __name__ == "__main__":
    main()
