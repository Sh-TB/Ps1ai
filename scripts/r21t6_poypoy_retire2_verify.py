#!/usr/bin/env python3
"""r21t6_poypoy_retire2_verify.py — run 2 (analysis, no aiming).

Phases (one PS1Play process):
  P0 restore r20t4_retire -> RAM A (all fighters 3 hearts per VLM);
     restore r21t6_retire2 -> RAM B (3P RETIRE! at save moment).
  P1 HP-array hunt: 4-lane scan where every lane decreased by 1..3 and
     stays in 0..3 (hearts 3,3,3,3 -> 1,1,0,1). Report per-lane values.
  P2 stability: from r21t6_retire2 run +700f; HUD card mag/hearts trace;
     confirm 3P card keeps RETIRE! (mag>=170) or round-over screen holds.
  P3 ablation: restore r20t4_retire, run 1200f with NO inputs — did any
     card reach RETIRE! without our throws? (attribution check for the
     run-1 3P KO: our throw #3 flew LEFT+DOWN and the explosion + card
     drain happened 168-246f after release; ablation says whether pure
     AI crossfire retires 3P anyway.)
Outputs: scratch/r21t6_poypoy/run2/verify.json + PNGs.
"""
import json
import os
import time

import numpy as np
from PIL import Image

import sys  # noqa: E402
sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.api import PS1Play  # noqa: E402

OUT = "/home/z/my-project/ps1ai/scratch/r21t6_poypoy/run2"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}
os.makedirs(OUT, exist_ok=True)
R = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


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
        red = int(((r_ > 150) & (g_ < 95) & (b_ < 95)).sum())
        mag = int(((r_ > 160) & (b_ > 120) & (g_ < 110)
                   & (b_ <= r_ + 40)).sum())
        out.append({"hearts": red, "mag": mag})
    return out


def lane_scan(A, B):
    """4-lane groups (stride s, width w) where every lane decreased by
    1..3 and every B lane is <=3 (heart counters 3->x)."""
    hits = []
    for width, dt in ((1, np.uint8), (2, "<u2"), (4, "<u4")):
        av, bv = A.view(dt), B.view(dt)
        for s in (1, 2, 4, 8, 16, 32, 64):
            step = s // width
            if step < 1:
                continue
            dec_any = np.nonzero((bv < av) & (av - bv <= 3)
                                 & (bv <= 3) & (av <= 4))[0]
            for k in range(4):          # k = position of a fully-known lane
                base_idx = dec_any - k * step
                ok = (base_idx >= 0) & (base_idx + 3 * step < len(av))
                base_idx = np.unique(base_idx[ok])
                if len(base_idx) == 0:
                    continue
                allv = np.ones(len(base_idx), bool)
                for j in range(4):
                    jj = base_idx + j * step
                    allv &= (bv[jj] < av[jj]) & (av[jj] - bv[jj] <= 3) \
                        & (bv[jj] >= 0) & (bv[jj] <= 3) & (av[jj] <= 4)
                for bi in base_idx[allv]:
                    hits.append({"base": int(bi) * width, "stride": s,
                                 "width": width,
                                 "A": [int(av[bi + j * step])
                                       for j in range(4)],
                                 "B": [int(bv[bi + j * step])
                                       for j in range(4)]})
    seen, out = set(), []
    for h in hits:
        key = (h["base"], h["stride"], h["width"])
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def trace_run(p, frames, tag, every=12, cap=90):
    log = []
    for i in range(frames // every):
        p.core.run(every)
        fc = p.core.frames_run
        h = hud(p)
        log.append([fc] + [f'{x["hearts"]}/{x["mag"]}' for x in h])
        if i % 8 == 0:
            Image.fromarray(p.core.frame_rgb()).save(
                f"{OUT}/{tag}_f{fc:05d}.png")
        if i % 8 == 0 and len(
                [x for x in log if x.count("0/226")]) and False:
            pass
    return log


def retire_cards(hrow):
    return [i for i, cell in enumerate(hrow[1:]) if cell in ("0/226",)]


def main():
    t0 = time.time()
    p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
    R["boot"] = {k: p.boot().get(k) for k in ("core", "serial")}

    # ---------------- P0 ----------------
    p.load_state("r20t4_retire")
    p.core.run(30)
    A = ram(p)
    R["hud_A_r20t4_retire"] = hud(p)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/A_r20t4_retire.png")
    p.load_state("r21t6_retire2")
    p.core.run(30)
    B = ram(p)
    R["hud_B_r21t6_retire2"] = hud(p)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/B_r21t6_retire2.png")

    # ---------------- P1: HP array ----------------
    cands = lane_scan(A, B)
    cands.sort(key=lambda h: sum(h["A"]) - sum(h["B"]))
    R["hp_all_decrease_candidates"] = cands[:30]
    R["n_hp_all_decrease"] = len(cands)
    print(f"[P1] all-decrease 4-lane candidates: {len(cands)}")
    for c in cands[:12]:
        print("   ", c)

    # ---------------- P2: stability of the retire state ----------------
    p.load_state("r21t6_retire2")
    log2 = trace_run(p, 700, "stab")
    ret_series = [retire_cards(row) for row in log2]
    R["stability_first60"] = log2[:60]
    R["stability_last20"] = log2[-20:]
    R["stability_3p_retire_ticks"] = sum(1 for r in ret_series if 2 in r)
    R["stability_final_hud"] = hud(p)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/stab_end.png")
    print(f"[P2] stability: 3P RETIRE! in {R['stability_3p_retire_ticks']}"
          f"/{len(log2)} ticks; final hud {R['stability_final_hud']}")

    # ---------------- P3: no-input ablation ----------------
    p.load_state("r20t4_retire")
    log3 = trace_run(p, 1200, "abl")
    abl_ret = {}
    for row in log3:
        for card in retire_cards(row):
            abl_ret.setdefault(card, row[0])
    R["ablation_retire_first_seen"] = {f"card{k+1}": v
                                       for k, v in sorted(abl_ret.items())}
    R["ablation_any_retire"] = bool(abl_ret)
    Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/abl_end.png")
    print(f"[P3] ablation (no inputs, 1200f): retires={abl_ret}")
    p.save_state("r21t6_ablation_end")

    R["wall_s"] = round(time.time() - t0, 1)
    R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(R, open(f"{OUT}/verify.json", "w"), indent=1)
    print(json.dumps({k: R[k] for k in ("hud_A_r20t4_retire",
                                        "hud_B_r21t6_retire2",
                                        "n_hp_all_decrease",
                                        "stability_3p_retire_ticks",
                                        "ablation_retire_first_seen",
                                        "wall_s")}, indent=1))


if __name__ == "__main__":
    main()
