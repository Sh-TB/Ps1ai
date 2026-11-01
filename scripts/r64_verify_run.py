#!/usr/bin/env python3
"""r64_verify_run.py — R64 acceptance analysis.

Parses a real `python3 -m ps1play play tetrade` run directory
(episodes.jsonl + events.jsonl + per-episode traces) and writes the
committed acceptance summary:

  * the boot ledger (attempts, ready base)
  * per-episode records (result, decisions, real button presses,
    lines, death reason)
  * from the traces (the 222-value RAM vectors): pieces hard-dropped,
    NEXT-promotion cross-check (the piece that becomes current after a
    drop must be the NEXT the policy planned against), line-clear
    events with score-delta forensics (level 0: SINGLE adds 0 — any
    score delta on a clear row comes from the hard-drop cells,
    +2/cell), and the action histogram.
"""
import json
import os
import sys
from collections import Counter

import numpy as np

RUN = sys.argv[1] if len(sys.argv) > 1 else "/tmp/r64_accept"
OUT = sys.argv[2] if len(sys.argv) > 2 else \
    "/home/z/my-project/ps1ai/data/r64/r64_acceptance_summary.json"


def rows_of(path):
    with open(path) as f:
        for line in f:
            yield json.loads(line)


def main():
    eps = [r for r in rows_of(os.path.join(RUN, "episodes.jsonl"))]
    evs = [r for r in rows_of(os.path.join(RUN,
                                           "events.jsonl"))]
    summary = {
        "run_dir": RUN,
        "boot_ledger": {
            "emulator_boots": sum(1 for e in evs
                                  if e["event"] == "emulator_boot"),
            "boot_retries": sum(1 for e in evs
                                if e["event"] == "boot_retry"),
            "ready_base": next((e.get("hex_base") for e in evs
                                if e["event"] == "tetrade_ready"),
                               None),
        },
        "episodes": [],
        "totals": {},
    }
    tot = Counter()
    for ep in eps:
        n = ep["episode"]
        rec = {k: ep[k] for k in ("episode", "seed_k", "result",
                                  "death_reason", "pipes", "frames",
                                  "actions", "decisions",
                                  "trace_sha256", "wall_s")}
        trace = ep.get("trace_file")
        pieces = 0
        promotions_ok = promotions_checked = 0
        clears = []
        actions = Counter()
        pending_next = None
        pending_drop_type = None
        prev_lines = 0
        prev_score = None
        if trace and os.path.exists(trace):
            for row in rows_of(trace):
                v = np.asarray(row["x"], dtype=np.float32)
                a = row["a"]
                actions[a] += 1
                tslot = v[200:207]
                ptype = (int(np.argmax(tslot)) + 1
                         if tslot.sum() > 0.5 else 0)
                nslot = v[210:217]
                next_type = (int(np.argmax(nslot)) + 1
                             if nslot.sum() > 0.5 else 0)
                lines = int(v[218])
                score = int(v[217])
                if a == "HARD_DROP":
                    pieces += 1
                    pending_next = next_type
                    pending_drop_type = ptype
                elif pending_next is not None:
                    # the lock/respawn window still shows the dropped
                    # piece (or the transient 0); the promotion is
                    # decided by the first LIVE type that differs
                    # from the dropped piece (R63 read after the
                    # settle — same semantics, frame-accurate here)
                    if ptype == 0 or ptype == pending_drop_type:
                        pass
                    else:
                        promotions_checked += 1
                        if ptype == pending_next:
                            promotions_ok += 1
                        pending_next = None
                        pending_drop_type = None
                if lines > prev_lines:
                    clears.append({"at_step": row["step"],
                                   "from": prev_lines, "to": lines,
                                   "score_before": prev_score,
                                   "score_after": score,
                                   "score_delta": (score -
                                                   prev_score
                                                   if prev_score
                                                   is not None
                                                   else None)})
                prev_lines = lines
                prev_score = score
        rec.update({
            "pieces_hard_dropped": pieces,
            "next_promotion_check": {
                "checked": promotions_checked,
                "ok": promotions_ok,
            },
            "line_clears": clears,
            "action_histogram": dict(actions),
            "trace": os.path.basename(trace) if trace else None,
        })
        summary["episodes"].append(rec)
        tot["pieces"] += pieces
        tot["lines"] += ep["pipes"]
        tot["presses"] += ep["actions"]
        tot["frames"] += ep["frames"]
        tot["deaths"] += 1 if ep["result"] == "death" else 0
    summary["totals"] = dict(tot)
    summary["verdict"] = {
        "natural_game_overs": tot["deaths"],
        "line_clears_via_product": tot["lines"],
        "restart_flow_exercised": len(eps) >= 2,
        "fresh_start_after_restart": all(
            e["seed_k"] for e in eps) and len(eps) >= 2,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary["totals"]))
    print(json.dumps(summary["verdict"]))
    print("summary ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
