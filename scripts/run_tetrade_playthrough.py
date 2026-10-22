#!/usr/bin/env python3
"""THE PLAYTHROUGH RUNNER — first complete game through the plugin contract.

Issue #8 T6/T7: boot -> Marathon via plugin boot_script (real pad input,
no cheats, no writes) -> closed-loop play with the TetradePlayPlugin ->
verified line clear(s) -> deliberate wrap-up -> NATURAL game over ->
refuse CONTINUE with CIRCLE -> back at the title = one complete game loop.

Everything is journaled (JSONL): every chunk's semantic state, every
decision, every milestone, with frame numbers. Evidence PNGs at
milestones. Hard budgets with honest partial reports. LOCAL-ONLY
artifacts; only textual summaries enter git.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play  # noqa: E402
from ps1play.plugins.tetrade_play import TetradePlayPlugin  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_tetrade_run"
OV = {b"beetle_psx_override_bios": b"openbios"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-lines", type=int, default=6)
    ap.add_argument("--target-pieces", type=int, default=30)
    ap.add_argument("--max-frames", type=int, default=360000)
    ap.add_argument("--chunk", type=int, default=60)
    args = ap.parse_args()

    run_id = time.strftime("tplay_%Y%m%d_%H%M%S")
    out = f"/home/z/my-project/emu/games_homebrew/evidence/{run_id}"
    os.makedirs(out, exist_ok=True)
    trace = open(f"{out}/trace.jsonl", "w")

    def J(ev):
        trace.write(json.dumps(ev, default=str) + "\n")

    def shot(p, name):
        arr = np.asarray(p.core.frame_rgb())
        Image.fromarray(arr).save(f"{out}/{name}.png")
        return arr

    summary = {"run_id": run_id, "started": time.strftime("%H:%M:%S"),
               "targets": {"lines": args.target_lines,
                           "pieces": args.target_pieces},
               "budget_frames": args.max_frames}
    t0 = time.time()

    p = PS1Play(CUE, workspace=WS, var_overrides=OV)
    info = p.boot()
    # v2 plugin selection — explicit (registry keeps the v1 slice first)
    p.plugin = TetradePlayPlugin(p.profile)
    summary["boot"] = info
    J({"ev": "boot", "info": info})

    # ---- boot_script: real inputs only ----------------------------------
    r = p.run_steps(p.plugin.boot_script())
    J({"ev": "boot_script_done", **r})
    feat = p.plugin.features(p.mem, {"changed_bytes": 0})
    if feat.get("level") != 0 or feat.get("score") != 0:
        summary["abort"] = "marathon_entry_not_confirmed"
        summary["feat_at_entry"] = {k: feat.get(k) for k in
                                    ("level", "score", "type", "x", "y")}
        json.dump(summary, open(f"{out}/summary.json", "w"), indent=1)
        print(json.dumps(summary, indent=1))
        return 1
    shot(p, "00_marathon_entry")
    p.save_state("run_entry")
    summary["marathon_entry"] = {"fc": p.core.frames_run,
                                 "type": feat.get("type")}
    J({"ev": "marathon_entry", "fc": p.core.frames_run})

    # ---- main loop -------------------------------------------------------
    milestones = []
    piece0_score = 0
    fc_start = p.core.frames_run
    over_seen_fc = None
    done = False
    reason = None
    last_clear_ev = None
    score_traj = []

    while p.core.frames_run - fc_start < args.max_frames:
        fc0 = p.core.frames_run
        feat = p.plugin.features(p.mem, {"changed_bytes": 0})
        ctx = {"chunk": args.chunk, "fc": fc0, "feat": feat,
               "target_pieces": args.target_pieces,
               "target_lines": args.target_lines}
        segs = p.plugin.policy(ctx)
        # hard cap: segments must not exceed the chunk (defensive)
        # + pre-drop guard: never hard-drop in the type==-1 gap between
        # pieces (stale-shape hard drops corrupt score/board — observed)
        budget = args.chunk
        tf = (p.plugin.f or {}).get("tet_type")
        for s in segs:
            k = min(s["frames"], budget)
            budget -= k
            if k <= 0:
                break
            btns = s.get("btns") or set()
            if "UP" in btns and tf is not None:
                t_now = p.mem.u32(tf)
                if not (1 <= t_now <= 7):
                    J({"ev": "drop_skipped_gap", "fc": fc0, "type": t_now})
                    p.core.run(k, set())
                    continue
            p.core.run(k, btns)
        J({"ev": "chunk", "fc": fc0, "mode": p.plugin.mode,
           "type": feat.get("type"), "x": feat.get("x"),
           "y": feat.get("y"), "score": feat.get("score"),
           "lines": feat.get("lines_total"), "level": feat.get("level"),
           "pieces": p.plugin.pieces, "segs": len(segs),
           "events": p.plugin.events})
        if p.plugin.events:
            for e in p.plugin.events:
                if e["ev"] == "line_clear" and last_clear_ev is None:
                    last_clear_ev = e
                    milestones.append(("first_line_clear", fc0))
                    shot(p, f"milestone_first_clear_fc{fc0}")
            p.plugin.events = []

        if feat.get("lines_total") is not None:
            score_traj.append((p.core.frames_run, feat["score"],
                               feat["lines_total"]))

        # piece lock milestone: every 10 placed pieces
        if p.plugin.pieces and p.plugin.pieces % 10 == 0 and \
                p.plugin.pieces not in milestones:
            milestones.append(p.plugin.pieces)
            shot(p, f"milestone_pieces_{p.plugin.pieces:03d}")

        # game over transition
        if feat.get("game_over") and over_seen_fc is None:
            over_seen_fc = p.core.frames_run
            milestones.append("game_over")
            J({"ev": "game_over", "fc": over_seen_fc,
               "final_score": feat.get("score"),
               "final_lines": feat.get("lines_total")})
            shot(p, "milestone_gameover_anim")

        if p.plugin.mode == "done":
            done = True
            reason = "complete_loop"
            break

    # ---- post-game: capture the title (loop closed) ----------------------
    p.core.run(180, set())
    shot(p, "99_title_after_run")
    feat_end = p.plugin.features(p.mem, {"changed_bytes": 0})

    summary.update({
        "done": done, "reason": reason,
        "frames_used": p.core.frames_run - fc_start,
        "wall_s": round(time.time() - t0, 1),
        "pieces_placed": p.plugin.pieces,
        "lines_cleared_total": p.plugin.clears,
        "first_clear": last_clear_ev,
        "game_over_fc": over_seen_fc,
        "milestones": [str(m) for m in milestones],
        "final_feat": {k: feat_end.get(k) for k in
                       ("score", "lines_total", "level", "game_over")},
        "score_trajectory_tail": score_traj[-12:],
    })
    json.dump(summary, open(f"{out}/summary.json", "w"), indent=1)
    trace.close()
    print(json.dumps(summary, indent=1))
    return 0 if done else 2


if __name__ == "__main__":
    sys.exit(main())
