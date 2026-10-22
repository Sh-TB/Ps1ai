#!/usr/bin/env python3
"""gif_story_run.py — three-phase RECORDED MSX Mission-1 run that
produces the GIF evidence the user asked for:

  A  LEGIT traversal from mission start (no assists at all): the
     proven v1 policy loop (RoutePolicy + stall ladder + disclosed
     continues) with stride frame capture.
  B  DISCLOSED hp-freeze traversal (EXPLORATION, CheatSession tagged)
     purely to REACH the mosque lob window (player tile 22-28) without
     burning the session on attrition; every continue still disclosed.
  C  THE SHOWPIECE: from the lob window — grenade lobs LEFT (real
     grenades) until the +800 mosque-kill pattern, 150f rain-quiet
     check, then UNFREEZE and walk RIGHT (legit survival, hop on
     stall, rescue taps) past the truck toward the section clamp.

All phases write into the same frames dir with one continuous global
frame counter (seeding via --initial-frame), so the trace, the
highlights log and the GIFs line up 1:1.

Assists are NEVER counted as a no-assist achievement: phase B/C freeze
windows are recorded in the trace and the report as EXPLORATION.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np                                      # noqa: E402
from PIL import Image                                   # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                           # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from mission import ensure_mission, idle_churn          # noqa: E402
from run_mission1_legit import recover_v2               # noqa: E402
from issue4_controller import boot                      # noqa: E402
from issue5_controller import ContinueLedger            # noqa: E402
import msx_gate_probe as gp                             # noqa: E402
from gif_run_capture import (run_once as legit_run_once,    # noqa: E402
                             _flags_active, _flags_dead)

TABLE, STRIDE = gp.TABLE, gp.STRIDE


def _log(*a):
    print("[story]", *a, file=sys.stderr, flush=True)


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def snap(p, fdir, every, cap):
    g = p.core.frames_run
    if every and g % every == 0:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(
                os.path.join(fdir, f"f{g:07d}.jpg"), "JPEG", quality=85)
            cap["count"] += 1


def step_gs(p, session, frames, btns, fdir, every, cap, m):
    """Frame-stepped run with GS tick + capture (assisted phases)."""
    p.core.set_buttons(btns if btns else set())
    for _ in range(frames):
        p.core.run_frame()
        if session is not None:
            session.gs.tick()
        snap(p, fdir, every, cap)


def captured_report(tag, phase, p, cap, extra, t0, f0):
    return {"phase": phase, "tag": tag,
            "stop_frame": p.core.frames_run,
            "frames_captured": cap["count"],
            "wall_s": round(time.time() - t0, 1),
            "emu_fps": round((p.core.frames_run - f0) /
                             max(time.time() - t0, 1), 1),
            **extra}


# ------------------------------------------------------------------
# Phase B: assisted reach to the lob window
# ------------------------------------------------------------------
def _state_sane(p):
    """Active play AND a live player entity (the camera word reads
    0xFFDA/0xFFFF sentinels when 1UP=0 corpse states are loaded)."""
    tel = TelemetryAdapter(p)
    s = tel.snapshot(buttons=[], frame=p.core.frames_run)
    cx = int(s["camera_fx"]) >> 16
    return _flags_active(s["flags_word"]) and 0 <= cx <= 2400, s


def _player_responds(p):
    """The Issue-4 ownership probe, adapted: hold RIGHT 30f; a live
    player moves the camera. Corpse states (1UP=0) do not respond."""
    cx0 = camx_px(p.mem)
    p.core.run(30, {"RIGHT"})
    cx1 = camx_px(p.mem)
    p.core.run(10, set())
    return cx1 > cx0, cx0, cx1


def _ensure_live_then_freeze(p, tag):
    """Gate to a LIVE, INPUT-RESPONSIVE play state (the segA resume may
    sit on a 1UP=0 corpse that still passes flag/camera checks),
    accepting the game's own continue when needed, then freeze."""
    for attempt in range(4):
        ok, s = _state_sane(p)
        resp, cx0, cx1 = _player_responds(p) if ok else (False, -1, -1)
        if ok and resp:
            return gp.freeze_now(p, tag)
        _log(f"state not playable (attempt {attempt}): flags="
             f"{s['flags_word']:#x} camx={int(s['camera_fx']) >> 16} "
             f"resp={cx0}->{cx1} -> continue flow")
        recover_v2(p, log=_log)
        ensure_mission(p, tries=4, log=_log, want_hp_cands=False)
        p.core.run(180, set())
    _log("WARNING: state still not playable after 4 continue flows")
    return gp.freeze_now(p, tag)


def refill_grenades(p, fdir, every, cap, m, need=4, max_tries=3):
    """Grenade resupply via the game's own loop: unfreeze, walk right
    into the hazard zone to die, accept the checkpoint restart
    (grenades refill to 10), re-freeze, walk back to the window.
    Fully disclosed EXPLORATION choreography."""
    for attempt in range(max_tries):
        tel = TelemetryAdapter(p)
        if int(m.u8(0x0EDCF4)) >= need:
            return True
        _log(f"refill attempt {attempt}: grenades="
             f"{int(m.u8(0x0EDCF4))} -> suicide walk")
        step_gs(p, None, 400, {"RIGHT", "Y"}, fdir, every, cap, m)
        for _ in range(600):
            step_gs(p, None, 1, set(), fdir, every, cap, m)
            s = tel.snapshot(buttons=[], frame=p.core.frames_run)
            if _flags_dead(s["flags_word"]):
                break
        p.core.run(10, {"START"})
        for _ in range(80):
            p.core.run_frame()
        ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
        p.core.run(120, set())
        if int(m.u8(0x0EDCF4)) >= need:
            _log("refill OK:", int(m.u8(0x0EDCF4)))
            return True
    return False


WINDOW_LO, WINDOW_HI = 660.0, 880.0   # px, camera-verified player X
# (mosque/cannon area; grenade pickup pile at ~726)
KILL_LO, KILL_HI = 810.0, 868.0       # lob sweet spot: right side of
# the window so the left-facing arc lands on the mosque roof cannon


def camx_px(m):
    """Player-follow camera px from the VERIFIED camera word
    (0x0CA2E0 u32, >>16). Live-verified == slot-0 X scale in this
    context (trace B: tile==camera_x)."""
    return int(m.u32(0x0CA2E0)) >> 16


def walk_to_window(p, session, fdir, every, cap, m, budget=3600):
    """Direct walk (frozen hp) to the mosque lob window. Holds LEFT
    (+Y for footage/combat) from the village-end clamp; hops when the
    truck body blocks. Position = VERIFIED camera px."""
    stuck = 0
    x = camx_px(m)
    for i in range(budget):
        x = camx_px(m)
        if WINDOW_LO <= x <= WINDOW_HI:
            return x
        btns = {"LEFT", "Y"}
        if stuck > 40:
            btns.add("B")            # hop the truck/debris
        if x < WINDOW_LO:            # overshot: nudge back right
            btns = {"RIGHT"}
            stuck = 0
        step_gs(p, session, 1, btns, fdir, every, cap, m)
        nx = camx_px(m)
        stuck = stuck + 1 if nx == x else 0
    return camx_px(m)


def phase_b(p, chunks, trace, evlog, fdir, every, cap, outdir):
    m = p.mem
    session = _ensure_live_then_freeze(p, "gifB_reach")
    tel = TelemetryAdapter(p)
    trace.write({"type": "phase_b_start",
                 "assist": "hp_pair_freeze EXPLORATION (disclosed)",
                 "frame": p.core.frames_run})
    x0 = xfix(slot_words(m, 0))
    x = walk_to_window(p, session, fdir, every, cap, m)
    gren = int(m.u8(0x0EDCF4))
    trace.write({"type": "phase_b_walk", "x_start": round(x0, 1),
                 "x_end": round(x, 1), "grenades": gren})
    # grenade top-up from the pickup pile at ~726 if the counter is low
    if gren < 4:
        for _ in range(240):
            cur = camx_px(m)
            if cur > 760:
                step_gs(p, session, 1, {"LEFT"}, fdir, every, cap, m)
            elif cur < 700:
                step_gs(p, session, 1, {"RIGHT"}, fdir, every, cap, m)
            else:
                step_gs(p, session, 1, set(), fdir, every, cap, m)
            if int(m.u8(0x0EDCF4)) >= 4:
                break
        trace.write({"type": "pickup_attempt",
                     "grenades": int(m.u8(0x0EDCF4)),
                     "frame": p.core.frames_run})
    p.save_state("lob_window")
    trace.write({"type": "lob_window_reached",
                 "camx_px": camx_px(m),
                 "grenades": int(m.u8(0x0EDCF4)),
                 "frame": p.core.frames_run})
    evlog.write({"kind": "lob_window",
                 "gframe": p.core.frames_run})
    rep = {"phase": "B", "window_x": round(x, 1),
           "grenades": int(m.u8(0x0EDCF4)),
           "frames_captured": cap["count"],
           "frame": p.core.frames_run}
    trace.write({"type": "phase_b_end", **rep})
    return rep, session


# ------------------------------------------------------------------
# Phase C: mosque lob kill -> rain-quiet -> unfrozen walk to clamp
# ------------------------------------------------------------------
def phase_c(p, trace, evlog, fdir, every, cap, outdir,
            kill_budget_cycles=60, trav_budget=2200, session=None):
    m = p.mem
    tel = TelemetryAdapter(p)
    if session is None:
        session = gp.freeze_now(p, "gifC_lob")
    f0 = p.core.frames_run
    t0 = time.time()
    _last_new_tile_frame = p.core.frames_run
    trace.write({"type": "phase_c_start",
                 "assist": "hp_pair_freeze EXPLORATION for lob only",
                 "frame": f0})

    def rain_poll(frame, tag):
        evs = []
        prev_slots = rain_poll.prev                     # type: ignore
        for s in range(1, 40):
            w = slot_words(m, s)
            h, hp = w[63], w[71]
            ph = prev_slots[s][63]
            if hp and 0 < ph - h <= 20 and h > 60 and ph > 70:
                evs.append({"tag": tag, "f": frame, "slot": s,
                            "X": round(xfix(w), 1), "h": h, "hp": hp})
            prev_slots[s] = w
        return evs
    rain_poll.prev = {s: slot_words(m, s) for s in range(40)}  # type: ignore

    # ---- position into the lob sweet spot (px 810-868) ----
    for _ in range(400):
        t = camx_px(m)
        if KILL_LO <= t <= KILL_HI:
            break
        step_gs(p, session, 1, {"LEFT"} if t > KILL_HI else {"RIGHT"},
                fdir, every, cap, m)
    tile0 = camx_px(m)
    _log("POS tile", tile0)
    score0 = int(m.u16(gp.A_SCORE))

    # ---- lob campaign: phase 1 left-facing (mosque roof), phase 2
    # right-facing (rain zone / chopper at 915-1067) ----
    mosque_dead = False
    rain_events = 0
    out_of_grenades = False
    last_score = int(m.u16(gp.A_SCORE))
    score0 = int(m.u16(gp.A_SCORE))
    for phase_lob, lo, hi in (("LEFT", 700.0, 780.0),
                              ("RIGHT", 790.0, 850.0)):
        if mosque_dead:
            break
        # (re)position for this lob direction
        for _ in range(400):
            t = camx_px(m)
            if lo <= t <= hi:
                break
            step_gs(p, session, 1,
                    {"LEFT"} if t > hi else {"RIGHT"},
                    fdir, every, cap, m)
        for k in range(kill_budget_cycles * 40):
            gren = int(m.u8(0x0EDCF4))
            if gren == 0:
                out_of_grenades = True
                break
            cyc = k % 80
            btns = ({"A"} if cyc < 8 else
                    ({phase_lob} if cyc < 24 else set()))
            step_gs(p, session, 1, btns, fdir, every, cap, m)
            rain_events += len(rain_poll(p.core.frames_run, "KILL"))
            now_score = int(m.u16(gp.A_SCORE))
            delta = (now_score - last_score) & 0xFFFF
            if delta > 0:
                trace.write({"type": "kill_score_event",
                             "lob": phase_lob, "k": k, "delta": delta,
                             "score": now_score,
                             "frame": p.core.frames_run})
            last_score = now_score
            total = (now_score - score0) & 0xFFFF
            if (total >= 800 and (total & 0xFF) == 32) or \
                    (total >= 1100 and (total & 0xFF) == 76):
                mosque_dead = True
                trace.write({"type": "mosque_kill", "lob": phase_lob,
                             "total_delta": total,
                             "score": now_score,
                             "frame": p.core.frames_run})
                evlog.write({"kind": "mosque_kill",
                             "gframe": p.core.frames_run})
                rgb = p.core.frame_rgb()
                if rgb is not None:
                    Image.fromarray(rgb).save(os.path.join(
                        outdir, "mosque_kill.png"))
                break
            if k % 240 == 0:
                _log(f"KILL[{phase_lob}] k={k} score={now_score} "
                     f"x={camx_px(m)}")
        if out_of_grenades:
            break
    _log(f"mosque_dead={mosque_dead} score {score0}->"
         f"{int(m.u16(gp.A_SCORE))}")

    # ---- rain-quiet check: 150f idle, counted separately ----
    rain_window_events = 0
    for _ in range(150):
        step_gs(p, session, 1, set(), fdir, every, cap, m)
        rain_window_events += len(rain_poll(p.core.frames_run, "RAIN"))
    rain_quiet = rain_window_events < 10
    trace.write({"type": "rain_check", "faller_events_kill": rain_events,
                 "faller_events_rain_window": rain_window_events,
                 "rain_quiet": rain_quiet,
                 "frame": p.core.frames_run})
    evlog.write({"kind": "rain_quiet" if rain_quiet else "rain_active",
                 "events": rain_events, "gframe": p.core.frames_run})

    # ---- UNFREEZE and walk RIGHT (legit survival) ----
    gp.unfreeze(session, "gifC_lob")
    trace.write({"type": "assists_off", "frame": p.core.frames_run})
    evlog.write({"kind": "assists_off", "gframe": p.core.frames_run})
    stall = 0
    last_x = None
    hop_until = -1
    max_tile = camx_px(m)
    max_prog = int(m.u16(gp.A_PROGRESS))
    continue_taps = 0
    low = 0
    pauses = 0
    stop = None
    rgb_prev = p.core.frame_rgb()
    tap_cooldown = 0
    k = -1
    for k in range(trav_budget):
        ptile = camx_px(m)
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        step_gs(p, None, 1, btns, fdir, every, cap, m)
        # per-frame PIXEL churn (no emulation advance, unlike
        # idle_churn) so every traversal frame stays captured
        rgb_now = p.core.frame_rgb()
        ch_px = None
        if rgb_prev is not None and rgb_now is not None:
            ch_px = float(np.abs(rgb_prev.astype(np.int16) -
                                 rgb_now.astype(np.int16)).mean())
        rgb_prev = rgb_now
        if last_x is not None and ptile == last_x:
            stall += 1
        else:
            stall = 0
            max_tile = max(max_tile, ptile)
        last_x = ptile
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        prog = int(m.u16(gp.A_PROGRESS))
        max_prog = max(max_prog, prog)
        if k % 120 == 0:
            trace.write({"type": "trav_sample", "k": k,
                         "tile": ptile, "prog": prog,
                         "churn_px": None if ch_px is None
                         else round(ch_px, 2),
                         "max_tile": max_tile,
                         "max_prog": max_prog,
                         "frame": p.core.frames_run})
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        dead = _flags_dead(cur["flags_word"])
        if dead:
            low += 1
        else:
            low = 0
        if tap_cooldown > 0:
            tap_cooldown -= 1
        if dead and tap_cooldown == 0:
            p.core.run(10, {"START"})
            for _ in range(70):
                p.core.run_frame()
            snap(p, fdir, every, cap)
            continue_taps += 1
            evlog.write({"kind": "continue_tap", "n": continue_taps,
                         "dead": dead, "gframe": p.core.frames_run})
            low = 0
            stall = 0
            hop_until = -1
            tel.prev = None
            rgb_prev = p.core.frame_rgb()
            tap_cooldown = 240
            if continue_taps >= 3:
                stop = "TRAVERSAL_DIED_X3"
                break
        if k > 900 and p.core.frames_run - _last_new_tile_frame > 1200:
            stop = "CLAMP_NO_PROGRESS"
            break
        if ptile >= max_tile:
            _last_new_tile_frame = p.core.frames_run
    if stop is None and k >= trav_budget - 1:
        stop = "TRAV_BUDGET_END"
    trace.write({"type": "trav_stop", "reason": stop,
                 "max_tile": max_tile,
                 "max_prog": max_prog,
                 "frame": p.core.frames_run})
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, "phase_c_end.png"))
    rep = captured_report("C", "C", p, cap,
                          {"mosque_dead": mosque_dead,
                           "rain_quiet": rain_quiet,
                           "rain_events": rain_events,
                           "max_tile": round(max_tile, 2),
                           "max_prog": max_prog,
                           "pauses": pauses,
                           "continue_taps": continue_taps,
                           "stop": stop},
                          t0, f0)
    trace.write({"type": "phase_c_end", **rep})
    try:
        p.save_state("gif2_final")
    except Exception as e:                     # noqa: BLE001
        _log("final save failed:", repr(e))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("A", "B", "BC", "C"),
                    required=True)
    ap.add_argument("--chunks", type=int, default=350)
    ap.add_argument("--capture-every", type=int, default=10)
    ap.add_argument("--tag", default="gif2")
    ap.add_argument("--resume-state", default=None)
    ap.add_argument("--initial-frame", type=int, default=0)
    ap.add_argument("--save-resume", default=None)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_gif_{args.tag}")
    fdir = os.path.join(outdir, "frames")
    os.makedirs(fdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, f"trace_{args.tag}.jsonl"))
    evlog = JsonlTrace(os.path.join(outdir, "highlights.jsonl"))
    _log(f"phase={args.phase} chunks={args.chunks} "
         f"resume={args.resume_state} f0={args.initial_frame}")
    p, fwmode = boot()
    if args.resume_state:
        p.load_state(args.resume_state)
        p.core.frames_run = args.initial_frame
        _log(f"resumed from {args.resume_state}")
        for _ in range(30):
            p.core.run(1, set())
        p.core.frames_run = args.initial_frame
    cap = {"count": 0}
    if args.phase == "A":
        rep = legit_run_once(p, args.chunks, trace, f"A_{args.tag}",
                             outdir, fdir, args.capture_every, evlog)
        if args.save_resume:
            p.save_state(args.save_resume)
            _log(f"resume saved {args.save_resume} "
                 f"frame {p.core.frames_run}")
    elif args.phase in ("B", "BC"):
        rb, sess = phase_b(p, args.chunks, trace, evlog, fdir,
                           args.capture_every, cap, outdir)
        if args.phase == "BC":
            rep = phase_c(p, trace, evlog, fdir, args.capture_every,
                          cap, outdir, session=sess)
            rep["phase_B"] = rb
        else:
            gp.unfreeze(sess, "gifB_reach")
            rep = rb
        if args.save_resume:
            p.save_state(args.save_resume)
            _log(f"resume saved {args.save_resume} "
                 f"frame {p.core.frames_run}")
    else:
        rep = phase_c(p, trace, evlog, fdir, args.capture_every, cap,
                      outdir)
    out = {"schema": "ps1play-storyrun/1", "phase": args.phase,
           "firmware_mode": fwmode,
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "report": rep}
    rp = os.path.join(outdir, f"story_{args.phase}.json")
    with open(rp, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", rp)
    _log("RESULT:", json.dumps(rep))
    trace.close()
    evlog.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
