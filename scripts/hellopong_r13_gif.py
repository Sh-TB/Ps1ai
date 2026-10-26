#!/usr/bin/env python3
"""hellopong_r13_gif.py — Round 13: complete-gameplay GIF of the
FINISHED game (hello_pong — accepted round-4, COMPLETE_LOOP_CAUSAL
round-11, WIN_CAUSAL round-12).

ONE beetle boot in THIS process. Drive and CAPTURE EVERY EMULATED
FRAME of the complete loop:

  boot -> MENU/PLAYING -> [game N: natural play to 5-x GAME_OVER]
  -> (CROSS release) -> MENU -> (CROSS release) -> [game N+1] -> ...

Two natural games minimum + every menu transition, paddle-control
wiggle visible in game 1. Upstream triggers (marconvcm/ps1_dev @
dec2f3f0, MIT): start/restart = is_button_just_released(CROSS);
win = 5 points; serve always rightward at a STATIC right paddle ->
left walkovers every ~85 f with zero input.

Outputs:
  scratch/round13_hellopong/gif/frames/f%06d.png (every frame)
  scratch/round13_hellopong/gif/{events.jsonl,report.json}
  /home/z/my-project/download/hello_pong_complete_gameplay.gif
  (ffmpeg palettegen fps=20; uploaded to a public host afterwards)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hellopong_r12_lib import (                              # noqa: E402
    boot_hellopong, settle_boot, classify, hold_and_release, madiff,
    save_png, ball_centroid, make_jrn, LOST_TELEPORT_PX, i32, u32)

OUT = os.path.join(REPO, "scratch", "round13_hellopong", "gif")
FRAMES = os.path.join(OUT, "frames")
WS = "/home/z/my-project/emu/games_homebrew/ws_hellopong_r13_gif"
GIF_OUT = "/home/z/my-project/download/hello_pong_complete_gameplay.gif"
SCORE_L = 0x1FFEB4            # round-12 verified left-score word (secondary)
MAX_GAME_FRAMES = 2400        # natural walkover ~500 f; safety only
OVER_CONFIRM = 6              # consecutive static GAME_OVER frames


def read_score(p):
    try:
        s = bytes(p.mem.snapshot())
        return int(u32(s)[SCORE_L // 4])
    except Exception as e:                                   # pragma: no cover
        return {"err": str(e)}


def capture(p, jrn, n, btns=None, idx0=0, points=0, last_cx=None,
            btn_fn=None):
    """Advance n frames one at a time, saving EVERY frame. Returns
    (idx, per-frame records, points, last_cx)."""
    btns = btns or set()
    recs = []
    prev = p.core.frame_rgb()
    idx = idx0
    for k in range(n):
        b = btn_fn(k) if btn_fn is not None else btns
        p.core.run(1, b)
        fr = p.core.frame_rgb()
        idx += 1
        save_png(FRAMES, fr, f"f{idx:06d}.png")
        a = madiff(prev, fr)
        prev = fr
        cls, facts = classify(fr, a)
        ball = ball_centroid(fr)
        tp = False
        if ball is not None and last_cx is not None and \
                abs(ball[0] - last_cx) > LOST_TELEPORT_PX:
            tp = True
            points += 1
        if ball is not None:
            last_cx = ball[0]
        recs.append({"i": idx, "f": p.core.frames_run, "cls": cls,
                     "mean": facts["frame_mean"],
                     "madiff": None if a is None else round(a, 4),
                     "tp": tp,
                     "ball": None if ball is None
                     else (round(ball[0]), round(ball[1]))})
    return idx, recs, points, last_cx


def score_read(p):
    try:
        s = bytes(p.mem.snapshot())
        return int(u32(s)[SCORE_L // 4])
    except Exception as e:
        return None


def game_over_confirmed(recs_tail):
    """Last OVER_CONFIRM records: GAME_OVER and static."""
    t = recs_tail[-OVER_CONFIRM:]
    return (len(t) == OVER_CONFIRM and
            all(r["cls"] == "GAME_OVER" for r in t))


def play_one_game(p, jrn, idx0, wiggle=False):
    """Capture until natural GAME_OVER (or timeout). Returns dict."""
    g = {"points": 0, "score_reads": [], "score_addr": hex(SCORE_L)}
    idx = idx0
    start_f = p.core.frames_run
    recs = []
    last_cx = ball_centroid(p.core.frame_rgb())
    last_cx = last_cx[0] if last_cx else None
    pts = 0

    def wig_fn(off):
        """Per-frame paddle wiggle (visible control in the GIF):
        4 px/f holds of 20 f = ~80 px sweeps, never near the ball path."""
        if 80 <= off < 100 or 200 <= off < 220 or 320 <= off < 340:
            return {"UP"}
        if 120 <= off < 140 or 240 <= off < 260:
            return {"DOWN"}
        return set()

    batch = 60
    while p.core.frames_run - start_f < MAX_GAME_FRAMES:
        idx, r, pts, last_cx = capture(
            p, jrn, batch, set(), idx, pts, last_cx,
            btn_fn=(wig_fn if wiggle else None))
        recs.extend(r)
        for e in r:
            if e["tp"]:
                sc = score_read(p)
                g["score_reads"].append({"i": e["i"],
                                         "f": e["f"], "score_l": sc})
                jrn({"ev": "point", "i": e["i"], "f": e["f"],
                     "score_l": sc, "points": pts})
        g["points"] = pts
        if game_over_confirmed(recs):
            g["end"] = "GAME_OVER"
            break
    else:
        g["end"] = "TIMEOUT"
    last = p.core.frame_rgb()
    save_png(OUT, last, f"game_end_{g['end'].lower()}_i{idx:06d}.png")
    g["i0"], g["i1"] = idx0 + 1, idx
    g["frames"] = idx - idx0
    g["final_class"] = classify(last, 0.0)[0]
    g["final_score_read"] = score_read(p)
    jrn({"ev": "game_end", **{k: v for k, v in g.items()
                              if k != "score_reads"}})
    return g, idx


def x_release(p, jrn, idx0, expect):
    """CROSS hold+release, capture the transition, verify expectation."""
    mir = hold_and_release(p, "B", ADDRS)
    idx, r, _, _ = capture(p, jrn, 120, set(), idx0)
    last = p.core.frame_rgb()
    cls, facts = classify(last, 0.0)
    out = {"expect": expect, "after_class": cls,
           "mirror_held": mir, "i0": idx0 + 1, "i1": idx}
    save_png(OUT, last, f"after_x_i{idx:06d}.png")
    jrn({"ev": "x_release", **out})
    return out, cls, idx


ADDRS = []


def main():
    global ADDRS
    os.makedirs(FRAMES, exist_ok=True)
    os.makedirs(os.path.dirname(GIF_OUT), exist_ok=True)
    jrn = make_jrn(OUT, "[r13gif]")
    t0 = time.time()
    p, boot = boot_hellopong(WS, jrn)
    cls, timeline, addrs = settle_boot(p, jrn)
    ADDRS = addrs
    jrn({"ev": "settled", "cls": cls, "pad_id41": len(addrs)})
    rep = {"boot": boot, "settled_class": cls, "games": [],
           "transitions": [], "frames_total": 0}
    idx = 0
    # snapshot current screen as frame 1
    fr0 = p.core.frame_rgb()
    idx = 1
    save_png(FRAMES, fr0, f"f{idx:06d}.png")
    cls_now, _ = classify(fr0, 0.0)

    # ---- normalize to MENU (if boot auto-started or over) ----
    if cls_now == "GAME_OVER":
        tr, cls_now, idx = x_release(p, jrn, idx, "MENU")
        rep["transitions"].append({"from": "GAME_OVER(auto)", **tr})
    if cls_now == "MENU":
        tr, cls_now, idx = x_release(p, jrn, idx, "PLAYING")
        rep["transitions"].append({"from": "MENU", **tr})
    # (if auto-started PLAYING we simply play it as game 1)

    for n in (1, 2):
        cls_check, _ = classify(p.core.frame_rgb(), 0.0)
        if cls_check == "MENU":
            tr, _, idx = x_release(p, jrn, idx, "PLAYING")
            rep["transitions"].append({"from": f"MENU(pre-game{n})", **tr})
        jrn({"ev": "game_start", "game": n, "i": idx})
        g, idx = play_one_game(p, jrn, idx, wiggle=(n == 1))
        g["game"] = n
        rep["games"].append(g)
        # game over -> MENU
        tr, cls_now, idx = x_release(p, jrn, idx, "MENU")
        rep["transitions"].append({"from": f"GAME_OVER(g{n})", **tr})

    # final menu dwell
    idx, r, _, _ = capture(p, jrn, 90, set(), idx)
    rep["frames_total"] = idx
    rep["wall_s"] = round(time.time() - t0, 1)
    rep["verdict"] = "GIF_COMPLETE_LOOP" if all(
        g["end"] == "GAME_OVER" and g["points"] >= 4 for g in rep["games"]
    ) else "PARTIAL"
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=2)

    # ---- assemble GIF via ffmpeg palettegen ----
    cmd = ["ffmpeg", "-y", "-framerate", "60",
           "-start_number", "1", "-i", os.path.join(FRAMES, "f%06d.png"),
           "-vf", ("fps=20,split[a][b];[a]palettegen=max_colors=112:"
                   "stats_mode=diff[p];[b][p]paletteuse=dither=bayer:"
                   "bayer_scale=5:diff_mode=rectangle"),
           "-loop", "0", GIF_OUT]
    jrn({"ev": "ffmpeg", "cmd": " ".join(cmd)})
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    gif_ok = r.returncode == 0 and os.path.exists(GIF_OUT)
    if not gif_ok:
        jrn({"ev": "ffmpeg_fail", "stderr": r.stderr[-800:]})
        sys.exit(3)
    size = os.path.getsize(GIF_OUT)
    h = hashlib.sha256()
    with open(GIF_OUT, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    rep["gif"] = {"path": GIF_OUT, "bytes": size,
                  "sha256": h.hexdigest(),
                  "frames_captured": idx,
                  "fps": 20}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=2)
    jrn({"ev": "gif_done", "bytes": size, "sha256": rep["gif"]["sha256"],
         "verdict": rep["verdict"], "frames": idx,
         "wall_s": rep["wall_s"]})
    print("GIF_DONE", size, rep["verdict"], flush=True)


if __name__ == "__main__":
    main()
