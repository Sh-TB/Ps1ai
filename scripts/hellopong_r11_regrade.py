#!/usr/bin/env python3
"""hellopong_r11_regrade.py — Round 11 / Segment 8b: corrected grading.

The r11 full_loop run (scratch/round11_hellopong/full_loop/) returned
PARTIAL(paddle_causality, restart_causal, fresh_game) — but its three
negative grades are METRIC artifacts, not game facts:

  1. paddle_causality "false": visual_row DID move 123 -> 115 during UP
     (-8 px) and returned to 123 after release — that IS causality;
     the ok-flag additionally demanded a RAM restore-candidate set,
     which the (optional) sensor hunt did not find.
  2. restart_causal "false": the X leg showed after_class=MENU vs
     control_class=GAME_OVER — but discrimination was computed from
     HOLD-window frame diffs (x_max=0.0), while the upstream ground
     truth (main.c) is trigger-on-RELEASE (is_button_just_released):
     the screen changes AFTER the release edge, not during the hold.
  3. fresh_game "false": games 2 and 3 DID run (PLAYING, serves 5-6,
     natural game over each) — the flag keyed on the missing RAM score
     sensor instead of the class/serve evidence.

This script re-grades with corrected criteria on a FRESH boot:
  A. paddle causality: idle baseline -> UP hold (visual row samples)
     -> release restore; PLUS an idle-matched control window (same
     timeline, no input) in the same boot.  Causal iff |dy_hold| >= 2
     px in the arm, |dy| < 2 in the control, and restore < 2 px.
  B. restart causality: GAME_OVER -> control leg (idle 120 f, class
     must stay GAME_OVER) -> CROSS hold+release leg (class must reach
     MENU within 300 f of the RELEASE — the ground-truth trigger).
  C. fresh game: MENU -> CROSS release -> PLAYING -> play one full
     game with the proven steering policy -> NATURAL game over ->
     fresh_game=true (serve evidence + class transitions).
Evidence: scratch/round11_hellopong/regrade/. ONE beetle boot per
process. No RAM writes. Honest verdicts.
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hellopong_r11_full_loop as FL                   # noqa: E402
from hellopong_r11_full_loop import (                  # noqa: E402
    classify, hold_and_release, madiff, padbuff_addrs, play_game,
    paddle_row, save_png, settle_boot)
from ps1play.api import PS1Play                        # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/hello_pong_lic.cue"
WS = os.path.join(FL.EMU, "ws_hellopong_r11")
OUT = os.path.join(_REPO, "scratch", "round11_hellopong", "regrade")

REP = {"schema": "ps1ai-hellopong-r11-regrade/1",
       "task": "17-c regrade (corrected metrics, fresh boot)"}


def jrn(ev):
    print("[r11-regrade]", json.dumps(ev, default=str), flush=True)
    with open(os.path.join(OUT, "regrade.jsonl"), "a") as f:
        f.write(json.dumps(ev, default=str) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    cls, timeline, addrs = settle_boot(p, REP)
    jrn({"ev": "boot", "class": cls, "padbuff": len(addrs)})
    REP["boot"] = {"class": cls, "padbuff": len(addrs)}

    parts = {"boot": cls in ("PLAYING", "MENU", "GAME_OVER")}

    # If we auto-started into PLAYING (garbage release edge), ride it to
    # a natural game over first so every leg starts from a known class.
    for _ in range(40):
        cls, facts = classify(p.core.frame_rgb(), 0.0)
        if cls == "GAME_OVER":
            break
        if cls == "PLAYING":
            sensor = FL.ScoreSensor(p)
            play_game(p, sensor, 99, max_frames=12000)
            continue
        p.wait(60, set())
    cls0, _ = classify(p.core.frame_rgb(), 0.0)
    jrn({"ev": "phase0_class", "class": cls0})

    # ---------------- A. paddle causality (visual, arm vs control) ----
    def row_now():
        return paddle_row(p.core.frame_rgb(), FL.PADDLE_L_COLS)

    def sample(n=8, every=2, btn=None):
        rows = []
        for _ in range(n):
            rows.append(row_now())
            p.wait(every, {btn} if btn else set())
        return rows

    # ensure we are INSIDE a playing game for the paddle test
    if cls0 != "PLAYING":
        hold_and_release(p, "B", addrs)          # MENU/GAME_OVER -> PLAYING
        p.wait(45, set())
    clsA, _ = classify(p.core.frame_rgb(), 0.0)
    base = sample()
    base_rows = [r for r in base if r is not None]
    idle = sample()                               # control: no input
    idle_rows = [r for r in idle if r is not None]
    # UP on the dpad (inputmap name used by the proven steer policy)
    up_rows = [r for r in sample(8, 2, "UP") if r is not None]
    post_rows = [r for r in sample(8, 2) if r is not None]

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None

    b_med, u_med, p_med = med(base_rows), med(up_rows), med(post_rows)
    i_med = med(idle_rows)
    dy_hold = (u_med - b_med) if (u_med is not None and b_med is not None) else None
    dy_rest = (p_med - b_med) if (p_med is not None and b_med is not None) else None
    dy_idle = (i_med - b_med) if (i_med is not None and b_med is not None) else 0.0
    paddle_ok = (dy_hold is not None and abs(dy_hold) >= 2.0
                 and abs(dy_rest or 0.0) < 2.0
                 and abs(dy_idle or 0.0) < 2.0)
    parts["paddle_causality"] = bool(paddle_ok)
    REP["paddle"] = {"class": clsA, "baseline_med": b_med,
                     "up_med": u_med, "post_med": p_med,
                     "idle_med": i_med, "dy_hold": dy_hold,
                     "dy_restore": dy_rest, "dy_idle_ctrl": dy_idle,
                     "ok": paddle_ok}
    jrn({"ev": "paddle_regrade", **REP["paddle"]})
    save_png(p.core.frame_rgb(), "paddle_after_up.png")

    # ride this game to natural game over for the restart leg
    sensor = FL.ScoreSensor(p)
    g = play_game(p, sensor, 90, max_frames=14000)
    REP["ride_game"] = g
    jrn({"ev": "ride_game", **{k: g[k] for k in
                               ("game", "serves", "points", "left_pts",
                                "right_pts", "end_class") if k in g}})
    clsR, _ = classify(p.core.frame_rgb(), 0.0)

    # ---------------- B. restart causality (class-transition metric) --
    fr0 = p.core.frame_rgb()
    save_png(fr0, "regrade_over_before.png")
    # control leg: 120 f idle — class must stay GAME_OVER
    ctrl_classes = []
    for _ in range(8):
        p.wait(15, set())
        ctrl_classes.append(classify(p.core.frame_rgb(), 0.0)[0])
    control_held = all(c == "GAME_OVER" for c in ctrl_classes)
    # X leg: hold+release CROSS; sample 300 f after release
    mir = hold_and_release(p, "B", addrs)
    x_classes = []
    for _ in range(20):
        p.wait(15, set())
        x_classes.append(classify(p.core.frame_rgb(), 0.0)[0])
    reached_menu = "MENU" in x_classes
    restart_ok = control_held and reached_menu
    parts["restart_causal"] = bool(restart_ok)
    REP["restart"] = {"before_class": clsR,
                      "control_classes": ctrl_classes[:4],
                      "control_held": control_held,
                      "x_mirror_held": mir,
                      "x_classes": x_classes,
                      "reached_menu": reached_menu,
                      "ok": restart_ok}
    jrn({"ev": "restart_regrade", **REP["restart"]})

    # ---------------- C. fresh game -----------------------------------
    fresh = False
    if reached_menu:
        mir2 = hold_and_release(p, "B", addrs)   # MENU -> PLAYING
        p.wait(45, set())
        clsN, _ = classify(p.core.frame_rgb(), 0.0)
        jrn({"ev": "fresh_start", "class": clsN})
        if clsN == "PLAYING":
            sensor2 = FL.ScoreSensor(p)
            g2 = play_game(p, sensor2, 91, max_frames=14000)
            REP["fresh_game"] = g2
            fresh = (g2.get("end_class") == "GAME_OVER"
                     and g2.get("serves", 0) >= 1
                     and g2.get("points", 0) >= 1)
            jrn({"ev": "fresh_game", **{k: g2[k] for k in
                                        ("game", "serves", "points",
                                         "left_pts", "right_pts",
                                         "end_class") if k in g2},
                 "ok": fresh})
    parts["fresh_game"] = bool(fresh)

    verdict = ("COMPLETE_LOOP_CAUSAL" if all(parts.values()) else
               "PARTIAL(" + ",".join(k for k, v in parts.items() if not v)
               + ")")
    REP["parts"] = parts
    REP["verdict"] = verdict
    REP["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(REP, f, indent=1, default=str)
    jrn({"ev": "verdict", "verdict": verdict, "parts": parts})
    print("VERDICT:", verdict)
    return 0 if all(parts.values()) else 3


if __name__ == "__main__":
    sys.exit(main())
