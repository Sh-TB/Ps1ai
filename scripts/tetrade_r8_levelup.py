#!/usr/bin/env python3
"""tetrade_r8_levelup.py — Issue #6 round 8 (Task 8-c): LEVEL-UP causality
for Tetrade, on top of the round-7 bot (REUSED, unmodified).

Upstream ground truth pinned from the actual source (MIT
Logan-Campbell/Tetrade, src/main.c @ tag v1.0 =
commit 5155664152162a0dc04dc1f0d4f3c807c1e15388; local clone
scratch/issue6_round8_tetrade/tetrade_upstream):

  LEVEL-UP RULE  main.c:395-404 (check_lines): totalLines is computed
      from the counters BEFORE this clear increments them (line 397);
      `if(totalLines >= LEVEL_GOAL * (game->level+1)) game->level++;`
      (lines 399-403) with LEVEL_GOAL 8 (line 65).  The scoring switch
      (lines 406-425) runs AFTER the possible level++, so the clearing
      action that flips the level scores at the NEW level.  => with all
      singles the level flips on the 9th line (pre-clear total 8 >= 8).
  DROP RATE      main.c:1078-1080: dropRate = (level > 0) ?
      FixedToInt(DivFixed(IntToFixed(BASE_DROP_RATE),
      LEVEL_DROP_RATE_MULTI*level)) : BASE_DROP_RATE; BASE_DROP_RATE 30
      (line 50), LEVEL_DROP_RATE_MULTI 4506 = 1.10 in 12.12 fixed
      (fpmath.h:25-31) => level 1 = (30<<12)*4096/4506 >> 12 = 27
      f/cell (level 2 = 13).  A y-step fires when gameTimer.time %
      dropRate == 0 (line 1083) => consecutive free-fall y-steps are
      exactly dropRate frames apart.
  SCORE          main.c:59-64 + 406-425: single 200*level,
      double 500*level, triple 700*level, tetrade 1000*level (level
      read AFTER level++); hard drop +2/cell (line 1017), soft drop
      +1/cell (line 1088).  reset_tetris_game zeroes level (line 766)
      — every life starts at level 0, so the flip must happen within
      one life (>= 9 lines all-singles).

MEASUREMENT (one beetle boot per process — the lab's hard rule):
  boot -> title -> START -> menu -> B -> Marathon via the round-7
  TetradeLoopPolicy (scripts/playloop.py, REUSED unchanged) — its
  calibration ladder re-verifies the live struct gates (base
  0x1FECA0 profile anchor + input-causality fallback).  This driver
  then executes every policy segment FRAME BY FRAME and records
  per-frame telemetry (type/x/y/score/single/double/triple/tetra/
  level/over/paused/ghost_y/set_time + active buttons) to JSONL.
  Events: y-step cadence samples (clean windows only: same piece,
  +1 cell, no UP/DOWN held), line clears (score decomposed into
  hard-drop points 2*dy + clear table*level), LEVEL FLIPS (PNG +
  counters), game overs.  NO RAM WRITES to game state anywhere —
  the level-up must come from natural clears only.

Verdicts (honest): (a) LEVEL_UP_OBSERVED, (b) SPEED_CAUSAL
(median f/y-step level 0 vs >=1, n>=20 each, source predicts
30 -> 27), (c) SCORE_CAUSAL (clear deltas == table x level).
Evidence: scratch/issue6_round8_tetrade/ (report + JSONL + PNGs).
"""
import argparse
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playloop import Playloop, TetradeLoopPolicy  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/ws_tetrade_r8"
EVID = os.path.join(REPO, "scratch", "issue6_round8_tetrade")
OVERRIDES = {b"beetle_psx_override_bios": b"openbios"}

# source-predicted constants (cited above)
SRC = {
    "repo": "https://github.com/Logan-Campbell/Tetrade",
    "file": "src/main.c",
    "commit": "5155664152162a0dc04dc1f0d4f3c807c1e15388 (tag v1.0)",
    "LEVEL_GOAL": 8,                     # main.c:65
    "BASE_DROP_RATE_L0": 30,             # main.c:50
    "drop_rate": {1: 27, 2: 13},         # 12.12 fixed math on line 1080
    "clear_table": {1: 200, 2: 500, 3: 700, 4: 1000},   # main.c:59-62
    "hard_drop_per_cell": 2,             # main.c:64,1017
    "soft_drop_per_cell": 1,             # main.c:63,1088
}

FIELDS = ("tet_type", "tet_x", "tet_y", "score", "single", "double",
          "triple", "tetra", "level", "over", "paused", "ghost_y")
# not in playloop's OFF map — read at the calibrated base via the
# source offsets (main.c layout, same ones tetrade_calib verified):
EXTRA_OFF = {"set_time": 2300, "move_cd": 2296}


class _ShimObs:
    """Minimal obs for the policy (PNG capture handled by this driver)."""
    frame = None
    madiff = None
    padbuff_hits = 0
    state_raw = None
    step = -1


class R8Driver:
    """Frame-granular executor around the UNMODIFIED round-7 policy."""

    def __init__(self, loop, policy, trace, out_dir, tag):
        self.loop = loop
        self.policy = policy
        self.core = loop.p.core
        self.mem = loop.p.mem
        self.trace = trace
        self.out_dir = out_dir
        self.tag = tag
        self.prev = None
        self.prev_y_fc = None        # fc of the previous +1 y-step
        self.prev_y_piece = None     # piece type at that y-step
        self.steps = []              # natural y-step events (fc/level/...)
        self.clear_n = 0
        self.events = []
        self.level_flips = []
        self.clears = []
        self.cadence = {}            # level -> [gap,...]
        self.piece_ud = False        # UP/DOWN seen during current piece
        self.stop_reason = None

    def ev(self, kind, **kw):
        e = {"ev": kind, "fc": self.core.frames_run, **kw}
        self.events.append(e)
        self.loop.journal(e)
        return e

    def png(self, name):
        try:
            from PIL import Image
            arr = self.core.frame_rgb()
            if arr is None:
                return None
            path = os.path.join(self.out_dir, f"{name}.png")
            Image.fromarray(arr).save(path)
            return path
        except Exception:
            return None

    # ---- per-frame telemetry + event detection ----
    def frame(self, btns):
        self.core.run(1, btns)
        p = self.policy
        fc = self.core.frames_run
        if p.base is None:
            row = {"fc": fc, "state": p.state}
            self.trace.write(json.dumps(row) + "\n")
            return
        g = p.base
        m = self.mem
        cur = {k: m.u32(g + p.OFF[k]) for k in FIELDS}
        for k, off in EXTRA_OFF.items():
            cur[k] = m.u32(g + off)
        for k in ("tet_type", "tet_x", "tet_y", "ghost_y"):
            if cur[k] >= 2 ** 31:          # the game stores signed ints
                cur[k] -= 2 ** 32
        cur["fc"] = fc
        cur["cycle"] = p.cycle
        cur["state"] = p.state
        cur["inp"] = "".join(sorted(b[0] for b in btns)) if btns else ""
        cur["lines"] = (cur["single"] + 2 * cur["double"]
                        + 3 * cur["triple"] + 4 * cur["tetra"])
        prev = self.prev
        self.trace.write(json.dumps(cur, default=str) + "\n")
        if prev is not None and prev.get("state") != cur["state"]:
            self.ev("policy_state", frm=prev.get("state"), to=cur["state"])
        if prev is None or prev["fc"] != fc - 1:
            prev = None               # frame gap (calib internals) — resync

        # --- piece identity / y-step cadence ---
        if cur["inp"] and any(c in cur["inp"] for c in ("U", "D")):
            self.piece_ud = True          # UP/DOWN touched this piece
        typ = cur["tet_type"]
        if prev is not None and typ == prev["tet_type"] and typ > 0:
            dy = cur["tet_y"] - prev["tet_y"]
            if dy == 1 and not self.piece_ud:
                self.steps.append({"fc": fc, "level": cur["level"],
                                   "cycle": cur["cycle"], "piece": typ})
                if (self.prev_y_fc is not None
                        and self.prev_y_piece == typ):
                    self.cadence.setdefault(cur["level"],
                                            []).append(fc - self.prev_y_fc)
                self.prev_y_fc = fc
                self.prev_y_piece = typ
        if prev is not None and typ != prev["tet_type"]:
            self.prev_y_fc = None
            self.piece_ud = False         # new piece: reset assistance tag
            if typ == -1 and prev["tet_type"] > 0:
                self.ev("piece_locked", piece=prev["tet_type"],
                        y=prev["tet_y"], score=cur["score"],
                        lines=cur["lines"], level=cur["level"])

        # --- level flip ---
        if prev is not None and cur["level"] != prev["level"]:
            thr = SRC["LEVEL_GOAL"] * (prev["level"] + 1)
            e = self.ev("level_flip", frm=prev["level"], to=cur["level"],
                        lines_prev=prev["lines"], lines=cur["lines"],
                        single=cur["single"], double=cur["double"],
                        triple=cur["triple"], tetra=cur["tetra"],
                        score_prev=prev["score"], score=cur["score"],
                        goal=SRC["LEVEL_GOAL"],
                        threshold_ok=bool(prev["lines"] >= thr))
            e["png"] = self.png(
                f"levelflip_c{cur['cycle']}_fc{fc}")
            self.level_flips.append(e)

        # --- line clear (counters moved) ---
        if prev is not None and cur["lines"] > prev["lines"]:
            d = cur["lines"] - prev["lines"]
            # drop distance of the piece that just locked: the struct
            # already shows the NEXT piece on a hard-drop frame (the
            # game promotes at main.c:1045 in the same frame), so use
            # the PREVIOUS frame's ghost_y - y (ghost = last_valid_y,
            # main.c:1098) — 0 for a gravity lock.
            dy_drop = 0
            if prev["tet_type"] and prev["tet_type"] > 0:
                dy_drop = max(0, prev["ghost_y"] - prev["tet_y"])
            self.clear_n += 1
            e = self.ev("line_clear", cycle=cur["cycle"], delta=d,
                        level=cur["level"], lines=cur["lines"],
                        single=cur["single"], double=cur["double"],
                        triple=cur["triple"], tetra=cur["tetra"],
                        score_prev=prev["score"], score=cur["score"],
                        dy_drop=dy_drop)
            e["png"] = self.png(
                f"clear_c{cur['cycle']}_n{self.clear_n}_fc{fc}")
            self.clears.append(e)

        # --- score change without a clear (drop points) ---
        elif prev is not None and cur["score"] != prev["score"]:
            dy = None
            if prev["tet_type"] and prev["tet_type"] > 0:
                dy = max(0, prev["ghost_y"] - prev["tet_y"])
            self.ev("score_delta", level=cur["level"],
                    frm=prev["score"], to=cur["score"],
                    dy_drop=dy, inp=cur["inp"])

        if prev is None or cur["over"] != prev.get("over"):
            if cur["over"]:
                self.ev("game_over", cycle=cur["cycle"],
                        score=cur["score"], lines=cur["lines"],
                        level=cur["level"])
                self.png(f"gameover_c{cur['cycle']}_fc{fc}")
        self.prev = cur

    # ---- main loop ----
    def run(self, max_steps, max_frames, wall_budget, t0):
        step = 0
        while True:
            p = self.policy
            if p.state in ("done", "dead"):
                self.stop_reason = f"policy_{p.state}"
                break
            if p.frames_done > max_frames:
                self.stop_reason = "frame_budget"
                break
            if time.time() - t0 > wall_budget:
                self.stop_reason = "wall_budget"
                break
            seg = p.act(step, _ShimObs())
            if not seg:
                self.stop_reason = "policy_returned_none"
                break
            btns, n = seg
            for _ in range(n):
                self.frame(btns)
            step += 1
        return step


def cadence_summary(gaps, steps):
    """gaps = same-piece consecutive y-step distances; steps = all
    natural y-step events.  The source drops at time%dropRate==0
    (main.c:1083) so step frames are phase-locked to gameTimer.time:
    at level 0 every step fc is congruent mod 30, at level 1 mod 27.
    Concentration in the right modulus (and NOT in the wrong one) is
    the causal signature; same-piece gaps give the direct median."""
    out = {}
    if gaps:
        s = sorted(gaps)
        n = len(s)
        med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        hist = {}
        for v in gaps:
            hist[v] = hist.get(v, 0) + 1
        out["gaps"] = {"n": n, "median": med, "min": s[0],
                       "max": s[-1], "hist": hist}
    else:
        out["gaps"] = {"n": 0}
    conc = {}
    for r in (30, 27):
        residues = {}
        for st in steps:
            # gameTimer restarts each life (reset_tetris_game, main.c:793)
            # so the phase is per (cycle, level) bucket
            key = (st["cycle"], st["fc"] % r)
            residues[key] = residues.get(key, 0) + 1
        if residues:
            best = max(residues.values())
            conc[r] = {"n_steps": len(steps),
                       "buckets": len({k[0] for k in residues}),
                       "distinct_phase_keys": len(residues),
                       "top_residue_count": best,
                       "concentration": round(best / len(steps), 3)}
        else:
            conc[r] = {"n_steps": 0}
    out["phase"] = conc
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=4)
    ap.add_argument("--target-lines", type=int, default=14,
                    help="per-life wrap threshold; the level flip is "
                         "predicted at 9 lines (all-singles), so the bot "
                         "must keep steering well past it")
    ap.add_argument("--max-pieces", type=int, default=240)
    ap.add_argument("--max-frames", type=int, default=400000)
    ap.add_argument("--wall-budget", type=float, default=500.0)
    ap.add_argument("--seed-idle", type=int, default=0,
                    help="idle frames after boot BEFORE the policy nav "
                         "starts.  Real-input timing wobble: the game "
                         "seeds srand(mainTimer.time) at the title "
                         "START press (main.c:1118-1122), so this "
                         "changes the piece sequence between attempts "
                         "without touching any RAM.")
    ap.add_argument("--out-dir", default=EVID)
    ap.add_argument("--tag", default=time.strftime("%H%M%S"))
    ap.add_argument("--refixverdict", action="store_true",
                    help="offline: recompute the verdicts block of "
                         "r8_report_<tag>.json from its own cadence/"
                         "flip/clear data (no emulator, no boot) and "
                         "rewrite the report in place.  Used after a "
                         "verdict-logic fix; the patch is recorded in "
                         "the report.")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()

    if args.refixverdict:
        rp = os.path.join(args.out_dir, f"r8_report_{args.tag}.json")
        with open(rp) as f:
            OUT = json.load(f)
        old = {k: v.get("verdict") for k, v
               in OUT.get("verdicts", {}).items()}
        c0 = OUT.get("cadence", {}).get("0", {})
        c1 = OUT.get("cadence", {}).get("1", {})

        def _ph(c, r):
            ph = c.get("phase", {})
            return ph.get(str(r), ph.get(r, {}))   # JSON keys are str

        def _locked(c, r):
            ph = _ph(c, r)
            return bool(ph and ph.get("n_steps", 0) >= 20
                        and ph.get("distinct_phase_keys")
                        == ph.get("buckets"))

        def _spread(c, r):
            ph = _ph(c, r)
            return bool(ph and ph.get("n_steps", 0) >= 20
                        and ph.get("distinct_phase_keys")
                        > ph.get("buckets"))

        v = OUT.get("verdicts", {})
        n0 = _ph(c0, 30).get("n_steps", 0)
        n1 = _ph(c1, 27).get("n_steps", 0)
        if n0 >= 20 and n1 >= 20:
            g0 = c0.get("gaps", {})
            g1 = c1.get("gaps", {})
            gmed0, gmed1 = g0.get("median"), g1.get("median")
            gap_ok = ((g0.get("n", 0) < 20 or gmed0 == 30)
                      and (g1.get("n", 0) < 20 or gmed1 == 27))
            ok = (_locked(c0, 30) and _spread(c0, 27)
                  and _locked(c1, 27) and _spread(c1, 30) and gap_ok)
            v["b_speed_causal"] = {
                "verdict": "CAUSAL" if ok else "MISMATCH",
                "level0": c0, "level1": c1,
                "gap_median_level0": gmed0,
                "gap_median_level1": gmed1,
                "phase_locked": {"level0_mod30": _locked(c0, 30),
                                 "level0_mod27_spread": _spread(c0, 27),
                                 "level1_mod27": _locked(c1, 27),
                                 "level1_mod30_spread": _spread(c1, 30)},
                "source_predicts": {"level0": SRC["BASE_DROP_RATE_L0"],
                                    "level1": SRC["drop_rate"][1]}}
        OUT["verdicts"] = v
        OUT["refixverdict"] = {"previous": old,
                               "reason": "verdict-logic fix: phase "
                                        "locking is per (cycle, level) "
                                        "bucket (gameTimer restarts "
                                        "each life), so global "
                                        "concentration was the wrong "
                                        "metric; recomputed offline "
                                        "from the same measured data "
                                        "(no emulator, no boot)"}
        with open(rp, "w") as f:
            json.dump(OUT, f, indent=1, default=str)
        print("refixverdict:", rp)
        print(json.dumps({k: x.get("verdict")
                          for k, x in v.items()}, indent=1))
        return 0

    tag = args.tag
    trace_path = os.path.join(args.out_dir, f"r8_frames_{tag}.jsonl")
    ev_path = os.path.join(args.out_dir, f"r8_events_{tag}.jsonl")
    rep_path = os.path.join(args.out_dir, f"r8_report_{tag}.json")
    trace = open(trace_path, "w")
    evf = open(ev_path, "w")

    def J(e):
        e = {"t_s": round(time.time() - t0, 1), **e}
        evf.write(json.dumps(e, default=str) + "\n")
        evf.flush()
        print("[r8]", json.dumps(e, default=str)[:200], flush=True)

    OUT = {"script": "tetrade_r8_levelup", "tag": tag,
           "started": time.strftime("%FT%TZ"),
           "cue": CUE, "workspace": WS, "args": vars(args),
           "source": SRC, "overrides": {"beetle_psx_override_bios":
                                        "openbios"}}
    loop = None
    policy = None
    drv = None
    try:
        loop = Playloop(CUE, WS, journal=J, var_overrides=OVERRIDES)
        b = loop.boot()
        OUT["boot"] = {k: b.get(k) for k in ("booted", "padbuff_hits")}
        J({"ev": "boot", **OUT["boot"]})
        loop.p.save_state("r8_start")
        J({"ev": "checkpoint_saved", "name": "r8_start"})
        if args.seed_idle > 0:
            loop.p.core.run(args.seed_idle, set())
            J({"ev": "seed_idle", "frames": args.seed_idle,
               "fc": loop.p.core.frames_run})
        policy = TetradeLoopPolicy(loop=loop, cycles=args.cycles,
                                   out_dir=args.out_dir,
                                   target_lines=args.target_lines,
                                   max_pieces=args.max_pieces,
                                   max_frames=args.max_frames)
        drv = R8Driver(loop, policy, trace, args.out_dir, tag)
        steps = drv.run(args.max_frames + 4000, args.max_frames,
                        args.wall_budget, t0)
        OUT["steps"] = steps
        OUT["stop_reason"] = drv.stop_reason
        OUT["struct_base"] = policy.base
        OUT["struct_base_hex"] = hex(policy.base) if policy.base else None
        OUT["anchor_src"] = policy.anchor_src
        OUT["totals"] = dict(policy.totals)
        OUT["cycles_played"] = policy.cycle
        OUT["policy_events_tail"] = policy.events[-12:]

        # ---- analysis ----
        OUT["level_flips"] = drv.level_flips
        OUT["cadence"] = {}
        for lvl in sorted(drv.cadence):
            sub_steps = [s for s in drv.steps if s["level"] == lvl]
            OUT["cadence"][str(lvl)] = cadence_summary(
                drv.cadence[lvl], sub_steps)
        OUT["n_steps_total"] = len(drv.steps)
        # clear decomposition: delta score minus hard-drop points vs table
        for e in drv.clears:
            drop_pts = SRC["hard_drop_per_cell"] * (e.get("dy_drop") or 0)
            e["drop_pts_est"] = drop_pts
            e["clear_pts_est"] = e["score"] - e["score_prev"] - drop_pts
            e["expected_pts"] = SRC["clear_table"].get(
                e["delta"], 0) * e["level"]
            e["match"] = bool(e["clear_pts_est"] == e["expected_pts"])
        OUT["clears"] = drv.clears
        lv0 = [c for c in drv.clears if c["level"] == 0]
        lv1p = [c for c in drv.clears if c["level"] >= 1]
        OUT["clear_score_level0"] = {
            "n": len(lv0),
            "all_zero_clear_pts": bool(lv0) and all(
                c["clear_pts_est"] == 0 for c in lv0)}
        OUT["clear_score_level1p"] = {
            "n": len(lv1p),
            "all_match_table": bool(lv1p) and all(
                c["match"] for c in lv1p)}

        # ---- verdicts (honest) ----
        flips_up = [f for f in drv.level_flips if f["to"] > f["frm"]]
        flips_01 = [f for f in flips_up if f["frm"] == 0]
        v = {}
        if flips_01:
            f0 = flips_01[0]
            v["a_level_up_observed"] = {
                "verdict": ("CAUSAL (natural play; no RAM writes)")
                if all(f.get("threshold_ok") for f in flips_up) else
                "OBSERVED (some flip failed the source threshold check)",
                "fc": f0["fc"], "to_level": f0["to"],
                "lines_at_flip_prev": f0["lines_prev"],
                "lines_at_flip": f0["lines"],
                "threshold_rule": "totalLines >= LEVEL_GOAL(8) * "
                                  "(level+1), pre-clear counters "
                                  "(main.c:397-403)",
                "n_0_to_1_flips": len(flips_01),
                "n_upward_flips": len(flips_up),
                "all_threshold_ok": bool(all(
                    f.get("threshold_ok") for f in flips_up)),
                "png": f0.get("png")}
        else:
            v["a_level_up_observed"] = {
                "verdict": "INCONCLUSIVE",
                "reason": ("level never left 0 within budget; "
                           "max lines reached = %s"
                           % max([c["lines"] for c in drv.clears]
                                 or [0]))}
        c0 = OUT["cadence"].get("0", {})
        c1 = OUT["cadence"].get("1", {})

        def _ph(c, r):
            return (c.get("phase", {}).get(r, {})
                    if isinstance(c, dict) else {})

        def _locked(c, r):
            """every (cycle) bucket has exactly ONE step-frame residue
            mod r => the y-step cadence is exactly r frames."""
            ph = _ph(c, r)
            return bool(ph and ph.get("n_steps", 0) >= 20
                        and ph.get("distinct_phase_keys")
                        == ph.get("buckets"))

        def _spread(c, r):
            ph = _ph(c, r)
            return bool(ph and ph.get("n_steps", 0) >= 20
                        and ph.get("distinct_phase_keys")
                        > ph.get("buckets"))

        n0 = _ph(c0, 30).get("n_steps", 0)
        n1 = _ph(c1, 27).get("n_steps", 0)
        if n0 >= 20 and n1 >= 20:
            ok0 = _locked(c0, 30) and _spread(c0, 27)
            ok1 = _locked(c1, 27) and _spread(c1, 30)
            g0 = c0.get("gaps", {})
            g1 = c1.get("gaps", {})
            gmed0 = g0.get("median")
            gmed1 = g1.get("median")
            gap_ok = ((g0.get("n", 0) < 20 or gmed0 == 30)
                      and (g1.get("n", 0) < 20 or gmed1 == 27))
            v["b_speed_causal"] = {
                "verdict": ("CAUSAL" if (ok0 and ok1 and gap_ok)
                            else "MISMATCH"),
                "level0": c0, "level1": c1,
                "gap_median_level0": gmed0, "gap_median_level1": gmed1,
                "phase_locked": {"level0_mod30": _locked(c0, 30),
                                 "level0_mod27_spread": _spread(c0, 27),
                                 "level1_mod27": _locked(c1, 27),
                                 "level1_mod30_spread": _spread(c1, 30)},
                "source_predicts": {"level0": SRC["BASE_DROP_RATE_L0"],
                                    "level1": SRC["drop_rate"][1]}}
        else:
            v["b_speed_causal"] = {
                "verdict": "INCONCLUSIVE",
                "reason": "n<20 natural y-steps in a level bucket",
                "level0": c0, "level1": c1}
        if lv1p and OUT["clear_score_level1p"]["all_match_table"]:
            v["c_score_causal"] = {
                "verdict": "CAUSAL",
                "n_level1p_clears": len(lv1p),
                "deltas": [{"delta": c["delta"], "level": c["level"],
                            "clear_pts_est": c["clear_pts_est"],
                            "expected_pts": c["expected_pts"]}
                           for c in lv1p]}
        elif lv1p:
            v["c_score_causal"] = {"verdict": "MISMATCH",
                                   "detail": OUT["clear_score_level1p"],
                                   "clears": lv1p}
        else:
            v["c_score_causal"] = {
                "verdict": "INCONCLUSIVE",
                "reason": "no line clear at level >=1",
                "level0_zero_check": OUT["clear_score_level0"]}
        OUT["verdicts"] = v
        OUT["wall_s"] = round(time.time() - t0, 1)
        J({"ev": "R8_DONE", "stop": drv.stop_reason,
           "verdicts": {k: x.get("verdict") for k, x in v.items()},
           "wall_s": OUT["wall_s"]})
    except Exception as ex:                     # honest failure record
        OUT["error"] = repr(ex)
        J({"ev": "EXC", "err": repr(ex)})
        raise
    finally:
        with open(rep_path, "w") as f:
            json.dump(OUT, f, indent=1, default=str)
        trace.close()
        evf.close()
        if loop is not None:
            try:
                loop.close()
            except Exception:
                pass
    print("report:", rep_path)
    print(json.dumps(OUT.get("verdicts", {}),
                     indent=1, default=str)[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
