#!/usr/bin/env python3
"""msx_clamp_globals_diff.py — the D7 experiment DECLARED in the
session-2 worklog: with the FIXED u32 reader, diff the camera-adjacent
globals (0xD4938/0xD4970/0xD4974/0xD4A1C + the surrounding data window)
between a pre-clamp walk and the clamped stall, to find the
village-section scroll-LIMIT variable and any completion flag.

Method (read-only observation; the ONLY assist is the disclosed
hp_pair_freeze EXPLORATION freeze used for the reach, same precedent as
gif_story_run phase_b / heli-ladder):
  P  pre-clamp walk (RIGHT held) from mission start to px>=650
     -> full-RAM snapshot A
  W  keep walking until px stalls (player hits the ~1164 screen-edge
     clamp while the scroll stops at ~988) -> savestate clamp0 + PNG
  C  clamped stall: keep holding RIGHT 20 chunks, recording
     -> full-RAM snapshot B
Analysis (numpy, in-script, artifacts saved for re-analysis):
  LIMIT_CONST32  u32 unchanged A->B, value>>16 in [880..1150]
  SCROLL32       u32 changed A->B, B>>16 in [940..1030] (the ~988
                 saturation), A>>16 in [500..900] (was following)
  FLIP16         u16 in the window that flipped A->B (state candidates)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np                                    # noqa: E402
from PIL import Image                                 # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                         # noqa: E402
from mission import ensure_mission                    # noqa: E402
from issue4_controller import boot                    # noqa: E402
import msx_gate_probe as gp                           # noqa: E402

EVID = os.path.join(
    labconfig.resolve_path("evidence_dir"), "clamp_globals")
WINDOW_LO, WINDOW_HI = 0xD4900, 0xD4B00          # u32 dump window
NAMED = [0xD4938, 0xD4970, 0xD4974, 0xD4A1C]
# words sampled per-row in addition to the window (scroll struct +
# flips + candidates found in clampdiff1)
EXTRA = [0xEB590, 0xEB594, 0xEB598, 0xEB59C, 0xEB5A0, 0xEB5D0,
         0xD4A22, 0xD494E, 0xD4958]
PAIR = (0xCA2F6, 0xCA2FE)
RAM_SIZE = 0x200000


def log(*a):
    print("[clampdiff]", *a, flush=True)


def px_of(m):
    return int(m.u32(0x0CA2E0)) >> 16


def png(p, outdir, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))


def row_of(p, m):
    w = m.ram[WINDOW_LO:WINDOW_HI].view("<u4").astype(np.uint32)
    row = {"f": int(p.core.frames_run), "px": px_of(m),
           "hp0": int(m.u16(PAIR[0])), "hp1": int(m.u16(PAIR[1])),
           "w": {f"{a:X}": int(v) for a, v in
                 zip(range(WINDOW_LO, WINDOW_HI, 4), w)},
           "x": {f"{a:X}": int(m.u32(a)) for a in EXTRA}}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="clampdiff1")
    ap.add_argument("--max-chunks", type=int, default=50)
    ap.add_argument("--stall-chunks", type=int, default=20)
    args = ap.parse_args()

    outdir = os.path.join(EVID, args.tag)
    os.makedirs(outdir, exist_ok=True)
    p, fwmode = boot()
    m = p.mem
    ensure_mission(p, tries=4)
    sess = gp.freeze_now(p, "clampdiff_reach")   # disclosed EXPLORATION
    v0 = int(m.u16(PAIR[0]))
    log(f"start px={px_of(m)} hp={v0} fw={fwmode}")

    jf = open(os.path.join(outdir, "trace.jsonl"), "w")
    t0 = time.time()
    pxA = None
    snapA = None
    snapB = None
    snapC = None
    pxB = None
    clamped_at = None
    stall = 0
    phase = "P"
    px_prev = None
    c = -1
    for c in range(args.max_chunks):
        for _k in range(6):                       # 60f per chunk
            p.core.run(10, {"RIGHT"})
            jf.write(json.dumps(row_of(p, m)) + "\n")
        px = px_of(m)
        if phase == "P" and snapA is None and px >= 650:
            snapA = m.snapshot()
            pxA = px
            png(p, outdir, "snapA.png")
            log(f"snapshot A at px={px} frame={p.core.frames_run}")
        if phase == "P" and px >= 650:
            phase = "W"
        if px_prev is not None:
            d = px - px_prev
            stall = stall + 1 if abs(d) < 1.5 else 0
            if stall == 3 and clamped_at is None:
                clamped_at = px
                pxB = px
                snapB = m.snapshot()          # AT pin arrival, pre-death
                p.save_state("clamp0")
                png(p, outdir, "clamp_arrival.png")
                log(f"CLAMP reached px={px} frame={p.core.frames_run} "
                    f"-> snapshot B + savestate clamp0")
            if stall == 3 + 8 and snapC is None:
                snapC = m.snapshot()          # ~8 chunks still pinned
                log(f"snapshot C at px={px} frame={p.core.frames_run}")
        px_prev = px
        if clamped_at is not None and stall >= 3 + args.stall_chunks:
            break
    if snapC is None:
        snapC = snapB
    np.save(os.path.join(outdir, "snapA.npy"), snapA)
    np.save(os.path.join(outdir, "snapB.npy"), snapB)
    np.save(os.path.join(outdir, "snapC.npy"), snapC)

    # ---------- analysis (pin-boundary aware) ----------
    a32 = snapA.view("<u4")
    b32 = snapB.view("<u4")
    c32 = snapC.view("<u4")
    rep = {"schema": "ps1play-clampdiff/2",
           "tag": args.tag, "firmware_mode": fwmode,
           "pxA": pxA, "pxB": pxB, "clamped_at": clamped_at,
           "pxC": px_of(m),
           "chunks": c + 1, "frames": int(p.core.frames_run),
           "wall_s": round(time.time() - t0, 1),
           "named": {f"{a:X}": {"A": int(a32[a // 4]),
                                "B": int(b32[a // 4]),
                                "C": int(c32[a // 4])}
                     for a in NAMED + EXTRA}}
    # B->C freezers: followed during the walk, FROZE at the pin while
    # RIGHT is still held — the clamp-involved set
    dAB = a32 != b32
    dBC = b32 != c32
    freezer = np.where(dAB & ~dBC)[0]
    rep["FREEZE_AT_PIN"] = [
        {"addr": f"{i * 4:X}", "A": int(a32[i]), "B": int(b32[i]),
         "C": int(c32[i])}
        for i in freezer.tolist()
        if 0xCA0000 <= i * 4 < 0xF0000][:120]
    rep["n_freeze_pin"] = int(len(freezer))
    # flips exactly at the pin (completion-state candidates)
    flip_pin = np.where(~dAB & dBC)[0]
    rep["FLIP_AT_PIN"] = [
        {"addr": f"{i * 4:X}", "A": int(a32[i]), "B": int(b32[i]),
         "C": int(c32[i])}
        for i in flip_pin.tolist()
        if 0xCA0000 <= i * 4 < 0xF0000][:120]
    rep["n_flip_pin"] = int(len(flip_pin))
    # limit-constant candidates: unchanged A->B->C, plausible pin px
    lim = np.where((a32 == b32) & (b32 == c32)
                   & (a32 >= 1140 << 16) & (a32 <= 1190 << 16))[0]
    rep["LIMIT_CANDIDATES"] = [
        {"addr": f"{i * 4:X}", "val": int(a32[i]),
         "px": int(a32[i]) >> 16} for i in lim.tolist()][:80]
    # u16 limit candidates near 1163/72 tiles
    a16 = snapA.view("<u2")
    b16 = snapB.view("<u2")
    c16 = snapC.view("<u2")
    lim16 = np.where((a16 == b16) & (b16 == c16)
                     & (((a16 >= 1140) & (a16 <= 1190))
                        | ((a16 >= 71) & (a16 <= 74))))[0]
    rep["LIMIT16_CANDIDATES"] = [
        {"addr": f"{i * 2:X}", "val": int(a16[i])} for i in
        lim16.tolist() if 0xCA0000 <= i * 2 < 0xF0000][:80]
    rep["n_limit16"] = int(len(lim16))
    with open(os.path.join(outdir, "analysis.json"), "w") as f:
        json.dump(rep, f, indent=1)
    log("analysis:", os.path.join(outdir, "analysis.json"))
    log(f"RESULT pxA={pxA} clamped_at={clamped_at} "
        f"freeze_at_pin={rep['n_freeze_pin']} "
        f"flip_at_pin={rep['n_flip_pin']} "
        f"limit32={len(rep['LIMIT_CANDIDATES'])} "
        f"limit16_window={len(rep['LIMIT16_CANDIDATES'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
