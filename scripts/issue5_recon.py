#!/usr/bin/env python3
"""issue5_recon.py — CHEAT_ASSISTED_EXPLORATION full-map reconnaissance.

Operator directive (Issue #5 addendum, user priority): make the player
invincible (freeze-verified HP slot), give infinite bombs (live grenade
anchor), then march right through the WHOLE mission to map the
encounter: enemy positions, enemy-shot windows, camera/flag transitions.

Legitimacy contract (issue sections + cheatprof.py):
  * profile is CHEAT_ASSISTED_EXPLORATION with explicit opt-in;
  * only freeze-VERIFIED, live-anchored codes are engaged (hp, bombs);
  * every cheat interval is logged (start/end frame + names);
  * the result of this run is a MAP, never a Mission-1 clear claim.
    A cheat-assisted traversal is reported as CHEAT_ASSISTED and does
    not count toward the no-cheat success definition.

Anchors are re-derived EVERY boot AND after every recovery (the player
cluster is dynamically placed per boot/respawn): hp via
perception.find_player_hp (freeze test + survival), grenades via
PerceptionGuard.anchor (strict 4-press series).
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
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.cheatprof import (                      # noqa: E402
    CheatSession, CHEAT_ASSISTED, derive_freeze_code)
from ps1play.agent.perception import PerceptionGuard        # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from mission import ensure_mission, responsive               # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_controller import (savestate_recover, ContinueLedger)  # noqa
from issue5_invuln import find_countdowns                    # noqa: E402


def _log(*a):
    print("[recon]", *a, file=sys.stderr, flush=True)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def _blink_candidates(p):
    """Sample the countdown window twice across a savestate reload and
    return candidates that reproduce, start small (<=80), strictly
    decrease to 0 and STAY 0 for the last >=10 samples (the real blink
    plateaus at zero; impostors like the u16 0xCB7B6 [127,122,115,112,
    ...] countdown from big values or plateau high — recon2 caught one)."""
    def one():
        snaps = [p.mem.snapshot()]
        for _ in range(29):
            p.core.run(5, set())
            snaps.append(p.mem.snapshot())
        out = {}
        for cd in find_countdowns(snaps):
            s = cd["series"]
            if s[0] > 80:
                continue
            if sum(1 for v in s[-12:] if v == 0) < 10:
                continue
            out[(cd["addr"], cd["width"])] = cd
        return out
    p.save_state("_armchk")          # snapshot BEFORE the first window
    a = one()
    p.load_state("_armchk")          # replays the same blink window
    b = one()
    return [a[k] for k in a if k in b]


def arm_cheats(p, session, evid, tag=""):
    """Engage the only still-VERIFIED freeze: bombs (strict-series
    grenade anchor). TRUE invincibility remains UNRESOLVED:
      0xCA2FE 'hp'  -> SUPERSEDED false positive (recon1 died 4x)
      0xEF13F blink -> REJECTED (helicopter bomb kills through it)
      0xCB225 lives -> REJECTED (mirror; game-over still came)
    Death recovery therefore uses the game's own legal continue
    (accept_continue, proven cadence) + savestate restart fallback."""
    session.disable_all()
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=_log)
    if not anch.get("ok"):
        _log("!! grenade anchor failed", tag)
        return None
    bombs_addr = int(guard.addrs["bombs"])
    bombs_dtype = guard.dtypes.get("bombs", "u8")
    bombs_code, bombs_val = derive_freeze_code(p, bombs_addr,
                                               dtype=bombs_dtype)
    session.enable("bombs_freeze", [bombs_code])
    info = {"bombs_addr": hex(bombs_addr),
            "bombs_dtype": bombs_dtype, "bombs_value": bombs_val,
            "invincibility": "UNRESOLVED (see cheats.json statuses)",
            "codes": [bombs_code.raw]}
    _log("cheats armed", tag, info)
    return info


def verify_invincibility(p, session, evid, frames=600):
    """Operator step 1 proof: with the blink freeze ON, walk into live
    enemy contact; no death may occur for the whole window."""
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=False, jump_enabled=False)
    det = StallDetector()
    t0 = time.time()
    for _ in range(frames // 60):
        segs = policy.decide(60, det)
        for s in segs:
            session.run_frames(s["frames"], set(s["btns"] or set()))
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        if cur["flags_word"] != 0xFF:
            png(p, evid, "invincible_FAILED.png")
            res = {"frames": frames, "died": True,
                   "verdict": "FAILED"}
            _log("invincibility:", res)
            return res
    ok, gate = responsive(p)
    png(p, evid, "invincible_proof.png")
    res = {"frames": frames, "died": False, "alive": bool(ok),
           "gate": list(gate), "wall_s": round(time.time() - t0, 1),
           "verdict": "INVINCIBLE_TESTED" if ok else "FAILED"}
    _log("invincibility:", res)
    return res


def verify_bomb_freeze(p, session, bombs_addr, bombs_dtype, evid):
    """Event-conditioned proof in-run: throw a grenade with the freeze
    ON; the counter must not drop. (The counter's -1 series without the
    freeze was already proven by the strict anchor itself.)"""
    read = p.mem.u8 if bombs_dtype == "u8" else p.mem.u16
    before = int(read(bombs_addr))
    p.core.run(8, frozenset())
    p.core.set_buttons({"A"})
    for _ in range(12):
        p.core.run_frame()
        session.gs.tick()
    p.core.set_buttons(frozenset())
    for _ in range(90):
        p.core.run_frame()
        session.gs.tick()
    p._advance()
    after = int(read(bombs_addr))
    res = {"bombs_addr": hex(bombs_addr), "dtype": bombs_dtype,
           "before": before, "after": after, "frozen": after == before,
           "verdict": "BOMBS_FROZEN_TESTED" if after == before
           else "FAILED"}
    _log("bombs:", res)
    return res


def recover_full(p, tel, trace, evid, chunk, tag, max_rounds=6):
    """Legal in-game recovery from any dead screen, reusing PROVEN
    components:
      1. mission.recover  — single START (accepts a live CONTINUE screen
         or unpauses) [proven cadence]
      2. p.enter_gameplay3 — the adaptive boot navigator: classifies
         the screen every ~60f and selects with B on the main menu,
         confirms dialogs, waits loading [proven every boot]
      3. mission.ensure_mission — the responsive() control gate
    Every recovery is disclosed in the trace (restart vs continue)."""
    from mission import recover as gate_recover, responsive
    for k in range(max_rounds):
        ok, _ = responsive(p)
        if ok:
            return True
        gate_recover(p, log=_log)                  # START + settle
        ok, _ = responsive(p)
        if ok:
            trace.write({"type": "recovery_continue", "chunk": chunk,
                         "round": k, "method": "start_tap"})
            return True
        r = p.enter_gameplay3()                     # menu: B-select path
        g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
        if r.get("in_game") and g.get("in_mission"):
            trace.write({"type": "recovery_menurelaunch", "chunk": chunk,
                         "round": k, "method": "enter_gameplay3_B",
                         "disclosed": True})
            return True
        png(p, evid, f"{tag}_round{k}.png")
    return False


def visual_dark(p, thresh=1.0, windows=2, wf=20):
    """Visual liveness: run `windows` gaps of wf frames and require the
    screen to stay static (churn < thresh in every gap) = dead/fade."""
    prev = p.core.frame_rgb()
    for _ in range(windows):
        p.core.run(wf, set())
        cur = p.core.frame_rgb()
        if cur is None or prev is None:
            return False
        c = float(np.abs(cur.astype(np.int16) -
                         prev.astype(np.int16)).mean())
        if c >= thresh:
            return False
        prev = cur
    return True


class FireHeldPolicy(RoutePolicy):
    """Operator directive: keep firing while advancing (RIGHT+Y held),
    grenade cadence + hop preserved. Replaces the burst gaps — the
    soldier-dense sections punish burst downtime."""

    def decide(self, chunk, detector):
        segs = []
        prev = None
        for _ in range(chunk):
            state = detector.state if detector is not None else "PROGRESS"
            btns = {"RIGHT", "Y"}
            if state == "RECOVERY":
                u = self.fc % 90
                if u < 30:
                    btns = {"LEFT", "Y"}
            if self.jump_enabled:
                if self.hop_hold > 0:
                    btns.add("B")
                    self.hop_hold -= 1
                elif self.hop_cd <= 0:
                    self.hop_hold = self.JUMP_HOLD
                    self.hop_cd = self.JUMP_PERIOD + self.JUMP_HOLD
                    self.stats["jump"] += 1
                else:
                    self.hop_cd -= 1
            if self.allow_grenades and self.fc % self.GRENADE_PERIOD == 0:
                self.press = 4
                self.stats["grenade"] += 1
            if self.press > 0:
                btns.add("A")
                self.press -= 1
            self.fc += 1
            if prev is not None and prev["btns"] == btns:
                prev["frames"] += 1
            else:
                prev = {"frames": 1, "btns": btns}
                segs.append(prev)
        return segs


def run_once(p, session, chunks, trace, label, evid, png_every=50,
             wall_budget=None, fire_held=False):
    tel = TelemetryAdapter(p)
    if fire_held:
        policy = FireHeldPolicy(allow_grenades=True, jump_enabled=True)
        policy.GRENADE_PERIOD = 120
    else:
        policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    ledger = ContinueLedger(no_progress_limit=12)   # recon: coverage first
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    trace.write({"type": "recon_start", "label": label,
                 "profile": CHEAT_ASSISTED, "start": prev,
                 "cheats_active": session.active_names()})
    stall_streak, ladder, deaths, stop = 0, 0, 0, None
    max_score = prev["score"]
    max_camx = prev["camera_x"]
    flags_prev = prev["flags_word"]
    rgb_prev = p.core.frame_rgb()
    transitions = []
    t0 = time.time()
    c = -1
    for c in range(chunks):
        if stop:
            break
        if wall_budget and (time.time() - t0) > wall_budget:
            stop = "WALL_BUDGET"
            trace.write({"type": "wall_budget_stop", "chunk": c})
            break
        segs = policy.decide(60, det)
        for s in segs:
            session.run_frames(s["frames"], set(s["btns"] or set()))
        cur = tel.snapshot(buttons=sorted(set().union(
            *[s["btns"] or set() for s in segs])),
            frame=p.core.frames_run)
        gain = tel.scroll_gain(prev, cur)
        evs = tel.events(prev, cur)
        for e in evs:
            trace.write({"type": "event", "chunk": c, **e})
        max_score = max(max_score, cur["score"])
        max_camx = max(max_camx, cur["camera_x"])
        churn = None
        if c % 2 == 0:                 # throttled: churn every 2nd chunk
            rgb_now = p.core.frame_rgb()
            if rgb_prev is not None and rgb_now is not None:
                churn = round(float(np.abs(
                    rgb_prev.astype(np.int16) -
                    rgb_now.astype(np.int16)).mean()), 3)
            rgb_prev = rgb_now
        trace.write({"type": "chunk", "chunk": c, "telemetry": cur,
                     "scroll_gain": gain, "churn_px": churn,
                     "cheats": session.active_names(),
                     "policy_stats": dict(policy.stats)})
        # flags transitions = encounter/menu boundaries of the map
        if cur["flags_word"] != flags_prev:
            transitions.append({"chunk": c, "frame": cur["frame"],
                                "from": flags_prev,
                                "to": cur["flags_word"]})
            trace.write({"type": "flags_transition", "chunk": c,
                         "from": flags_prev, "to": cur["flags_word"]})
            png(p, evid, f"transition_c{c:03d}_f{cur['flags_word']:X}.png")
            flags_prev = cur["flags_word"]
        # death / out-of-gameplay handling. Detection is VISUAL
        # (churn dark-window = death fade — flags_word reads 0xFF even
        # on CONTINUE screens and the telemetry score is low-byte only,
        # so both are unreliable here; see frameprobe/ad1 evidence).
        game_over = cur["flags_word"] == 0x1
        death_evt = any(e["type"] == "death_candidate" for e in evs)
        suspect = game_over or death_evt or gain < -50
        if suspect:
            session.run_frames(120, set())
            re = tel.snapshot(buttons=[], frame=p.core.frames_run)
            dark_ok = False
            if not game_over:
                dark_ok = visual_dark(p)     # static screen = dead/fade
            if re["flags_word"] == 0xFF and not game_over and not dark_ok:
                trace.write({"type": "false_death_trigger", "chunk": c,
                             "was": "score_wrap_or_noise"})
                prev = re
                rgb_prev = p.core.frame_rgb()
                flags_prev = re["flags_word"]
                continue
            deaths += 1
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": deaths,
                         "trigger": "game_over" if game_over else
                         ("score_collapse" if death_evt else
                          "camera_regress")})
            if deaths > 40:
                stop = "STOP_DEAD_LOOP"
                break
            png(p, evid, f"recovery{deaths}_c{c:03d}.png")
            ledger.observe(prev["score"])
            ok = recover_full(p, tel, trace, evid, c,
                              f"rec{deaths}")
            # bounded resume wait: after a continue/menu-relaunch the
            # game still shows banner/loading for a few seconds
            after = tel.snapshot(buttons=[], frame=p.core.frames_run)
            wait = 0
            while ok and wait < 600:
                if after["flags_word"] == 0xFF:
                    break
                session.run_frames(60, set())
                wait += 60
                after = tel.snapshot(buttons=[],
                                     frame=p.core.frames_run)
            if ok and after["flags_word"] == 0xFF:
                trace.write({"type": "recovery_resumed", "chunk": c,
                             "deaths": deaths, "wait_f": wait,
                             "cheats": session.active_names()})
                det.reset()
                prev = after
                rgb_prev = p.core.frame_rgb()
                flags_prev = after["flags_word"]
                continue
            # one more full recovery attempt before giving up
            ok2 = recover_full(p, tel, trace, evid, c, f"rec{deaths}b")
            if ok2:
                continue
            stop = "STOP_RESTART_FAILED"
            trace.write({"type": "stop", "chunk": c, "reason": stop})
            break
        ledger.observe(cur["score"])
        # stall ladder (pixel churn, same thresholds as issue5_controller)
        stalled = churn is not None and churn < 3.0 and gain <= 0
        stall_streak = 0 if not stalled else stall_streak + 1
        if not stalled:
            ladder = 0
        if stall_streak >= 6:
            ladder += 1
            stall_streak = 0
            if ladder == 1:
                trace.write({"type": "stall_l1_jump", "chunk": c})
                session.run_frames(20, {"RIGHT"})
                session.run_frames(40, {"RIGHT", "B"})
            elif ladder == 2:
                trace.write({"type": "stall_l2_grenade", "chunk": c})
                session.run_frames(8, set())
                session.run_frames(30, {"A"})
                session.run_frames(30, {"RIGHT", "Y"})
            elif ladder == 3:
                trace.write({"type": "stall_l3_unstick", "chunk": c})
                session.run_frames(60, {"LEFT", "Y"})
                session.run_frames(120, {"RIGHT", "Y"})
            else:
                stop = f"STOP_STALLED chunk={c} camx={cur['camera_x']}"
                trace.write({"type": "stop", "chunk": c, "reason": stop})
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        if c % png_every == 0:
            png(p, evid, f"recon_c{c:03d}.png")
        prev = cur
    ivals = session.finalize_intervals()
    report = {
        "label": label, "profile": CHEAT_ASSISTED,
        "chunks_run": c + 1 if not stop and c >= 0 else max(c, 0),
        "stop_reason": stop or "BUDGET_END",
        "deaths": deaths,
        "max_score": max_score, "max_camera_x": max_camx,
        "final_camera_x": prev["camera_x"], "final_score": prev["score"],
        "flags_transitions": transitions,
        "cheat_intervals": ivals,
        "policy_stats": policy.stats,
        "wall_s": round(time.time() - t0, 1),
        "clear_claim": None,
        "note": ("CHEAT_ASSISTED reconnaissance only — never counted "
                 "as a no-cheat Mission-1 clear"),
    }
    trace.write({"type": "recon_end", **report})
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=300)
    ap.add_argument("--tag", default="recon1")
    ap.add_argument("--png-every", type=int, default=50)
    ap.add_argument("--wall-budget", type=int, default=None,
                    help="seconds; graceful BUDGET stop for foreground "
                         "tool-call limits")
    ap.add_argument("--fire-held", action="store_true",
                    help="use FireHeldPolicy (RIGHT+Y always)")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_recon_{args.tag}")
    os.makedirs(outdir, exist_ok=True)

    _log("=== boot (real-play gate) ===")
    p, fwmode = boot()
    _log("booted:", fwmode)
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)

    info = arm_cheats(p, session, outdir)
    if info is None:
        sys.exit("!! anchor derivation failed")
    bmb = verify_bomb_freeze(p, session,
                             int(info["bombs_addr"], 16),
                             info["bombs_dtype"], outdir)

    p.save_state("recon_m1_start")
    trace = JsonlTrace(os.path.join(outdir, "trace_recon.jsonl"))
    try:
        rep = run_once(p, session, args.chunks, trace, args.tag, outdir,
                       png_every=args.png_every,
                       wall_budget=args.wall_budget,
                       fire_held=args.fire_held)
    finally:
        trace.close()
    session.disable_all()
    rep["boot"] = {"firmware": fwmode, **info}
    rep["bombs_freeze"] = bmb
    with open(os.path.join(outdir, "recon_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    _log("report:", os.path.join(outdir, "recon_report.json"))
    _log("cheat-assisted recon finished:", rep["stop_reason"],
         "max_camx=", rep["max_camera_x"], "max_score=", rep["max_score"])
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
