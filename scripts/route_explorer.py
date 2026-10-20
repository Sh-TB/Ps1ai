#!/usr/bin/env python3
"""route_explorer.py — bounded Mission-1 route discovery with two
HARD-SEPARATED execution profiles (Issue #2 sections 4/7).

  --mode cheat-assisted  CHEAT_ASSISTED_EXPLORATION: applies ONLY codes
        that are VERIFIED in the registry, and only with the explicit
        operator opt-in (--opt-in). Every active cheat interval is
        recorded with exact frame ranges.
  --mode legit           LEGIT_CONTROLLER_RUN: ordinary controller input
        only. The session refuses any cheat and asserts a clean state
        before, during and after the run.

Both modes run the same deliberately simple state-aware policy
(ps1play.agent.route.RoutePolicy: RIGHT + burst fire + periodic jump,
bounded recovery on stalls), a bounded StallDetector, continue-screen
recovery, and produce a route ledger + JSON report + screenshots.
A cheat-assisted result is never reported as a no-cheat success.

Usage:
  python3 scripts/route_explorer.py --mode cheat-assisted --opt-in \
      --cheats bombs,invuln --budget-minutes 8
  python3 scripts/route_explorer.py --mode legit --budget-minutes 6
"""
import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                         # noqa: E402

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from ps1play.agent.cheatprof import (                      # noqa: E402
    CheatSession, CheatRegistry, CHEAT_ASSISTED, LEGIT,
    ProfileViolation, derive_freeze_code, quick_verify_freeze,
    ST_VERIFIED)
from ps1play.agent.route import (                          # noqa: E402
    RoutePolicy, RouteLedger, StallDetector, MODE_CHEAT, MODE_LEGIT)
from ps1play.agent.events import MissionClearDetector      # noqa: E402
from run_mission1_legit import (                           # noqa: E402
    find_progress_addr, read_score_raw, recover_v2, responsive_live,
    SCORE_ADDR, MISSION_ADDR)
from mission import ensure_mission                         # noqa: E402

DEF_REGISTRY = os.path.join(_REPO, "data", "games", "SLUS-01212",
                            "cheats.json")
DEF_ROUTE = os.path.join(_REPO, "data", "games", "SLUS-01212",
                         "mission1_route.json")

# derived freeze cheats: codes are re-derived from fresh event-verified
# anchors EVERY run (the player cluster is dynamically placed per boot);
# the registry only records the derivation contract + latest evidence
DERIVED_CHEATS = {"bombs_freeze", "hp_freeze"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, evid, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(evid, name))
            return name
    except Exception as e:                                  # noqa: BLE001
        log("png fail:", e)
    return None


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", required=True,
                    choices=["cheat-assisted", "legit"],
                    help="execution profile (issue section 4)")
    ap.add_argument("--opt-in", action="store_true",
                    help="EXPLICIT operator opt-in for cheat-assisted "
                         "exploration; without it the cheat mode "
                         "refuses to start")
    ap.add_argument("--cheats", default="bombs_freeze,hp_freeze",
                    help="comma list of registry cheat names to apply "
                         "(cheat mode only; every one must be VERIFIED)")
    ap.add_argument("--registry", default=DEF_REGISTRY)
    ap.add_argument("--route-ledger", default=DEF_ROUTE,
                    help="seed route ledger (landmark expectations)")
    ap.add_argument("--game", default=labconfig.resolve_path("game"))
    ap.add_argument("--core", default=labconfig.resolve_path("core"))
    ap.add_argument("--workspace", default=labconfig.resolve_path(
        "workspace"))
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--firmware", default=os.environ.get(
        "M1_FIRMWARE", "auto"),
        choices=list(labconfig.FIRMWARE_MODES))
    ap.add_argument("--budget-minutes", type=float, default=8.0)
    ap.add_argument("--chunks", type=int, default=100000,
                    help="hard chunk cap (60 frames each)")
    ap.add_argument("--stall-limit", type=int, default=4,
                    help="stalled chunks before bounded recovery")
    ap.add_argument("--recovery-chunks", type=int, default=3)
    ap.add_argument("--report", default=None)
    a = ap.parse_args(argv)
    a.cheat_names = [s.strip() for s in a.cheats.split(",")
                     if s.strip()] if a.mode == "cheat-assisted" else []
    if a.mode == "cheat-assisted" and not a.opt_in:
        ap.error("cheat-assisted mode requires --opt-in (explicit "
                 "operator consent; the default mode never applies "
                 "cheats)")
    if a.evidence_dir is None:
        base = labconfig.resolve_path("evidence_dir") or os.path.join(
            _REPO, "evidence_local")
        a.evidence_dir = os.path.join(
            base, f"route_{a.mode}_{time.strftime('%Y%m%d_%H%M%S')}")
    return a


def execute_segs(p, segs, session, total=60):
    """Run exactly `total` frames following the policy segments, ticking
    the cheat session every frame (no-op when no cheat is active)."""
    done = 0
    for s in segs:
        k = min(s["frames"], total - done)
        if k <= 0:
            break
        p.core.set_buttons(s["btns"])
        for _ in range(k):
            p.core.run_frame()
            session.tick(frame=p.t)
        done += k
    p._advance()
    return done


def main(argv=None):
    args = parse_args(argv)
    evid = args.evidence_dir
    os.makedirs(evid, exist_ok=True)
    mode = MODE_CHEAT if args.mode == "cheat-assisted" else MODE_LEGIT
    t0 = None                # budget clock starts AFTER setup (run loop)
    budget_s = args.budget_minutes * 60.0

    # ---- registry + profile contract -------------------------------
    registry = CheatRegistry.load(args.registry)
    problems = registry.validate()
    if problems:
        sys.exit(f"!! registry invalid: {problems}")
    session_codes = []
    cheat_meta = []
    if mode == MODE_CHEAT:
        # registry STATUS gate for every requested cheat (VERIFIED
        # evidence required before either kind may drive exploration)
        unverified = [n for n in args.cheat_names
                      if registry.entries.get(n, {}).get("status")
                      != ST_VERIFIED]
        if unverified:
            sys.exit(
                f"!! cheats not VERIFIED in {args.registry}: "
                f"{', '.join(unverified)} — run scripts/"
                "validate_cheats.py first; CANDIDATE codes never "
                "drive exploration")
        literal = [n for n in args.cheat_names if n not in DERIVED_CHEATS]
        session_codes = registry.codes_for(literal,
                                           require_verified=True) \
            if literal else []
        cheat_meta = [{"name": n,
                       "codes": [raw for n2, raw in session_codes
                                 if n2 == n]}
                      for n in args.cheat_names]
        log("[profile] CHEAT_ASSISTED_EXPLORATION (operator opt-in) "
            "cheats:", args.cheat_names)
    else:
        log("[profile] LEGIT_CONTROLLER_RUN — cheats forbidden")

    # ---- boot through the shared config contract --------------------
    try:
        fw = labconfig.resolve_firmware(args.firmware, args.workspace)
    except labconfig.FirmwareError as e:
        sys.exit(f"!! firmware: {e}")
    kw = {}
    if args.core:
        kw["core"] = args.core
    if args.workspace:
        kw["workspace"] = args.workspace
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(args.game, **kw)
    info = p.boot()
    log("boot:", info)
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    fw_ok, fw_detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not fw_ok:
        sys.exit(f"!! firmware trust failed: {fw_detail}")

    session = CheatSession(p, mode, opt_in=args.opt_in)
    if mode == MODE_LEGIT:
        session.assert_clean("pre-run")

    r = p.enter_gameplay3()
    log("enter:", r.get("in_game"))
    if not r.get("in_game"):
        sys.exit("!! boot failed")
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")

    # ---- calibration -------------------------------------------------
    cam = find_progress_addr(p, log=log)
    prog = None
    if cam["addr"] is not None:
        from ps1play.agent.progress import ProgressSignal
        prog = ProgressSignal(cam["addr"], cam["verified"])
    log(f"[cal] progress word: {cam['addr'] and hex(cam['addr'])} "
        f"verified={cam['verified']}")
    raw0, score0 = read_score_raw(p.mem)
    mb0 = p.mem.u8(MISSION_ADDR)
    mcd = MissionClearDetector(baseline_byte=mb0, sustain_chunks=4,
                               log=log)

    # ---- cheat activation AFTER the mission gate (clean intervals) ---
    derived_used = {}
    skipped_cheats = []
    if mode == MODE_CHEAT:
        p.save_state("rx_base")
        from ps1play.agent.perception import PerceptionGuard
        guard = PerceptionGuard(p)
        for name in args.cheat_names:
            if name in DERIVED_CHEATS:
                if name == "bombs_freeze":
                    anch = guard.anchor(log=log)
                    if not anch.get("ok"):
                        sys.exit("!! bombs anchor failed — cannot "
                                 "derive the freeze code")
                    addr = guard.addrs["bombs"]
                    code, val = derive_freeze_code(p, addr)
                    qv = quick_verify_freeze(p, session, code, addr,
                                             "rx_base", action={"A"})
                    if not qv["works"]:
                        sys.exit(f"!! derived {name} failed the "
                                 f"in-run check: {qv}")
                elif name == "hp_freeze":
                    hp = guard.find_player_hp(log=log)
                    if hp is None:
                        # non-deterministic environment (enemies may not
                        # reach the idle player) — skip honestly, keep
                        # the run going with the remaining verified set
                        log("[cheat] hp_freeze skipped: no damage "
                            "event in the anchor window this boot")
                        skipped_cheats.append(
                            {"name": name,
                             "reason": "no freeze-verified HP anchor "
                                       "(no damage event in window)"})
                        continue
                    addr = hp
                    code, val = derive_freeze_code(p, addr)
                    from ps1play.agent.cheatprof import (
                        verify_survival_freeze)
                    qv = verify_survival_freeze(p, session, code, addr,
                                                "rx_base", frames=300)
                    if not qv["works"]:
                        sys.exit(f"!! derived {name} failed the "
                                 f"survival check: {qv}")
                session.enable(name, [code])
                derived_used[name] = {"code": code.raw,
                                      "addr": hex(addr),
                                      "frozen_value": int(val),
                                      "in_run_check": qv}
                log(f"[cheat] derived+verified {name}: {code.raw}")
            else:
                codes = [raw for n, raw in session_codes if n == name]
                session.enable(name, codes)
                log(f"[cheat] enabled {name}: {codes}")
        for m in cheat_meta:
            if m["name"] in derived_used:
                m["codes"] = [derived_used[m["name"]]["code"]]
                m["derived"] = True
    png(p, evid, "01_run_start.png")
    t0 = time.time()         # bounded run budget starts here

    ledger = RouteLedger()
    seg_i = 0
    seg = ledger.start_segment(
        f"S{seg_i:03d}", None, p.t, args.mode,
        progress=(p.mem.u16(cam["addr"]) if cam["addr"] else None))
    policy = RoutePolicy(allow_grenades=(mode == MODE_CHEAT),
                         jump_enabled=True)
    detector = StallDetector(stall_limit=args.stall_limit,
                             recovery_chunks=args.recovery_chunks)
    run_t0 = p.t
    last_mb = mb0
    score_events = []
    transitions = []
    chunks_run = 0
    stopped_reason = None

    for i in range(args.chunks):
        if (time.time() - t0) > budget_s:
            stopped_reason = "budget"
            break
        # ---- mission-clear detector --------------------------------
        mb = p.mem.u8(MISSION_ADDR)
        if mb != last_mb:
            ledger.add_event("MISSION_STATE_CHANGED", p.t,
                             frm=last_mb, to=int(mb))
            transitions.append({"chunk": i, "mission_byte": int(mb)})
            last_mb = mb
        mcd.feed(mb, frame=p.t, chunk=i)
        if mcd.verified:
            png(p, evid, "99_MISSION_CLEAR_VERIFIED.png")
            stopped_reason = "mission_clear_verified"
            ledger.close_segment(seg, p.t,
                                 progress=(p.mem.u16(cam["addr"])
                                           if cam["addr"] else None),
                                 completed=True)
            break

        # ---- keepalive / death recovery ------------------------------
        if i % 3 == 2:
            ok, gate = responsive_live(p)
            if not ok:
                ledger.add_event("RESPONSIVE_LOST", p.t, gate=list(gate))
                png(p, evid, f"deadevent_{i:04d}.png")
                if mode == MODE_LEGIT:
                    ledger.add_event("DEATH_OR_CONTINUE_CANDIDATE", p.t)
                if not recover_v2(p, log=log):
                    mm = ensure_mission(p, tries=4, log=log)
                    if not mm.get("in_mission"):
                        p.enter_gameplay3()
                        ensure_mission(p, tries=4, log=log)
                ledger.add_event("RECOVERY_DONE", p.t)
                detector.reset()

        # ---- policy + execute ---------------------------------------
        segs = policy.decide(60, detector)
        s_before = p.mem.snapshot()
        done = execute_segs(p, segs, session)
        churn = int(np.count_nonzero(s_before != p.mem.snapshot()))
        chunks_run += 1

        # ---- signals -------------------------------------------------
        raw_a, score_a = read_score_raw(p.mem)
        score_delta = int(score_a) - int(score0)
        if score_delta != (score_events[-1]["cum"] if score_events
                           else 0):
            score_events.append({"chunk": i, "frame": p.t,
                                 "cum": score_delta})
        cam_now = p.mem.u16(cam["addr"]) if cam["addr"] else None
        prog_delta = None
        if prog is not None and cam_now is not None and cam["verified"]:
            st = prog.update(cam_now, churn=churn, frame=p.t)
            prog_delta = (prog.n_progress if st == "PROGRESS" else 0)
        state = detector.update(prog_delta, churn, score_delta)

        if state == "RECOVERY" and not seg.get("recovery_used"):
            seg["recovery_used"] = True
            ledger.add_event("BOUNDED_RECOVERY_START", p.t)
        if state == "BLOCKED":
            ledger.close_segment(
                seg, p.t,
                progress=cam_now, completed=False, stalled=True,
                hazard="stall: bounded recovery exhausted",
                action_pattern="RIGHT+fire+jump; recovery LEFT+fire+hop")
            png(p, evid, f"50_stalled_seg{seg_i:03d}.png")
            stopped_reason = "stall_blocked"
            break

        # ---- segment bookkeeping -------------------------------------
        if i and i % 25 == 24:
            ledger.add_event("CHECKPOINT", p.t, chunk=i,
                             score=int(score_a),
                             cam=(int(cam_now) if cam_now is not None
                                  else None))
            png(p, evid, f"play_{i // 25 + 1:02d}.png")
            p.save_state(f"rx_cp_{i}")
        if i % 4 == 0:
            session.assert_clean() if mode == MODE_LEGIT else None

    else:
        stopped_reason = "chunk_cap"

    # ---- close out ----------------------------------------------------
    if seg["exit_frame"] is None:
        ledger.close_segment(seg, p.t,
                             progress=(p.mem.u16(cam["addr"])
                                       if cam["addr"] else None),
                             completed=(stopped_reason ==
                                        "mission_clear_verified"),
                             stalled=(stopped_reason == "stall_blocked"))
    if mode == MODE_LEGIT:
        session.assert_clean("post-run")

    frames_actual = p.t - run_t0
    wall = time.time() - t0
    raw_end, score_end = read_score_raw(p.mem)
    report = {
        "mode": mode,
        "cheats_enabled": cheat_meta if mode == MODE_CHEAT else [],
        "derived_cheats": derived_used,
        "skipped_cheats": skipped_cheats,
        "cheat_intervals": (session.finalize_intervals()
                            if mode == MODE_CHEAT else []),
        "no_cheat_assertion": (mode == MODE_LEGIT),
        "identity": {
            "game": p.game,
            "game_md5": (labconfig.file_md5(_cue_bin(p.game))
                         if _cue_bin(p.game) else None),
            "core_md5": labconfig.file_md5(p.core_path),
            "firmware_mode": fw["mode"],
            "repo_head": _repo_head(),
        },
        "progress_word": {"addr": (hex(cam["addr"])
                                   if cam["addr"] else None),
                          "verified": cam["verified"]},
        "play": {
            "chunks": chunks_run,
            "frames": frames_actual,
            "wall_s": round(wall, 1),
            "fps": round(frames_actual / max(wall, 0.1), 1),
            "score_start": int(score0), "score_end": int(score_end),
            "score_events": score_events[-40:],
            "mission_clear": mcd.to_dict(),
            "detector": detector.to_dict(),
            "policy_stats": policy.stats,
            "stopped_reason": stopped_reason,
        },
        "route_ledger": ledger.to_dict(),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out_path = args.report or os.path.join(evid, "route_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=1, default=str)
    ledger.save(os.path.join(evid, "route_ledger.json"))
    log(f"[route] report -> {out_path}")
    print(json.dumps({k: report[k] for k in
                      ("mode", "cheats_enabled", "play",
                       "progress_word")}, indent=1, default=str))


def _cue_bin(game):
    if game and game.lower().endswith(".cue"):
        try:
            with open(game, "r", errors="replace") as f:
                for ln in f:
                    if 'FILE "' in ln:
                        return os.path.join(os.path.dirname(game),
                                            ln.split('"')[1])
        except OSError:                                     # noqa: BLE001
            return None
    return game


def _repo_head():
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    main()
