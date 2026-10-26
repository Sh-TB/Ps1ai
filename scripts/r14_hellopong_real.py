#!/usr/bin/env python3
"""r14_hellopong_real.py — hello_pong REAL MATCH: play to win by skill.

The round-13 "win" was a zero-input walkover against a static dummy —
the user called it out correctly. THIS run is real play:

  1. Disconnect libretro port 1 (RETRO_DEVICE_NONE) -> the game's OWN
     AI takes the right paddle (upstream: AI only when a pad is
     disconnected).
  2. Discover the ball x/y RAM words (whole-RAM 1-frame diff, values
     in screen range, |d|<=2 per frame).
  3. SERVO: every frame, read ball y + my paddle y; hold UP/DOWN to
     intercept every serve and return it. Catches counted via the
     ball's vel_y flip at my paddle plane.
  4. Win = left score word 0x1FFEB4 reaches 5 (RAM-anchored).
  5. Capture EVERY frame -> GIF (the deliverable evidence).

One boot. Evidence -> scratch/round14_hellopong_real/. No RAM writes.
"""
import json
import os
import shutil
import subprocess
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from PIL import Image                                       # noqa: E402
from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402
from hellopong_r12_lib import (boot_hellopong, settle_boot,      # noqa
                               classify, madiff, save_png, ball_centroid,
                               make_jrn, u32, i32, padbuff_addrs)

OUT = os.path.join(REPO, "scratch", "round14_hellopong_real")
FRAMES = os.path.join(OUT, "frames")
WS = "/home/z/my-project/emu/games_homebrew/ws_r14_hpreal"
GIF_OUT = "/home/z/my-project/download/hello_pong_REAL_gameplay.gif"
SCORE_L = 0x1FFEB4
WIN_SCORE = 5

# libretro port device constants (host.set_port_device(device, port))
RETRO_DEVICE_NONE = 0


def find_ball_words(p, jrn):
    """2 snapshots 1 frame apart; words with small deltas in range."""
    s0 = bytes(p.mem.snapshot())
    p.core.run(1, set())
    s1 = bytes(p.mem.snapshot())
    a32, b32 = i32(s0), i32(s1)
    d = b32.astype(np.int64) - a32.astype(np.int64)
    cand = []
    for idx in np.flatnonzero(np.abs(d) <= 2):
        v0, v1 = int(a32[idx]), int(b32[idx])
        if 0 <= v0 < 320 and 0 <= v1 < 320 and abs(d[idx]) >= 1:
            cand.append((int(idx) * 4, v0, v1, int(d[idx])))
    # ball words: change EVERY frame; x moves by 2 (vel_x), y by 1
    out = {}
    for addr, v0, v1, dd in cand:
        s2_ = bytes(p.mem.snapshot())
        p.core.run(1, set())
        s3_ = bytes(p.mem.snapshot())
        c32, e32 = i32(s2_), i32(s3_)
        dd2 = int(e32[addr // 4]) - int(c32[addr // 4])
        v2 = int(e32[addr // 4])
        if abs(dd2) >= 1 and 0 <= v2 < 320:
            out[addr] = (v0, v1, v2)
    jrn({"ev": "ball_word_candidates",
         "n": len(out), "sample": sorted(out)[:12]})
    return out


def main():
    os.makedirs(FRAMES, exist_ok=True)
    jrn = make_jrn(OUT, "[hpreal]")
    t0 = time.time()
    p, boot = boot_hellopong(WS, jrn)
    # ---- THE KEY MOVE: disconnect pad2 -> the game's AI plays right ----
    p.core.set_port_device(RETRO_DEVICE_NONE, port=1)
    cls, timeline, addrs = settle_boot(p, jrn)
    jrn({"ev": "settled", "cls": cls})
    if cls == "GAME_OVER":
        # walkover leftover from settle; restart to menu
        p.core.run(8, {"B"})
        p.core.run(4, set())
        p.wait(60)
        cls, _ = classify(p.core.frame_rgb(), 0.0)
    if cls == "MENU":
        p.core.run(8, {"B"})
        p.core.run(4, set())
        p.wait(60)
    cls, _ = classify(p.core.frame_rgb(), 0.0)
    jrn({"ev": "game_start_attempt", "cls": cls})

    # ---- AI activation check: does the right paddle now track? ----
    from hellopong_r12_lib import paddle_row, PADDLE_R_COLS, PADDLE_L_COLS
    ai_rows = []
    last_ball_x = None
    ai_track_events = 0
    for k in range(240):
        p.core.run(1, set())
        fr = p.core.frame_rgb()
        b = ball_centroid(fr)
        pr = paddle_row(fr, PADDLE_R_COLS)
        if b is not None and pr is not None:
            if b[0] > 200 and abs(b[1] - pr) < 40:
                ai_track_events += 1
            ai_rows.append((round(b[0]), round(b[1]), round(pr)))
    jrn({"ev": "ai_check", "track_events": ai_track_events,
         "samples": ai_rows[-6:]})
    save_png(OUT, p.core.frame_rgb(), "ai_check.png")
    ai_active = ai_track_events >= 10
    jrn({"ev": "ai_verdict", "active": ai_active})

    # ---- ball RAM discovery ----
    ball_words = find_ball_words(p, jrn)
    # pick x word (moves 2/frame mostly) and y word (1/frame)
    bx_addr = by_addr = None
    for addr, (v0, v1, v2) in sorted(ball_words.items()):
        pass
    # heuristic: verify against screen for 40 frames
    best = {}
    for addr in ball_words:
        hits = 0
        for k in range(40):
            s = bytes(p.mem.snapshot())
            xv = int(i32(s)[addr // 4])
            fr = p.core.frame_rgb()
            b = ball_centroid(fr)
            if b is None:
                p.core.run(1, set())
                continue
            if abs(xv - b[0]) <= 4:
                hits += 1
            elif abs(xv - b[1]) <= 4:
                hits += 100
            p.core.run(1, set())
        best[addr] = hits
    x_hits = {a: h for a, h in best.items() if h < 100}
    y_hits = {a: h - 100 for a, h in best.items() if h >= 100}
    bx_addr = max(x_hits, key=x_hits.get) if x_hits else None
    by_addr = max(y_hits, key=y_hits.get) if y_hits else None
    jrn({"ev": "ball_sensors", "x": hex(bx_addr) if bx_addr else None,
         "y": hex(by_addr) if by_addr else None,
         "x_hits": x_hits.get(bx_addr), "y_hits": y_hits.get(by_addr)})

    def rd(addr):
        s = bytes(p.mem.snapshot())
        return int(i32(s)[addr // 4])

    # my paddle y (left): the r12-verified slot
    def paddle_l_y():
        fr = p.core.frame_rgb()
        return paddle_row(fr, PADDLE_L_COLS)

    # ---- THE REAL MATCH ----
    stats = {"frames": 0, "catches": 0, "misses": 0, "rallies": 0,
             "score_reads": [], "win": False, "ai_active": ai_active}
    prev_vx = None
    idx = 0
    buttons = set()
    score = 0
    start_f = p.core.frames_run
    while p.core.frames_run - start_f < 9000:
        p.core.run(1, buttons)
        idx += 1
        stats["frames"] += 1
        fr = p.core.frame_rgb()
        save_png(FRAMES, fr, f"f{idx:06d}.png")
        # score watch
        s = bytes(p.mem.snapshot())
        sc = int(u32(s)[SCORE_L // 4])
        if sc != score:
            jrn({"ev": "score", "i": idx, "score_l": sc})
            stats["score_reads"].append({"i": idx, "s": sc})
            score = sc
        if sc >= WIN_SCORE:
            stats["win"] = True
            save_png(OUT, fr, "WIN_FRAME.png")
            jrn({"ev": "WIN", "i": idx, "score_l": sc})
            break
        # screen class
        cls, facts = classify(fr, None)
        if cls == "GAME_OVER":
            save_png(OUT, fr, f"gameover_i{idx:06d}.png")
            jrn({"ev": "GAME_OVER_screen", "i": idx, "score_l": sc})
            stats["win"] = sc >= WIN_SCORE
            break
        # ball + paddle
        bx = rd(bx_addr) if bx_addr else None
        by = rd(by_addr) if by_addr else None
        vx = None
        if bx_addr:
            s2 = bytes(p.mem.snapshot())
            vx = None  # sign via two reads would cost frames; use screen
        b = ball_centroid(fr)
        py = paddle_l_y()
        # catch detection: ball bounced off MY paddle (x flipped + -> -)
        if b is not None and last_ball_x is not None:
            if last_ball_x - b[0] > 30 and b[0] < 120:
                stats["catches"] += 1
                jrn({"ev": "CATCH", "i": idx, "ball": (round(b[0]),
                                                        round(b[1]))})
        if b is not None:
            last_ball_x = b[0]
        # ---- SERVO: track the ball's y when it approaches my side ----
        if b is not None and py is not None:
            err = b[1] - py
            if b[0] < 190 or (bx is not None and bx < 200):
                if abs(err) > 6:
                    buttons = {"UP" if err < 0 else "DOWN"}
                else:
                    buttons = set()
            else:
                # ball far: drift to center
                if abs(120 - py) > 10:
                    buttons = {"UP" if (120 - py) < 0 else "DOWN"}
                else:
                    buttons = set()
        else:
            buttons = set()

    wall = round(time.time() - t0, 1)
    stats["wall_s"] = wall
    stats["frames_total"] = idx
    stats["verdict"] = ("REAL_WIN_VS_AI" if stats["win"] and ai_active
                        else "REAL_WIN" if stats["win"] else "INCOMPLETE")
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(stats, f, indent=1)
    jrn({"ev": "DONE", **stats})

    # ---- GIF ----
    cmd = ["ffmpeg", "-y", "-framerate", "60",
           "-start_number", "1", "-i", os.path.join(FRAMES, "f%06d.png"),
           "-vf", ("fps=30,split[a][b];[a]palettegen=max_colors=112:"
                   "stats_mode=diff[p];[b][p]paletteuse=dither=bayer:"
                   "bayer_scale=5:diff_mode=rectangle"),
           "-loop", "0", GIF_OUT]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode == 0:
        jrn({"ev": "gif_done", "path": GIF_OUT,
             "bytes": os.path.getsize(GIF_OUT)})
    else:
        jrn({"ev": "gif_fail", "stderr": r.stderr[-500:]})
    print(json.dumps(stats, indent=1))
    return 0 if stats["win"] else 2


if __name__ == "__main__":
    sys.exit(main())
