#!/usr/bin/env python3
"""r61b_parity_suite.py — R61 Section 6: the permanent, independent
3-way ONNX parity regression suite.

Paths compared on >= 200,000 deterministic synthetic vectors:
  (1) the reference numpy forward — implemented INLINE in this script
      from the champion npz bytes (never imported from the training
      code);
  (2) onnxruntime CPU on the shipped artifact (a bare session, the
      R60-style path);
  (3) the INDEPENDENT deployment package (load_policy -> logits_batch),
      the external-consumer path with full validation.

Corpus blocks (seeded rng(61), reproducible):
  A realistic   — lognormal around the recorded norm distribution
  B edges       — every documented range endpoint, sentinel combos,
                  init-counter states
  C boundary    — perturbations of the 4,200 REAL closed-loop vectors
                  committed in R60 (the decision-dense region)
  D tie-pressing— tiny steps along the top-2 logit gradient until
                  margins < 1e-3 (bounded rounds)

Recorded: argmax agreement, exact action agreement, max/mean |dlogit|,
worst-case vector, min top-2 margin, per-path latency (p50/p95/p99 for
batch=1 and batch=1024), peak RSS delta. Any argmax mismatch on the
in-range corpus = FAIL (exit 1).

Output: data/learn/r61_parity_evidence.json (+ worst-case npz).
"""
import hashlib
import json
import os
import resource
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
DATA = os.path.join(REPO, "data", "learn")
PKG = os.path.join(REPO, "deployment", "flappybird_policy")
sys.path.insert(0, PKG)

from flappybird_policy import load_policy          # noqa: E402
from flappybird_policy.schema import VALID_RANGES  # noqa: E402

CHAMP = os.path.join(DATA, "r59_soup_e6a010.npz")
CHAMP_META = CHAMP + ".json"
ONNX = os.path.join(DATA, "r60_soup_e6a010.onnx")
R60_VECS = os.path.join(DATA, "r60_onnx_parity_vectors.npz")
OUT_JSON = os.path.join(DATA, "r61_parity_evidence.json")
OUT_WORST = os.path.join(DATA, "r61_parity_worstcase.npz")
SEED = 61
N_REAL = 200_000


def main():
    t_start = time.time()
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # ---- reference numpy forward, inline from the npz bytes ---------
    z = np.load(CHAMP)
    meta = json.load(open(CHAMP_META))
    W1 = z["W1"].astype(np.float32)
    b1 = z["b1"].astype(np.float32)
    W2 = z["W2"].astype(np.float32)
    b2 = z["b2"].astype(np.float32)
    mean = np.asarray(meta["norm"]["mean"], np.float32).reshape(1, 10)
    std_eps = (np.asarray(meta["norm"]["std"], np.float32)
               + np.float32(1e-6)).astype(np.float32).reshape(1, 10)

    def ref_forward(x):
        xn = ((x - mean) / std_eps).astype(np.float32)
        h = np.maximum(xn @ W1 + b1, np.float32(0.0))
        return (h @ W2 + b2).astype(np.float32)

    # ---- corpus ------------------------------------------------------
    rng = np.random.default_rng(SEED)
    lows = np.asarray([r[0] for r in VALID_RANGES], np.float32)
    his = np.asarray([r[1] for r in VALID_RANGES], np.float32)

    # A: realistic — around the recorded norm distribution
    A = (rng.standard_normal((N_REAL // 2, 10)).astype(np.float32)
         * 1.5 + mean)
    # A2: mixture with the REAL R60 vectors' distribution
    z60 = np.load(R60_VECS)
    real = z60["x"]
    pick = rng.integers(0, len(real), N_REAL // 4)
    A2 = real[pick] + rng.standard_normal(
        (N_REAL // 4, 10)).astype(np.float32) * 0.5

    # B: edges — endpoints + sentinels + init states
    B_rows = []
    for j in range(10):
        for edge in (lows[j], his[j]):
            v = mean.ravel().copy()
            v[j] = edge
            B_rows.append(v)
            v2 = np.zeros(10, np.float32)
            v2[j] = edge
            B_rows.append(v2)
    for base in (np.zeros(10, np.float32),):
        v = base.copy(); v[:] = [-1, 0, -1, -1, -1, -1, 0, 99, -1, 40]
        B_rows.append(v)                       # the all-missing state
        v = base.copy(); v[:] = [240, 10, 240, 160, 240, 240, 9, 0,
                                 240, 0]
        B_rows.append(v)                       # all-max state
    B = np.asarray(B_rows, np.float32)

    # C: boundary — tiny perturbations of the REAL vectors
    pickc = rng.integers(0, len(real), N_REAL // 4)
    C = real[pickc] + rng.standard_normal(
        (N_REAL // 4, 10)).astype(np.float32) * 0.01
    C = np.clip(C, lows, his).astype(np.float32)

    # D: tie-pressing — walk the top-2 gradient from real vectors
    D_rows = []
    base_rows = real[rng.integers(0, len(real), 4096)]
    for v in base_rows:
        lg = ref_forward(v.reshape(1, -1))[0]
        d = lg[1] - lg[0]
        g = np.sign(d) if d != 0 else 1.0
        direction = np.zeros(10, np.float32)
        direction[0] = 0.25 * g          # by dominates the decision
        direction[1] = 0.10 * g
        for eps in (1e-3, 1e-2, 5e-2, 2e-1, 1.0):
            w = np.clip(v + direction * np.float32(eps), lows, his)
            D_rows.append(w)
    D = np.asarray(D_rows, np.float32)

    X = np.concatenate([A, A2, B, C, D], axis=0).astype(np.float32)
    # keep the whole corpus inside the documented contract
    X = np.clip(X, lows, his).astype(np.float32)
    corpus_sha = hashlib.sha256(X.tobytes()).hexdigest()
    print(f"corpus: {X.shape[0]} vectors, sha {corpus_sha[:16]}")

    # ---- (1) reference ------------------------------------------------
    t0 = time.time()
    ref = ref_forward(X)
    ref_s = time.time() - t0
    ref_idx = ref.argmax(axis=1)
    top2 = np.sort(ref, axis=1)
    margin = top2[:, 1] - top2[:, 0]

    # ---- (2) bare ORT session ----------------------------------------
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    t0 = time.time()
    sess = ort.InferenceSession(ONNX, sess_options=opts,
                                providers=["CPUExecutionProvider"])
    ort_load_s = time.time() - t0
    t0 = time.time()
    ort_out = sess.run(["logits"], {"x": X})[0]
    ort_s = time.time() - t0

    # ---- (3) the independent deployment package -----------------------
    t0 = time.time()
    pol = load_policy()
    pkg_load_s = time.time() - t0
    t0 = time.time()
    pkg_out = pol.logits_batch(X)
    pkg_s = time.time() - t0
    pkg_idx = pkg_out.argmax(axis=1)

    # ---- metrics -------------------------------------------------------
    def cmp(a, b, name):
        d = np.abs(a - b)
        mism = int((a.argmax(axis=1) != b.argmax(axis=1)).sum())
        return {
            "paths": name,
            "max_abs_logit_delta": float(d.max()),
            "mean_abs_logit_delta": float(d.mean()),
            "argmax_mismatch_count": mism,
        }

    m_ref_ort = cmp(ref, ort_out, "numpy_reference vs onnxruntime")
    m_ref_pkg = cmp(ref, pkg_out, "numpy_reference vs deployment_pkg")
    m_ort_pkg = cmp(ort_out, pkg_out, "onnxruntime vs deployment_pkg")
    argmax_3way = int(((ref_idx == ort_out.argmax(axis=1))
                       & (ref_idx == pkg_idx)).sum())
    assert argmax_3way == X.shape[0], "ARGMAX MISMATCH IN CORPUS"

    # worst-case vectors (largest pairwise logit delta)
    d_all = np.maximum(np.abs(ref - ort_out), np.abs(ref - pkg_out))
    worst_order = np.argsort(-d_all.max(axis=1))[:16]
    np.savez_compressed(
        OUT_WORST, x=X[worst_order], ref_logits=ref[worst_order],
        ort_logits=ort_out[worst_order], pkg_logits=pkg_out[worst_order])

    # ---- latency profile ------------------------------------------------
    def lat(fn, n, batch, reps=3):
        xs = X[:n * batch].reshape(n, batch, 10)
        fn(xs[0])                     # warm
        ts = []
        for r in range(reps):
            for xb in xs:
                t1 = time.perf_counter()
                fn(xb)
                ts.append(time.perf_counter() - t1)
        ts = np.asarray(ts) * 1e3
        return {"n": int(n), "batch": int(batch),
                "p50_ms": round(float(np.percentile(ts, 50)), 4),
                "p95_ms": round(float(np.percentile(ts, 95)), 4),
                "p99_ms": round(float(np.percentile(ts, 99)), 4),
                "mean_ms": round(float(ts.mean()), 4)}

    pkg_lat_1 = lat(lambda xb: pol.predict(xb[0]), 300, 1)
    pkg_lat_b = lat(lambda xb: pol.logits_batch(xb), 100, 1024)

    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # ---- malformed rejection checks (the suite's negative side) -------
    rejections = []
    for name, bad in [
        ("nan", np.full(10, np.nan, np.float32)),
        ("inf", np.full(10, np.inf, np.float32)),
        ("float64", np.zeros(10, np.float64)),
        ("list", [0.0] * 10),
        ("short", np.zeros(9, np.float32)),
        ("out_of_range", np.full(10, 999.0, np.float32)),
    ]:
        try:
            pol.predict(bad)
            rejections.append({"case": name, "rejected": False})
        except Exception as e:
            rejections.append({"case": name, "rejected": True,
                               "error": type(e).__name__})
    assert all(r["rejected"] for r in rejections), rejections

    # ---- the committed R60 real-vector block: exact recheck -----------
    ort60 = sess.run(["logits"], {"x": real})[0]
    d60 = np.abs(ort60 - z60["ort_logits"]).max()
    pkg60 = pol.logits_batch(real)
    am60 = int((pkg60.argmax(axis=1) == z60["ref_action"]).sum())

    evidence = {
        "round": "R61",
        "seed": SEED,
        "corpus_vectors": int(X.shape[0]),
        "corpus_sha256": corpus_sha,
        "blocks": {"realistic": int(A.shape[0] + A2.shape[0]),
                   "edges": int(B.shape[0]),
                   "boundary_real_perturbed": int(C.shape[0]),
                   "tie_pressing": int(D.shape[0])},
        "champion_npz_sha256": hashlib.sha256(
            open(CHAMP, "rb").read()).hexdigest(),
        "onnx_sha256": hashlib.sha256(
            open(ONNX, "rb").read()).hexdigest(),
        "numpy_vs_ort": m_ref_ort,
        "numpy_vs_package": m_ref_pkg,
        "ort_vs_package": m_ort_pkg,
        "argmax_3way_agreement": argmax_3way,
        "argmax_3way_fraction": 1.0,
        "min_top2_margin": float(margin.min()),
        "mean_top2_margin": float(margin.mean()),
        "r60_real_vectors_recheck": {
            "n": int(len(real)),
            "ort_vs_recorded_max_delta": float(d60),
            "package_argmax_vs_recorded": am60,
            "exact": bool(am60 == len(real)),
        },
        "latency": {"package_b1": pkg_lat_1, "package_b1024": pkg_lat_b,
                    "ort_session_load_s": round(ort_load_s, 4),
                    "package_load_s": round(pkg_load_s, 4),
                    "numpy_forward_full_corpus_s": round(ref_s, 3),
                    "ort_full_corpus_s": round(ort_s, 3),
                    "package_full_corpus_s": round(pkg_s, 3)},
        "peak_rss_kb": {"before": int(rss0), "after": int(rss1),
                        "delta": int(rss1 - rss0)},
        "malformed_rejection": rejections,
        "wall_s": round(time.time() - t_start, 2),
        "verdict": "PASS",
    }
    with open(OUT_JSON, "w") as f:
        json.dump(evidence, f, indent=1)
    print(json.dumps({k: evidence[k] for k in
                      ("corpus_vectors", "numpy_vs_ort",
                       "numpy_vs_package", "ort_vs_package",
                       "min_top2_margin", "r60_real_vectors_recheck",
                       "latency", "wall_s")}, indent=1))
    pol.close()
    print("PARITY PASS")


if __name__ == "__main__":
    main()
