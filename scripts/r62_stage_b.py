#!/usr/bin/env python3
"""r62_stage_b.py — R62 Section 13 Stage B: TWENTY autonomous
episodes with the canonical one-command runtime, zero human input.

The sandbox kills any process that outlives a single tool call
(~10 min wall), so the 20-episode ladder runs as FOUR launches of
FIVE consecutive episodes each (fully autonomous inside every
launch; no gameplay buttons exist anywhere on the path). The
same-launch multi-episode property (no stale state, no input between
episodes, byte-identical repeats) is additionally proven by the
release gate (3x k=45 in ONE launch) and the integration test
(2x k=45) — byte-exact against the R61 records.

Seeds (published BEFORE any result collection):
    k = 6, 12, 18, ..., 120  (the deterministic ladder, 20 seeds)
Family seeds inside the ladder (6, 12, 30, 60, 90) are cross-checked
byte-exactly against the R61 family records.

Usage:
    python3 scripts/r62_stage_b.py chunk N      # N in 0..3
    python3 scripts/r62_stage_b.py summarize
"""
import hashlib
import json
import os
import subprocess
import sys
import time

REPO = "/home/z/my-project/ps1ai"
BASE = os.path.join(REPO, "scratch", "r62", "stage_b")
SUMMARY = os.path.join(REPO, "data", "r62", "r62_stage_b_summary.json")
SEEDS = list(range(6, 121, 6))          # 20 seeds, published up front
PER_CHUNK = 5
FAMILY = {6, 12, 30, 60, 90}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def chunk(n: int) -> int:
    seeds = SEEDS[n * PER_CHUNK:(n + 1) * PER_CHUNK]
    out = os.path.join(BASE, f"chunk{n}")
    os.makedirs(out, exist_ok=True)
    cmd = [sys.executable, "-m", "ps1play", "play", "flappybird",
           "--episodes", str(len(seeds)),
           "--seed-start", str(seeds[0]),
           "--seed-step", str(seeds[1] - seeds[0]),
           "--record", "--max-frames", "10000",
           "--max-runtime", "520", "--output", out]
    print("CHUNK", n, "seeds", seeds, flush=True)
    print("CMD:", " ".join(cmd), flush=True)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True,
                           text=True, timeout=590)
        rc, tail = r.returncode, r.stdout[-1200:]
        err = r.stderr[-800:]
    except subprocess.TimeoutExpired as e:
        rc, tail, err = 124, (e.stdout or b"")[-500:], "TOOL TIMEOUT"
    wall = time.time() - t0
    print(tail)
    if err:
        print("STDERR:", err, file=sys.stderr)
    rows = []
    ep_file = os.path.join(out, "episodes.jsonl")
    if os.path.exists(ep_file):
        with open(ep_file) as f:
            rows = [json.loads(l) for l in f]
    print(f"chunk{n}: rc={rc} episodes={len(rows)} wall={wall:.0f}s",
          flush=True)
    return 0 if rows else 1


def summarize() -> int:
    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    with open(os.path.join(BASE, "SEEDS_PREREGISTERED.json")) as f:
        pre = json.load(f)
    rows = []
    chunks = {}
    for n in range((len(SEEDS) + PER_CHUNK - 1) // PER_CHUNK):
        ep_file = os.path.join(BASE, f"chunk{n}", "episodes.jsonl")
        n_rows = 0
        if os.path.exists(ep_file):
            with open(ep_file) as f:
                for line in f:
                    d = json.loads(line)
                    d["launch"] = n
                    rows.append(d)
                    n_rows += 1
        chunks[n] = n_rows
    fam_ref = {}
    with open(os.path.join(REPO, "data", "learn",
                           "r61_family_rows.jsonl")) as f:
        for line in f:
            d = json.loads(line)
            fam_ref[int(d["k"])] = d
    byte_matches = []
    for row in rows:
        k = row["seed_k"]
        if k in FAMILY and k in fam_ref:
            ref = fam_ref[k]
            byte_matches.append({
                "k": k,
                "byte_match_r61": (row["trace_sha256"]
                                   == ref["trace_sha256"]
                                   and row["pipes"] == ref["pipes"]
                                   and row["frames"] == ref["frames"])})
    seeds_run = [row["seed_k"] for row in rows]
    n_gifs = n_shots = 0
    for n in chunks:
        d = os.path.join(BASE, f"chunk{n}")
        if not os.path.isdir(d):
            continue
        n_gifs += len([f for f in os.listdir(d)
                       if f.startswith("video_")])
        sd = os.path.join(d, "shots")
        n_shots += len(os.listdir(sd)) if os.path.isdir(sd) else 0
    summary = {
        "stage": "B", "round": "R62",
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "constraint": "sandbox kills processes between tool calls "
                      "(~10 min) -> 4 launches x 5 consecutive "
                      "autonomous episodes; same-launch continuity "
                      "proven byte-exactly by the release gate "
                      "(3x k45) and the integration test (2x k45)",
        "seeds_preregistered": pre["seeds"],
        "seeds_run": seeds_run,
        "episodes_per_launch": chunks,
        "n_episodes_completed": len(rows),
        "results": [{k: x[k] for k in ("episode", "seed_k", "result",
                                       "pipes", "frames", "flaps",
                                       "wall_s", "trace_sha256",
                                       "launch")} for x in rows],
        "family_byte_matches": byte_matches,
        "family_byte_match_all": all(m["byte_match_r61"]
                                     for m in byte_matches) and
                                 len(byte_matches) == len(FAMILY),
        "n_videos": n_gifs, "n_screenshots": n_shots,
    }
    with open(SUMMARY, "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: summary[k] for k in
                      ("n_episodes_completed", "episodes_per_launch",
                       "family_byte_match_all", "n_videos",
                       "n_screenshots")}, indent=1))
    ok = (summary["n_episodes_completed"] >= 20
          and summary["family_byte_match_all"])
    print("STAGE_B:", "PASS" if ok else "INCOMPLETE")
    return 0 if ok else 1


def main():
    os.makedirs(BASE, exist_ok=True)
    with open(os.path.join(BASE, "SEEDS_PREREGISTERED.json"), "w") as f:
        json.dump({"seeds": SEEDS, "published_at": time.time(),
                   "rule": "k = 6..120 step 6 (deterministic ladder, "
                           "published before collection)"}, f, indent=1)
    if len(sys.argv) > 1 and sys.argv[1] == "chunk":
        return chunk(int(sys.argv[2]))
    return summarize()


if __name__ == "__main__":
    sys.exit(main())
