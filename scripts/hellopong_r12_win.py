#!/usr/bin/env python3
"""hellopong_r12_win.py — Round 12 (Task 16-c) SEGMENT 2: the WIN arm.

ONE process, ONE beetle boot. Goal: FINISH a game by WINNING it —
drive the LEFT (P1) score sensor 0 -> 5 with honest, frame-anchored
evidence:

  boot -> (auto-started fresh game | MENU | GAME_OVER) -> reach PLAYING
  -> score-sensor discovery via NATURAL point events (observe-only;
     see hellopong_r12_lib.discover_score_by_points for why the r11
     UP-tap-first order was replaced)
  -> UP-tap VERIFICATION of the y field (r11 idiom)
  -> play P1: track the ball with UP/DOWN taps (STEP=2, policy copied
     verbatim from hellopong_r11_full_loop.py); the serve is ALWAYS
     rightward toward the STATIC right paddle (pad2 connected -> no AI),
     x>320 -> LEFT scores
  -> LEFT reaches 5 -> GAME_OVER screen (text region captured; the score
     sensor is the primary evidence, text is corroboration only)
  -> restart causality on the game-over screen (idle control vs X
     release) -> MENU -> X release -> FRESH game (scores 0-0) -> stop.

Verdicts: WIN_CAUSAL / PARTIAL(...) / FAILED — with numbers.
Evidence: scratch/round12_hellopong/win/.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hellopong_r12_lib import (                    # noqa: E402
    REPO, STEP, WIN_SCORE, LOST_TELEPORT_PX,
    ScoreSensor, ball_centroid, boot_hellopong, classify,
    discover_score_by_points, hold_and_release, madiff, make_jrn,
    paddle_row, restart_causality, save_png, score_crop, settle_boot,
    text_crop, verify_y_tap)

OUT = os.path.join(REPO, "scratch", "round12_hellopong", "win")
WS = "/home/z/my-project/emu/games_homebrew/ws_hellopong_r12_win"
MAX_FRAMES = 20000                # task cap for the whole run


def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


def play_game_win(p, sensor, jrn, out_dir, start_frame, pts0=0,
                  anchors0=None, left0=0, right0=0):
    """Steer the left paddle (r11 policy verbatim) until LEFT reaches 5
    (WIN) or RIGHT does (LOST) or the frame budget expires."""
    g = {"serves": 0, "points": pts0, "left_pts": left0,
         "right_pts": right0, "steps": 0, "ball_tracked_steps": 0,
         "steered_steps": 0, "max_ball_speed_px_f": 0.0, "rallies": [],
         "anchors": list(anchors0 or []), "score_progression": [],
         "frames_start": start_frame}
    last_cx = None
    prev_frame = p.core.frame_rgb()
    rally_start = p.core.frames_run
    last_sc = None
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
            if last_cx is not None:
                vx = (cx - last_cx) / STEP
                g["max_ball_speed_px_f"] = round(
                    max(g["max_ball_speed_px_f"], abs(vx)), 2)
            if g["serves"] == 0:
                g["serves"] += 1
                sc0 = sensor.scores()
                jrn({"ev": "serve", "serve_no": 0,
                     "note": "first ball sighting in the play phase",
                     "ball_x": round(cx, 1), "ball_y": round(cy, 1),
                     "scores": sc0})
                save_png(out_dir, fr, "serve00.png")
            # ---- point event: reset teleport ----
            if last_cx is not None and abs(cx - last_cx) > LOST_TELEPORT_PX:
                sc = sensor.scores()
                sc_prev = last_sc if last_sc is not None else sc
                dl = (sc[0] - sc_prev[0]) if (sc and sc_prev) else None
                dr = ((sc[1] - sc_prev[1])
                      if (sc and sc_prev and sc[1] is not None) else None)
                scorer = ("left" if dl == 1 else
                          "right" if dr == 1 else "unverified")
                g["points"] += 1
                if str(scorer).startswith("left"):
                    g["left_pts"] += 1
                elif str(scorer).startswith("right"):
                    g["right_pts"] += 1
                pn = g["points"]
                png = save_png(out_dir, fr,
                               f"point{pn:02d}_{scorer}.png")
                anchor = {"point": pn, "scorer": scorer,
                          "frame": p.core.frames_run,
                          "teleport_dx": round(cx - last_cx, 1),
                          "score_deltas": [dl, dr], "scores": sc,
                          "rally_frames": p.core.frames_run - rally_start,
                          "png": png,
                          "score_crop_sha": sha16(score_crop(fr))}
                g["anchors"].append(anchor)
                g["score_progression"].append({"frame":
                                               p.core.frames_run,
                                               "scores": sc})
                g["rallies"].append(p.core.frames_run - rally_start)
                jrn({"ev": "point", **anchor})
                g["serves"] += 1
                jrn({"ev": "serve", "serve_no": g["serves"],
                     "ball_x": round(cx, 1), "ball_y": round(cy, 1),
                     "scores": sc})
                rally_start = p.core.frames_run
                last_sc = sc
                last_cx = cx          # post-reset ball; avoid re-trigger
                # ---- win / lose terminal check on the sensor ----
                if sc and sc[0] >= WIN_SCORE:
                    return finish(p, g, "WIN", jrn, out_dir, sc)
                if sc and sc[1] >= WIN_SCORE:
                    return finish(p, g, "LOST", jrn, out_dir, sc)
            else:
                last_cx = cx
        # ---- score watch (observe-only safety net, every 4 steps) ----
        if g["steps"] % 4 == 0:
            sc_w = sensor.scores()
            if sc_w is not None:
                if last_sc is not None and sc_w != last_sc:
                    pn = g["points"] + 1
                    g["points"] = pn
                    dl = sc_w[0] - last_sc[0]
                    dr = ((sc_w[1] - last_sc[1])
                          if sc_w[1] is not None and
                          last_sc[1] is not None else None)
                    scorer = ("left(watch)" if dl == 1 else
                              "right(watch)" if dr == 1 else
                              "unknown(watch)")
                    if dl == 1:
                        g["left_pts"] += 1
                    elif dr == 1:
                        g["right_pts"] += 1
                    png = save_png(out_dir, p.core.frame_rgb(),
                                   f"point{pn:02d}_{scorer}.png")
                    g["anchors"].append({"point": pn, "scorer": scorer,
                                         "frame": p.core.frames_run,
                                         "score_deltas": [dl, dr],
                                         "scores": sc_w, "png": png})
                    g["score_progression"].append(
                        {"frame": p.core.frames_run, "scores": sc_w})
                    jrn({"ev": "point_watch_no_teleport", "point": pn,
                         "scorer": scorer, "scores": sc_w,
                         "score_deltas": [dl, dr],
                         "frame": p.core.frames_run, "png": png})
                    last_cx = None
                    if sc_w[0] >= WIN_SCORE:
                        return finish(p, g, "WIN", jrn, out_dir, sc_w)
                    if sc_w[1] is not None and sc_w[1] >= WIN_SCORE:
                        return finish(p, g, "LOST", jrn, out_dir, sc_w)
                last_sc = sc_w
        # ---- static game-over screen ends the loop (safety) ----
        if cls == "GAME_OVER" and a is not None and a < 0.02:
            sc_end = sensor.scores()
            if sc_end and sc_end[0] >= WIN_SCORE:
                return finish(p, g, "WIN", jrn, out_dir, sc_end)
            if sc_end and sc_end[1] is not None and sc_end[1] >= WIN_SCORE:
                return finish(p, g, "LOST", jrn, out_dir, sc_end)
            save_png(out_dir, fr, "static_gameover.png")
            jrn({"ev": "static_gameover_no_sensor_win",
                 "scores": sc_end, **facts})
            return finish(p, g, "STATIC_OVER", jrn, out_dir, sc_end)
        if cls == "MENU":
            jrn({"ev": "unexpected_menu_midplay", **facts})
            return finish(p, g, "MENU_ABORT", jrn, out_dir,
                          sensor.scores())
        # ---- steering policy (r11 verbatim): track the ball ----
        if ball is not None and prow is not None:
            err = ball[1] - prow
            if abs(err) > 6:
                g["steered_steps"] += 1
                p.core.run(STEP, {"UP" if err < 0 else "DOWN"})
            else:
                p.core.run(STEP, set())
        else:
            p.core.run(STEP, set())
        if p.core.frames_run % 300 < STEP:
            save_png(out_dir, p.core.frame_rgb(),
                     f"f{p.core.frames_run}.png")
        if p.core.frames_run - g["frames_start"] > MAX_FRAMES:
            jrn({"ev": "budget_exhausted", "max_frames": MAX_FRAMES})
            return finish(p, g, "BUDGET", jrn, out_dir, sensor.scores())


def finish(p, g, end, jrn, out_dir, sc_final):
    """Terminal screen evidence: the GAME_OVER text region (corroboration;
    the score sensor progression is the primary win evidence)."""
    p.wait(30, set())
    fr2 = p.core.frame_rgb()
    cls2, f2 = classify(fr2, 0.0)
    save_png(out_dir, fr2, "gameover.png")
    crop = text_crop(fr2)
    save_png(out_dir, crop, "gameover_textcrop.png")
    gband = int((crop > 150).sum())
    g.update({"end": end, "end_class": cls2, "end_facts": f2,
              "scores_final": sc_final,
              "textcrop_bright_px": gband,
              "textcrop_sha16": sha16(crop.tobytes()),
              "frames": p.core.frames_run - g["frames_start"],
              "frames_run_total": p.core.frames_run})
    jrn({"ev": "game_over", "end": end, "class": cls2, **f2,
         "scores": sc_final, "textcrop_bright_px": gband,
         "note": "winner text is corroboration only; the score sensor "
                 "progression is the primary evidence"})
    return g


def main():
    jrn = make_jrn(OUT, "[r12win]")
    # honest archival of any previous attempt in this dir
    if os.path.exists(os.path.join(OUT, "report.json")):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        arch = os.path.join(OUT, f"attempt_archived_{stamp}")
        os.makedirs(arch, exist_ok=True)
        for fn in os.listdir(OUT):
            if fn.endswith((".png", ".json", ".jsonl")):
                os.rename(os.path.join(OUT, fn), os.path.join(arch, fn))
        jrn({"ev": "archived_previous_attempt", "dir": arch})
    rep = {"schema": "ps1ai-hellopong-r12-win/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "task": "16-c", "lane": "16-c hello_pong WIN arm",
           "one_boot_per_process": True,
           "upstream_ground_truth": {
               "repo": "marconvcm/ps1_dev @ dec2f3f0 (MIT)",
               "files": ["src/main.c", "src/libs/game_pad.c",
                         "src/libs/game_pad.h"],
               "facts": ["start/restart = is_button_just_released(CROSS)",
                         "GAME_OVER -(X rel)-> MENU; MENU -(X rel)-> PLAYING",
                         "win at 5 either side; x<0 right scores, "
                         "x>320 left scores; serve always rightward "
                         "(reset_ball: x=152 even -> +2; y=112 -> vy=-1)",
                         "P1 left paddle = pad1 UP/DOWN 4px/f; no AI "
                         "(beetle exposes 2 pads) -> right paddle STATIC",
                         "left_paddle/right_paddle are main() STACK "
                         "locals; &left_paddle taken every frame -> "
                         "materialized stack slot (sensor-viable)",
                         "libretro X=TRIANGLE is in-play pause (negative)"]},
           }
    t0 = time.time()
    p, boot_info = boot_hellopong(WS, jrn)
    rep["boot"] = boot_info
    jrn.cur["f"] = p.core.frames_run

    cls, timeline, addrs = settle_boot(p, jrn)
    jrn.cur["f"] = p.core.frames_run
    rep["boot_state"] = {"class": cls, "polls": len(timeline),
                         "padbuff": [hex(a) for a in addrs]}
    jrn({"ev": "boot_state", **rep["boot_state"]})
    if cls == "TIMEOUT":
        rep["verdict"] = "FAILED(boot: no game screen)"
        with open(os.path.join(OUT, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        return 1

    sensor = ScoreSensor(p)

    # ---------- reach a fresh PLAYING start ----------
    if cls == "PLAYING":
        jrn({"ev": "auto_start_observed",
             "note": "upstream pad-init garbage CROSS release auto-starts "
                     "a fresh game (scores 0-0)"})
    if cls == "GAME_OVER":
        rc = restart_causality(p, jrn, OUT, "boot", addrs)
        rep["restart_causality_boot"] = rc
        cls = rc["after_class"]
    if cls == "GAME_OVER":       # still stuck: second attempt
        rc = restart_causality(p, jrn, OUT, "boot2", addrs)
        rep["restart_causality_boot2"] = rc
        cls = rc["after_class"]
    if cls == "MENU":
        mir_x = hold_and_release(p, "B", addrs)
        p.wait(40, set())
        fr_p = p.core.frame_rgb()
        cls_p, facts_p = classify(fr_p, 0.3)
        save_png(OUT, fr_p, "menu_after_x_playing.png")
        rep["menu_x_start"] = {"mirror": mir_x, "class_after": cls_p,
                               **facts_p}
        jrn({"ev": "start_from_menu", "class_after": cls_p})
        if cls_p != "PLAYING":
            p.wait(120, set())
            cls_p, facts_p = classify(p.core.frame_rgb(), 0.3)
            rep["menu_x_start"]["class_after_retry"] = cls_p
        cls = cls_p if cls_p == "PLAYING" else cls
    if cls != "PLAYING":
        rep["verdict"] = f"FAILED(start chain ended in {cls})"
        rep["sensor"] = sensor.sensor_block()
        with open(os.path.join(OUT, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        return 1

    # ---------- score-sensor discovery ----------
    # v2: the r11 UP-tap idiom FIRST (16 frames, no time pressure);
    # the points-diff walk is the fallback (the game self-plays fast and
    # game-overed during discovery in attempt 1).
    dleft = sensor.discover_left()
    jrn({"ev": "discover_left_r11",
         "ok": dleft.get("ok"),
         "y_addr": dleft.get("y_addr"), "l_addr": dleft.get("l_addr"),
         "cands": len(dleft.get("up_restore_candidates", []))})
    if dleft.get("ok"):
        disc = {"ok": True, "via": "up_tap_restore_r11",
                "y_addr": dleft.get("y_addr"),
                "l_addr": dleft.get("l_addr"),
                "points": 0, "left_after": 0, "anchors": [],
                "end_class": "PLAYING"}
    else:
        disc = discover_score_by_points(p, jrn, OUT, sensor,
                                        need_points=3, max_frames=4000)
    rep["sensor_discovery"] = {k: v for k, v in disc.items()
                               if k != "anchors"}
    jrn({"ev": "sensor_discovery_summary",
         "ok": disc.get("ok"), "points": disc.get("points"),
         "l_addr": disc.get("l_addr"), "y_addr": disc.get("y_addr"),
         "end_class": disc.get("end_class")})
    if disc.get("end_class") == "GAME_OVER":
        # the walkover finished during discovery: this IS a completed
        # game (idle). Treat as a played game with the discovered points.
        jrn({"ev": "note", "text": "game over during discovery"})
    if not disc.get("ok"):
        rep["verdict"] = "FAILED(score sensor not discoverable)"
        rep["sensor"] = sensor.sensor_block()
        with open(os.path.join(OUT, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        return 1

    # ---------- UP-tap verification of the y field (r11 idiom) ----------
    ytap = verify_y_tap(p, sensor, jrn, OUT)
    rep["y_tap_verify"] = ytap

    # ---------- play to WIN ----------
    left0 = disc.get("left_after") or 0
    g = play_game_win(p, sensor, jrn, OUT, p.core.frames_run,
                      pts0=disc.get("points", 0),
                      anchors0=disc.get("anchors", []),
                      left0=left0, right0=0)
    rep["game"] = {k: v for k, v in g.items() if k != "anchors"}
    rep["anchors"] = g.get("anchors", [])
    rep["sensor"] = sensor.sensor_block()
    rep["final_scores"] = g.get("scores_final")

    # ---------- restart chain on the game-over screen ----------
    restart_ok = None
    fresh = None
    if g.get("end") in ("WIN", "LOST", "STATIC_OVER"):
        rc = restart_causality(p, jrn, OUT, "win", addrs)
        rep["restart_causality_win"] = rc
        restart_ok = bool(rc["x_max"] > 1.0 and
                          rc["x_max"] >= 3.0 * max(rc["control_max"], 1e-9)
                          and rc["after_class"] == "MENU")
        if rc["after_class"] == "MENU":
            # X release once more: MENU -> fresh PLAYING (scores 0-0)
            hold_and_release(p, "B", addrs)
            p.wait(40, set())
            fr_f = p.core.frame_rgb()
            cls_f, facts_f = classify(fr_f, 0.3)
            if cls_f != "PLAYING":
                p.wait(120, set())
                cls_f, facts_f = classify(p.core.frame_rgb(), 0.3)
            save_png(OUT, p.core.frame_rgb(), "fresh_after_restart.png")
            sc_f = sensor.scores()
            fresh = {"class": cls_f, "scores": sc_f,
                     "scores_reset_ok": sc_f == [0, 0]}
            jrn({"ev": "fresh_game_after_restart", **fresh})
            rep["fresh_after_restart"] = fresh

    # ---------- verdict ----------
    progression_ok = bool(
        g.get("scores_final") and g["scores_final"][0] == WIN_SCORE and
        len(g.get("anchors", [])) >= WIN_SCORE)
    played = bool(g.get("steered_steps", 0) > 10 and
                  g.get("ball_tracked_steps", 0) > 30)
    over_screen = g.get("end_class") == "GAME_OVER"
    parts = {
        "played": played,
        "left_score_5_anchored": progression_ok,
        "gameover_screen": over_screen,
        "restart_causal": bool(restart_ok),
    }
    if all(parts.values()):
        verdict = "WIN_CAUSAL"
    elif parts["played"] or parts["left_score_5_anchored"]:
        verdict = "PARTIAL(" + ",".join(k for k, v in parts.items()
                                        if not v) + ")"
    else:
        verdict = f"FAILED({g.get('end')})"
    rep["verdict_parts"] = parts
    rep["verdict"] = verdict
    rep["wall_s"] = round(time.time() - t0, 1)
    rep["frames_run"] = p.core.frames_run
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    jrn({"ev": "verdict", "verdict": verdict, "parts": parts,
         "scores_final": rep["final_scores"],
         "frames_run": rep["frames_run"], "wall_s": rep["wall_s"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
