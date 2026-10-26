#!/usr/bin/env python3
"""tetrade_lineclear.py — Issue #6 round 7: the RAM-truth greedy Tetris
bot (the Nortis-playbook goal for the last accepted game without it).

Runs THROUGH the generalized playloop tool (Playloop + the registered
"tetrade" policy TetradeLoopPolicy — one beetle boot per process):

  boot -> title -> START -> menu -> B -> Marathon (3-2-1)
       -> savestate anchor "r7_start"
       -> closed-loop greedy play (ps1play.agent.tetris_ai placement
          evaluator + per-cell taps, re-planned from live RAM at every
          queue drain; struct base re-verified against the calibration
          gates, profile anchor 0x1FECA0 / behavioral fallback)
       -> >= --target-lines LINE CLEARS (lines counters singleLine@
          base+2280 etc. increment in RAM; clear-moment PNGs)
       -> wrap-up: stop steering, hard-drop in place -> NATURAL game
          over (top-out, isGameOver @base+2312, game-over PNG)
       -> CONTINUE? refused with A (CIRCLE, source lose_game)
       -> title -> restart (START -> menu -> B) x --cycles
       -> fresh counters verified in RAM (reset_tetris_game) = the
          counters-reset half of the causality claim.

Evidence: lineclear_<tag>.jsonl + lineclear_report_<tag>.json + PNGs
(menu, gameplay, CLEAR moments, game over, restart title) — all in the
round-7 evidence dir (gitignored).  Honest verdicts only.
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

from playloop import (Playloop, TetradeLoopPolicy,  # noqa: E402
                      verdict_from)

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/ws_tetrade_r7"
EVID = os.path.join(REPO, "scratch", "issue6_round7_tetrade")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--target-lines", type=int, default=3)
    ap.add_argument("--max-pieces", type=int, default=150)
    ap.add_argument("--steps", type=int, default=8000,
                    help="hard act-loop cap (the wall-guard proxy; "
                         "each act ~= 1-6 frames)")
    ap.add_argument("--out-dir", default=EVID)
    ap.add_argument("--tag", default=time.strftime("%H%M%S"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    jl = open(os.path.join(args.out_dir,
                           f"lineclear_{args.tag}.jsonl"), "w")

    def J(ev):
        ev = {"t_s": round(time.time() - T0, 1), **ev}
        jl.write(json.dumps(ev, default=str) + "\n")
        jl.flush()
        print("[lc]", json.dumps(ev, default=str)[:220], flush=True)

    T0 = time.time()
    OUT = {"script": "tetrade_lineclear", "tag": args.tag,
           "started": time.strftime("%FT%TZ"), "cue": CUE,
           "workspace": WS, "args": vars(args)}
    loop = Playloop(CUE, WS, journal=J)
    booted = False
    responded = False
    policy = None
    try:
        b = loop.boot()
        booted = bool(b["booted"])
        responded = b["padbuff_hits"] > 0
        OUT["boot"] = {k: b.get(k) for k in ("booted", "padbuff_hits")}
        J({"ev": "boot", **OUT["boot"]})
        # durable anchor BEFORE any steering (calibration ladder keeps
        # its own "r7_fresh"; this one guards the lineclear run)
        loop.p.save_state("r7_start")
        J({"ev": "checkpoint_saved", "name": "r7_start"})
        policy = TetradeLoopPolicy(loop=loop, cycles=args.cycles,
                                   out_dir=args.out_dir,
                                   target_lines=args.target_lines,
                                   max_pieces=args.max_pieces)
        report = loop.run(policy, args.steps, png_every=250,
                          out_dir=args.out_dir)
    finally:
        try:
            loop.close()
        except Exception:
            pass
    OUT["run_report"] = report
    OUT["policy_events"] = policy.events if policy else []
    OUT["totals"] = dict(policy.totals) if policy else {}
    OUT["struct_base"] = getattr(policy, "base", None)
    OUT["anchor_src"] = getattr(policy, "anchor_src", None)
    flags = policy.verdict_flags() if policy else {}
    OUT["verdict_flags"] = flags
    OUT["verdict"] = verdict_from({**(report or {}), **flags},
                                  booted, responded)
    OUT["wall_s"] = round(time.time() - T0, 1)
    # per-cycle digest
    cyc = {}
    for e in OUT["policy_events"]:
        c = cyc.setdefault(e.get("cycle", 0), {"clears": 0, "pieces": 0,
                                               "score_max": 0})
        if e["ev"] == "line_clear":
            c["clears"] += e["delta"]
            c.setdefault("clears_detail", []).append(
                {k: e[k] for k in ("delta", "lines_total", "score",
                                   "single", "double", "triple",
                                   "tetra")})
        elif e["ev"] == "game_over":
            c["over_score"] = e["score"]
            c["over_lines"] = e["lines_total"]
        elif e["ev"] == "restart_counters_reset":
            c_next = cyc.setdefault(e["cycle"], {"clears": 0, "pieces": 0,
                                                 "score_max": 0})
            c_next["fresh_counters"] = e["struct"]
    OUT["cycles"] = cyc
    with open(os.path.join(args.out_dir,
                           f"lineclear_report_{args.tag}.json"), "w") as f:
        json.dump(OUT, f, indent=1, default=str)
    J({"ev": "LC_DONE", "verdict": OUT["verdict"],
       "totals": OUT["totals"], "wall_s": OUT["wall_s"]})
    print("lineclear verdict:", OUT["verdict"],
          "clears:", OUT["totals"].get("clears"),
          "pieces:", OUT["totals"].get("pieces"),
          "wall_s:", OUT["wall_s"])
    return 0 if OUT["totals"].get("clears") else 1


if __name__ == "__main__":
    sys.exit(main())
