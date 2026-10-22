#!/usr/bin/env python3
"""gif_run_capture.py — recorded real-play run of MSX Mission 1 with
the PROVEN Issue-5/#7 v1 controller loop + full frame capture for
GIF evidence.

Legitimacy (mirrors issue5_controller.py exactly):
  * No cheats, no RAM writes, no HP/lives freezes (hp_pair words
    0xCA2F6/0xCA2FE are READ-ONLY observations here, OBSERVED grade).
  * Continues are legal in-game options and are counted + disclosed.
  * Savestate used only as an out-of-gameplay recovery (disclosed),
    never to rewind into the claimed run.
  * Policy = RoutePolicy v1 (RIGHT + fire bursts + hop cadence +
    grenades on a period), the exact loop that reached the train yard
    live at c650 in the Issue-7 wagon runs.

Capture: every Nth global frame (default 10 -> 6 captured frames per
game second -> GIF playback at 6 fps = real-time speed).  Every
captured frame index is the global emulator frame number, so frames
map 1:1 onto the JSONL trace.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace, replay_gain  # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from mission import ensure_mission                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_controller import (                           # noqa: E402
    ContinueLedger, STARTUP_GRACE, STALL_CHUNKS)


def _flags_active(fw):
    """Active play = low byte 0xFF (0x1FF seen live at the rope/
    checkpoint states — bit 8 is an unverified extra flag; the low
    byte is the OBSERVED 0xFF active / 0x1 game-over gate)."""
    return (fw & 0xFF) == 0xFF


def _flags_dead(fw):
    return (fw & 0xFF) == 0x1


def savestate_recover(p, tel, trace, chunk, ledger, outdir_evid,
                      state_name="issue5_m1_start"):
    """Relaxed copy of issue5_controller.savestate_recover: accepts
    the 0x1FF active-play variant after the reload."""
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
    g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
    after = tel.snapshot(buttons=[], frame=p.core.frames_run)
    ok = bool(g.get("in_mission")) and _flags_active(after["flags_word"])
    if ok:
        ledger.on_continue_restart()
        trace.write({"type": "mission_restart", "chunk": chunk,
                     "count": ledger.continues,
                     "no_progress_streak": ledger.no_progress_streak,
                     "method": "savestate_reload", "disclosed": True})
    return ok

# HP-pair observation words (READ-ONLY; from post_issue5 causal-
# reduction batch: baseline damaged/died, treatment eliminated both).
HP_PAIR = (0xCA2F6, 0xCA2FE)


def _log(*a):
    print("[gifrun]", *a, file=sys.stderr, flush=True)


def snap_frame(p, fdir, every):
    """Capture one frame if the global counter hits the stride."""
    g = p.core.frames_run
    if every and g % every == 0:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(
                os.path.join(fdir, f"f{g:07d}.jpg"), "JPEG", quality=85)
            return 1
    return 0


def run_frames_captured(p, frames, btns, fdir, every, cap):
    for _ in range(frames):
        p.core.run(1, btns if btns else set())
        cap["count"] += snap_frame(p, fdir, every)


def run_once(p, chunks, trace, label, outdir, fdir, every, evlog,
             resumed=False):
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    ledger = ContinueLedger()
    cap = {"count": 0}
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    trace.write({"type": "run_start", "label": label, "start": prev})
    stall_streak = 0
    ladder = 0
    deaths = 0
    stop = None
    camera_series = [prev["camera_fx"]]
    max_score = prev["score"]
    max_camx = prev["camera_x"]
    hp_hist = []
    t0 = time.time()
    f0 = p.core.frames_run
    if not resumed:
        try:
            p.save_state("issue5_m1_start")
            trace.write({"type": "checkpoint_saved",
                         "state": "issue5_m1_start"})
        except Exception as e:                 # noqa: BLE001
            trace.write({"type": "checkpoint_save_failed",
                         "err": repr(e)[:200]})
    c = -1
    for c in range(chunks):
        if stop:
            break
        segs = policy.decide(60, det)
        btn_union = set().union(*[s["btns"] or set() for s in segs])
        frame_start = p.core.frames_run
        for s in segs:
            run_frames_captured(p, s["frames"], s["btns"] or set(),
                                fdir, every, cap)
        cur = tel.snapshot(buttons=sorted(btn_union),
                           frame=p.core.frames_run)
        hp1 = int(p.mem.u16(HP_PAIR[0]))
        hp2 = int(p.mem.u16(HP_PAIR[1]))
        hp_hist.append((c, hp1, hp2))
        gain = tel.scroll_gain(prev, cur)
        camera_series.append(cur["camera_fx"])
        max_camx = max(max_camx, cur["camera_x"])
        evs = tel.events(prev, cur)
        max_score = max(max_score, cur["score"])
        for e in evs:
            trace.write({"type": "event", "chunk": c, **e})
            if e["type"] == "score_gain" and e["delta"] >= 300:
                evlog.write({"kind": "score_gain", "delta": e["delta"],
                             "gframe": p.core.frames_run, "chunk": c})
            elif e["type"] == "grenade_used":
                evlog.write({"kind": "grenade_used",
                             "gframe": p.core.frames_run, "chunk": c})
            elif e["type"] == "game_over_screen":
                evlog.write({"kind": "game_over_screen",
                             "gframe": p.core.frames_run, "chunk": c})
        trace.write({"type": "chunk", "chunk": c,
                     "frame_start": frame_start,
                     "frame_end": p.core.frames_run,
                     "telemetry": cur, "hp_pair": [hp1, hp2],
                     "scroll_gain": gain,
                     "policy_stats": dict(policy.stats)})
        if (c + 1) % 100 == 0:
            try:
                p.save_state("gif1_auto")
                trace.write({"type": "auto_state",
                             "name": "gif1_auto",
                             "frames_run": p.core.frames_run,
                             "chunk": c})
            except Exception as e:             # noqa: BLE001
                trace.write({"type": "auto_state_failed",
                             "err": repr(e)[:120]})
        # ---- out-of-gameplay / death handling (issue5 semantics) ----
        game_over = _flags_dead(cur["flags_word"])
        cam_regress = gain < -50
        death_evt = any(e["type"] == "death_candidate" for e in evs)
        if game_over or death_evt or cam_regress:
            deaths += 1
            trigger = ("game_over_screen" if game_over else
                       ("score_collapse" if death_evt else
                        "camera_regress"))
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": deaths, "trigger": trigger})
            evlog.write({"kind": "death", "trigger": trigger,
                         "gframe": p.core.frames_run, "chunk": c})
            if deaths > 12:
                stop = "STOP_DEAD_LOOP"
                break
            ledger.observe(prev["score"])
            if not game_over:
                recover_v2(p, log=_log)
                for _ in range(6):
                    cap["count"] += snap_frame(p, fdir, every)
                    p.core.run(1, set())
            g = ensure_mission(p, tries=4, log=_log,
                               want_hp_cands=False)
            after = tel.snapshot(buttons=[], frame=p.core.frames_run)
            if g.get("in_mission") and _flags_active(
                    after["flags_word"]):
                det.reset()
                prev = after
                continue
            ok = savestate_recover(p, tel, trace, c, ledger, outdir)
            evlog.write({"kind": "restart",
                         "method": "savestate_reload" if ok else "failed",
                         "gframe": p.core.frames_run, "chunk": c})
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
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        # ---- progress ledger (verified score dimension) ----
        ledger.observe(cur["score"])
        # ---- stall ladder (pixel churn gate kept identical) ----
        # churn computed on captured-vs-now frames like issue5
        rgb_now = p.core.frame_rgb()
        churn_px = getattr(run_once, "_rgb_prev", None)
        if churn_px is not None and rgb_now is not None:
            churn_px = round(float(np_absdiff(churn_px, rgb_now)), 3)
        run_once._rgb_prev = rgb_now
        stalled = churn_px is not None and churn_px < 3.0 and gain <= 0
        in_grace = c < STARTUP_GRACE
        stall_streak = 0 if (not stalled or in_grace) else \
            stall_streak + 1
        if not stalled:
            ladder = 0
        if stall_streak >= STALL_CHUNKS:
            ladder += 1
            stall_streak = 0
            if ladder == 1:
                trace.write({"type": "stall_l1_jump", "chunk": c})
                evlog.write({"kind": "stall_l1_jump",
                             "gframe": p.core.frames_run, "chunk": c})
                run_frames_captured(p, 20, {"RIGHT"}, fdir, every, cap)
                run_frames_captured(p, 40, {"RIGHT", "B"}, fdir, every,
                                    cap)
            elif ladder == 2:
                trace.write({"type": "stall_l2_grenade", "chunk": c,
                             "grenades_before": cur["grenades"]})
                evlog.write({"kind": "stall_l2_grenade",
                             "gframe": p.core.frames_run, "chunk": c})
                if cur["grenades"] > 0:
                    run_frames_captured(p, 8, set(), fdir, every, cap)
                    run_frames_captured(p, 30, {"A"}, fdir, every, cap)
                run_frames_captured(p, 30, {"RIGHT", "Y"}, fdir, every,
                                    cap)
            elif ladder == 3:
                trace.write({"type": "stall_l3_unstick", "chunk": c})
                evlog.write({"kind": "stall_l3_unstick",
                             "gframe": p.core.frames_run, "chunk": c})
                run_frames_captured(p, 60, {"LEFT", "Y"}, fdir, every,
                                    cap)
                run_frames_captured(p, 120, {"RIGHT", "Y"}, fdir, every,
                                    cap)
            else:
                stop = (f"STOP_STALLED chunk={c} "
                        f"camera_x={cur['camera_x']}")
                trace.write({"type": "stop", "chunk": c,
                             "reason": stop, "telemetry": cur})
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        if c % 50 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir, f"progress_c{c:03d}.png"))
            speed = (p.core.frames_run - f0) / max(time.time() - t0, 1)
            _log(f"chunk {c}: score={cur['score']} camx={cur['camera_x']} "
                 f"hp=({hp1},{hp2}) fps={speed:.1f} caps={cap['count']}")
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
        "max_camera_x": max_camx,
        "final": prev,
        "scroll_gain_total": sum(g for g in gains if g > 0),
        "policy_stats": policy.stats,
        "frames_captured": cap["count"],
        "capture_every": every,
        "wall_sec": round(time.time() - t0, 1),
        "emu_fps": round((p.core.frames_run - f0) /
                         max(time.time() - t0, 1), 1),
        "hp_pair_last": list(hp_hist[-1]) if hp_hist else None,
    }
    trace.write({"type": "run_end", **report})
    return report


def np_absdiff(a, b):
    import numpy as np
    return float(np.abs(a.astype(np.int16) -
                        b.astype(np.int16)).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=800)
    ap.add_argument("--capture-every", type=int, default=10)
    ap.add_argument("--tag", default="gif1")
    ap.add_argument("--resume-state", default=None,
                    help="named savestate to continue from (after boot)")
    ap.add_argument("--initial-frame", type=int, default=0,
                    help="seed core.frames_run after resume (file-"
                         "name continuity across segmented runs)")
    ap.add_argument("--save-resume", default=None,
                    help="save a named resume savestate at run end")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_gif_{args.tag}")
    fdir = os.path.join(outdir, "frames")
    os.makedirs(fdir, exist_ok=True)
    evlog = JsonlTrace(os.path.join(outdir, "highlights.jsonl"))
    _log(f"outdir={outdir} chunks={args.chunks} every={args.capture_every} "
         f"resume={args.resume_state} initial_frame={args.initial_frame}")
    p, fwmode = boot()
    if args.resume_state:
        p.load_state(args.resume_state)
        p.core.frames_run = args.initial_frame
        tel0 = TelemetryAdapter(p)
        s0 = tel0.snapshot(buttons=[], frame=p.core.frames_run)
        _log(f"resumed: flags={s0['flags_word']:#x} score={s0['score']} "
             f"camx={s0['camera_x']}")
        for _ in range(30):
            p.core.run(1, set())
        p.core.frames_run = args.initial_frame
    out = {"schema": "ps1play-gifrun/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "tag": args.tag, "firmware_mode": fwmode, "runs": []}
    trace = JsonlTrace(os.path.join(outdir, f"trace_{args.tag}.jsonl"))
    try:
        rep = run_once(p, args.chunks, trace, f"{args.tag}", outdir, fdir,
                       args.capture_every, evlog,
                       resumed=bool(args.resume_state))
    except KeyboardInterrupt:
        _log("interrupted; writing partial report")
        rep = {"label": args.tag, "stop_reason": "INTERRUPTED"}
    finally:
        trace.close()
        evlog.close()
    out["runs"].append(rep)
    if args.save_resume:
        try:
            r = p.save_state(args.save_resume)
            rep["resume_state"] = {"name": args.save_resume,
                                   "frames": p.core.frames_run,
                                   "bytes": r.get("bytes")}
            _log(f"resume state saved: {args.save_resume} "
                 f"at frame {p.core.frames_run}")
        except Exception as e:                  # noqa: BLE001
            _log(f"save-resume FAILED: {e!r}")
    rpath = (os.path.join(outdir, "gif_run_report.json")
             if not args.resume_state else
             os.path.join(outdir,
                          f"gif_run_report_{args.tag}.json"))
    with open(rpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", rpath)
    _log(f"RESULT: {rep.get('stop_reason')} max_score={rep.get('max_score')} "
         f"max_camx={rep.get('max_camera_x')} deaths={rep.get('deaths')} "
         f"continues={rep.get('continues_used')} caps={rep.get('frames_captured')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
