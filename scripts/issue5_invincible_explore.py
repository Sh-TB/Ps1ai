#!/usr/bin/env python3
"""issue5_invincible_explore.py — CHEAT-ASSISTED EXPLORATION profile
(user directive: become invincible, pass the helicopter barrier, map
pits/channels and reach the end of the Mission-1 path).

LEGITIMACY CONTRACT (never violated):
  * opt-in, disclosed, ISOLATED from legit runs; never a no-cheat
    clear; every record carries mode=CHEAT_ASSISTED_EXPLORATION.
  * Grenades = published instruction patch 800398BE 2400 (VERIFIED for
    this revision; branch-checked at runtime).

DESIGN v3 — continuous real-play loop, live A/B anchor:
  * patchab evidence: a CONTINUOUS policy loop stays in real play for
    40+ chunks (the boot's deaths at c1/5/6/8 + GAME OVER c35 are real
    attrition).  Every savestate RELOAD in the hot path (anchor
    replays, death recoveries) risks pulling the attract script over
    real play (inv13/inv14 frames: demo HUD 1UP-2/score-frozen while
    telemetry bounced).  Therefore: NO savestate loads mid-run — the
    game's own checkpoint respawn handles deaths; GAME OVER ends the
    run honestly (continue taps attempted, disclosed).
  * HP anchor = LIVE A/B on the running loop: the min-tracker (u16+u8,
    fine-grained) accumulates damage droppers; at the first real death
    the top droppers are frozen one-by-one; a candidate whose freeze
    stops the death cadence for the test window IS the player HP
    (deaths recurred every 2-4 chunks pre-anchor — an 5-6 chunk clean
    window is decisive).
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
from ps1play.agent.gameshark import GameShark, GSCode     # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402

BOMBS_PATCH = "800398BE 2400"     # VERIFIED instruction patch (this rev)

CP_PERIOD = 15                    # periodic ring checkpoint cadence
STARTUP_GRACE = 6
STALL_CHUNKS = 5
DEATH_WARMUP = 3                  # chunks: skip mission-init resets
ANCHOR_TEST_CHUNKS = 6            # clean window that proves a freeze
ANCHOR_MAX_CANDS = 5
SCORE_ADDR = 0x0EE318
FLAGS_ADDR = 0x0EE518
PAD_MIRROR = 0x0D4948


def resume_play(state_name):
    """New process, same boot: restore a disk-backed savestate into a
    freshly constructed core."""
    from ps1play.api import PS1Play
    ws = labconfig.resolve_path("workspace")
    kw = {}
    core_path = labconfig.resolve_path("core")
    if core_path:
        kw["core"] = core_path
    if ws:
        kw["workspace"] = ws
    p = PS1Play(labconfig.resolve_path("game"), **kw)
    p.boot()
    p.load_state(state_name)
    return p


class MinTracker:
    """Damage-dropper accumulator over u16 words AND u8 bytes (the
    grenades counter is u8 — a u16-only scan cannot see an u8 HP)."""

    def __init__(self, p):
        ram = p.mem.ram[:0x1FC000]
        self.a0_16 = ram.view("<u2").astype(np.int32)
        self.min_16 = self.a0_16.copy()
        self.a0_8 = ram.astype(np.int32)
        self.min_8 = self.a0_8.copy()
        self.n = 0

    def sample(self, p):
        ram = p.mem.ram[:0x1FC000]
        np.minimum(self.min_16, ram.view("<u2").astype(np.int32),
                   out=self.min_16)
        np.minimum(self.min_8, ram.astype(np.int32), out=self.min_8)
        self.n += 1

    def value_for(self, addr, width):
        """The mission-start (full) value of a candidate — the freeze
        must engage HERE, never at the post-death current value
        (freezing a dead player's 0 is a false protection, inv15)."""
        if width == 1:
            return int(self.a0_8[addr])
        return int(self.a0_16[addr >> 1])

    def droppers(self, max_cands=ANCHOR_MAX_CANDS):
        out = []
        band16 = ((self.a0_16 >= 60) & (self.a0_16 <= 250) &
                  (self.min_16 < self.a0_16 - 15))
        out += [(int(w) * 2, 2) for w in np.flatnonzero(band16)]
        band8 = ((self.a0_8 >= 60) & (self.a0_8 <= 250) &
                 (self.min_8 < self.a0_8 - 15))
        out += [(int(w), 1) for w in np.flatnonzero(band8)]
        seen16 = {a for a, w in out if w == 2}
        out = [(a, w) for a, w in out
               if w == 2 or (a not in seen16 and
                             (a & ~1) not in seen16)]
        out.sort(key=lambda t: (t[1] != 2, abs(t[0] - 0xCABE4)))
        return out[:max_cands]


def pick_retry_pattern(n):
    """Escalating bounded pit-crossing patterns (pure)."""
    return n % 4


def run_seg(p, gs, frames, btns, tracker=None):
    """Run `frames` with the GS engine ticking every frame (hardware
    behavior; re-arms freezes after any savestate load)."""
    p.core.set_buttons(set(btns) if btns else set())
    for _ in range(frames):
        p.core.run_frame()
        gs.tick()
        if tracker is not None:
            tracker.n += 1
            if tracker.n % 6 == 0:
                tracker.sample(p)


def _log(*a):
    print("[invexp]", *a, file=sys.stderr, flush=True)


class ChunkRunner:
    """Continuous policy chunk advance + stall ladder."""

    def __init__(self, p, gs, tracker=None):
        self.p = p
        self.gs = gs
        self.tracker = tracker
        self.tel = TelemetryAdapter(p)
        self.policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
        self.det = StallDetector()
        self.rgb_prev = p.core.frame_rgb()
        self.stall_streak = 0
        self.ladder = 0
        self.prev = None

    def reset(self, prev):
        self.prev = prev
        self.det.reset()
        self.rgb_prev = self.p.core.frame_rgb()

    def chunk(self, c):
        """Advance one 60-frame chunk (+ ladder recovery when stalled).
        Returns (cur, evs, gain, churn_px, rgb_now)."""
        p, gs = self.p, self.gs
        segs = self.policy.decide(60, self.det)
        for s in segs:
            run_seg(p, gs, s["frames"], s["btns"], self.tracker)
        cur = self.tel.snapshot(buttons=sorted(set().union(
            *[s["btns"] or set() for s in segs])),
            frame=p.core.frames_run)
        gain = self.tel.scroll_gain(self.prev, cur)
        rgb_now = p.core.frame_rgb()
        churn_px = None
        if self.rgb_prev is not None and rgb_now is not None:
            churn_px = round(float(np.abs(
                self.rgb_prev.astype(np.int16) -
                rgb_now.astype(np.int16)).mean()), 3)
        evs = self.tel.events(self.prev, cur)
        # stall ladder (same thresholds as issue5_controller)
        in_grace = c < STARTUP_GRACE
        stalled = churn_px is not None and churn_px < 3.0 and gain <= 0
        self.stall_streak = 0 if (not stalled or in_grace) \
            else self.stall_streak + 1
        if not stalled:
            self.ladder = 0
        if self.stall_streak >= STALL_CHUNKS:
            self.ladder += 1
            self.stall_streak = 0
            if self.ladder == 1:
                run_seg(p, gs, 20, {"RIGHT"})
                run_seg(p, gs, 40, {"RIGHT", "B"})
            elif self.ladder == 2:
                run_seg(p, gs, 8, set())
                run_seg(p, gs, 30, {"A"})
                run_seg(p, gs, 30, {"RIGHT", "Y"})
            elif self.ladder == 3:
                run_seg(p, gs, 60, {"LEFT", "Y"})
                run_seg(p, gs, 120, {"RIGHT", "Y"})
            self.det.reset()
            cur = self.tel.snapshot(buttons=[],
                                    frame=p.core.frames_run)
            evs = []
            gain = 0
            rgb_now = p.core.frame_rgb()
            churn_px = 0
        self.rgb_prev = rgb_now
        self.prev = cur
        return cur, evs, gain, churn_px, rgb_now


def death_snapshot(p):
    """RAM views taken AT a death event (both widths)."""
    ram = p.mem.ram[:0x1FC000]
    return (ram.view("<u2").astype(np.int32), ram.astype(np.int32))


def lives_candidates(p, snap_groups, max_cands=10):
    """Strict-series lives scan, segmented at continues (the lives
    reset to full at every accepted continue — the -1 series holds
    WITHIN a segment only).  A candidate must satisfy the strict -1
    per death + 0..9 bound in EVERY segment that has >= 2 snapshots
    (intersection across segments).  snap_groups = [[snap, ...], ...]
    where snap = (u16 view, u8 view).  Returns [(addr, width)]."""
    sets = []
    for snaps in snap_groups:
        if len(snaps) < 2:
            continue
        for width, idx in ((2, 0), (1, 1)):
            arrs = [s[idx] for s in snaps]
            dec = np.ones(arrs[0].shape, bool)
            bounded = np.ones(arrs[0].shape, bool)
            for i in range(len(arrs) - 1):
                dec &= (arrs[i + 1] - arrs[i]) == -1
            for a in arrs:
                bounded &= (a >= 0) & (a <= 9)
            sets.append((width,
                         set(int(w) for w in
                             np.flatnonzero(dec & bounded))))
    if not sets:
        return []
    out = []
    for width in (2, 1):
        word_sets = [s for w, s in sets if w == width]
        inter = set.intersection(*word_sets) if word_sets else set()
        out += [(int(w) * width, width) for w in sorted(inter)]
    seen16 = {a for a, w in out if w == 2}
    out = [(a, w) for a, w in out
           if w == 2 or (a not in seen16 and (a & ~1) not in seen16)]
    return out[:max_cands]


def engage_freeze(gs, cand, value=None):
    """cand = (addr, width) -> named GameShark freeze at `value`
    (default: current).  The HP anchor passes the tracker's
    mission-start full value."""
    addr, width = cand
    if width == 1:
        v0 = int(gs.mem.u8(addr)) if value is None else int(value)
        gs.freeze("hp_freeze", addr, "u8", value=v0)
    else:
        v0 = int(gs.mem.u16(addr)) if value is None else int(value)
        gs.freeze("hp_freeze", addr, "u16", value=v0)
    return v0


def explore_once(p, chunks, trace, label, outdir,
                 hp_addr_override=None):
    gs = GameShark(p.mem)
    # grenades: published revision-matched instruction patch
    code = GSCode(BOMBS_PATCH)
    ok, hi = gs.branch_plausible(code.addr)
    trace.write({"type": "bombs_patch_check", "code": BOMBS_PATCH,
                 "branch_plausible": bool(ok), "pre_hi": hex(hi)})
    bombs_on = False
    if ok:
        gs.enable("bombs_patch", [code])
        bombs_on = True
        trace.write({"type": "cheat_engaged", "name": "bombs_patch",
                     "code": BOMBS_PATCH,
                     "mode": "CHEAT_ASSISTED_EXPLORATION"})
    if hp_addr_override is not None:
        hp = int(hp_addr_override, 16) \
            if isinstance(hp_addr_override, str) else hp_addr_override
        width = 1 if hp & 1 else 2
        v0 = engage_freeze(gs, (hp, width))
        hp_addr, hp_tier, hp_width = hp, "resume_override", width
        trace.write({"type": "cheat_engaged", "name": "hp_freeze",
                     "addr": hex(hp), "value": v0, "width": width,
                     "tier": hp_tier,
                     "mode": "CHEAT_ASSISTED_EXPLORATION"})
    else:
        hp_addr, hp_tier, hp_width = None, "not_yet_anchored", 2

    tracker = MinTracker(p)
    runner = ChunkRunner(p, gs, tracker)
    deaths = []                  # [{chunk, score}]
    ring = []                    # periodic checkpoint ledger
    cp_ring = 0
    trace.write({"type": "run_start", "label": label,
                 "mode": "CHEAT_ASSISTED_EXPLORATION",
                 "disclosed_cheats":
                     ["hp_freeze@" + hex(hp_addr) if hp_addr else
                      "hp_freeze:live_anchor_pending",
                      "bombs_patch:" + BOMBS_PATCH if bombs_on
                      else "bombs_patch:OFF"]})
    try:
        p.save_state("invexp_m1_start")   # resume point ONLY (never
        # loaded mid-run — reloads pull the attract script over play)
        trace.write({"type": "checkpoint_saved",
                     "state": "invexp_m1_start", "chunk": -1})
    except Exception as e:                     # noqa: BLE001
        trace.write({"type": "checkpoint_save_failed", "err": repr(e)})
    prev = runner.tel.snapshot(buttons=[], frame=p.core.frames_run)
    runner.reset(prev)
    hp_protection = ("confirmed" if hp_addr is not None else "pending")
    lives_addr, lives_width, lives_value = None, 0, None
    lives_frozen = []
    death_snaps = []
    snap_groups = []
    anchor_tried = set() if hp_addr is None else None
    score_max = int(p.mem.u32(SCORE_ADDR))
    warm_until = DEATH_WARMUP
    stop = None
    c = -1
    for c in range(chunks):
        if stop:
            break
        cur, evs, gain, churn_px, rgb_now = runner.chunk(c)
        for e in evs:
            trace.write({"type": "event", "chunk": c, **e})
        trace.write({"type": "chunk", "chunk": c,
                     "mode": "CHEAT_ASSISTED_EXPLORATION",
                     "telemetry": cur, "scroll_gain": gain,
                     "churn_px": churn_px,
                     "hp_addr": hex(hp_addr) if hp_addr else None,
                     "hp_value": int(p.mem.u16(hp_addr))
                     if hp_addr else None,
                     "policy_stats": dict(runner.policy.stats)})
        # ---- death: chunk-level score-collapse oracle (-30; the
        # telemetry event threshold -200 misses real respawns) plus
        # flags; DEATH_WARMUP skips the mission-init score reset, and
        # the max is REBASED when the warm-up expires (the reset
        # happens inside the warm-up — comparing against the stale
        # leftover max produces a false death at the boundary, inv15) ----
        score_now = int(p.mem.u32(SCORE_ADDR))
        if c == warm_until:
            score_max = score_now
        prev_max = score_max
        score_max = max(score_max, score_now)
        game_over = cur["flags_word"] != 0xFF
        death_evt = (c >= warm_until and
                     score_now < prev_max - 30) or \
            (c >= warm_until and
             any(e["type"] == "death_candidate" for e in evs))
        if game_over or death_evt:
            score_max = score_now
            warm_until = c + DEATH_WARMUP
            deaths.append({"chunk": c, "score": cur["score"]})
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": len(deaths),
                         "score": cur["score"],
                         "hp_protection": hp_protection})
            Image.fromarray(rgb_now).save(os.path.join(
                outdir, f"death_c{c:03d}.png")) \
                if rgb_now is not None else None
            # ---- LIVES strict-series scan, segmented at continues
            # (the lives reset to full at every accepted continue) —
            # freezing ALL candidates covers the real counter.
            if game_over:
                # close the current segment before the snapshot
                if death_snaps:
                    snap_groups.append(death_snaps)
                    death_snaps = []
            death_snaps.append(death_snapshot(p))
            if lives_addr is None and len(death_snaps) >= 2:
                groups = snap_groups + [death_snaps]
                lc = lives_candidates(p, groups)
                trace.write({"type": "lives_candidates",
                             "cands": [f"{hex(a)}w{w}"
                                       for a, w in lc],
                             "deaths_observed": len(death_snaps)})
                _log(f"lives candidates: "
                     f"{[f'{hex(a)}w{w}' for a, w in lc]}")
                if lc:
                    # freeze ALL strict-series candidates: the real
                    # lives counter is guaranteed to be among them;
                    # freezing a bystander (e.g. the POW counter) is
                    # cosmetic for exploration and fully disclosed.
                    frozen_list = []
                    for la, lw in lc:
                        if lw == 1:
                            cur_v = int(p.mem.u8(la))
                        else:
                            cur_v = int(p.mem.u16(la))
                        fv = cur_v if cur_v >= 2 else 2
                        gs.freeze(f"lives_freeze_{hex(la)}", la,
                                  "u8" if lw == 1 else "u16",
                                  value=fv)
                        frozen_list.append({"addr": hex(la),
                                            "width": lw, "value": fv})
                    lives_addr = frozen_list[0]["addr"]
                    lives_width = frozen_list[0]["width"]
                    lives_value = frozen_list[0]["value"]
                    lives_frozen = frozen_list
                    trace.write({"type": "cheat_engaged",
                                 "name": "lives_freeze_all",
                                 "frozen": frozen_list,
                                 "tier": "strict_series_-1_per_death",
                                 "deaths_observed": len(death_snaps),
                                 "mode":
                                 "CHEAT_ASSISTED_EXPLORATION"})
                    _log(f"LIVES frozen (all strict candidates): "
                         f"{[(f['addr'], f['value']) for f in frozen_list]}")
            # ---- LIVE A/B HP anchor (secondary; runs once the lives
            # freeze is safe — the operative cheat is lives_freeze) ----
            if hp_addr is None and lives_addr is not None:
                cands = tracker.droppers()
                trace.write({"type": "anchor_candidates",
                             "cands": [f"{hex(a)}w{w}"
                                       for a, w in cands],
                             "death_chunk": c})
                _log(f"anchor candidates at death c{c}: "
                     f"{[f'{hex(a)}w{w}' for a, w in cands]}")
                for X, width in cands:
                    if (X, width) in anchor_tried:
                        continue
                    anchor_tried.add((X, width))
                    full = tracker.value_for(X, width)
                    if not (0 < full <= 250):
                        continue          # implausible full value
                    v0 = engage_freeze(gs, (X, width), value=full)
                    trace.write({"type": "anchor_freeze_on",
                                 "cand": hex(X), "width": width,
                                 "value": v0, "window_from": c})
                    _log(f"testing freeze {hex(X)}w{width}={v0} "
                         f"from chunk {c}")
                    # run the test window IN the live loop
                    clean = True
                    for k in range(ANCHOR_TEST_CHUNKS):
                        cc = c + 1 + k
                        cur2, evs2, gain2, churn2, rgb2 = \
                            runner.chunk(cc)
                        s2 = int(p.mem.u32(SCORE_ADDR))
                        dec2 = (cc >= warm_until and
                                s2 < score_max - 30) or \
                            cur2["flags_word"] != 0xFF or \
                            any(e["type"] == "death_candidate"
                                for e in evs2)
                        score_max = max(score_max, s2)
                        trace.write({"type": "chunk",
                                     "chunk": cc,
                                     "mode":
                                     "CHEAT_ASSISTED_EXPLORATION",
                                     "telemetry": cur2,
                                     "scroll_gain": gain2,
                                     "churn_px": churn2,
                                     "hp_addr": hex(X),
                                     "hp_value": v0,
                                     "anchor_probe": hex(X),
                                     "policy_stats":
                                     dict(runner.policy.stats)})
                        if dec2:
                            clean = False
                            c = cc
                            cur, evs, gain, churn_px, rgb_now = \
                                cur2, evs2, gain2, churn2, rgb2
                            break
                    if clean:
                        hp_addr, hp_tier, hp_width = X, \
                            "in_run_live_ab", width
                        hp_protection = "confirmed"
                        trace.write({"type": "cheat_engaged",
                                     "name": "hp_freeze",
                                     "addr": hex(X), "value": v0,
                                     "width": width, "tier": hp_tier,
                                     "mode":
                                     "CHEAT_ASSISTED_EXPLORATION"})
                        _log(f"PLAYER HP = {hex(X)}w{width} "
                             "(live A/B: death cadence stopped)")
                        break
                    gs.disable("hp_freeze")
                    trace.write({"type": "anchor_freeze_rejected",
                                 "cand": hex(X), "width": width})
            if game_over:
                # the port: GAME OVER -> passive screens -> main menu;
                # continue taps are attempted EVERY game over and
                # disclosed (each accepted continue refills lives and
                # closes a strict-series segment; a clear reached after
                # continues is never a no-continue clear)
                resumed = False
                for i in range(14):
                    p.core.run(130, set())
                    for btn in ({"START"}, {"Y"}):
                        p.core.run(8, btn)
                        p.core.run(80, set())
                        if int(p.mem.u32(FLAGS_ADDR)) & 0xFF == 0xFF:
                            resumed = True
                            break
                    if resumed:
                        break
                trace.write({"type": "game_over_continue",
                             "chunk": c, "resumed": resumed,
                             "disclosed": True})
                if not resumed:
                    stop = "STOP_GAME_OVER_NO_RESUME"
                    trace.write({"type": "stop", "chunk": c,
                                 "reason": stop})
                    break
                # a continue refills lives -> new strict-series segment
                snap_groups.append(death_snaps)
                death_snaps = []
                score_max = int(p.mem.u32(SCORE_ADDR))
                warm_until = c + DEATH_WARMUP
                runner.reset(runner.tel.snapshot(
                    buttons=[], frame=p.core.frames_run))
                continue
        # ---- periodic ring checkpoint (save-only; never loaded
        # mid-run — reloads pull the attract script) ----
        if c % CP_PERIOD == CP_PERIOD - 1:
            slot = f"invexp_cp{cp_ring % 3}_{label}"
            p.save_state(slot)
            ring.append({"state": slot, "chunk": c,
                         "score": cur["score"]})
            cp_ring += 1
            trace.write({"type": "checkpoint_saved", "state": slot,
                         "chunk": c, "score": cur["score"]})
            Image.fromarray(rgb_now).save(os.path.join(
                outdir, f"cp_c{c:03d}_s{cur['score']}.png")) \
                if rgb_now is not None else None
        # ---- landmark capture ----
        if c % 25 == 0:
            Image.fromarray(rgb_now).save(os.path.join(
                outdir, f"exp_c{c:04d}_s{cur['score']}.png")) \
                if rgb_now is not None else None
    report = {
        "label": label,
        "mode": "CHEAT_ASSISTED_EXPLORATION",
        "disclosed_cheats":
            [f"lives_freeze@{lives_addr}={lives_value}"
             if lives_addr else "lives_freeze:not_anchored",
             "hp_freeze@" + hex(hp_addr) if hp_addr else
             "hp_freeze:not_anchored",
             "bombs_patch:" + BOMBS_PATCH if bombs_on
             else "bombs_patch:OFF"],
        "lives_freeze": {"frozen": lives_frozen,
                         "tier": "strict_series_-1_per_death"
                         if lives_frozen else None},
        "hp_anchor_tier": hp_tier,
        "hp_protection": hp_protection,
        "chunks_run": c + 1 if not stop and c >= 0 else c,
        "stop_reason": stop or "BUDGET_END",
        "max_score": max([e["score"] for e in ring] +
                         [d["score"] for d in deaths] + [0]),
        "ring": ring,
        "deaths": deaths,
        "never_a_no_cheat_clear": True,
    }
    trace.write({"type": "run_end", **report})
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=500)
    ap.add_argument("--tag", default="inv1")
    ap.add_argument("--resume", default=None,
                    help="savestate name to continue from; requires "
                         "--hp-addr when the anchor was already found")
    ap.add_argument("--hp-addr", default=None,
                    help="hex HP anchor recorded by the previous run")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir,
                          f"issue5_invexp_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    if args.resume:
        _log(f"=== invincible exploration (resume {args.resume}) ===")
        p = resume_play(args.resume)
        g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
        if not g.get("in_mission"):
            raise SystemExit("resume gate failed")
        fwmode = f"resume:{args.resume}"
        trace = JsonlTrace(os.path.join(
            outdir, f"trace_resume_{int(time.time())}.jsonl"))
        try:
            rep = explore_once(p, args.chunks, trace, args.tag,
                               outdir,
                               hp_addr_override=args.hp_addr)
        finally:
            trace.close()
    else:
        _log("=== invincible exploration (fresh boot) ===")
        p, fwmode = boot()
        trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))
        try:
            rep = explore_once(p, args.chunks, trace, args.tag,
                               outdir)
        finally:
            trace.close()
    rep["firmware_mode"] = fwmode
    outpath = os.path.join(outdir, "exploration_report.json")
    with open(outpath, "w") as f:
        json.dump(rep, f, indent=1)
    _log("report:", outpath)
    _log("stop=%s max_score=%d deaths=%d hp=%s tier=%s" % (
        rep["stop_reason"], rep["max_score"], len(rep["deaths"]),
        rep["disclosed_cheats"][0], rep["hp_anchor_tier"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
