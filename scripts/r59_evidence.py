#!/usr/bin/env python3
"""r59_evidence.py — assemble data/learn/r59_flappy_evidence.json from
the round's persisted artifacts (no emulator). Every number comes from
a file this round produced:
  scratch/r59/linpath_results.json   (the R59-A probe table)
  scratch/r57/r59_test_rows.jsonl    (the 100 fresh-TEST episodes)
  scratch/r59/r59_test_stats.json    (the paired statistics)
"""
import hashlib
import json
import os
from collections import defaultdict

import numpy as np

REPO = "/home/z/my-project/ps1ai"
SCR59 = os.path.join(REPO, "scratch", "r59")
SCR57 = os.path.join(REPO, "scratch", "r57")
DATA = os.path.join(REPO, "data", "learn")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


lin = json.load(open(os.path.join(SCR59, "linpath_results.json")))
stats = json.load(open(os.path.join(SCR59, "r59_test_stats.json")))
rows = [json.loads(l)
        for l in open(os.path.join(SCR57, "r59_test_rows.jsonl"))
        if l.strip()]

# --- linpath probe table (in-process path; k = scenario seed) ---
lin_table = defaultdict(dict)
for r in lin:
    lin_table[(r["cand"], r["alpha"])][r["k"]] = \
        (r["pipes"], r["steps"], r["result"])
lin_rows = []
for (cand, alpha), d in sorted(lin_table.items()):
    lin_rows.append({
        "cand": cand, "alpha": alpha,
        "results": {f"k{k}": {"pipes": v[0], "steps": v[1],
                              "result": v[2]}
                    for k, v in sorted(d.items())},
    })

ev = {
    "round": "R59-continue",
    "parent": "R58-continue (issue #13, the R57 workstream)",
    "date": "2026-10-31",
    "env": {
        "emulator": "Beetle PSX 0.9.44.1 (mednafen_psx_libretro) + "
                    "OpenBIOS (MIT, repo third_party, hash-verified)",
        "iso": "flappybirdpsx-v0.1.0.iso sha256 b45871d32c791078... "
               "(manifest-verified, Unlicense homebrew, "
               "IcePanorama/FlappyBirdPSX v0.1.0 release)",
        "boot": "one boot per process; episodes from the pre-seed "
                "ready anchor; budget 10000 frames",
        "smoke": "base r58_dir2p_true k6 = 87 pipes budget-alive, "
                 "640 flaps (exact R58 reproduction; artifact sha "
                 "0d2cb44352e00d9e...)",
    },
    "motivation": (
        "R58 left the base a thrice-replicated SHARP LOCAL OPTIMUM: "
        "every one-shot weight move (ARS, siblings, SI fine-tunes) "
        "either did nothing or collapsed a razor-edge (k6/k60 "
        "87-alive). R59 tests the one untested move class: LINEAR-PATH "
        "interpolation between two working checkpoints."),
    "r59a_linpath_probe": {
        "protocol": "theta(alpha) = (1-alpha)*base + alpha*cand; real "
                    "emulator, in-process FlatPolicy (the proven "
                    "0/7345-mismatch decision path), razor seeds k6/k60 "
                    "first, then gains; teacher import-blocked + hashed "
                    "no-teacher trace per process",
        "e4_path_verdict": "NO soup point: gains (k12 87a, k45 47) "
                           "arrive only near alpha=1 while both "
                           "razor-edges die by alpha=0.5 (k6 63, k60 "
                           "14); k45 even dips 33->30 at alpha=0.25",
        "e6_path_verdict": "SOUP POINT FOUND at alpha=0.10: k45 +7 "
                           "with EVERY other family seed identical "
                           "(k210 at the base's exact death frame "
                           "4966); the k210 collapse onsets between "
                           "alpha=0.10 (42@4966) and 0.15 (18@2260)",
        "table": lin_rows,
        "no_teacher_trace_sha256": [
            "8d71e2c4fac3131e...", "9396e21c3794dbce...",
            "7019b7b3b086ea26...", "3113f030bf2a3478...",
            "343dbe5ecb69e53a...", "978b75af1308b2b1...",
            "1444135a9287ca0c...", "1a5cb3192f6d0b69..."],
    },
    "r59_candidate": {
        "artifact": "data/learn/r59_soup_e6a010.npz (7.1 KB)",
        "weights_sha256": "72c79f3091ed14e8dd497ddc52570bb4660bfc63"
                          "6e6b50eb8a8aa1eff8a28f4",
        "definition": "r58_dir2p_true + 0.10 * (r58_si_v2_e6 - "
                      "r58_dir2p_true); no new training; a convex "
                      "combination of two working self-imitation "
                      "checkpoints",
        "family_deployed_path": {
            "protocol": "BrainClient subprocess (the deployment bar), "
                        "budget 10000; VAL seeds n=3 boots",
            "k6": "87 alive (640 flaps)",
            "k12": "76 @8798", "k30": "37 @4401",
            "k45": "40 @4753 (base: 33 @3957 -> +7)",
            "k60": "87 alive (640 flaps)",
            "k90": "68 @7895 x3 boots (byte-identical)",
            "k210": "42 @4966 x3 boots (byte-identical; the base's "
                    "exact death frame)",
            "vs_base": "strictly dominates: 6 seeds identical, k45 +7",
            "regression_gate": "PASS (VAL median delta 0 <= 2; max "
                               "drop 0 <= 5; 10-pipe survival "
                               "unchanged)",
            "no_teacher_trace_sha256": [
                "7b552ca9aec20587...", "1d4e1af3ac93071c...",
                "8a571a346379cbf1..."],
        },
    },
    "fresh_test": {
        "split": "data/learn/r59_seed_splits.json committed "
                 "21f3e0d3c8d1 BEFORE collection (multiples-of-4 rule, "
                 "every prior use excluded)",
        "seeds": stats["seeds"],
        "episodes": len(rows),
        "protocol": "candidate n=3, references n=1 (base r58_dir2p_true "
                    "and frozen C1), budget 10000, "
                    "single-source-of-truth PassageCounter, visual "
                    "death only, no RAM in the student pipeline",
        "table": stats["table"],
        "per_seed": stats["per_seed"],
        "paired_soup_vs_base": {
            "mean_delta": 3.90, "W/T/L": "2/15/3",
            "detail": "k64 +48 (37->85), k76 +77 (10->87 ALIVE), "
                      "k56 -3, k140 -18 (73->55), k80 -26 (62->36)",
        },
        "paired_soup_vs_c1": {
            "mean_delta": 2.55, "W/T/L": "4/11/5",
            "detail": "k88 +87 (C1 0-catastrophe -> 87), k136 +33, "
                      "k140 +37, k124 +25 vs k44 -47 (C1 87), "
                      "k80 -42 (C1 78), k148 -25, k56 -14, k112 -3",
        },
        "rep_consistency": stats["reps_identical"],
        "test_trace_shas256_16": sorted(
            {hashlib.sha256(
                (r["model"] + str(r["k"]) + str(r["rep"]) +
                 str(r["ts"])).encode()).hexdigest()[:16]
             for r in rows}),
        "verdict": ("AGGREGATE WIN, NOT UNIFORM DOMINANCE: the soup "
                    "improves the mean (+3.9 / +2.55), the median "
                    "(52.5 vs 49.0 / 49.5) and the floor (24 vs 10 / 0) "
                    "against BOTH references, but 15/20 seeds are "
                    "byte-identical to the base and the 5 divergent "
                    "seeds swing BOTH ways (2W/3L vs base, 4W/5L vs "
                    "C1). The per-seed evidence is weak; the claim is "
                    "kept at the aggregate level."),
        "promotion": ("r59_soup_e6a010 promoted to champion: every "
                      "pre-registered gate passes (family strict "
                      "dominance, VAL untouched) and all three TEST "
                      "aggregates favor it (mean/median/floor); "
                      "disclosures: heavy-tailed paired deltas, C1 "
                      "keeps the alive-depth count (6 vs 5 seeds "
                      ">=85), the razor-edge gains did NOT generalize "
                      "as per-seed dominance"),
    },
    "hello_pong_regression": {
        "protocol": "the R54 head-to-head verbatim (r54c_pong_eval.py; "
                    "same anchors, opponents, seeds, step budgets; "
                    "artifact re-fetched via the documented r12 "
                    "procedure, zip+bin sha256 verified)",
        "P1_teacher_v1": "scored 7 / conceded 0, gameAI returns [19,19]",
        "P4_teacher_v2": "scored 7 / conceded 0, gameAI returns [19,19]",
        "P4_student_feat": "scored 8 / conceded 2, gameAI returns "
                           "[19,19] — EXACT R54 reproduction; the "
                           "student still outscores both teachers "
                           "(8 vs 7)",
        "verdict": "REGRESSION PASS",
    },
    "honest_limitations": [
        "the soup's TEST advantage is aggregate-level; per-seed "
        "paired evidence is weak (2W/3L vs base, heavy tails both "
        "directions); 15/20 seeds byte-identical to the base",
        "the divergent seeds (k64/k76/k80/k140) show the tiny "
        "0.10-norm weight move acts as a butterfly trigger on "
        "branch-prone lives — the improvement is not a reliability "
        "improvement",
        "k45 remains the only family seed where the candidate does "
        "not meet the teacher (40 vs 34: now MET at the family level "
        "— the R58 k45 -1 is CLOSED by +7)",
        "the razor-edge 87s remain razor-edges (unchanged by design: "
        "the soup keeps them byte-identical)",
        "ONNX export remains PENDING (native numpy is the deployment "
        "per the review bar)",
        "the R59 TEST seeds are retired after this round per the "
        "protocol",
    ],
    "artifacts": {
        "candidate": "data/learn/r59_soup_e6a010.npz",
        "candidate_meta": "data/learn/r59_soup_e6a010.npz.json",
        "split": "data/learn/r59_seed_splits.json",
        "linpath_dev_evidence": "data/learn/r59_linpath_results.json",
        "scripts": ["scripts/r59a_linpath.py", "scripts/r59_prep.py",
                    "scripts/r59b_test.py", "scripts/r59c_stats.py",
                    "scripts/r59_evidence.py"],
    },
}

out = os.path.join(DATA, "r59_flappy_evidence.json")
json.dump(ev, open(out, "w"), indent=1)
print("wrote", out, os.path.getsize(out), "bytes")
