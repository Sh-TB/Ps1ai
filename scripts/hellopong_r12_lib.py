#!/usr/bin/env python3
"""hellopong_r12_lib.py — Round 12 (Task 16-c) shared idioms.

COPIED from scripts/hellopong_r11_full_loop.py / hellopong_r11_fetch_boot.py
(sensor + boot + screen-classifier + input-release idioms, kept identical
wherever possible). One beetle boot PER PROCESS: the WIN run and the idle
control run each live in their own script/process and boot exactly once.

Upstream ground truth (marconvcm/ps1_dev @ dec2f3f0, MIT, src/main.c):
  * start/restart trigger = is_button_just_released(CROSS=0x4000) pad1/pad2
  * GAME_MENU -(X rel)-> GAME_PLAYING (scores 0-0); GAME_OVER -(X rel)-> MENU
  * win at 5 points either side; check_scoring: x<0 -> right scores,
    x>320 -> left scores; serve ALWAYS rightward (x=152, vel_x=+2)
  * P1 left paddle = pad1 UP/DOWN (4 px/f); AI only when a pad is
    disconnected (beetle exposes 2 -> right paddle STATIC)
  * libretro X=TRIANGLE is the in-play pause (negative); ball 16x16
Score sensor (OBSERVE-ONLY): Paddle{int y; int score;} — an UP-tap
(2 frames) decrements y by exactly 8; score lives at y+4.
"""
from __future__ import annotations

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

EMU = "/home/z/my-project/emu/games_homebrew"
LIC_CUE = os.path.join(EMU, "patched", "hello_pong_lic.cue")
LIC_BIN = os.path.join(EMU, "patched", "hello_pong_lic.bin")
CANON_BIN = os.path.join(EMU, "hello_pong.bin")
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")

PADBUFF_SIG = b"\x00\x41\xff\xff"

STEP = 2                     # frames per control step
PADDLE_SPEED = 4             # px/frame (source)
BALL_BAND = (32, 222, 24, 296)      # rows r0:r1, cols c0:c1 for the ball
PADDLE_L_COLS = (6, 24)
PADDLE_R_COLS = (296, 314)
MENU_MEAN_THR = 21.2         # game-over screen 20.24 vs menu 22.0 (observed)
LOST_TELEPORT_PX = 100       # ball x jump > this = reset teleport (point)
WIN_SCORE = 5                # first to 5 (source)


def make_jrn(out_dir, tag):
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, "events.jsonl")
    if os.path.exists(jpath):
        os.rename(jpath, jpath + "." + time.strftime("%Y%m%d_%H%M%S"))
    cur = {"f": 0}

    def jrn(ev):
        ev = {"t": round(time.time(), 3), "f": cur.get("f", 0), **ev}
        with open(jpath, "a") as f:
            f.write(json.dumps(ev, default=str) + "\n")
        print(tag, json.dumps(ev, default=str)[:200], flush=True)

    jrn.path = jpath
    jrn.cur = cur
    return jrn


def madiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def save_png(out_dir, arr, name):
    from PIL import Image
    path = os.path.join(out_dir, name)
    Image.fromarray(arr).save(path)
    return name


def padbuff_addrs(snap):
    hits, i = [], 0
    while True:
        i = snap.find(PADBUFF_SIG, i)
        if i < 0:
            break
        hits.append(i)
        i += 1
    return hits


def i32(arr):
    return np.frombuffer(bytes(arr), dtype="<i4")


def u32(arr):
    return np.frombuffer(bytes(arr), dtype="<u4")


def pad_mirrors(p, addrs):
    return {hex(a): p.mem.u16(a + 2) for a in addrs}


def paddle_row(fr, cols):
    g = fr.mean(axis=2)
    band = g[:, cols[0]:cols[1]]
    ys = np.nonzero((band > 200).any(axis=1))[0]
    if len(ys) < 20:
        return None
    return float(np.median(ys))


def ball_centroid(fr):
    g = fr.mean(axis=2)
    r0, r1, c0, c1 = BALL_BAND
    reg = g[r0:r1, c0:c1]
    mx = float(reg.max())
    if mx < 150:
        return None
    thr = max(150.0, mx - 60.0)
    mask = reg >= thr
    n = int(mask.sum())
    if n < 15 or n > 320:                 # ball bright core ~90 px observed
        return None
    ys, xs = np.nonzero(mask)
    return (float(xs.mean()) + c0, float(ys.mean()) + r0, n)


def classify(fr, anim_madiff=None):
    """Facts-based screen class (numbers from upstream draw sets)."""
    if fr is None:
        return "NO_FRAME", {"frame_mean": None}
    g = fr.mean(axis=2)
    mean = float(g.mean())
    pl = paddle_row(fr, PADDLE_L_COLS)
    pr = paddle_row(fr, PADDLE_R_COLS)
    facts = {"frame_mean": round(mean, 2),
             "paddle_l_row": pl, "paddle_r_row": pr,
             "anim_madiff": None if anim_madiff is None
             else round(anim_madiff, 4)}
    if pl is not None and pr is not None:
        if anim_madiff is not None and anim_madiff > 0.05:
            return "PLAYING", facts
        return "PAUSED_LIKE", facts
    return ("MENU" if mean > MENU_MEAN_THR else "GAME_OVER"), facts


def hold_and_release(p, btn, addrs, hold=8):
    """Hold btn, read the pad-buffer mirror WHILE HELD, then RELEASE
    explicitly (the game triggers on just_released for CROSS)."""
    p.core.run(hold, {btn})
    mir = pad_mirrors(p, addrs)
    p.core.run(4, set())                  # explicit RELEASE (just_released)
    return mir


def score_crop(fr):
    """Score-band crop bytes (score digits at y=20, x=120/192 upstream)."""
    g = fr.mean(axis=2)
    return np.ascontiguousarray(g[14:34, 96:224]).tobytes()


def text_crop(fr):
    """Game-over text band crop (text lines live in rows ~60..150)."""
    g = fr.mean(axis=2)
    return np.ascontiguousarray(g[40:170, 0:320]).astype(np.uint8)


def boot_hellopong(ws, jrn):
    """ONE beetle boot in THIS process. Verifies the local license-patched
    image exists, resolves OpenBIOS firmware, boots, checks fw trust."""
    if not os.path.exists(LIC_CUE):
        raise SystemExit("license-patched image missing; run "
                         "scripts/hellopong_r12_fetch.py first")
    os.makedirs(os.path.join(ws, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(ws, "system",
                                               "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=ws)
    p = PS1Play(LIC_CUE, workspace=ws, var_overrides=fw["override_vars"])
    boot_info = p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    jrn({"ev": "boot", "core": boot_info, "fw_trust": ok,
         "fw_detail": detail, "fw_mode": fw["mode"]})
    if not ok:
        raise SystemExit(f"firmware trust failed: {detail}")
    return p, {"core": boot_info, "fw": {"mode": fw["mode"],
                                         "detail": fw["detail"],
                                         "trust_ok": ok}}


def settle_boot(p, jrn):
    """Wait for the game's own screen; catch the auto-started game early
    when it happens (upstream: garbage CROSS release edge at pad-driver
    init auto-starts GAME_PLAYING with fresh scores)."""
    p.wait(240)
    timeline = []
    addrs = []
    prev = None
    for k in range(60):
        fr = p.core.frame_rgb()
        snap = bytes(p.mem.snapshot())
        addrs = padbuff_addrs(snap) or addrs
        m = madiff(prev, fr)
        prev = fr
        cls, facts = classify(fr, m)
        ent = {"f": p.core.frames_run, "class": cls, **facts,
               "pad_id41": len(addrs)}
        timeline.append(ent)
        jrn({"ev": "boot_poll", **ent})
        if len(addrs) >= 1 and cls in ("PLAYING", "MENU", "GAME_OVER"):
            # confirm non-transient: one more poll must agree for text
            if cls in ("MENU", "GAME_OVER"):
                p.wait(30, set())
                cls2, _ = classify(p.core.frame_rgb(), 0.0)
                if cls2 == cls:
                    return cls, timeline, addrs
            else:
                return cls, timeline, addrs
        p.wait(30)
    return "TIMEOUT", timeline, addrs


class ScoreSensor:
    """OBSERVE-ONLY score counters via the source-anchored Paddle
    layout {int y; int score;} + point-event diffs. No RAM writes."""

    def __init__(self, p):
        self.p = p
        self.y_addr = None
        self.l_addr = None
        self.r_addr = None
        self.confirmed_pts = 0

    def discover_left(self, row_fn=None):
        s0 = bytes(self.p.mem.snapshot())
        self.p.core.run(2, {"UP"})
        self.p.core.run(6, set())
        s1 = bytes(self.p.mem.snapshot())
        row_up = row_fn() if row_fn else None
        d = i32(s1).astype(np.int64) - i32(s0).astype(np.int64)
        c1 = np.flatnonzero(d == -PADDLE_SPEED * 2)
        self.p.core.run(2, {"DOWN"})
        self.p.core.run(6, set())
        s2 = bytes(self.p.mem.snapshot())
        row_back = row_fn() if row_fn else None
        d2 = i32(s2).astype(np.int64) - i32(s1).astype(np.int64)
        c2 = np.flatnonzero(d2 == PADDLE_SPEED * 2)
        restored = set(c1.tolist()) & set(c2.tolist())
        cands = []
        for idx in restored:
            v0, v2 = int(i32(s0)[idx]), int(i32(s2)[idx])
            if not (0 < v0 < 240 and 0 < v2 < 240):
                continue
            sc = int(u32(s2)[idx + 1]) if idx + 1 < len(s2) // 4 else -1
            if sc == 0:                       # left_paddle.score == 0 now
                cands.append(idx * 4)
        out = {"up_restore_candidates": [hex(c) for c in cands],
               "visual_row_during_up": row_up,
               "visual_row_after_restore": row_back}
        if cands:
            self.y_addr = cands[0]
            self.l_addr = self.y_addr + 4
            out["y_addr"] = hex(self.y_addr)
            out["l_addr"] = hex(self.l_addr)
            out["ok"] = True
        else:
            out["ok"] = False
        return out

    def snapshot_scores(self):
        """(scores list, full snapshot bytes) — one RAM read."""
        if self.l_addr is None:
            return None, None
        s = bytes(self.p.mem.snapshot())
        w = u32(s)
        li = self.l_addr // 4
        l = int(w[li])
        r = (int(w[self.r_addr // 4])
             if self.r_addr is not None else None)
        return [l, r], s

    def scores(self):
        sc, _ = self.snapshot_scores()
        return sc

    def identify_right(self, s_before, s_after):
        """At a point event: the +1 i32 delta(s) are the score counters.
        left is known; the other one is right."""
        if self.l_addr is None or self.r_addr is not None:
            return None
        d = i32(s_after).astype(np.int64) - i32(s_before).astype(np.int64)
        cand = np.flatnonzero(d == 1)
        li = self.l_addr // 4
        others = []
        for idx in cand:
            v = int(u32(s_after)[idx])
            if idx == li:
                continue
            if 0 <= v <= 6:
                others.append(int(idx) * 4)
        if len(others) == 1:
            self.r_addr = others[0]
            return self.r_addr
        return {"ambiguous": [hex(x) for x in others]} if others else None

    def verify_point(self, s_before, s_after):
        d = i32(s_after).astype(np.int64) - i32(s_before).astype(np.int64)
        li = (self.l_addr or 0) // 4
        ri = (self.r_addr or 0) // 4
        dl = int(d[li]) if self.l_addr else None
        dr = int(d[ri]) if self.r_addr else None
        if dl == 1 or dr == 1:
            self.confirmed_pts += 1
        return dl, dr

    def sensor_block(self):
        return {"ok": self.l_addr is not None,
                "y_addr": hex(self.y_addr) if self.y_addr else None,
                "l_addr": hex(self.l_addr) if self.l_addr else None,
                "r_addr": hex(self.r_addr) if self.r_addr else None,
                "confirmed_points": self.confirmed_pts}


def find_plus1_candidates(s_prev, s_now, value_after=None):
    """Addresses whose i32 value incremented by exactly +1 between two
    snapshots (optionally filtered to a post-value). Observe-only."""
    d = i32(s_now).astype(np.int64) - i32(s_prev).astype(np.int64)
    cand = np.flatnonzero(d == 1)
    out = []
    for idx in cand:
        v = int(u32(s_now)[idx])
        if value_after is not None and v != value_after:
            continue
        out.append(int(idx) * 4)
    return out


def discover_score_by_points(p, jrn, out_dir, sensor, need_points=3,
                             max_frames=4000):
    """Observe-only score-sensor discovery via NATURAL point events.

    WHY (round-12, source-anchored): reset_ball() always serves
    (x=152 even -> vel_x=+2; y=112 -> vel_y=-1) and the STATIC right
    paddle (y=90, h=60; pad2 connected -> no AI) can never intercept
    (ball bottom = 45+16 = 61 < 90 at the paddle plane), so LEFT scores
    every ~85 frames with ZERO input (the round-11 fetch_boot note
    "5x left points -> GAME_OVER" is the same walkover). Each natural
    point increments left_paddle.score — a main() STACK local whose
    address IS taken every frame (&left_paddle -> materialized slot) —
    by exactly +1.

    IDENTIFICATION RULE (per RAM poll, 4 frames apart):
      * a poll window is a POINT WINDOW iff the ball reset teleport
        (|dx| > 100) was seen in it;
      * in a point window, i32 counters that +1'd (post-value 1..5)
        are candidates (first window: adopt; later: intersect — the
        true counter +1s at EVERY point);
      * outside point windows, any candidate that +1s is pruned
        (fires without a point = not a score counter);
      * ASCII digit artifacts ('0'->'1' = 0x30->0x31 = 49) are rejected
        by the post-value 1..5 filter.
    Resolution: a unique candidate after >= need_points confirmed
    points. y = score_addr - 4 (Paddle {int y; int score;}).

    This replaces the r11 UP-tap-first discovery as the PRIMARY method:
    the tap idiom's `score == 0` filter provably rejects the true y
    whenever a natural point falls during calibration (observed this
    round; the walkover makes that near-certain). The UP-tap survives
    as the y-field VERIFICATION (verify_y_tap).

    No RAM writes, NO button input. Returns a facts dict."""
    g = {"points": 0, "anchors": [], "ball_steps": 0, "steps": 0,
         "left_after": None, "teleports": 0, "prunes": []}
    s_prev = bytes(p.mem.snapshot())
    cands = None                    # None until the first point window
    cand_vals = {}                  # addr -> last observed value
    last_cx = None
    prev_frame = p.core.frame_rgb()
    frames_start = p.core.frames_run
    teleport_window = False
    poll_i = 0
    while p.core.frames_run - frames_start < max_frames:
        fr = p.core.frame_rgb()
        a = madiff(prev_frame, fr)
        prev_frame = fr
        cls, facts = classify(fr, a)
        ball = ball_centroid(fr)
        g["steps"] += 1
        if ball is not None:
            g["ball_steps"] += 1
            if last_cx is not None and \
                    abs(ball[0] - last_cx) > LOST_TELEPORT_PX:
                teleport_window = True
                g["teleports"] += 1
            last_cx = ball[0]
        # ---- static game-over safety (discovery started too late and
        # the walkover already finished) ----
        if cls == "GAME_OVER" and a is not None and a < 0.02:
            g["end_class"] = "GAME_OVER"
            jrn({"ev": "discover_static_gameover", **facts,
                 "points": g["points"]})
            return g
        if cls == "MENU":
            g["end_class"] = "MENU"
            jrn({"ev": "discover_menu_state", **facts})
            return g
        # ---- RAM poll every 2 steps (4 frames) ----
        poll_i += 1
        if poll_i % 2 == 0:
            s_now = bytes(p.mem.snapshot())
            d = i32(s_now).astype(np.int64) - \
                i32(s_prev).astype(np.int64)
            plus1 = np.flatnonzero(d == 1)
            fired = {}
            for idx in plus1:
                v = int(u32(s_now)[idx])
                if 1 <= v <= 5:
                    fired[int(idx) * 4] = v
            if teleport_window:
                if cands is None:
                    if fired:
                        cands = set(fired)
                        cand_vals.update(fired)
                        jrn({"ev": "discover_first_point_window",
                             "candidates": sorted(hex(c) for c in cands),
                             "values": {hex(k): v for k, v in
                                        fired.items()}})
                        g["points"] += 1
                        png = save_png(out_dir, fr,
                                       f"disc_point{g['points']:02d}.png")
                        g["anchors"].append(
                            {"point": g["points"],
                             "frame": p.core.frames_run,
                             "values": {hex(k): v for k, v in
                                        fired.items()},
                             "png": png})
                        jrn({"ev": "discover_point",
                             "point": g["points"],
                             "frame": p.core.frames_run,
                             "candidates": sorted(hex(c) for c in cands),
                             "png": png})
                else:
                    kept = {a2: v for a2, v in fired.items()
                            if a2 in cands}
                    missed = [a2 for a2 in cands if a2 not in kept]
                    if missed:
                        g["prunes"].append(
                            {"why": "missed_point",
                             "addrs": [hex(x) for x in missed]})
                        jrn({"ev": "discover_pruned",
                             "why": "missed_point",
                             "addrs": [hex(x) for x in missed]})
                    if kept:
                        g["points"] += 1
                        cands = set(kept)
                        cand_vals.update(kept)
                        png = save_png(out_dir, fr,
                                       f"disc_point{g['points']:02d}.png")
                        g["anchors"].append(
                            {"point": g["points"],
                             "frame": p.core.frames_run,
                             "values": {hex(k): v for k, v in
                                        kept.items()},
                             "png": png})
                        jrn({"ev": "discover_point",
                             "point": g["points"],
                             "frame": p.core.frames_run,
                             "candidates": sorted(hex(c) for c in cands),
                             "values": {hex(k): v for k, v in
                                        kept.items()},
                             "png": png})
            else:
                # +1 outside a point window -> not a score counter
                if cands is not None and fired:
                    drop = [a2 for a2 in fired if a2 in cands]
                    if drop:
                        g["prunes"].append(
                            {"why": "fired_without_point",
                             "addrs": [hex(x) for x in drop]})
                        jrn({"ev": "discover_pruned",
                             "why": "fired_without_point",
                             "addrs": [hex(x) for x in drop]})
                        cands -= set(drop)
            teleport_window = False
            s_prev = s_now
            # ---- resolution check ----
            if cands is not None and len(cands) == 1 and \
                    g["points"] >= need_points:
                addr = next(iter(cands))
                sensor.l_addr = addr
                sensor.y_addr = addr - 4
                yv = int(u32(s_now)[(addr - 4) // 4])
                sensor.confirmed_pts = g["points"]
                g["ok"] = True
                g["left_after"] = cand_vals.get(addr)
                g["l_addr"] = hex(addr)
                g["y_addr"] = hex(sensor.y_addr)
                g["y_value"] = yv
                g["y_in_range"] = 0 < yv < 240
                jrn({"ev": "sensor_resolved", "l_addr": hex(addr),
                     "y_addr": hex(sensor.y_addr), "y_value": yv,
                     "y_in_range": g["y_in_range"],
                     "points_confirmed": g["points"]})
                return g
            if cands is not None and len(cands) > 1 and \
                    g["points"] >= need_points + 3:
                adj = [c for c in cands
                       if 0 < int(u32(s_now)[(c - 4) // 4]) < 240]
                if len(adj) == 1:
                    addr = adj[0]
                    sensor.l_addr = addr
                    sensor.y_addr = addr - 4
                    g["ok"] = True
                    g["left_after"] = cand_vals.get(addr)
                    g["l_addr"] = hex(addr)
                    g["y_addr"] = hex(sensor.y_addr)
                    jrn({"ev": "sensor_resolved_adjacency",
                         "l_addr": hex(addr)})
                    return g
                jrn({"ev": "discover_ambiguous",
                     "candidates": sorted(hex(c) for c in cands)})
                g["ok"] = False
                return g
        # ---- advance (NO input during discovery) ----
        p.core.run(STEP, set())
    g["ok"] = False
    g["end_class"] = "TIMEOUT"
    jrn({"ev": "discover_timeout", "points": g["points"]})
    return g


def verify_y_tap(p, sensor, jrn, out_dir):
    """r11 UP-tap idiom, now used as a VERIFICATION of the point-anchored
    y field: UP 2f -> y decrements exactly 8 (and the drawn paddle row
    moves -8), DOWN 2f restores. Score must be unchanged."""
    if sensor.l_addr is None or sensor.y_addr is None:
        return {"ok": False, "reason": "sensor unresolved"}
    row_fn = lambda: paddle_row(p.core.frame_rgb(), PADDLE_L_COLS)
    s0 = bytes(p.mem.snapshot())
    row0 = row_fn()
    p.core.run(2, {"UP"})
    p.core.run(6, set())
    s1 = bytes(p.mem.snapshot())
    row_up = row_fn()
    p.core.run(2, {"DOWN"})
    p.core.run(6, set())
    s2 = bytes(p.mem.snapshot())
    row_back = row_fn()
    yi = sensor.y_addr // 4
    li = sensor.l_addr // 4
    dy0 = int(i32(s1)[yi]) - int(i32(s0)[yi])
    dy1 = int(i32(s2)[yi]) - int(i32(s1)[yi])
    dsc = int(i32(s2)[li]) - int(i32(s0)[li])
    out = {"ram_dy_up": dy0, "ram_dy_restore": dy1,
           "score_delta": dsc,
           "visual_row0": row0, "visual_row_up": row_up,
           "visual_row_back": row_back,
           "visual_dy_up": (None if row0 is None or row_up is None
                            else round(row_up - row0, 1)),
           "visual_dy_restore": (None if row0 is None or row_back is None
                                 else round(row_back - row0, 1)),
           "y_up_ok": dy0 == -PADDLE_SPEED * 2,
           "y_restore_ok": dy1 == PADDLE_SPEED * 2,
           "score_unchanged": dsc == 0}
    out["ok"] = bool(out["y_up_ok"] and out["y_restore_ok"] and
                     out["score_unchanged"] and
                     out["visual_dy_up"] is not None and
                     out["visual_dy_up"] < -2)
    save_png(out_dir, p.core.frame_rgb(), "y_tap_verify_after.png")
    jrn({"ev": "y_tap_verify", **out})
    return out


def restart_causality(p, jrn, out_dir, tag, addrs):
    """On the game-over screen: idle control leg vs CROSS-release leg.
    Proves the X release (not idle time) advances GAME_OVER -> MENU."""
    fr0 = p.core.frame_rgb()
    save_png(out_dir, fr0, f"{tag}_over_before.png")
    cls0, facts0 = classify(fr0, 0.0)
    # control leg: 90f idle
    ctrl = []
    for _ in range(6):
        a = p.core.frame_rgb()
        p.wait(15, set())
        ctrl.append(round(madiff(a, p.core.frame_rgb()) or 0.0, 4))
    still = p.core.frame_rgb()
    cls_ctrl, _ = classify(still, 0.0)
    save_png(out_dir, still, f"{tag}_over_control.png")
    # X leg: hold+release CROSS
    mir = hold_and_release(p, "B", addrs)
    seq = []
    pre = still
    for _ in range(12):
        prev = p.core.frame_rgb()
        p.wait(2, set())
        fr = p.core.frame_rgb()
        seq.append(round(madiff(prev, fr) or 0.0, 4))
    p.wait(120, set())
    after = p.core.frame_rgb()
    cls_after, facts_after = classify(after, 0.0)
    save_png(out_dir, after, f"{tag}_after_x.png")
    out = {"tag": tag, "before_class": cls0, "before": facts0,
           "control_madiffs": ctrl, "control_max": max(ctrl),
           "control_class": cls_ctrl,
           "x_mirror_held": mir, "x_seq": seq, "x_max": max(seq),
           "after_class": cls_after, "after": facts_after,
           "discrimination": round(max(seq) - max(ctrl), 4)}
    jrn({"ev": "restart_causality", **out})
    return out
