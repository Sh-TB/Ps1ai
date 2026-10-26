#!/usr/bin/env python3
"""hellopong_r11_full_loop.py — Round 11 (Task 17-c) SEGMENT 2.

ONE beetle boot per process; drive the COMPLETE hello_pong loop with
honest, frame-anchored evidence:

  boot -> (auto-started or menu) -> PLAY -> natural game over (first to
  5) -> RESTART causality on the game-over screen (idle control vs CROSS
  release) -> MENU -> START negative control -> X start -> FRESH game
  (score sensor 0-0 + played) -> ... x3 games total.

Upstream ground truth (marconvcm/ps1_dev @ dec2f3f0, MIT,
src/main.c + src/libs/game_pad.{h,c}, fetched to
scratch/round11_hellopong/upstream_src/):
  * start/restart trigger = is_button_just_released(CROSS=0x4000) on
    pad1 OR pad2 (so: hold, then RELEASE).
  * GAME_MENU -(X rel)-> GAME_PLAYING (scores=0, ball reset);
    GAME_OVER -(X rel)-> GAME_MENU; win = 5 points either side.
  * paddles: P1 left = pad1 UP/DOWN (4 px/f), P2 right = pad2; AI only
    when a pad is disconnected (beetle exposes 2 connected pads -> no
    AI; the right paddle never moves under our single-port input).
  * ball: 16x16 sprite at (x,y), vel (+-2, +-1..3); serve is ALWAYS
    rightward (ball.x=152 even -> vel_x=+2) toward the uncontrolled
    right paddle; check_scoring: x<0 -> right scores, x>320 -> left.
  * score reset on MENU->PLAYING only; left_paddle.y carries across
    games (honest quirk, source lines 324-330).

Score sensor (OBSERVE-ONLY, no RAM writes): left_paddle is
`Paddle{int y; int score;}` — an UP-tap (2 frames) decrements y by
exactly 8 and a DOWN-tap restores it; score lives at y+4. right score
is identified at the first point event as the second +1 i32 delta.

Verdicts: COMPLETE_LOOP_CAUSAL / PARTIAL(stage) / FAILED — with
numbers. Evidence: scratch/round11_hellopong/full_loop/.
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
WS = os.path.join(EMU, "ws_hellopong_r11")
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")
OUT = os.path.join(REPO, "scratch", "round11_hellopong", "full_loop")
JRN_PATH = os.path.join(OUT, "events.jsonl")

PADBUFF_SIG = b"\x00\x41\xff\xff"
OVERRIDE = {b"beetle_psx_override_bios": b"openbios"}

STEP = 2                     # frames per control step
PADDLE_SPEED = 4             # px/frame (source)
BALL_BAND = (32, 222, 24, 296)      # rows r0:r1, cols c0:c1 for the ball
PADDLE_L_COLS = (6, 24)
PADDLE_R_COLS = (296, 314)
MENU_MEAN_THR = 21.2         # game-over screen 20.24 vs menu 22.0 (observed)
LOST_TELEPORT_PX = 100       # ball x jump > this = reset teleport (point)


def jrn(ev):
    ev = {"t": round(time.time(), 3), "f": CUR.get("f", 0), **ev}
    with open(JRN_PATH, "a") as f:
        f.write(json.dumps(ev, default=str) + "\n")
    print("[r11fl]", json.dumps(ev, default=str)[:200], flush=True)


CUR = {}


def madiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def save_png(arr, name):
    from PIL import Image
    Image.fromarray(arr).save(os.path.join(OUT, name))
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
    p.core.run(hold, {btn})
    mir = pad_mirrors(p, addrs)
    p.core.run(4, set())                  # explicit RELEASE (just_released)
    return mir


def settle_boot(p, rep):
    """Wait for the game's own screen; catch the auto-started game early
    when it happens (upstream: garbage CROSS release edge at pad-driver
    init auto-starts GAME_PLAYING with fresh scores)."""
    p.wait(240)
    timeline = []
    addrs = []
    for k in range(60):
        fr = p.core.frame_rgb()
        snap = bytes(p.mem.snapshot())
        addrs = padbuff_addrs(snap) or addrs
        prev = getattr(settle_boot, "_prev", None)
        m = madiff(prev, fr)
        settle_boot._prev = fr
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
                    settle_boot._prev = None
                    return cls, timeline, addrs
            else:
                settle_boot._prev = None
                return cls, timeline, addrs
        p.wait(30)
    settle_boot._prev = None
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
               "visual_row_before": row_up and row_fn and None,
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
        jrn({"ev": "sensor_discover_left", **out})
        return out

    def scores(self):
        if self.l_addr is None:
            return None
        l = int(u32(self.p.mem.snapshot())[self.l_addr // 4])
        r = (int(u32(self.p.mem.snapshot())[self.r_addr // 4])
             if self.r_addr is not None else None)
        return [l, r]

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
            jrn({"ev": "sensor_right_identified",
                 "r_addr": hex(self.r_addr)})
            return self.r_addr
        jrn({"ev": "sensor_right_ambiguous",
             "candidates": [hex(x) for x in others]})
        return None

    def verify_point(self, s_before, s_after):
        d = i32(s_after).astype(np.int64) - i32(s_before).astype(np.int64)
        li = (self.l_addr or 0) // 4
        ri = (self.r_addr or 0) // 4
        dl = int(d[li]) if self.l_addr else None
        dr = int(d[ri]) if self.r_addr else None
        if dl == 1 or dr == 1:
            self.confirmed_pts += 1
        return dl, dr


def play_game(p, sensor, game_no, max_frames=14000):
    """Steer the left paddle to play one full game until natural
    game over (either side reaches 5). Returns dict summary."""
    g = {"game": game_no, "serves": 0, "rallies": 0, "points": 0,
         "left_pts": 0, "right_pts": 0, "steps": 0,
         "ball_tracked_steps": 0, "max_ball_speed_px_f": 0.0,
         "steered_steps": 0, "frames_start": p.core.frames_run}
    last_cx = None
    teleport = None
    rally_start = p.core.frames_run
    rally = 0
    serve_no = 0
    prev_frame = p.core.frame_rgb()
    s_before_point = bytes(p.mem.snapshot())
    while True:
        # ---- observe ----
        fr = p.core.frame_rgb()
        a = madiff(prev_frame, fr)
        prev_frame = fr
        cls, facts = classify(fr, a)
        ball = ball_centroid(fr)
        prow = facts.get("paddle_l_row")
        g["steps"] += 1
        if ball is not None:
            g["ball_tracked_steps"] += 1
            cx, cy, n = ball
            if serve_no == 0:
                serve_no += 1
                g["serves"] += 1
                sc = sensor.scores()
                jrn({"ev": "serve", "game": game_no, "serve_no": 0,
                     "note": "game-start serve", "ball_x": round(cx, 1),
                     "ball_y": round(cy, 1), "scores": sc})
                save_png(fr, f"g{game_no}_serve00.png")
                s_before_point = bytes(p.mem.snapshot())
            if last_cx is not None:
                vx = (cx - last_cx) / STEP
                g["max_ball_speed_px_f"] = round(
                    max(g["max_ball_speed_px_f"], abs(vx)), 2)
                if abs(cx - last_cx) > LOST_TELEPORT_PX:
                    # reset teleport -> a point was just scored
                    s_after = bytes(p.mem.snapshot())
                    if sensor.r_addr is None and sensor.l_addr is not None:
                        sensor.identify_right(s_before_point, s_after)
                    dl, dr = sensor.verify_point(s_before_point, s_after)
                    scorer = ("left" if dl == 1 else
                              "right" if dr == 1 else
                              ("left(visual)" if last_cx > 160
                               else "right(visual)"))
                    g["points"] += 1
                    if str(scorer).startswith("left"):
                        g["left_pts"] += 1
                    elif str(scorer).startswith("right"):
                        g["right_pts"] += 1
                    sc = sensor.scores()
                    jrn({"ev": "point", "game": game_no,
                         "point_no": g["points"], "scorer": scorer,
                         "score_deltas": [dl, dr], "scores": sc,
                         "teleport_dx": round(cx - last_cx, 1),
                         "rally_frames":
                             p.core.frames_run - rally_start})
                    save_png(fr, f"g{game_no}_point{g['points']:02d}_"
                             f"{scorer}.png")
                    g["serves"] += 1
                    serve_no += 1
                    jrn({"ev": "serve", "game": game_no,
                         "serve_no": serve_no, "ball_x": round(cx, 1),
                         "ball_y": round(cy, 1), "scores": sc})
                    rally_start = p.core.frames_run
                    rally = 0
                    s_before_point = bytes(p.mem.snapshot())
                    sc_now = sensor.scores()
                    if sc_now and max(sc_now) >= 5:
                        jrn({"ev": "win_score_reached", "game": game_no,
                             "scores": sc_now})
                        # let the game-over frame render, then confirm
                        p.wait(30, set())
                        fr2 = p.core.frame_rgb()
                        cls2, f2 = classify(fr2, 0.0)
                        save_png(fr2, f"g{game_no}_gameover.png")
                        sc_go = sensor.scores()
                        jrn({"ev": "game_over", "game": game_no,
                             "scores": sc_go, "class": cls2,
                             **f2})
                        g["scores"] = sc_go
                        g["frames"] = p.core.frames_run - g["frames_start"]
                        g["end_class"] = cls2
                        return g
                    last_cx = cx
                    # ---- steer (below) then continue ----
                else:
                    rally += STEP
            last_cx = cx
        # ---- game-over without teleport safety (e.g. we missed the
        # teleport): static text screen ends the loop ----
        if cls == "GAME_OVER" and a is not None and a < 0.02:
            save_png(fr, f"g{game_no}_gameover.png")
            g["scores"] = sensor.scores()
            jrn({"ev": "game_over", "game": game_no,
                 "scores": g["scores"], "class": cls, **facts,
                 "note": "static-screen end (teleport missed)"})
            g["frames"] = p.core.frames_run - g["frames_start"]
            g["end_class"] = cls
            return g
        if cls in ("MENU", "PAUSED_LIKE"):
            jrn({"ev": "unexpected_state", "game": game_no, "class": cls,
                 **facts})
            if cls == "MENU":
                # got bumped to menu (should not happen mid-game):
                # record honestly and stop this game
                g["frames"] = p.core.frames_run - g["frames_start"]
                g["end_class"] = cls
                return g
        # ---- steering policy: track the ball with the left paddle ----
        if ball is not None and prow is not None:
            err = ball[1] - prow
            if abs(err) > 6:
                g["steered_steps"] += 1
                p.core.run(STEP, {"UP" if err < 0 else "DOWN"})
            else:
                p.core.run(STEP, set())
        else:
            p.core.run(STEP, set())
        if rally and rally % 60 == 0:
            jrn({"ev": "rally", "game": game_no, "dur_f": rally,
                 "ball": None if ball is None else
                 [round(ball[0], 1), round(ball[1], 1)],
                 "paddle_row": prow})
        if p.core.frames_run % 300 < STEP:
            save_png(p.core.frame_rgb(), f"g{game_no}_f{p.core.frames_run}.png")
        if p.core.frames_run - g["frames_start"] > max_frames:
            jrn({"ev": "game_budget_exhausted", "game": game_no,
                 "max_frames": max_frames})
            g["frames"] = p.core.frames_run - g["frames_start"]
            g["end_class"] = "BUDGET"
            return g


def restart_causality(p, sensor, tag):
    """On the game-over screen: idle control leg vs CROSS-release leg."""
    fr0 = p.core.frame_rgb()
    save_png(fr0, f"{tag}_over_before.png")
    cls0, facts0 = classify(fr0, 0.0)
    # control leg: 90f idle
    ctrl = []
    for _ in range(6):
        a = p.core.frame_rgb()
        p.wait(15, set())
        ctrl.append(round(madiff(a, p.core.frame_rgb()) or 0.0, 4))
    still = p.core.frame_rgb()
    cls_ctrl, _ = classify(still, 0.0)
    save_png(still, f"{tag}_over_control.png")
    # X leg: hold+release CROSS
    addrs = padbuff_addrs(bytes(p.mem.snapshot()))
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
    save_png(after, f"{tag}_after_x.png")
    out = {"tag": tag, "before_class": cls0, "before": facts0,
           "control_madiffs": ctrl, "control_max": max(ctrl),
           "control_class": cls_ctrl,
           "x_mirror_held": mir, "x_seq": seq, "x_max": max(seq),
           "after_class": cls_after, "after": facts_after,
           "discrimination": round(max(seq) - max(ctrl), 4)}
    jrn({"ev": "restart_causality", **out})
    return out


def score_crop(fr):
    """Score-band crop bytes (score digits at y=20, x=120/192 upstream)."""
    g = fr.mean(axis=2)
    return np.ascontiguousarray(g[14:34, 96:224]).tobytes()


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(JRN_PATH):
        os.rename(JRN_PATH, JRN_PATH + "." +
                  time.strftime("%Y%m%d_%H%M%S"))
    rep = {"schema": "ps1ai-hellopong-r11-fullloop/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "task": "17-c", "lane": "17-c hello_pong full loop"}
    t0 = time.time()

    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system",
                                               "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(LIC_CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot_info = p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    jrn({"ev": "boot", "core": boot_info, "fw_trust": ok,
         "fw_detail": detail})
    if not ok:
        raise SystemExit(f"firmware trust failed: {detail}")
    rep["boot"] = {"core": boot_info, "fw_detail": detail}

    CUR["f"] = 0
    cls, timeline, addrs = settle_boot(p, rep)
    CUR["f"] = p.core.frames_run
    rep["boot_state"] = {"class": cls, "polls": len(timeline),
                         "padbuff": [hex(a) for a in addrs]}
    jrn({"ev": "boot_state", **rep["boot_state"]})
    if cls == "TIMEOUT":
        rep["verdict"] = "FAILED(boot: no game screen)"
        with open(os.path.join(OUT, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        return 1

    sensor = ScoreSensor(p)
    games = []
    # ---------- reach a fresh PLAYING start ----------
    if cls == "PLAYING":
        jrn({"ev": "auto_start_observed",
             "note": "upstream pad-init garbage CROSS release "
                     "auto-starts a fresh game (scores 0-0)"})
    if cls == "GAME_OVER":
        # restart causality FIRST (this is the round milestone), then
        # menu -> fresh start
        rc = restart_causality(p, sensor, "boot")
        rep["restart_causality_boot"] = rc
        cls = rc["after_class"]
    if cls in ("MENU", "GAME_OVER"):
        if cls == "GAME_OVER":
            rc = restart_causality(p, sensor, "boot2")
            rep["restart_causality_boot2"] = rc
            cls = rc["after_class"]
        # START negative control on the menu
        mir_s = hold_and_release(p, "START", addrs)
        p.wait(60, set())
        fr_s = p.core.frame_rgb()
        cls_s, _ = classify(fr_s, 0.0)
        save_png(fr_s, "menu_start_negctl.png")
        jrn({"ev": "menu_start_negctl", "mirror": mir_s,
             "class_after": cls_s})
        rep["menu_start_negctl"] = {"mirror": mir_s,
                                    "class_after": cls_s}
        # X -> PLAYING (the causal 'start the game')
        mir_x = hold_and_release(p, "B", addrs)
        seq = []
        pre = fr_s
        for _ in range(12):
            prev = p.core.frame_rgb()
            p.wait(2, set())
            fr = p.core.frame_rgb()
            seq.append(round(madiff(prev, fr) or 0.0, 4))
        p.wait(40, set())
        fr_p = p.core.frame_rgb()
        cls_p, facts_p = classify(fr_p, 0.3)
        save_png(fr_p, "menu_after_x_playing.png")
        rep["menu_x_start"] = {"mirror": mir_x, "seq": seq,
                               "max": max(seq), "class_after": cls_p,
                               **facts_p}
        jrn({"ev": "start_from_menu", "max": max(seq),
             "class_after": cls_p})
        if cls_p != "PLAYING":
            p.wait(120, set())
            cls_p, facts_p = classify(p.core.frame_rgb(), 0.3)
            rep["menu_x_start"]["class_after_retry"] = cls_p

    # ---------- paddle + score sensor calibration (in PLAYING) ----------
    fr_c = p.core.frame_rgb()
    row0 = paddle_row(fr_c, PADDLE_L_COLS)
    disc = sensor.discover_left(
        row_fn=lambda: paddle_row(p.core.frame_rgb(), PADDLE_L_COLS))
    fr_c2 = p.core.frame_rgb()
    row_back = paddle_row(fr_c2, PADDLE_L_COLS)
    save_png(fr_c2, "paddle_after_updown_cal.png")
    disc["visual_dy_up"] = (None if row0 is None or
                            disc.get("visual_row_during_up") is None
                            else round(disc["visual_row_during_up"]
                                       - row0, 1))
    disc["visual_dy_restore"] = (None if row0 is None or row_back is None
                                 else round(row_back - row0, 1))
    jrn({"ev": "paddle_visual_dy",
         "row0": row0, "row_up": disc.get("visual_row_during_up"),
         "row_back": row_back,
         "dy_up": disc.get("visual_dy_up"),
         "dy_restore": disc.get("visual_dy_restore"),
         "ram": disc.get("ok")})
    rep["paddle_causality"] = disc
    sensor_ok = bool(disc.get("ok"))
    scores0 = sensor.scores() if sensor_ok else None
    crop0 = score_crop(fr_c2)
    rep["scores_at_calibration"] = scores0
    rep["score_crop_cal_sha"] = __import__("hashlib").sha256(
        crop0).hexdigest()[:16]
    jrn({"ev": "scores_at_calibration", "scores": scores0,
         "sensor_ok": sensor_ok,
         "score_crop_sha": rep["score_crop_cal_sha"]})

    # ---------- play games ----------
    game_no = 0
    restarts = []
    while game_no < 3:
        game_no += 1
        g = play_game(p, sensor, game_no)
        games.append(g)
        jrn({"ev": "game_summary", **g})
        if game_no >= 3 or g.get("end_class") not in ("GAME_OVER",):
            break
        # restart chain for the next fresh game (control leg repeated)
        rc = restart_causality(p, sensor, f"g{game_no}")
        restarts.append(rc)
        if rc["after_class"] != "MENU":
            jrn({"ev": "restart_chain_stuck", "class": rc["after_class"]})
            break
        # START negative control on this menu too (cheap, causal)
        mir_s = hold_and_release(p, "START", addrs)
        p.wait(40, set())
        # X -> fresh game
        hold_and_release(p, "B", addrs)
        p.wait(40, set())
        fr_p = p.core.frame_rgb()
        cls_p, _ = classify(fr_p, 0.3)
        save_png(fr_p, f"fresh_g{game_no + 1}_serve.png")
        sc = sensor.scores() if sensor_ok else None
        crop_eq = __import__("hashlib").sha256(
            score_crop(fr_p)).hexdigest()[:16] == \
            rep["score_crop_cal_sha"]
        jrn({"ev": "fresh_game_started", "game": game_no + 1,
             "class": cls_p, "scores": sc,
             "scores_reset_ok": (sc == [0, 0]) if sc else None,
             "score_crop_eq_cal": crop_eq})
        rep.setdefault("fresh_games", []).append(
            {"game": game_no + 1, "class": cls_p, "scores": sc,
             "score_crop_eq_cal": crop_eq})
        if cls_p != "PLAYING":
            p.wait(120, set())

    rep["games"] = games
    rep["restarts"] = restarts
    rep["final_scores"] = sensor.scores() if sensor_ok else None
    rep["sensor"] = {"ok": sensor_ok,
                     "y_addr": hex(sensor.y_addr) if sensor.y_addr
                     else None,
                     "l_addr": hex(sensor.l_addr) if sensor.l_addr
                     else None,
                     "r_addr": hex(sensor.r_addr) if sensor.r_addr
                     else None,
                     "confirmed_points": sensor.confirmed_pts}

    # ---------- verdict ----------
    played = any(g.get("steered_steps", 0) > 10 and
                 g.get("ball_tracked_steps", 0) > 30 for g in games)
    natural_over = [g for g in games if g.get("end_class") == "GAME_OVER"]
    over_scores_ok = all(
        (g.get("scores") or [0, 0]) and max(g["scores"]) >= 5
        for g in natural_over) if sensor_ok else len(natural_over) > 0
    restart_ok = all(r["x_max"] > 1.0 and
                     r["x_max"] >= 3.0 * max(r["control_max"], 1e-9)
                     for r in restarts) if restarts else False
    fresh_ok = False
    if rep.get("fresh_games"):
        if sensor_ok:
            fresh_ok = all(f.get("scores") == [0, 0]
                           for f in rep["fresh_games"])
        else:
            fresh_ok = all(f.get("score_crop_eq_cal")
                           for f in rep["fresh_games"])
    cal_ok = bool(disc.get("ok")) and \
        disc.get("visual_dy_up") is not None and \
        disc.get("visual_dy_up") < -2
    start_ok = bool(rep.get("menu_x_start", {}).get("max", 0) > 1.0) or \
        any(g.get("serves", 0) > 0 for g in games)

    parts = {
        "boot": True,
        "paddle_causality": cal_ok,
        "played": played,
        "natural_game_over": len(natural_over) >= 1 and over_scores_ok,
        "restart_causal": restart_ok,
        "fresh_game": fresh_ok,
        "start_causal": start_ok,
    }
    if all(parts.values()):
        verdict = "COMPLETE_LOOP_CAUSAL"
    elif parts["boot"] and (played or natural_over):
        verdict = "PARTIAL(" + ",".join(
            k for k, v in parts.items() if not v) + ")"
    else:
        verdict = "FAILED"
    rep["verdict_parts"] = parts
    rep["verdict"] = verdict
    rep["wall_s"] = round(time.time() - t0, 1)
    rep["frames_run"] = p.core.frames_run
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    jrn({"ev": "verdict", "verdict": verdict, "parts": parts,
         "wall_s": rep["wall_s"],
         "frames_run": rep["frames_run"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
