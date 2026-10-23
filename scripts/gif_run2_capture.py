#!/usr/bin/env python3
"""gif_run2_capture.py — instrumented real-play capture comparing the
NEW entity-aware CombatPolicy vs the OLD forward-only RoutePolicy
(Issue #5 focused follow-up session 3; answers the user's gameplay
feedback with live data).

Policies:
  --policy combat  CombatPolicy: nearest threat front/rear is faced and
                   engaged; derived end-clamp -> walk back + rear-clear
                   + bounded up-left fire (chopper/rain zone).
  --policy route   RoutePolicy v1 (the loop behind the recorded GIFs):
                   RIGHT + fire bursts, hop cadence, grenades. The
                   instrumented BASELINE used to CONFIRM/REFUTE the
                   user-reported defects (rear-death, pass-through).

Instrumentation (per 60f chunk, READ-ONLY):
  * player px (u32@0xCA2E0 >>16), hp pair, score, grenades
  * live entity scan (ps1play-combat-scan/1: slot,x_px,dx_px,hp)
  * policy mode + button union
  * DEATH records dump the enemy snapshot AT death (rear-geometry
    ground truth) + the px where it happened
  * score gains are correlated with the active mode (rear/front kill
    proxy; score/RAM delta alone is NOT a kill proof, but mode+
    geometry+delta together are strong evidence)

Legitimacy (identical to gif_run_capture.py):
  no cheats, no RAM writes, no freezes; continues counted+disclosed;
  savestate only as out-of-gameplay recovery / segmented-run resume.

Frames: every Nth global frame captured (default 10 -> 6 fps GIF).
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
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.agent.combat import (                        # noqa: E402
    CombatPolicy, scan_entities, PLAYER_X, PLAYER_HP)
from mission import ensure_mission                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_controller import (                           # noqa: E402
    ContinueLedger, STARTUP_GRACE, STALL_CHUNKS)

FLAGS = 0x0EE518
HP_PAIR = (0xCA2F6, 0xCA2FE)


def _flags_active(fw):
    return (fw & 0xFF) == 0xFF


def _flags_dead(fw):
    return (fw & 0xFF) == 0x1


def _log(*a):
    print("[gif2]", *a, file=sys.stderr, flush=True)


def savestate_recover(p, tel, trace, chunk, ledger, outdir,
                      state_name="issue5_m1_start"):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(
            outdir, f"prerestart_c{chunk:03d}.png"))
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
                     "method": "savestate_reload", "disclosed": True})
    return ok


def snap_frame(p, fdir, every):
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
             policy_name, resumed=False):
    tel = TelemetryAdapter(p)
    if policy_name == "combat":
        policy = CombatPolicy()
    else:
        policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    run_once._last_px = None
    run_once._last_intent = False
    det = StallDetector()
    ledger = ContinueLedger()
    cap = {"count": 0}
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    trace.write({"type": "run_start", "label": label,
                 "policy": policy_name, "start": prev})
    stall_streak = 0
    ladder = 0
    deaths = 0
    stop = None
    camera_series = [prev["camera_fx"]]
    max_score = prev["score"]
    max_px = int(p.mem.u32(PLAYER_X)) / 65536.0
    hp_hist = []
    t0 = time.time()
    f0 = p.core.frames_run
    if not resumed:
        try:
            p.save_state("gif2_start")
            trace.write({"type": "checkpoint_saved", "state": "gif2_start"})
        except Exception as e:                 # noqa: BLE001
            trace.write({"type": "checkpoint_save_failed",
                         "err": repr(e)[:200]})
    c = -1
    for c in range(chunks):
        if stop:
            break
        chunk = 60
        # ---- READ-ONLY observation before deciding -----------------
        mem = p.mem
        px = int(mem.u32(PLAYER_X)) / 65536.0
        hp1 = int(mem.u16(HP_PAIR[0]))
        hp2 = int(mem.u16(HP_PAIR[1]))
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        enemies = scan_entities(mem, px=px)
        # ---- policy decision ----------------------------------------
        if policy_name == "combat":
            last_px = run_once._last_px
            advanced = (px - last_px) if last_px is not None else 0.0
            intent = bool(run_once._last_intent)
            policy.observe(px, advanced, intent)
            segs = policy.decide(chunk, px, enemies,
                                 grenades=cur["grenades"], hp=hp1)
            run_once._last_px = px
            run_once._last_intent = any(
                "RIGHT" in s["btns"] for s in segs)
            mode = policy.mode
            pstats = dict(policy.stats)
        else:
            segs = policy.decide(chunk, det)
            mode = "route"
            pstats = dict(policy.stats)
        btn_union = set().union(*[s["btns"] or set() for s in segs])
        frame_start = p.core.frames_run
        for s in segs:
            run_frames_captured(p, s["frames"], s["btns"] or set(),
                                fdir, every, cap)
        cur = tel.snapshot(buttons=sorted(btn_union),
                           frame=p.core.frames_run)
        hp1b = int(p.mem.u16(HP_PAIR[0]))
        hp2b = int(p.mem.u16(HP_PAIR[1]))
        hp_hist.append((c, hp1b, hp2b))
        px_b = int(p.mem.u32(PLAYER_X)) / 65536.0
        gain = tel.scroll_gain(prev, cur)
        camera_series.append(cur["camera_fx"])
        max_px = max(max_px, px_b)
        evs = tel.events(prev, cur)
        max_score = max(max_score, cur["score"])
        for e in evs:
            trace.write({"type": "event", "chunk": c, "mode": mode, **e})
            if e["type"] == "score_gain" and e["delta"] >= 100:
                evlog.write({"kind": "score_gain", "delta": e["delta"],
                             "mode": mode,
                             "gframe": p.core.frames_run, "chunk": c})
            elif e["type"] == "grenade_used":
                evlog.write({"kind": "grenade_used", "mode": mode,
                             "gframe": p.core.frames_run, "chunk": c})
            elif e["type"] == "game_over_screen":
                evlog.write({"kind": "game_over_screen",
                             "gframe": p.core.frames_run, "chunk": c})
        trace.write({"type": "chunk", "chunk": c,
                     "frame_start": frame_start,
                     "frame_end": p.core.frames_run,
                     "mode": mode, "policy_stats": pstats,
                     "px": round(px, 1), "px_end": round(px_b, 1),
                     "hp_pair": [hp1b, hp2b],
                     "telemetry": cur, "scroll_gain": gain,
                     "enemies": enemies,
                     "buttons": sorted(btn_union)})
        if (c + 1) % 100 == 0:
            try:
                p.save_state("gif2_auto")
                trace.write({"type": "auto_state", "name": "gif2_auto",
                             "frames_run": p.core.frames_run,
                             "chunk": c})
            except Exception as e:             # noqa: BLE001
                trace.write({"type": "auto_state_failed",
                             "err": repr(e)[:120]})
        # ---- out-of-gameplay / death handling ------------------------
        game_over = _flags_dead(cur["flags_word"])
        cam_regress = gain < -50
        death_evt = any(e["type"] == "death_candidate" for e in evs)
        if game_over or death_evt or cam_regress or hp1b == 0:
            deaths += 1
            # DEATH GEOMETRY: enemies at the moment of death
            mem2 = p.mem
            px2 = int(mem2.u32(PLAYER_X)) / 65536.0
            geom = scan_entities(mem2, px=px2)
            rear = [e for e in geom
                    if e["dx_px"] < -20
                    and e.get("kind", "enemy") == "enemy"]
            trigger = ("game_over_screen" if game_over else
                       ("hp_zero" if hp1b == 0 else
                        ("score_collapse" if death_evt else
                         "camera_regress")))
            trace.write({"type": "death_geometry", "chunk": c,
                         "trigger": trigger, "px": round(px2, 1),
                         "enemies": geom,
                         "rear_enemies": rear,
                         "hp_pair": [hp1b, hp2b]})
            evlog.write({"kind": "death", "trigger": trigger,
                         "rear_count": len(rear),
                         "px": round(px2, 1),
                         "gframe": p.core.frames_run, "chunk": c})
            if deaths > 12:
                stop = "STOP_DEAD_LOOP"
                break
            ledger.observe(prev["score"])
            if not game_over and hp1b != 0:
                recover_v2(p, log=_log)
                for _ in range(6):
                    cap["count"] += snap_frame(p, fdir, every)
                    p.core.run(1, set())
            g = ensure_mission(p, tries=4, log=_log,
                               want_hp_cands=False)
            after = tel.snapshot(buttons=[], frame=p.core.frames_run)
            if g.get("in_mission") and _flags_active(after["flags_word"]):
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
        # ---- progress ledger + stall ladder --------------------------
        ledger.observe(cur["score"])
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
                run_frames_captured(p, 20, {"RIGHT"}, fdir, every, cap)
                run_frames_captured(p, 40, {"RIGHT", "B"}, fdir, every,
                                    cap)
            elif ladder == 2:
                trace.write({"type": "stall_l2_grenade", "chunk": c,
                             "grenades_before": cur["grenades"]})
                if cur["grenades"] > 0:
                    run_frames_captured(p, 8, set(), fdir, every, cap)
                    run_frames_captured(p, 30, {"A"}, fdir, every, cap)
                run_frames_captured(p, 30, {"RIGHT", "Y"}, fdir, every,
                                    cap)
            elif ladder == 3:
                trace.write({"type": "stall_l3_unstick", "chunk": c})
                run_frames_captured(p, 60, {"LEFT", "Y"}, fdir, every,
                                    cap)
                run_frames_captured(p, 120, {"RIGHT", "Y"}, fdir, every,
                                    cap)
            else:
                stop = (f"STOP_STALLED chunk={c} px={px_b:.0f}")
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
            _log(f"chunk {c}: mode={mode} px={px_b:.0f} "
                 f"score={cur['score']} hp=({hp1b},{hp2b}) "
                 f"enemies={len(enemies)} fps={speed:.1f}")
        prev = cur
    report = {
        "label": label,
        "policy": policy_name,
        "chunks_run": c + 1 if not stop and c >= 0 else max(c, 0),
        "stop_reason": stop or "BUDGET_END",
        "deaths": deaths,
        "continues_used": ledger.continues,
        "continues_disclosed": True,
        "max_score": max_score,
        "max_px": round(max_px, 1),
        "final_hp_pair": list(hp_hist[-1]) if hp_hist else None,
        "policy_stats": dict(policy.stats),
        "frames_captured": cap["count"],
        "capture_every": every,
        "wall_sec": round(time.time() - t0, 1),
        "emu_fps": round((p.core.frames_run - f0) /
                         max(time.time() - t0, 1), 1),
    }
    trace.write({"type": "run_end", **report})
    return report


def np_absdiff(a, b):
    import numpy as np
    return float(np.abs(a.astype(np.int16) -
                        b.astype(np.int16)).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=200)
    ap.add_argument("--capture-every", type=int, default=10)
    ap.add_argument("--policy", choices=["combat", "route"],
                    default="combat")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--resume-state", default=None)
    ap.add_argument("--initial-frame", type=int, default=0)
    ap.add_argument("--save-resume", default=None)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    tag = args.tag or f"{args.policy}_1"
    outdir = os.path.join(args.evidence_dir, f"gif2_{tag}")
    fdir = os.path.join(outdir, "frames")
    os.makedirs(fdir, exist_ok=True)
    evlog = JsonlTrace(os.path.join(outdir, "highlights.jsonl"))
    _log(f"outdir={outdir} policy={args.policy} chunks={args.chunks} "
         f"resume={args.resume_state}")
    p, fwmode = boot()
    if args.resume_state:
        p.load_state(args.resume_state)
        p.core.frames_run = args.initial_frame
        tel0 = TelemetryAdapter(p)
        s0 = tel0.snapshot(buttons=[], frame=p.core.frames_run)
        _log(f"resumed: flags={s0['flags_word']:#x} "
             f"score={s0['score']}")
        for _ in range(30):
            p.core.run(1, set())
        p.core.frames_run = args.initial_frame
    out = {"schema": "ps1play-gifrun2/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "tag": tag, "policy": args.policy,
           "firmware_mode": fwmode, "runs": []}
    trace = JsonlTrace(os.path.join(outdir, f"trace_{tag}.jsonl"))
    try:
        rep = run_once(p, args.chunks, trace, tag, outdir, fdir,
                       args.capture_every, evlog, args.policy,
                       resumed=bool(args.resume_state))
    except KeyboardInterrupt:
        _log("interrupted; writing partial report")
        rep = {"label": tag, "stop_reason": "INTERRUPTED"}
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
    rpath = os.path.join(outdir, f"gif2_report_{tag}.json")
    with open(rpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", rpath)
    _log(f"RESULT: {rep.get('stop_reason')} max_score="
         f"{rep.get('max_score')} max_px={rep.get('max_px')} "
         f"deaths={rep.get('deaths')} "
         f"continues={rep.get('continues_used')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
