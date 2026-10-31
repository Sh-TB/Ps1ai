#!/usr/bin/env python3
"""r61_final_verify.py — R61 Section 14: the ONE-command final release
gate.

    python3 scripts/r61_final_verify.py [--fast]

Runs every required gate and writes a machine-readable result to
data/learn/r61_gate_result.json. Exit 0 = all required gates PASS or
NOT_APPLICABLE; exit 1 = any FAIL/BLOCKED. Every gate checks its
condition explicitly — a script exiting 0 is never taken as PASS.

Gates:
  repo_state          HEAD + the frozen artifacts exist
  manifest_hashes     FINAL_MODEL_MANIFEST <-> npz/onnx/sidecar binding
                      + the bitwise soup re-derivation
  deployment_package  fresh import + identity + CLI smoke (subprocess)
  synthetic_parity    fast in-gate 3-way parity (20k vectors; the full
                      220k suite is the committed evidence)
  emulator_smoke      REAL emulator: k6 through the deployment package
                      must reproduce 87-alive/640 flaps exactly
                      (BLOCKED when the emulator assets are absent)
  validation_evidence the pre-registered split + 120 merged rows +
                      rep identity + summary consistency
  regression_tests    the full pytest suite, 0 failures required
  pong_regression     the committed R54-protocol record 7/0, 7/0, 8/2
  reports_complete    the R61 reports + evidence files exist
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
PKG = os.path.join(REPO, "deployment", "flappybird_policy")
DATA = os.path.join(REPO, "data", "learn")
OUT = os.path.join(DATA, "r61_gate_result.json")

FAMILY_K6 = {"result": "alive", "pipes": 87, "frames": 10000,
             "flaps": 640}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class Gates:
    def __init__(self):
        self.results = {}

    def record(self, name, status, detail):
        self.results[name] = {"status": status, "detail": detail}
        print(f"[{status:>14}] {name}: {detail}")

    def __bool__(self):
        return all(r["status"] in ("PASS", "NOT_APPLICABLE")
                   for r in self.results.values())


def gate_repo_state(g):
    need = [os.path.join(DATA, "r59_soup_e6a010.npz"),
            os.path.join(DATA, "r60_soup_e6a010.onnx"),
            os.path.join(DATA, "FINAL_MODEL_MANIFEST.json"),
            os.path.join(PKG, "flappybird_policy", "policy.py")]
    missing = [p for p in need if not os.path.exists(p)]
    if missing:
        g.record("repo_state", "FAIL", f"missing: {missing}")
        return False
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
        text=True).stdout.strip()
    g.record("repo_state", "PASS", f"HEAD {head[:12]}; artifacts present")
    return True


def gate_manifest(g):
    man = json.load(open(os.path.join(DATA, "FINAL_MODEL_MANIFEST.json")))
    npz_h = sha(os.path.join(DATA, "r59_soup_e6a010.npz"))
    onnx_h = sha(os.path.join(DATA, "r60_soup_e6a010.onnx"))
    ok = (man["source_checkpoint"]["sha256"] == npz_h
          and man["onnx_artifact"]["sha256"] == onnx_h)
    side = json.load(open(os.path.join(DATA,
                                       "r60_soup_e6a010.onnx.json")))
    ok &= side["source_sha256"] == npz_h
    ok &= side["onnx"]["sha256"] == onnx_h
    if not ok:
        g.record("manifest_hashes", "FAIL", "hash binding broken")
        return False
    # bitwise soup re-derivation (the R61 audit's core assertion)
    zc = np.load(os.path.join(DATA, "r59_soup_e6a010.npz"))
    zb = np.load(os.path.join(DATA, "r58_dir2p_true.npz"))
    zd = np.load(os.path.join(DATA, "r58_si_v2_e6.npz"))
    for k in ("W1", "b1", "W2", "b2"):
        want = (zb[k].astype(np.float64)
                + 0.10 * (zd[k].astype(np.float64)
                          - zb[k].astype(np.float64))).astype(np.float32)
        if not np.array_equal(want, zc[k].astype(np.float32)):
            g.record("manifest_hashes", "FAIL", f"soup re-derivation {k}")
            return False
    g.record("manifest_hashes", "PASS",
             "manifest<->artifacts bound; soup re-derived bitwise")
    return True


def gate_package(g):
    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {PKG!r})\n"
        "from flappybird_policy import load_policy\n"
        "p = load_policy()\n"
        "i = p.identity()\n"
        "assert i['model_sha256'].startswith('4dd592a7118a5c4d'), i\n"
        "import numpy as np\n"
        "x = np.zeros(10, dtype=np.float32); x[0] = 97.9\n"
        "a = p.predict(x)\n"
        "assert a in ('HOVER', 'FLAP')\n"
        "p.close(); print('PKG_OK')\n")
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=180,
                       cwd=tempfile.gettempdir())
    if r.returncode != 0 or "PKG_OK" not in r.stdout:
        g.record("deployment_package", "FAIL", r.stderr[-300:])
        return False
    cli = subprocess.run([sys.executable, "-m", "flappybird_policy"],
                         capture_output=True, text=True, timeout=180,
                         cwd=PKG)
    if cli.returncode != 0 or "SMOKE PASS" not in cli.stdout:
        g.record("deployment_package", "FAIL", "CLI smoke failed")
        return False
    g.record("deployment_package", "PASS",
             "fresh-import + identity + CLI smoke green")
    return True


def gate_parity(g):
    sys.path.insert(0, PKG)
    from flappybird_policy import load_policy
    z = np.load(os.path.join(DATA, "r59_soup_e6a010.npz"))
    meta = json.load(open(os.path.join(DATA,
                                       "r59_soup_e6a010.npz.json")))
    W1, b1 = z["W1"].astype(np.float32), z["b1"].astype(np.float32)
    W2, b2 = z["W2"].astype(np.float32), z["b2"].astype(np.float32)
    mean = np.asarray(meta["norm"]["mean"], np.float32).reshape(1, 10)
    se = (np.asarray(meta["norm"]["std"], np.float32)
          + np.float32(1e-6)).astype(np.float32).reshape(1, 10)
    rng = np.random.default_rng(611)
    X = (rng.standard_normal((20_000, 10)).astype(np.float32)
         * 1.5 + mean)
    from flappybird_policy.schema import VALID_RANGES
    lows = np.asarray([r[0] for r in VALID_RANGES], np.float32)
    his = np.asarray([r[1] for r in VALID_RANGES], np.float32)
    X = np.clip(X, lows, his).astype(np.float32)
    xn = ((X - mean) / se).astype(np.float32)
    ref = np.maximum(xn @ W1 + b1, np.float32(0.0)) @ W2 + b2
    pol = load_policy()
    pkg = pol.logits_batch(X)
    d = np.abs(ref - pkg).max()
    am = int((ref.argmax(axis=1) == pkg.argmax(axis=1)).sum())
    pol.close()
    if d == 0.0 and am == len(X):
        g.record("synthetic_parity", "PASS",
                 f"20k in-gate vectors exact (full 220k evidence "
                 f"committed)")
        return True
    g.record("synthetic_parity", "FAIL", f"max delta {d}, argmax {am}")
    return False


def gate_emulator(g, fast=False):
    iso = "/home/z/my-project/emu/games_homebrew/flappybird.cue"
    if not os.path.exists(iso):
        g.record("emulator_smoke", "BLOCKED",
                 "emulator assets absent on this machine")
        return False
    for p in (REPO, os.path.join(REPO, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from ps1play.learn.games import FlappyEnv  # noqa: E402
    from r61e_deploy_loop import run_episode   # noqa: E402
    from flappybird_policy import load_policy  # noqa: E402
    env = FlappyEnv(workspace="/home/z/my-project/emu/games_homebrew/"
                                "ws_r61_gate")
    try:
        env.reach_ready()
        pol = load_policy()
        rec = run_episode(env, pol, 6, 10000, tag="r61_gate")
        pol.close()
    finally:
        env.close()
    ok = (rec["result"] == FAMILY_K6["result"]
          and rec["pipes"] == FAMILY_K6["pipes"]
          and rec["frames"] == FAMILY_K6["frames"]
          and rec["flaps"] == FAMILY_K6["flaps"])
    if ok:
        g.record("emulator_smoke", "PASS",
                 "k6 through the package = 87-alive/640 flaps (the "
                 "exact family record)")
        return True
    g.record("emulator_smoke", "FAIL", json.dumps(
        {k: rec[k] for k in ("result", "pipes", "frames", "flaps")}))
    return False


def gate_validation(g):
    split_p = os.path.join(DATA, "r61_validation_split.json")
    rows_p = os.path.join(DATA, "r61_validation_rows.jsonl")
    sum_p = os.path.join(DATA, "r61_validation_summary.json")
    for p in (split_p, rows_p, sum_p):
        if not os.path.exists(p):
            g.record("validation_evidence", "FAIL", f"missing {p}")
            return False
    split = json.load(open(split_p))
    if not split.get("committed_before_collection"):
        g.record("validation_evidence", "FAIL", "split not pre-registered")
        return False
    seeds = split["validation_seeds"]
    rows = [json.loads(l) for l in open(rows_p)]
    from collections import defaultdict
    bypk = defaultdict(list)
    for r in rows:
        bypk[(r["policy"], r["k"])].append(r)
    for (pol, k), rs in bypk.items():
        want = 2 if pol == "deploy" else 1
        if len(rs) != want:
            g.record("validation_evidence", "FAIL",
                     f"{pol} k={k}: {len(rs)} rows, want {want}")
            return False
        if pol == "deploy":
            sig = {(r["result"], r["pipes"], r["frames"], r["flaps"],
                    r["trace_sha256"]) for r in rs}
            if len(sig) != 1:
                g.record("validation_evidence", "FAIL",
                         f"deploy k={k} reps differ")
                return False
    ks = sorted({k for (_p, k) in bypk})
    if ks != sorted(seeds):
        g.record("validation_evidence", "FAIL", "seed set mismatch")
        return False
    g.record("validation_evidence", "PASS",
             f"{len(seeds)} pre-registered seeds; deploy n=2 "
             f"byte-identical; references n=1; {len(rows)} rows")
    return True


def gate_tests(g):
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q",
                        "-p", "no:cacheprovider"], cwd=REPO,
                       capture_output=True, text=True, timeout=560)
    tail = r.stdout.strip().splitlines()[-1] if r.stdout else "?"
    if " failed" in tail or " error" in tail or r.returncode != 0:
        g.record("regression_tests", "FAIL", tail)
        return False
    g.record("regression_tests", "PASS", tail)
    return True


def gate_pong(g):
    p = os.path.join(DATA, "r61_pong_regression.json")
    if not os.path.exists(p):
        g.record("pong_regression", "BLOCKED",
                 "no committed record; run scripts/r54c_pong_eval.py "
                 "--agents v1,v2 then --agents feat")
        return False
    d = json.load(open(p))
    t1 = d["teachers"]["P1_teacher_v1"]
    t2 = d["teachers"]["P4_teacher_v2"]
    st = d["student"]["P4_student_feat"]
    ok = (t1["scored"] == 7 and t1["conceded"] == 0
          and t2["scored"] == 7 and t2["conceded"] == 0
          and st["scored"] == 8 and st["conceded"] == 2)
    if ok:
        g.record("pong_regression", "PASS",
                 "teachers 7/0 each; student 8/2 (the exact R54/R59/"
                 "R60 record)")
        return True
    g.record("pong_regression", "FAIL", json.dumps(
        {"v1": t1, "v2": t2, "student": st}))
    return False


def gate_reports(g):
    need = [
        "docs/r61_final_closure.md",
        "docs/r61_training_record.md",
        os.path.join(DATA, "r61_parity_evidence.json"),
        os.path.join(DATA, "r61_profile.json"),
        os.path.join(DATA, "r61_family_rows.jsonl"),
        os.path.join(DATA, "r61_runner_incident.json"),
        "deployment/flappybird_policy/INTERFACE.md",
        "deployment/flappybird_policy/MODEL_CARD.md",
    ]
    missing = [p for p in need
               if not os.path.exists(os.path.join(REPO, p))]
    if missing:
        g.record("reports_complete", "FAIL", f"missing: {missing}")
        return False
    g.record("reports_complete", "PASS", f"{len(need)} evidence files")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="skip the ~2-minute emulator gate")
    a = ap.parse_args()
    g = Gates()
    t0 = time.time()
    ok = gate_repo_state(g)
    ok &= gate_manifest(g)
    ok &= gate_package(g)
    ok &= gate_parity(g)
    if a.fast:
        g.record("emulator_smoke", "SKIP", "--fast requested")
    else:
        ok &= gate_emulator(g)
    ok &= gate_validation(g)
    ok &= gate_tests(g)
    ok &= gate_pong(g)
    ok &= gate_reports(g)
    out = {
        "round": "R61",
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                               capture_output=True,
                               text=True).stdout.strip(),
        "wall_s": round(time.time() - t0, 1),
        "gates": g.results,
        "release": "PASS" if ok else "FAIL",
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("RELEASE:", out["release"], "->", OUT)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
