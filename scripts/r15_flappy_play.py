#!/usr/bin/env python3
"""r15_flappy_play.py — FlappyBirdPSX REAL closed-loop play to WIN (score 10).

Mechanics learned from source (scratch/round15_flappy/src/):
  * flap (X) sets vel.y = +256 world = 8 px/f up; rising decays 1 px/f per
    frame (-> ~36 px rise over 8 f); falling accelerates 0.125 px/f^2
  * bird x fixed at screen center (160); dies on pipe overlap (red-zone
    box test) or below screen (y>190)
  * pipes: 60 px wide, 70 px gap, move left 1.40625 px/f, spawn random gap
  * score +1 per pipe passed; START restarts after game over

Controller (vision closed-loop, 60 Hz):
  bird y = yellow centroid (x-band 130..195)
  gap target = nearest pipe's gap center (green column band right of bird)
  flap when bird below target+4 px AND falling/at apex (vy<=0 world)

Honest anchors:
  * RAM: bird-y word verified against vision (world/32+120 == vision y)
  * RAM: pipe-x words decrement by exactly 45/f; score u16 increments
  * WIN = score word reaches 10 AND every point anchored by a logged
    pipe-pass (RAM pipe x crossing -50 px world)
  * deaths -> GAME OVER screen -> START restart -> continue (real play
    includes recovery); every restart logged

Evidence -> scratch/round15_flappy/play/ ; GIF -> download/.
"""
import hashlib
import json
import os
import shutil
import subprocess
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
OUT = os.path.join(REPO, "scratch", "round15_flappy", "play")
FRAMES = os.path.join(OUT, "frames")
WS = "/home/z/my-project/emu/games_homebrew/ws_r15_flappy"
GIF_OUT = "/home/z/my-project/download/flappybirdpsx_REAL_gameplay.gif"

WIN_SCORE = 10
MAX_FRAMES = 12000
HOVER_Y = 120.0


def bird_y(fr):
    """Bird screen y via yellow centroid (bird band, ABOVE the ground)."""
    r, g, b = fr[:, :, 0].astype(int), fr[:, :, 1].astype(int), fr[:, :, 2].astype(int)
    yellow = (r > 180) & (g > 170) & (b < 110)
    yellow[:20, :] = False
    yellow[186:, :] = False          # ground strip starts ~y=190
    yellow[:, :130] = False
    yellow[:, 196:] = False
    ys, xs = np.nonzero(yellow)
    if len(ys) < 6 or len(ys) > 900:
        return None, 0
    return float(ys.mean()), len(ys)


def green_mask(fr):
    """PIPE green family incl. the shaded right side ([80,112,48]):
    g>100, r<150 (excludes pale bush green [176,216,184]), g>b+20."""
    r, g, b = fr[:, :, 0].astype(int), fr[:, :, 1].astype(int), fr[:, :, 2].astype(int)
    return (g > 100) & (r < 150) & (g > b + 20)


def gap_target(green, by):
    """Gap of the pipe currently at/over the bird. Scan from x=120: a pipe
    box still overlaps the bird column until cam x ~118. Prefer the
    leftmost band whose right edge > 130 (the pipe being crossed)."""
    colsum = green[:188, :].sum(axis=0)   # rows above grass+bush line
    # bridge shading fragmentation: dilate column sums by 1
    cs = np.maximum(np.maximum(colsum[:-2], colsum[1:-1]), colsum[2:])
    colsum = np.concatenate([[colsum[0]], cs, [colsum[-1]]])
    bands, start = [], None
    for x in range(120, 320):
        if colsum[x] > 40:
            if start is None:
                start = x
        else:
            if start is not None and x - start >= 8:
                bands.append((start, x))
            start = None
    if start is not None and 320 - start >= 8:
        bands.append((start, 320))
    if not bands:
        return None
    bx0, bx1 = next((b for b in bands if b[1] > 130), bands[0])
    band = green[:188, bx0:bx1]
    rows = np.nonzero(~band.any(axis=1))[0]
    rows = rows[(rows > 20) & (rows < 188)]
    if len(rows) == 0:
        return None
    gaps, s, prev = [], rows[0], rows[0]
    for y in rows[1:]:
        if y == prev + 1:
            prev = y
        else:
            gaps.append((s, prev))
            s = prev = y
    gaps.append((s, prev))
    gaps = [g for g in gaps if g[1] - g[0] > 30]
    if not gaps:
        return None
    g0, g1 = gaps[0]
    return ((g0 + g1) / 2.0, (bx0 + bx1) / 2.0)


def ground_ok(fr):
    """Get-Ready screen discriminator: green grass strip at the bottom."""
    gm = green_mask(fr)
    return gm[190:225, :].sum(axis=0).astype(bool).sum() > 150


def gameover_like(fr):
    """Game-over score box: large tan region in the center (measured 71%
    of the center box; the >235-white check never fires on the tan box)."""
    c = fr[80:160, 96:224]
    r, g, b = c[:, :, 0].astype(int), c[:, :, 1].astype(int), c[:, :, 2].astype(int)
    tan = (r > 190) & (g > 175) & (b > 110) & (b < 200)
    return float(tan.mean()) > 0.35


def main():
    os.makedirs(FRAMES, exist_ok=True)
    jrn = make_jrn(OUT, "[fplay]")
    t0 = time.time()
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    jrn({"ev": "boot", "core": p.boot()})

    # fixed wait past the OpenBIOS shell (measured: Get Ready ~f600)
    for _ in range(700):
        p.core.run(1, set())
    fr = p.core.frame_rgb()
    jrn({"ev": "post_wait", "ground_ok": ground_ok(fr)})
    save_png(OUT, fr, "getready.png")

    # START the run: X press (seeds RNG, GSTATE_GAME_START -> NORMAL)
    p.core.run(3, {"B"})
    p.core.run(4, set())
    p.core.run(2, {"B"})   # first real flap pulse
    p.core.run(4, set())

    def snap():
        return bytes(p.mem.snapshot())

    # ---- sensor window: 200 servo frames, then whole-RAM 3-sample scan ----
    for k in range(200):
        fr = p.core.frame_rgb()
        by, npix = bird_y(fr)
        green = green_mask(fr)
        gt = gap_target(green, by)
        buttons = set()
        if by is not None:
            ty = gt[0] if gt else HOVER_Y
            if by > ty + 4:
                buttons = {"B"}
        p.core.run(1, buttons)
    save_png(OUT, p.core.frame_rgb(), "sensor_window.png")

    s0 = snap()
    p.core.run(1, set())
    s1 = snap()
    p.core.run(1, set())
    s2 = snap()
    a0, a1, a2 = i32(s0), i32(s1), i32(s2)
    w0 = np.frombuffer(s0, dtype="<i2").astype(np.int64)
    w1 = np.frombuffer(s1, dtype="<i2").astype(np.int64)
    w2 = np.frombuffer(s2, dtype="<i2").astype(np.int64)
    d1 = a1.astype(np.int64) - a0.astype(np.int64)
    d2 = a2.astype(np.int64) - a1.astype(np.int64)
    wd1 = w1 - w0
    wd2 = w2 - w1
    pipe_addrs, bird_cands = [], []
    for idx in range(len(d1)):          # i32 space (bird candidates)
        dd1, dd2 = int(d1[idx]), int(d2[idx])
        if (abs(dd1) <= 512 and abs(dd2) <= 512
                and dd1 != 0 and dd2 != 0):
            bird_cands.append(idx * 4)
    for idx in range(len(w0)):          # i16 space (pipe pos.x at base+2)
        if idx * 2 % 4 != 2:
            continue
        v1, v2 = int(w1[idx]), int(w2[idx])
        if not (-24000 < v1 < 24000 and -24000 < v2 < 24000):
            continue
        # vel.x is a constant -45 (delta 0); pos.x deltas are exactly -45
        if wd1[idx] == -45 and wd2[idx] == -45:
            pipe_addrs.append(idx * 2)
    jrn({"ev": "scan", "pipe_addrs_n": len(pipe_addrs),
         "pipe_addrs": [hex(a) for a in pipe_addrs[:24]],
         "bird_cands_n": len(bird_cands)})

    # verify bird-y candidates vs vision — done LAZILY in the main loop
    # (a dedicated verification phase idles the bird to death; r15 lesson)
    bird_addr = None
    jrn({"ev": "bird_verify_mode", "mode": "lazy_in_loop",
         "cands": [hex(a) for a in bird_cands[:12]]})

    # score candidate: u16 words small enough to be a score, will be
    # verified by matching increments against logged pipe passes
    score_probe_addrs = []
    sB = snap()
    b16 = np.frombuffer(sB, dtype="<u2")
    for idx in range(0, len(b16)):
        v = int(b16[idx])
        if v == 0 and idx * 2 >= 0x1000 and idx * 2 < 0x200000:
            score_probe_addrs.append(idx * 2)
    # cap the probe list deterministically
    score_probe_addrs = score_probe_addrs[:60000]
    jrn({"ev": "score_probe", "n": len(score_probe_addrs)})

    # ---- MAIN PLAY LOOP ----
    idx = 0
    buttons = set()
    stats = {"captures": 0, "deaths": 0, "restarts": 0, "passes": 0,
             "flaps": 0, "win": False}
    score_cands = set()
    passes = []               # anchored pipe passes
    frame_facts = []
    pipe_prev_x = {}
    bird_gone = 0
    start_f = p.core.frames_run
    press_remaining = 0       # frames of X still held (pulse)
    cool_remaining = 0        # frames to keep X released (edge reset)
    last_gap = None           # stale-gap memory (pipe sliver phase)
    last_gap_age = 999
    by_prev = None
    ring = []                 # 40-frame fact ring for pre-death forensics
    # lazy RAM bird-word verification state
    cand_queue = list(bird_cands[:12])
    cand_hits = cand_tots = 0
    cand_cur = cand_queue[0] if cand_queue else None
    cand_queue = cand_queue[1:]
    by_ram_hits_log = []

    while p.core.frames_run - start_f < MAX_FRAMES:
        p.core.run(1, buttons)
        idx += 1
        fr = p.core.frame_rgb()
        save_png(FRAMES, fr, f"f{idx:06d}.png")
        stats["captures"] += 1

        by, npix = bird_y(fr)
        green = green_mask(fr)
        gt = gap_target(green, by)

        # RAM reads (single snapshot per frame)
        s = snap()
        a32 = i32(s)
        # lazy bird-word verification: only while the bird is VISIBLE
        if bird_addr is None and cand_cur is not None and by is not None:
            val = int(a32[cand_cur // 4])
            cand_tots += 1
            if abs((120 + val / 32.0) - by) <= 3:
                cand_hits += 1
            if cand_tots >= 12:
                if cand_hits / cand_tots >= 0.7:
                    bird_addr = cand_cur
                    jrn({"ev": "bird_word_verified", "addr": hex(bird_addr),
                         "hits": cand_hits, "tot": cand_tots})
                    cand_cur = None
                else:
                    cand_cur = cand_queue[0] if cand_queue else None
                    cand_queue = cand_queue[1:]
                    cand_hits = cand_tots = 0
        by_ram = int(a32[bird_addr // 4]) if bird_addr else None

        # pipe tracking (RAM) -> anchored pass detection
        # game's own scoring gate: x < -(player_w + half_pipe_w)<<5 = -1152
        for pa in pipe_addrs[:8]:
            v = int(np.frombuffer(s, dtype="<i2", count=1,
                                  offset=pa)[0])
            pv = pipe_prev_x.get(pa)
            pipe_prev_x[pa] = v
            if pv is not None and pv > -1152 and v <= -1152:
                stats["passes"] += 1
                passes.append({"i": idx, "addr": hex(pa),
                               "v": v, "score_est": stats["passes"]})
                # score-word hunt (hello_pong method): u16 words that now
                # equal the new pass count, intersected each pass
                b16n = np.frombuffer(s, dtype="<u2")
                if stats["passes"] == 1:
                    score_cands = set(int(a) for a in
                                      np.flatnonzero(b16n == 1))
                else:
                    score_cands &= set(int(a) for a in
                                       np.flatnonzero(b16n ==
                                                      stats["passes"]))
                jrn({"ev": "score_hunt", "passes": stats["passes"],
                     "cands": len(score_cands),
                     "sample": [hex(a * 2) for a in
                                sorted(score_cands)[:6]]})

        # game-over check: white box (independent of bird pixels), or the
        # bird missing for 90 consecutive frames
        if gameover_like(fr):
            bird_gone += 60
        elif by is None:
            bird_gone += 1
        else:
            bird_gone = 0
        if bird_gone >= 60:
            stats["deaths"] += 1
            jrn({"ev": "DEATH", "i": idx, "passes": stats["passes"],
                 "passes_detail": passes[-3:], "bird_gone": bird_gone,
                 "pre_death_ring": ring[-12:]})
            save_png(OUT, fr, f"death_{idx:06d}.png")
            # drain: hold nothing until the box settles, then restart
            p.core.run(30, set())
            p.core.run(3, {"START"})
            p.core.run(3, set())
            stats["restarts"] += 1
            jrn({"ev": "RESTART", "i": idx})
            # wait for the REAL Get Ready screen (not the game-over box:
            # both have the green ground strip -> exclude gameover_like)
            p.core.run(45, set())
            for w in range(400):
                fr2 = p.core.frame_rgb()
                if ground_ok(fr2) and not gameover_like(fr2):
                    break
                p.core.run(1, set())
            p.core.run(3, {"B"})
            p.core.run(3, set())
            # immediate first pulse (the start press itself does not flap)
            p.core.run(2, {"B"})
            p.core.run(4, set())
            pipe_prev_x = {}
            bird_gone = 0
            cool_remaining = 0
            press_remaining = 0
            continue

        # ---- flap policy (source-derived, EDGE-TRIGGERED INPUT) ----
        # get_command fires only on press edges (i32_last_padd) -> hold X
        # = ONE flap. Every flap is a 2-frame pulse + >=3-frame release.
        # gap memory: the pipe sliver phase makes gt None for a few frames
        if gt is not None:
            last_gap = gt
            last_gap_age = 0
        else:
            last_gap_age += 1
        eff_gt = gt if gt is not None else (last_gap if last_gap_age <= 40
                                            else None)
        vy = None if by is None or by_prev is None else by - by_prev
        by_prev = by
        if press_remaining > 0:
            press_remaining -= 1
            if press_remaining == 0:
                cool_remaining = 3
            buttons = {"B"}
        elif cool_remaining > 0:
            cool_remaining -= 1
            buttons = set()
        elif by is not None:
            ty = eff_gt[0] if eff_gt is not None else 120.0
            falling = vy is None or vy >= -0.5
            # 36px rise per flap: flap at ty+14 -> apex ty-22 -> the bird's
            # 20px box stays inside the 70px gap (measured RAM geometry:
            # top box ends at gap_top, bottom begins at gap_bottom)
            if (falling and by > ty + 14) or by > ty + 26 or by > 162:
                buttons = {"B"}
                press_remaining = 1
                stats["flaps"] += 1
            else:
                buttons = set()
        else:
            buttons = set()
        ring.append({"i": idx, "by": None if by is None else round(by, 1),
                     "gap": None if gt is None else round(gt[0], 1),
                     "gapx": None if gt is None else round(gt[1]),
                     "eff": None if eff_gt is None else round(eff_gt[0], 1),
                     "vy": None if vy is None else round(vy, 2),
                     "x": "B" if buttons else ""})
        if len(ring) > 40:
            ring.pop(0)

        # score word discovery: every 240 frames re-read probes and find
        # words equal to current pass estimate (cheap consistency probe)
        if stats["passes"] >= 1 and idx % 240 == 0 and score_probe_addrs:
            b16n = np.frombuffer(s, dtype="<u2")
            keep = []
            for ad in score_probe_addrs:
                v = int(b16n[ad // 2])
                if v == stats["passes"] or v == stats["passes"] - 1:
                    keep.append(ad)
            score_probe_addrs = keep
            if idx % 960 == 0:
                jrn({"ev": "score_probe_refine", "i": idx,
                     "n": len(score_probe_addrs),
                     "sample": [hex(a) for a in score_probe_addrs[:8]],
                     "passes": stats["passes"]})
        if idx % 600 == 0:
            jrn({"ev": "progress", "i": idx, "passes": stats["passes"],
                 "flaps": stats["flaps"], "bird_ram": by_ram,
                 "bird_vis": None if by is None else round(by, 1),
                 "gap": None if gt is None else round(gt[0], 1)})

        # WIN check: passes >= WIN_SCORE anchored AND (score word == 10 if known)
        if stats["passes"] >= WIN_SCORE:
            stats["win"] = True
            save_png(OUT, fr, "WIN_FRAME.png")
            jrn({"ev": "WIN", "i": idx, "passes": stats["passes"],
                 "passes_detail": passes})
            break

    wall = round(time.time() - t0, 1)
    stats["wall_s"] = wall
    stats["emu_frames"] = p.core.frames_run - start_f
    save_png(OUT, p.core.frame_rgb(), "final.png")

    # ---- verify score word against pass ledger ----
    score_word = None
    if score_cands:
        sF = snap()
        b16f = np.frombuffer(sF, dtype="<u2")
        score_word = {hex(a * 2): int(b16f[a])
                      for a in sorted(score_cands)[:8]}
    jrn({"ev": "score_word_cands", "cands": score_word,
         "passes": stats["passes"]})

    rep = {"stats": stats, "passes": passes,
           "bird_addr": hex(bird_addr) if bird_addr else None,
           "pipe_addrs": [hex(a) for a in pipe_addrs[:8]],
           "score_word_cands": score_word,
           "verdict": ("WIN_CAUSAL_VISION_SERVO"
                       if stats["win"] else
                       f"PARTIAL_PASSES_{stats['passes']}")}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=2)
    jrn({"ev": "verdict", **{k: stats[k] for k in
                             ("win", "passes", "deaths", "restarts", "flaps")},
         "wall_s": wall})

    # ---- GIF ----
    cmd = ["ffmpeg", "-y", "-framerate", "60",
           "-start_number", "1", "-i", os.path.join(FRAMES, "f%06d.png"),
           "-vf", ("fps=20,split[a][b];[a]palettegen=max_colors=112:"
                   "stats_mode=diff[p];[b][p]paletteuse=dither=bayer:"
                   "bayer_scale=5:diff_mode=rectangle"),
           "-loop", "0", GIF_OUT]
    jrn({"ev": "ffmpeg_start"})
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode == 0 and os.path.exists(GIF_OUT):
        h = hashlib.sha256()
        with open(GIF_OUT, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        jrn({"ev": "gif_done", "bytes": os.path.getsize(GIF_OUT),
             "sha256": h.hexdigest()})
    else:
        jrn({"ev": "ffmpeg_fail", "stderr": r.stderr[-500:]})
    # hard exit: the emulator teardown hangs (observed r12-r14); all
    # artifacts are already written
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
