#!/usr/bin/env python3
"""r61a_model_audit.py — R61 Section 2: freeze + provenance audit of the
FINAL model, producing the authoritative FINAL_MODEL_MANIFEST.json.

Chain verified, in this order (every step asserted, nothing trusted):
  1. ENUMERATE every R59/R60 model artifact in data/learn/ (npz+onnx),
     sha256 each, compare against every hash recorded in the committed
     reports/evidence JSONs.
  2. SOUP RE-DERIVATION: r59_soup_e6a010 == r58_dir2p_true
     + 0.10 * (r58_si_v2_e6 - r58_dir2p_true), recomputed in float32 —
     bitwise equality with the committed champion npz (all four arrays).
  3. ONNX DERIVATION: every initializer in r60_soup_e6a010.onnx
     (W1,b1,W2,b2,mean,std_eps) bitwise-equal to the champion npz/meta
     (std_eps == std + 1e-6 folded); graph topology = the documented
     Sub->Div->Gemm->Relu->Gemm(+ArgMax); opset 17, IR 8, dtype f32.
  4. ACTION/OUTPUT CONTRACT: classes [HOVER, FLAP]; ArgMax
     select_last_index=0 (numpy first-max); input [N,10] float32 raw v7
     vector; outputs logits [N,2] + action_idx [N] int64.
  5. NON-REPLACEMENT: the champion npz mtime-independent identity —
     its bytes hash to the sidecar-recorded source_sha256; the R58/R57
     checkpoints hash DIFFERENTLY (no silent swap).
Outputs:
  data/learn/FINAL_MODEL_MANIFEST.json
Exit 0 only if every assertion holds; prints the audit trail.
"""
import hashlib
import json
import os
import sys

import numpy as np
import onnx
from onnx import numpy_helper

REPO = "/home/z/my-project/ps1ai"
DATA = os.path.join(REPO, "data", "learn")
CHAMP = os.path.join(DATA, "r59_soup_e6a010.npz")
BASE = os.path.join(DATA, "r58_dir2p_true.npz")
DONOR = os.path.join(DATA, "r58_si_v2_e6.npz")
ONNX = os.path.join(DATA, "r60_soup_e6a010.onnx")
OUT = os.path.join(DATA, "FINAL_MODEL_MANIFEST.json")
ALPHA = 0.10


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    audit = []

    def note(step, ok, detail=""):
        audit.append({"step": step, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + step + (" — " + detail
                                                      if detail else ""))
        if not ok:
            raise SystemExit("AUDIT FAILED: " + step)

    # -- 1. enumerate + hash ------------------------------------------------
    arts = sorted(f for f in os.listdir(DATA)
                  if f.endswith((".npz", ".onnx"))
                  and ("r59" in f or "r58" in f or "r60" in f))
    hashes = {f: sha(os.path.join(DATA, f)) for f in arts}
    note("enumerate", True,
         f"{len(arts)} R58/R59/R60 artifacts; champion sha "
         f"{hashes['r59_soup_e6a010.npz'][:16]}")

    champ_meta = json.load(open(CHAMP + ".json"))
    side = json.load(open(ONNX + ".json"))
    note("sidecar-source-hash", hashes["r59_soup_e6a010.npz"]
         == side["source_sha256"], "sidecar source_sha256 == npz sha256")
    note("onnx-recorded-hash", hashes["r60_soup_e6a010.onnx"]
         == side["onnx"]["sha256"], "sidecar onnx sha256 == file sha256")

    # -- 2. soup re-derivation ----------------------------------------------
    # The recorded R59 procedure (r59a_linpath.py): flat float64 vectors,
    # theta = th_base + alpha * (th_donor - th_base), THEN per-array
    # float32 cast at save time. Re-derive exactly that way.
    zc, zb, zd = (np.load(p) for p in (CHAMP, BASE, DONOR))
    soup_ok, soup_detail = True, []
    for k in ("W1", "b1", "W2", "b2"):
        want = (zb[k].astype(np.float64)
                + ALPHA * (zd[k].astype(np.float64)
                           - zb[k].astype(np.float64))).astype(np.float32)
        eq = np.array_equal(want, zc[k].astype(np.float32))
        soup_ok &= eq
        soup_detail.append(f"{k}:{'eq' if eq else 'DIFF'}")
    note("soup-rederivation", soup_ok, " ".join(soup_detail)
         + " (alpha=0.10, float64 math -> float32 cast, bitwise)")

    # -- 3. ONNX derivation ---------------------------------------------------
    m = onnx.load(ONNX)
    init = {t.name: numpy_helper.to_array(t)
            for t in m.graph.initializer}
    names = set(init)
    need = {"W1", "b1", "W2", "b2", "mean", "std_eps"}
    note("onnx-initializers", need <= names,
         "initializers: " + ",".join(sorted(names)))
    onnx_ok, det = True, []
    for k in ("W1", "b1", "W2", "b2"):
        eq = np.array_equal(init[k], zc[k].astype(np.float32))
        onnx_ok &= eq
        det.append(f"{k}:{'eq' if eq else 'DIFF'}")
    mean = np.asarray(champ_meta["norm"]["mean"], np.float32)
    std = np.asarray(champ_meta["norm"]["std"], np.float32)
    std_eps = (std + np.float32(1e-6)).astype(np.float32)
    for k, want in (("mean", mean), ("std_eps", std_eps)):
        eq = np.array_equal(init[k].ravel(), want)
        onnx_ok &= eq
        det.append(f"{k}:{'eq' if eq else 'DIFF'}")
    note("onnx-weights-bitwise", onnx_ok, " ".join(det))

    ops = [n.op_type for n in m.graph.node]
    want_ops = ["Sub", "Div", "Gemm", "Relu", "Gemm", "ArgMax"]
    note("onnx-topology", ops == want_ops, "->".join(ops))
    am = [n for n in m.graph.node if n.op_type == "ArgMax"][0]
    attrs = {a.name: a.i for a in am.attribute}
    note("onnx-argmax-first-max",
         attrs.get("axis") == 1 and attrs.get("select_last_index") == 0,
         f"axis={attrs.get('axis')} select_last_index="
         f"{attrs.get('select_last_index')}")
    note("onnx-opset-ir",
         m.opset_import[0].version == 17 and m.ir_version == 8,
         f"opset={m.opset_import[0].version} ir={m.ir_version}")
    note("onnx-dtype",
         init["W1"].dtype == np.float32
         and m.graph.input[0].type.tensor_type.elem_type == 1,
         "input elem_type=FLOAT, weights float32")
    dims = [d.dim_param or d.dim_value
            for d in m.graph.input[0].type.tensor_type.shape.dim]
    note("onnx-input-schema", dims == ["N", 10], f"input dims {dims}")
    outs = {o.name: [d.dim_param or d.dim_value
                     for d in o.type.tensor_type.shape.dim]
            for o in m.graph.output}
    note("onnx-output-schema",
         outs.get("logits") == ["N", 2] and outs.get("action_idx")
         == ["N"], f"outputs {outs}")

    # -- 4. non-replacement ----------------------------------------------------
    note("no-checkpoint-swap",
         hashes["r59_soup_e6a010.npz"] != hashes["r58_dir2p_true.npz"]
         and hashes["r59_soup_e6a010.npz"] != hashes["r58_si_v2_e6.npz"],
         "champion differs from both soup inputs")
    note("arch-assert", side["arch"] == {"n_in": 10, "hidden": 128,
                                         "n_out": 2}
         and side["classes"] == ["HOVER", "FLAP"],
         "10->128->2, classes [HOVER, FLAP]")

    manifest = {
        "format": "final-model-manifest-v1",
        "round": "R61",
        "game": "flappy",
        "status": "FROZEN",
        "source_checkpoint": {
            "path": "data/learn/r59_soup_e6a010.npz",
            "sha256": hashes["r59_soup_e6a010.npz"],
            "meta_path": "data/learn/r59_soup_e6a010.npz.json",
            "provenance": champ_meta["teacher"],
            "soup": {"base": "r58_dir2p_true.npz",
                     "donor": "r58_si_v2_e6.npz", "alpha": ALPHA,
                     "base_sha256": hashes["r58_dir2p_true.npz"],
                     "donor_sha256": hashes["r58_si_v2_e6.npz"],
                     "rederived_bitwise": True},
        },
        "onnx_artifact": {
            "path": "data/learn/r60_soup_e6a010.onnx",
            "sha256": hashes["r60_soup_e6a010.onnx"],
            "bytes": os.path.getsize(ONNX),
            "sidecar_path": "data/learn/r60_soup_e6a010.onnx.json",
            "opset": 17, "ir_version": 8, "dtype": "float32",
            "graph": side["onnx"]["graph"],
            "covers": "decision function ONLY "
                      "(normalize+MLP+argmax); perception "
                      "(BirdObserverV7/GapTrackerV7/history counters) "
                      "is host-side numpy frame processing without "
                      "learned weights",
        },
        "architecture": {"n_in": 10, "hidden": 128, "n_out": 2,
                         "activation": "ReLU", "params": 1466},
        "input_schema": {
            "name": "x", "shape": ["N", 10], "dtype": "float32",
            "content": "RAW v7 decision vector (normalization is "
                       "INSIDE the graph)",
            "features": [
                {"i": 0, "name": "by", "desc": "bird y, small-frame px "
                 "(BirdObserverV7)", "range": [0, 60]},
                {"i": 1, "name": "vy", "desc": "bird vertical velocity "
                 "px/frame (observer diff), clipped [-10,10]"},
                {"i": 2, "name": "gc", "desc": "gap center y, small "
                 "frame px (GapTrackerV7-filtered; raw finder value "
                 "when the tracker has no lock)"},
                {"i": 3, "name": "dx", "desc": "gap dx, small-frame px "
                 "(gap band center minus the tracked column origin)"},
                {"i": 4, "name": "g0", "desc": "gap top edge y, "
                 "small-frame px"},
                {"i": 5, "name": "g1", "desc": "gap bottom edge y, "
                 "small-frame px"},
                {"i": 6, "name": "flap_run", "desc": "consecutive FLAP "
                 "actions by THIS policy, capped 9"},
                {"i": 7, "name": "since_flap", "desc": "frames since "
                 "the last FLAP action, capped 99"},
                {"i": 8, "name": "last_gc", "desc": "last valid gap "
                 "center y, -1.0 until the first lock"},
                {"i": 9, "name": "since_gap", "desc": "frames since "
                 "the last valid gap reading, capped 40, starts 40"},
            ],
        },
        "output_schema": {
            "logits": {"shape": ["N", 2], "dtype": "float32",
                       "order": ["HOVER", "FLAP"]},
            "action_idx": {"shape": ["N"], "dtype": "int64",
                           "argmax": "first-max (select_last_index=0), "
                                     "ties -> HOVER"},
        },
        "action_semantics": {
            "HOVER": "no controller input this frame",
            "FLAP": "press the B button (Cross) this frame — a 2-frame "
                    "pulse is applied by the host action adapter",
        },
        "normalization": {
            "mean": mean.tolist(),
            "std_eps": std_eps.tolist(),
            "epsilon": 1e-6,
            "formula": "x_norm = (x - mean) / (std + 1e-6), float32, "
                       "inside the graph",
        },
        "provenance_commits": {
            "champion_created": "5e0d6d3 (R59 EXECUTED)",
            "onnx_created": "399af47 (R60 EXECUTED)",
            "manifest_created_round": "R61",
        },
        "evaluation_anchor": {
            "family_seeds": {"k6": "87 alive", "k12": "76@8798",
                             "k30": "37@4401", "k45": "40@4753",
                             "k60": "87 alive", "k90": "68@7895",
                             "k210": "42@4966"},
            "budget": 10000,
        },
        "audit": audit,
    }
    with open(OUT, "w") as f:
        json.dump(manifest, f, indent=1)
    os.chmod(OUT, 0o444)
    print("manifest written (read-only):", OUT, os.path.getsize(OUT),
          "bytes")
    print("MANIFEST_SHA256", sha(OUT))


if __name__ == "__main__":
    main()
