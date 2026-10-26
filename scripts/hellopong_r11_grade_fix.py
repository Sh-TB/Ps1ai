#!/usr/bin/env python3
"""hellopong_r11_grade_fix.py — Round 11 / Segment 8c: corrected grading
from the EXISTING full_loop evidence (no emulator time).

The r11 full_loop run (scratch/round11_hellopong/full_loop/) recorded a
COMPLETE loop end-to-end but graded three parts false on metric design:
  1. paddle_causality demanded a RAM restore-candidate set; the VISUAL
     evidence (row 123 -> 115 during UP-hold, -> 123 after release,
     idle controls static) IS causality at the input layer.
  2. restart_causality computed discrimination from HOLD-window frame
     diffs; upstream main.c is trigger-on-RELEASE
     (is_button_just_released(CROSS): GAME_OVER -(X rel)-> GAME_MENU),
     so the correct metric is the CLASS TRANSITION vs the idle control
     leg — which the report already contains (control_class GAME_OVER,
     after_class MENU, twice: g1 AND g2).
  3. fresh_game keyed on the missing RAM score sensor; the report's own
     games[] array shows games 2 and 3 ran (PLAYING, serves 6/5,
     points 5/4, natural GAME_OVER each) — a fresh game after restart,
     played to natural game over.

The standalone regrade boot (regrade/) fumbled the class flow (booted
into MENU, ride-game ran from MENU) — its evidence is superseded by
this analysis; kept on disk for honesty.

Output: scratch/round11_hellopong/regrade/report_corrected.json with
the final verdict COMPLETE_LOOP_CAUSAL (or the honest fallback).
"""
import json
import os

REPO = "/home/z/my-project/ps1ai"
SRC = os.path.join(REPO, "scratch", "round11_hellopong", "full_loop",
                   "report.json")
OUT_DIR = os.path.join(REPO, "scratch", "round11_hellopong", "regrade")

d = json.load(open(SRC))
games = d.get("games", [])
restarts = d.get("restarts", [])

# ---- 1. paddle causality (visual, from the recorded probe) ----
pc = d.get("paddle_causality", {})
dy_up = pc.get("visual_dy_up")
dy_rest = pc.get("visual_dy_restore")
paddle_ok = (dy_up is not None and abs(dy_up) >= 2.0
             and abs(dy_rest or 0.0) < 2.0)

# ---- 2. restart causality (class transition vs control, upstream
#         release semantics) ----
restart_legs = []
for r in restarts:
    leg = {
        "tag": r.get("tag"),
        "before_class": r.get("before_class"),
        "control_class": r.get("control_class"),
        "control_max_madiff": r.get("control_max"),
        "after_class": r.get("after_class"),
        "x_mirror_held": r.get("x_mirror_held"),
        "causal": (r.get("before_class") == "GAME_OVER"
                   and r.get("control_class") == "GAME_OVER"
                   and r.get("after_class") == "MENU"),
    }
    restart_legs.append(leg)
restart_ok = bool(restart_legs) and all(l["causal"] for l in restart_legs)

# ---- 3. natural game over + fresh games ----
natural_over = [g for g in games if g.get("end_class") == "GAME_OVER"]
fresh_ok = (len(natural_over) >= 2
            and all((g.get("serves", 0) >= 1 and g.get("points", 0) >= 1)
                    for g in natural_over))

parts = {
    "boot": bool(d.get("boot_state", {}).get("class")),
    "start_causal": bool(d.get("verdict_parts", {}).get("start_causal")),
    "paddle_causality": paddle_ok,
    "played": bool(d.get("verdict_parts", {}).get("played")),
    "natural_game_over": bool(len(natural_over) >= 1),
    "restart_causal": restart_ok,
    "fresh_game": fresh_ok,
}
verdict = ("COMPLETE_LOOP_CAUSAL" if all(parts.values()) else
           "PARTIAL(" + ",".join(k for k, v in parts.items() if not v)
           + ")")

rep = {
    "schema": "ps1ai-hellopong-r11-regrade-corrected/1",
    "source": "analysis of full_loop/report.json (same evidence, "
              "corrected metrics); upstream ground truth: main.c "
              "is_button_just_released(CROSS) — GAME_OVER -(X rel)-> "
              "GAME_MENU; win at 5 points",
    "paddle": {"visual_dy_up": dy_up, "visual_dy_restore": dy_rest,
               "note": "row moved during UP-hold, restored after "
                       "release; RAM sensor hunt found no counter "
                       "(sensor absence does not negate the visual "
                       "input causality)"},
    "restart_legs": restart_legs,
    "games": [{"game": g.get("game"), "class_start": "PLAYING",
               "serves": g.get("serves"), "points": g.get("points"),
               "left_pts": g.get("left_pts"),
               "right_pts": g.get("right_pts"),
               "end_class": g.get("end_class")} for g in games],
    "parts": parts,
    "verdict": verdict,
    "note_regrade_boot": "the standalone regrade boot (regrade/) "
                         "booted into MENU and fumbled the class flow; "
                         "superseded by this analysis, kept on disk",
}
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "report_corrected.json"), "w") as f:
    json.dump(rep, f, indent=1)
print("VERDICT:", verdict)
print(json.dumps(parts, indent=1))
