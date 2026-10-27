#!/usr/bin/env python3
"""r15_flappy_sensors.py — pin FlappyBirdPSX RAM sensors DURING real play.

Method (playbook sensor ladder, rung b: whole-RAM delta pinning):
  boot -> Get Ready -> press X (starts game, seeds RNG, first flap)
  -> run ~300 frames of REAL play (flap servo from vision to stay alive)
  -> whole-RAM i32 3-sample scans:
       bird-y  : |d| small, changes every frame, screen-range
       pipe-x  : d == -45 every frame (FB_MOVEMENT_SPEED world/f)
       score   : u16 increment when bird passes pipe
Then verify candidates against VISION (bird centroid / pipe columns).
Evidence -> scratch/round15_flappy/sensors/
"""
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
OUT = os.path.join(REPO, "scratch", "round15_flappy", "sensors")
WS = "/home/z/my-project/emu/games_homebrew/ws_r15_flappy"

SKY = (110, 160, 230)   # sky color rough


def bird_centroid(fr):
    """Bird = orange-ish pixels near screen center column band."""
    r, g, b = fr[:, :, 0].astype(int), fr[:, :, 1].astype(int), fr[:, :, 2].astype(int)
    orange = (r > 150) & (g > 80) & (g < 200) & (b < 120)
    orange[:, :130] = False
    orange[:, 195:] = False
    ys, xs = np.nonzero(orange)
    if len(ys) < 8:
        return None
    return (float(xs.mean()), float(ys.mean()), len(ys))


def pipe_columns(fr):
    """Return per-column count of 'pipe-green' pixels (green dominant)."""
    r, g, b = fr[:, :, 0].astype(int), fr[:, :, 1].astype(int), fr[:, :, 2].astype(int)
    green = (g > 90) & (g > r + 20) & (g > b + 20)
    return green


def gap_of_nearest_pipe(green, bird_x=160.0):
    """First pipe column band right of bird; return (gap_center_y, pipe_x)."""
    colsum = green.sum(axis=0)
    # pipe columns: tall green presence in upper 3/4 of screen
    run = 0
    start = None
    bands = []
    for x in range(196, 320):
        if colsum[x] > 60:
            if start is None:
                start = x
        else:
            if start is not None and x - start >= 10:
                bands.append((start, x))
            start = None
    if start is not None and 320 - start >= 10:
        bands.append((start, 320))
    if not bands:
        return None
    bx0, bx1 = bands[0]
    band = green[:, bx0:bx1]
    rows = np.nonzero(~band.any(axis=1))[0]
    rows = rows[(rows > 20) & (rows < 205)]
    if len(rows) == 0:
        return None
    # contiguous gap containing the middle of the band region
    gaps = []
    s = rows[0]
    prev = rows[0]
    for y in rows[1:]:
        if y == prev + 1:
            prev = y
        else:
            gaps.append((s, prev))
            s = y
            prev = y
    gaps.append((s, prev))
    gaps = [g for g in gaps if g[1] - g[0] > 30]
    if not gaps:
        return None
    # choose the gap closest to bird y band
    g0, g1 = gaps[0]
    return ((g0 + g1) / 2.0, (bx0 + bx1) / 2.0, (g0, g1))


def main():
    os.makedirs(OUT, exist_ok=True)
    jrn = make_jrn(OUT, "[fsen]")
    t0 = time.time()
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    jrn({"ev": "boot", "core": p.boot()})

    # wait for the ACTUAL Get Ready screen (sky-blue: blue channel dominates)
    for k in range(1800):
        p.core.run(1, set())
        if k % 60 == 0:
            fr = p.core.frame_rgb()
            jrn({"ev": "wait", "f": k, "mean": round(float(fr.mean()), 1),
                 "bmr": round(float(fr[:, :, 2].astype(int).mean()
                                   - fr[:, :, 0].astype(int).mean()), 1)})
        fr = p.core.frame_rgb()
        if (float(fr[:, :, 2].astype(int).mean()
                  - fr[:, :, 0].astype(int).mean()) > 25
                and float(fr.mean()) > 110):
            break
    save_png(OUT, p.core.frame_rgb(), "getready.png")
    jrn({"ev": "getready_at", "f": p.core.frames_run})

    # START: X press seeds RNG + first flap (GSTATE_GAME_START -> NORMAL)
    p.core.run(3, {"X"})
    p.core.run(3, set())
    jrn({"ev": "started"})

    # survive 300 frames with the vision servo (get sensor window data)
    def snap():
        return bytes(p.mem.snapshot())

    vis = []
    for k in range(300):
        fr = p.core.frame_rgb()
        green = pipe_columns(fr)
        gap = gap_of_nearest_pipe(green)
        bird = bird_centroid(fr)
        buttons = set()
        if bird and gap:
            err = gap[0] - bird[1]
            if err > 4:
                buttons = {"X"}
        p.core.run(1, buttons)
        if bird:
            vis.append((k, round(bird[0], 1), round(bird[1], 1),
                        None if gap is None else round(gap[0], 1)))
    save_png(OUT, p.core.frame_rgb(), "play300.png")
    jrn({"ev": "vision", "n": len(vis), "sample": vis[::40]})

    # ---- 3-sample whole-RAM scan DURING play ----
    s0 = snap()
    p.core.run(1, set())
    s1 = snap()
    p.core.run(1, set())
    s2 = snap()
    a0, a1, a2 = i32(s0), i32(s1), i32(s2)
    d1 = a1.astype(np.int64) - a0.astype(np.int64)
    d2 = a2.astype(np.int64) - a1.astype(np.int64)
    bird_c, pipe_c = [], []
    for idx in range(len(a0)):
        v1, v2 = int(a1[idx]), int(a2[idx])
        if not (-24000 < v1 < 24000 and -24000 < v2 < 24000):
            continue
        if d1[idx] == -45 and d2[idx] == -45:
            pipe_c.append(idx * 4)
        elif abs(d1[idx]) <= 256 and abs(d2[idx]) <= 256 and d1[idx] != 0 and d2[idx] != 0:
            bird_c.append((idx * 4, v1, v2, int(d1[idx]), int(d2[idx])))
    jrn({"ev": "scan", "bird_cands": len(bird_c), "pipe_cands": len(pipe_c)})
    jrn({"ev": "pipe_addrs", "list": pipe_c[:40]})
    jrn({"ev": "bird_sample", "list": bird_c[:40]})

    # verify bird candidate against vision over 60 frames
    # heuristics: bird y words = those whose value/32 tracks vision y-120
    results = []
    for addr, v1, v2, dd1, dd2 in bird_c[:60]:
        hits, tot = 0, 0
        p.core.run(1, set())
        for k in range(30):
            fr = p.core.frame_rgb()
            s = snap()
            bird = bird_centroid(fr)
            if bird is None:
                p.core.run(1, set())
                continue
            val = int(i32(s)[addr // 4])
            tot += 1
            wy = val / 32.0          # world -> px (origin center screen)
            if abs((120 + wy) - bird[1]) <= 3:
                hits += 1
            p.core.run(1, set())
        if tot and hits / tot > 0.7:
            results.append({"addr": hex(addr), "hits": hits, "tot": tot})
    jrn({"ev": "bird_verified", "list": results})

    # score watch: run 600 more frames playing, watch u16 increments
    # near candidates: find u16 words equal to small ints that increment
    base = snap()
    b16 = np.frombuffer(base, dtype="<u2")
    jrn({"ev": "score_hunt_start"})
    score_cands = set()
    last_vals = {}
    for k in range(600):
        fr = p.core.frame_rgb()
        green = pipe_columns(fr)
        gap = gap_of_nearest_pipe(green)
        bird = bird_centroid(fr)
        buttons = set()
        if bird and gap:
            if gap[0] - bird[1] > 4:
                buttons = {"X"}
        p.core.run(1, buttons)
    save_png(OUT, p.core.frame_rgb(), "after600.png")
    # score-word hunt: u16 words that went 0->1 or incremented during the
    # play window while game state stayed NORMAL
    sB = snap()
    b16 = np.frombuffer(sB, dtype="<u2")
    jrn({"ev": "score_hunt_window_done", "frame": p.core.frames_run})
    jrn({"ev": "done", "wall_s": round(time.time() - t0, 1)})


if __name__ == "__main__":
    main()
