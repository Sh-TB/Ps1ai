#!/usr/bin/env python3
"""issue5_controller.py — Priority Refinement §4+§5: controller-layer
fix driven by the recovered failure chain.

Failure chain established by evidence (Issues #2/#4 + Issue #5):
  Marco advances legally to the train/POW area, then attrition
  (enemy-dense section + no defensive behavior) burns lives; when the
  last life dies the game shows the CONTINUE screen ("1000 CONTINUE"
  visible in issue4_controller progress_c200.png).  The Issue-4 FSM
  had NO continue-screen concept: recover_v2's START taps silently
  accepted a continue (fresh lives, checkpoint restart, score reset)
  or missed it, and the run degraded into an unaccounted loop.

Fix at the controller layer (smallest reusable change, no game hack):
  1. CONTINUE accounting: after every death recovery, detect a
     continue-restart signature (per-life camera accumulator reset +
     score reset) and count it explicitly in the trace/report.
  2. Progress ledger: track per-life max camera_fx; if N continues
     pass without beating the previous life's max progress, STOP
     (honest attrition-loop stop instead of an infinite burn).
  3. Combat cadence: fire (Y) held while advancing — the train/POW
     section is enemy-dense; hop cadence reduced (issue-4 traces show
     79 jumps with no benefit).
  4. flags_word telemetry (0x0EE518) recorded for offline correlation
     with the ==-1 GAME OVER gate (static evidence; live meaning
     remains opaque).

Legitimacy: continues are legal in-game options and are DISCLOSED;
a clear reached with continues is never reported as a no-continue
clear.  Cheats remain disabled.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import (                           # noqa: E402
    TelemetryAdapter, JsonlTrace, replay_gain, is_clear_candidate)
from mission import ensure_mission                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from issue4_real_start import boot_to_demo, owns_pad      # noqa: E402
from issue4_controller import boot                        # noqa: E402

STALL_CHUNKS = 6
STARTUP_GRACE = 6
CONTINUE_NO_PROGRESS_LIMIT = 2   # continues w/o new max progress -> STOP
FIRE_HELD_ADVANCE = False        # A/B: fire-held traversal DIES at c045
                                 # deterministically (full1..full5); the
                                 # proven v1 cadence survives to c200 —
                                 # variable reverted, evidence recorded


class ContinueLedger:
    """Pure continue/progress accounting (unit-testable core of the
    controller fix).  Progress is measured on the VERIFIED max-score
    dimension (camera_fx saturates near 255 in real play and is not a
    distance meter — full-run trace finding).  A continue counts as
    progress-free when the global max score did not grow since the
    previous continue; too many in a row = attrition loop, stop."""

    def __init__(self, no_progress_limit=CONTINUE_NO_PROGRESS_LIMIT,
                 progress_epsilon=50):
        self.no_progress_limit = no_progress_limit
        self.progress_epsilon = progress_epsilon
        self.continues = 0
        self.max_score = 0
        self.score_at_last_continue = None
        self.no_progress_streak = 0

    def observe(self, score):
        self.max_score = max(self.max_score, score)

    def on_continue_restart(self):
        """Called when a continue-restart is confirmed."""
        self.continues += 1
        if self.score_at_last_continue is not None and \
                self.max_score <= self.score_at_last_continue \
                + self.progress_epsilon:
            self.no_progress_streak += 1
        else:
            self.no_progress_streak = 0
        self.score_at_last_continue = self.max_score
        return self.no_progress_streak > self.no_progress_limit

    def should_stop(self):
        return (self.no_progress_streak > self.no_progress_limit,
                f"STOP_ATTRITION_LOOP continues={self.continues} "
                f"max_score={self.max_score}")


def accept_continue(p, tel, trace, chunk, ledger, outdir_evid,
                    rounds=14):
    """Bounded GAME-OVER/continue accept.  The death sequence spans a
    passive GAME OVER screen (~2-3 s, ignores input) then the CONTINUE?
    countdown; full-run evidence (trace full1) shows resume happened
    only after long settles with Y/B in the mix, so each round settles
    then alternates START and FIRE.  Every accepted continue is counted
    + disclosed.  Returns True when play resumed (flags back to 0xFF)."""
    for i in range(rounds):
        p.core.run(130, set())          # settle through GAME OVER fade
        for btn in ({"START"}, {"Y"}):
            p.core.run(8, btn)
            p.core.run(100, set())
            cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
            if i % 2 == 0:              # diagnostic frame per pair
                rgb = p.core.frame_rgb()
                if rgb is not None:
                    Image.fromarray(rgb).save(os.path.join(
                        outdir_evid, f"accept_c{chunk:03d}_r{i:02d}_"
                        f"{sorted(btn)[0].lower()}.png"))
            if cur["flags_word"] == 0xFF:
                ledger.on_continue_restart()
                trace.write({"type": "continue_used", "chunk": chunk,
                             "count": ledger.continues,
                             "no_progress_streak":
                             ledger.no_progress_streak,
                             "accept_rounds": i + 1,
                             "accept_btn": sorted(btn)[0],
                             "disclosed": True})
                return True
    trace.write({"type": "continue_accept_failed", "chunk": chunk,
                 "rounds": rounds})
    return False


def savestate_recover(p, tel, trace, chunk, ledger, outdir_evid,
                      state_name="issue5_m1_start"):
    """Recover out-of-gameplay states by reloading the mission-start
    savestate (an in-process equivalent of the game's own menu
    restart).

    Live-diagnosed (diag4, accept_c045_r02_y.png): after GAME OVER the
    SLUS port sits on the MAIN MENU and blind taps cannot relaunch the
    mission.  A second in-process core boot SEGFAULTS (full4, twice),
    so the deterministic recovery is a savestate reload taken right
    after the boot gate.  Every restart is counted + disclosed; a
    clear reached after restarts is NEVER reported as a no-restart
    clear.  Returns True when active play (flags 0xFF) resumed."""
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(
            outdir_evid, f"prerestart_c{chunk:03d}.png"))
    try:
        p.load_state(state_name)
    except Exception as e:                     # noqa: BLE001
        trace.write({"type": "savestate_recover_failed", "chunk": chunk,
                     "err": repr(e)[:200]})
        return False
    # settle + re-gate after the load
    g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
    after = tel.snapshot(buttons=[], frame=p.core.frames_run)
    ok = bool(g.get("in_mission")) and after["flags_word"] == 0xFF
    if ok:
        ledger.on_continue_restart()
        trace.write({"type": "mission_restart", "chunk": chunk,
                     "count": ledger.continues,
                     "no_progress_streak": ledger.no_progress_streak,
                     "method": "savestate_reload", "disclosed": True})
    return ok


def _log(*a):
    print("[ctrl5]", *a, file=sys.stderr, flush=True)


def run_once(p, chunks, trace, label, outdir_evid):
    from ps1play.agent.route import RoutePolicy, StallDetector
    H = {"p": p}               # swappable session holder (soft reboot)
    tel = TelemetryAdapter(H["p"])
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    ledger = ContinueLedger()
    prev = tel.snapshot(buttons=[], frame=H["p"].core.frames_run)
    trace.write({"type": "run_start", "label": label, "start": prev})
    stall_streak = 0
    ladder = 0
    deaths = 0
    stop = None
    camera_series = [prev["camera_fx"]]
    max_score = prev["score"]
    frozen_chunks = 0
    rgb_prev = H["p"].core.frame_rgb()
    try:
        H["p"].save_state("issue5_m1_start")
        trace.write({"type": "checkpoint_saved",
                     "state": "issue5_m1_start"})
    except Exception as e:                     # noqa: BLE001
        trace.write({"type": "checkpoint_save_failed",
                     "err": repr(e)[:200]})
    c = -1
    for c in range(chunks):
        if stop:
            break
        segs = policy.decide(60, det)
        for s in segs:
            btns = set(s["btns"] or set())
            if FIRE_HELD_ADVANCE and "RIGHT" in btns:
                btns.add("Y")       # combat cadence: shoot while walking
            H["p"].core.run(s["frames"], btns if btns else None)
        cur = tel.snapshot(buttons=sorted(set().union(
            *[s["btns"] or set() for s in segs])),
            frame=H["p"].core.frames_run)
        gain = tel.scroll_gain(prev, cur)
        camera_series.append(cur["camera_fx"])
        rgb_now = H["p"].core.frame_rgb()
        churn_px = None
        if rgb_prev is not None and rgb_now is not None:
            churn_px = round(float(np.abs(
                rgb_prev.astype(np.int16) -
                rgb_now.astype(np.int16)).mean()), 3)
        rgb_prev = rgb_now
        evs = tel.events(prev, cur)
        max_score = max(max_score, cur["score"])
        for e in evs:
            trace.write({"type": "event", "chunk": c, **e})
        trace.write({"type": "chunk", "chunk": c, "telemetry": cur,
                     "scroll_gain": gain, "churn_px": churn_px,
                     "policy_stats": dict(policy.stats)})
        # ---- out-of-gameplay / death handling ----
        # flags 0xFF = active play, 0x1 = menus/GAME OVER (OBSERVED,
        # 4/4 + diag4 menu screenshot).  Cheap in-place recovery first
        # (regular death anim), then a deterministic soft reboot.
        game_over = cur["flags_word"] == 0x1
        cam_regress = gain < -50
        death_evt = any(e["type"] == "death_candidate" for e in evs)
        if game_over or death_evt or cam_regress:
            deaths += 1
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": deaths,
                         "trigger": "game_over_screen" if game_over else
                         ("score_collapse" if death_evt else
                          "camera_regress")})
            if deaths > 12:
                stop = "STOP_DEAD_LOOP"
                break
            ledger.observe(prev["score"])
            if not game_over:
                recover_v2(H["p"], log=_log)
            g = ensure_mission(H["p"], tries=4, log=_log,
                               want_hp_cands=False)
            after = tel.snapshot(buttons=[], frame=H["p"].core.frames_run)
            if g.get("in_mission") and after["flags_word"] == 0xFF:
                det.reset()
                prev = after
                rgb_prev = H["p"].core.frame_rgb()
                continue
            # still out of gameplay -> savestate mission restart
            ok = savestate_recover(H["p"], tel, trace, c, ledger,
                                   outdir_evid)
            if not ok:
                stop = "STOP_RESTART_FAILED"
                trace.write({"type": "stop", "chunk": c,
                             "reason": stop, "telemetry": cur})
                break
            over, reason = ledger.should_stop()
            if over:
                stop = reason
                trace.write({"type": "stop", "chunk": c,
                             "reason": stop, "telemetry": cur})
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=H["p"].core.frames_run)
            rgb_prev = H["p"].core.frame_rgb()
            continue
        # ---- progress ledger (verified score dimension) ----
        ledger.observe(cur["score"])
        # ---- stall ladder (pixel churn, as issue-4) ----
        in_grace = c < STARTUP_GRACE
        stalled = churn_px is not None and churn_px < 3.0 and gain <= 0
        stall_streak = 0 if (not stalled or in_grace) else stall_streak + 1
        if not stalled:
            ladder = 0
        if stall_streak >= STALL_CHUNKS:
            ladder += 1
            stall_streak = 0
            if ladder == 1:
                trace.write({"type": "stall_l1_jump", "chunk": c})
                p.core.run(20, {"RIGHT"})
                p.core.run(40, {"RIGHT", "B"})
            elif ladder == 2:
                trace.write({"type": "stall_l2_grenade", "chunk": c,
                             "grenades_before": cur["grenades"]})
                if cur["grenades"] > 0:
                    p.core.run(8, set())
                    p.core.run(30, {"A"})
                p.core.run(30, {"RIGHT", "Y"})
            elif ladder == 3:
                trace.write({"type": "stall_l3_unstick", "chunk": c})
                p.core.run(60, {"LEFT", "Y"})
                p.core.run(120, {"RIGHT", "Y"})
            else:
                stop = f"STOP_STALLED chunk={c} camera_x={cur['camera_x']}"
                trace.write({"type": "stop", "chunk": c,
                             "reason": stop, "telemetry": cur})
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        # ---- clear candidate (honest, UNVERIFIED shape only) ----
        frozen_chunks = (frozen_chunks + 1) if gain <= 0 else 0
        best_gain = max((e["delta"] for e in evs
                         if e["type"] == "score_gain"), default=0)
        if is_clear_candidate(frozen_chunks, best_gain):
            trace.write({"type": "clear_candidate_unverified",
                         "chunk": c, "telemetry": cur})
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir_evid, f"clearcand_c{c:03d}.png"))
        if c % 50 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir_evid, f"progress_c{c:03d}.png"))
        prev = cur
    gains = replay_gain(camera_series)
    report = {
        "label": label,
        "chunks_run": c + 1 if not stop and c >= 0 else c,
        "stop_reason": stop or "BUDGET_END",
        "deaths": deaths,
        "continues_used": ledger.continues,
        "continues_disclosed": True,
        "max_score": max_score,
        "final": prev,
        "scroll_gain_total": sum(g for g in gains if g > 0),
        "policy_stats": policy.stats,
    }
    trace.write({"type": "run_end", **report})
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=200)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--tag", default="v2")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_controller_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    out = {"schema": "ps1play-controller/2",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "tag": args.tag, "runs": []}
    for k in range(args.runs):
        _log(f"=== run {k + 1}/{args.runs} (fresh boot) ===")
        p, fwmode = boot()
        out.setdefault("firmware_mode", fwmode)
        trace = JsonlTrace(os.path.join(outdir, f"trace_run{k + 1}.jsonl"))
        try:
            rep = run_once(p, args.chunks, trace, f"run{k + 1}", outdir)
        finally:
            trace.close()
        out["runs"].append(rep)
        _log(f"run{k + 1}: {rep['stop_reason']} "
             f"max_score={rep['max_score']} "
             f"continues={rep['continues_used']}")
        del p
    outpath = os.path.join(outdir, "controller_report.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", outpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
