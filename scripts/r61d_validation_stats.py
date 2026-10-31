#!/usr/bin/env python3
"""r61d_validation_stats.py — R61 Sections 7+8: merge the parallel
validation rows, verify determinism, and compute the final performance
statistics on the pre-registered fresh split.

Merges (main + shard0 + shard1), dedupes (policy,k,rep) triples —
duplicate groups are the CROSS-PROCESS determinism check and must all
be byte-identical in (result, pipes, frames, flaps, trace_sha256) —
then reports per-policy and per-seed statistics on the 30-seed split.
"""
import json
import os
import statistics
from collections import defaultdict

REPO = "/home/z/my-project/ps1ai"
SCR = os.path.join(REPO, "scratch", "r61")
FILES = ["r61_validation_rows.jsonl", "r61_val_shard0.jsonl",
         "r61_val_shard1.jsonl"]
OUT = os.path.join(SCR, "r61_validation_merged.jsonl")
SPLIT = os.path.join(REPO, "data", "learn", "r61_validation_split.json")


def main():
    rows, seen, dup_groups, dup_bad = [], {}, 0, 0
    for fn in FILES:
        p = os.path.join(SCR, fn)
        if not os.path.exists(p):
            continue
        for line in open(p):
            r = json.loads(line)
            key = (r["policy"], r["k"], r["rep"])
            sig = (r["result"], r["pipes"], r["frames"], r["flaps"],
                   r["trace_sha256"])
            if key in seen:
                dup_groups += 1
                if seen[key] != sig:
                    dup_bad += 1
                    print("NONDETERMINISM", key, seen[key], sig)
                continue
            seen[key] = sig
            rows.append(r)
    assert dup_bad == 0, f"{dup_bad} nondeterministic duplicate groups"
    print(f"rows kept: {len(rows)} (cross-process dup groups checked: "
          f"{dup_groups}, all byte-identical)")

    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    seeds = json.load(open(SPLIT))["validation_seeds"]
    byp = defaultdict(list)
    for r in rows:
        byp[r["policy"]].append(r)
    for pol, rs in byp.items():
        ks = sorted({r["k"] for r in rs})
        assert ks == seeds, (pol, "seed set mismatch", ks)

    rep_check = []
    bypk = defaultdict(list)
    for r in rows:
        bypk[(r["policy"], r["k"])].append(r)
    for key, rs in bypk.items():
        reps = {r["rep"] for r in rs}
        if key[0] == "deploy":
            assert len(rs) == 2 and reps == {0, 1}, (key, rs)
            s = {(r["result"], r["pipes"], r["frames"], r["flaps"],
                  r["trace_sha256"]) for r in rs}
            rep_check.append(len(s) == 1)
        else:
            assert len(rs) == 1, (key, rs)
    assert all(rep_check)
    print(f"deploy n=2 rep identity verified on {len(rep_check)} seeds")

    summary = {}
    for pol in ("deploy", "base", "c1"):
        rs = byp[pol]
        # one row per seed (rep 0) for the stats; deploy reps identical
        per_seed = {}
        for r in rs:
            per_seed.setdefault(r["k"], r)
        pipes = [per_seed[k]["pipes"] for k in seeds]
        frames = [per_seed[k]["frames"] for k in seeds]
        alive = [per_seed[k]["result"] == "alive" for k in seeds]
        qs = statistics.quantiles(pipes, n=4)
        summary[pol] = {
            "n_episodes": len(rs),
            "n_seeds": len(seeds),
            "mean": round(statistics.mean(pipes), 2),
            "median": statistics.median(pipes),
            "stdev": round(statistics.stdev(pipes), 2),
            "min": min(pipes), "max": max(pipes),
            "p25": qs[0], "p75": qs[2],
            "alive_at_budget": int(sum(alive)),
            "per_seed": {str(k): per_seed[k]["pipes"] for k in seeds},
        }

    # win/tie/loss on per-seed pipes (deploy vs each reference)
    def wtl(a, b):
        w = t = l = 0
        for k in seeds:
            xa, xb = summary[a]["per_seed"][str(k)], \
                summary[b]["per_seed"][str(k)]
            if xa > xb:
                w += 1
            elif xa == xb:
                t += 1
            else:
                l += 1
        return w, t, l

    comp = {
        "deploy_vs_base": {"wtl": wtl("deploy", "base"),
                           "seed_deltas": {
                               str(k): summary["deploy"]["per_seed"][
                                   str(k)]
                               - summary["base"]["per_seed"][str(k)]
                               for k in seeds}},
        "deploy_vs_c1": {"wtl": wtl("deploy", "c1"),
                         "seed_deltas": {
                             str(k): summary["deploy"]["per_seed"][
                                 str(k)]
                             - summary["c1"]["per_seed"][str(k)]
                             for k in seeds}},
    }
    out = {"policies": summary, "comparison": comp,
           "determinism": {
               "cross_process_dup_groups": dup_groups,
               "mismatches": dup_bad,
               "deploy_rep_identity": "byte-identical on all 30 seeds"},
           "split": SPLIT}
    with open(os.path.join(SCR, "r61_validation_summary.json"),
              "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(summary, indent=1))
    print(json.dumps(comp["deploy_vs_base"]["wtl"], default=str),
          comp["deploy_vs_c1"]["wtl"])


if __name__ == "__main__":
    main()
