#!/usr/bin/env python3
"""r15_flappy_boot.py — FlappyBirdPSX (Unlicense, IcePanorama) first boot.

Route: the game SHIPS a proper MODE2/2352 image WITH license sectors
("Licensed by Computer Entertainment Amer..." at sector 4) -> the proven
license-route applies (same as Tetrade/PSXMC/Doukutsu). No EXE-load games
here: BOOT=cdrom0:\\FLPPYBIR.EXE;1 via SYSTEM.CNF.

Plan:
  1. one boot, ~2400 frames
  2. PNG timeline every 60 frames + per-60 frame-mean log
  3. whole-RAM i32 delta scan (t vs t+1) -> candidate bird-y words
     (small |d|, screen-range values)
  4. screen classify by inspection of saved PNGs
Evidence -> scratch/round15_flappy/boot/
"""
import json
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from hellopong_r12_lib import make_jrn, save_png, i32, u32  # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "flappybird.cue")
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")
OUT = os.path.join(REPO, "scratch", "round15_flappy", "boot")
WS = "/home/z/my-project/emu/games_homebrew/ws_r15_flappy"

TOTAL = 2400


def main():
    os.makedirs(OUT, exist_ok=True)
    jrn = make_jrn(OUT, "[fboot]")
    t0 = time.time()
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot_info = p.boot()
    jrn({"ev": "boot", "core": boot_info})
    jrn({"ev": "fw_trust", "evidence": labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", [])) is not None})

    timeline = []
    means = []
    for f in range(TOTAL):
        p.core.run(1, set())
        if f % 60 == 0:
            fr = p.core.frame_rgb()
            g = fr.mean(axis=2)
            means.append((f, round(float(g.mean()), 2)))
            save_png(OUT, fr, f"t{f:05d}.png")
    jrn({"ev": "means", "series": means})

    # any-button probe: the GET READY screen needs ONE button press to
    # seed RNG and start (cmd_seed_rng mask 0xFFFF -> any button)
    fr = p.core.frame_rgb()
    save_png(OUT, fr, "pre_press.png")
    p.core.run(3, {"X"})
    p.core.run(3, set())
    for f in range(120):
        p.core.run(1, set())
    fr = p.core.frame_rgb()
    save_png(OUT, fr, "post_press.png")
    g = fr.mean(axis=2)
    jrn({"ev": "post_press_mean", "mean": round(float(g.mean()), 2)})

    # ---- RAM delta scan: bird-y candidates (2 samples 1 frame apart) ----
    def snap():
        return bytes(p.mem.snapshot())

    s0 = snap()
    p.core.run(1, set())
    s1 = snap()
    p.core.run(1, set())
    s2 = snap()
    a0, a1, a2 = i32(s0), i32(s1), i32(s2)
    d1 = a1.astype(np.int64) - a0.astype(np.int64)
    d2 = a2.astype(np.int64) - a1.astype(np.int64)
    cand = []
    for idx in range(len(a0)):
        if abs(d1[idx]) == 0 or abs(d1[idx]) > 1024:
            continue
        if abs(d2[idx]) == 0 or abs(d2[idx]) > 1024:
            continue
        v1, v2 = int(a1[idx]), int(a2[idx])
        if -20000 < v1 < 20000 and -20000 < v2 < 20000:
            cand.append((idx * 4, int(a0[idx]), v1, v2, int(d1[idx]), int(d2[idx])))
    jrn({"ev": "ram_delta_cands", "n": len(cand),
         "sample": cand[:40]})
    # pipe-x candidates: world x decreasing by exactly 45/frame
    pipes = [(c[0], c[1], c[2], c[3]) for c in cand if c[4] == -45 and c[5] == -45]
    jrn({"ev": "pipe_x_cands_vel45", "n": len(pipes), "list": pipes[:24]})
    save_png(OUT, p.core.frame_rgb(), "final.png")
    jrn({"ev": "done", "wall_s": round(time.time() - t0, 1)})


if __name__ == "__main__":
    main()
