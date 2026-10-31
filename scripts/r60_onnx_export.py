#!/usr/bin/env python3
"""r60_onnx_export.py — R60: export the R59 champion
(r59_soup_e6a010.npz) to ONNX with byte-faithful numerics.

The ONNX boundary = the DECISION FUNCTION exactly as deployed:
    x_norm = (x - mean) / (std + 1e-6)          # float32, meta norm
    h      = relu(x_norm @ W1 + b1)             # 10 -> 128
    logits = h @ W2 + b2                        # 128 -> 2
    action = classes[argmax(logits)]            # [HOVER, FLAP]
The perception state machine (BirdObserverV7 / GapTrackerV7 + the
policy's own history counters) stays in the numpy host — it is pure
frame processing, no learned weights.

Everything is float32 verbatim from the champion npz + its meta json;
the epsilon lives INSIDE the folded constant (std+1e-6) exactly like
the deployed line `(x - self.mean) / (self.std + 1e-6)`.

Outputs:
  data/learn/r60_soup_e6a010.onnx          (the deployment artifact)
  data/learn/r60_soup_e6a010.onnx.json     (sidecar: provenance+parity)
"""
import hashlib
import json
import os

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

REPO = "/home/z/my-project/ps1ai"
DATA = os.path.join(REPO, "data", "learn")
CHAMP = os.path.join(DATA, "r59_soup_e6a010.npz")
CHAMP_JSON = CHAMP + ".json"
OUT_ONNX = os.path.join(DATA, "r60_soup_e6a010.onnx")
OUT_JSON = OUT_ONNX + ".json"
OPSET = 17
EPS = 1e-6


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    z = np.load(CHAMP)
    meta = json.load(open(CHAMP_JSON))
    W1 = z["W1"].astype(np.float32)
    b1 = z["b1"].astype(np.float32)
    W2 = z["W2"].astype(np.float32)
    b2 = z["b2"].astype(np.float32)
    mean = np.asarray(meta["norm"]["mean"], dtype=np.float32)
    std = np.asarray(meta["norm"]["std"], dtype=np.float32)
    # the EXACT deployed normalization constant, folded:
    # numpy2 NEP50: float32 array + python float -> float32
    std_eps = (std + EPS).astype(np.float32)
    classes = list(meta["classes"])
    n_in, hidden, n_out = W1.shape[0], W1.shape[1], W2.shape[1]
    assert (n_in, hidden, n_out) == (10, 128, 2), (n_in, hidden, n_out)
    assert classes == ["HOVER", "FLAP"], classes

    mean2 = mean.reshape(1, n_in)
    std2 = std_eps.reshape(1, n_in)

    inits = [
        numpy_helper.from_array(mean2, "mean"),
        numpy_helper.from_array(std2, "std_eps"),
        numpy_helper.from_array(W1, "W1"),
        numpy_helper.from_array(b1, "b1"),
        numpy_helper.from_array(W2, "W2"),
        numpy_helper.from_array(b2, "b2"),
    ]
    inp = helper.make_tensor_value_info("x", TensorProto.FLOAT, ["N", n_in])
    out_logits = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, ["N", n_out])
    out_idx = helper.make_tensor_value_info(
        "action_idx", TensorProto.INT64, ["N"])
    nodes = [
        helper.make_node("Sub", ["x", "mean"], ["xn"]),
        helper.make_node("Div", ["xn", "std_eps"], ["xnorm"]),
        # weights stored verbatim (10,128)/(128,2): Gemm transB=0 -> x@W1
        helper.make_node("Gemm", ["xnorm", "W1", "b1"], ["hpre"]),
        helper.make_node("Relu", ["hpre"], ["h"]),
        helper.make_node("Gemm", ["h", "W2", "b2"], ["logits"]),
        helper.make_node("ArgMax", ["logits"], ["action_idx"], axis=1,
                         keepdims=0, select_last_index=0),
    ]
    graph = helper.make_graph(
        nodes, "r59_soup_e6a010_decision", [inp],
        [out_logits, out_idx], inits)
    model = helper.make_model(
        graph, opset_imports=[helper.make_opsetid("", OPSET)],
        producer_name="ps1ai-r60-onnx-export")
    model.ir_version = 8  # broad runtime compatibility
    onnx.checker.check_model(model)
    onnx.save(model, OUT_ONNX)
    sha = sha256_file(OUT_ONNX)
    size = os.path.getsize(OUT_ONNX)
    print("onnx written:", OUT_ONNX, size, "bytes sha", sha[:16])

    # ---- in-script numeric parity (numpy reference vs onnxruntime) ----
    import onnxruntime as ort
    sess = ort.InferenceSession(OUT_ONNX, providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(60)
    # synthetic sweep around the recorded norm distribution
    X = (rng.standard_normal((200_000, n_in)).astype(np.float32)
         * 1.5 + mean2)
    xn = (X - mean2) / std2
    h_np = np.maximum(xn @ W1 + b1, np.float32(0.0))
    ref = h_np @ W2 + b2
    ref_idx = ref.argmax(axis=1)
    o_logits, o_idx = sess.run(["logits", "action_idx"], {"x": X})
    arg_parity = float((o_idx == ref_idx).mean())
    delta = np.abs(o_logits - ref)
    top2 = np.sort(ref, axis=1)
    margin = top2[:, 1] - top2[:, 0]
    stats = {
        "sweep_vectors": int(X.shape[0]),
        "argmax_parity": arg_parity,
        "logit_max_abs_delta": float(delta.max()),
        "logit_mean_abs_delta": float(delta.mean()),
        "min_top2_margin": float(margin.min()),
        "argmax_mismatch_count": int((o_idx != ref_idx).sum()),
    }
    print(json.dumps(stats, indent=1))
    if arg_parity < 1.0:
        print("WARNING: sweep argmax mismatches — inspect margins")

    side = {
        "format": "onnx-decision-v1",
        "created": __import__("time").time(),
        "game": "flappy",
        "source_checkpoint": "r59_soup_e6a010.npz",
        "source_sha256": sha256_file(CHAMP),
        "source_provenance": meta.get("teacher"),
        "soup": meta.get("soup"),
        "arch": {"n_in": n_in, "hidden": hidden, "n_out": n_out},
        "classes": classes,
        "norm": {"mean": mean.tolist(), "std_eps": std_eps.tolist(),
                 "epsilon": EPS,
                 "note": ("the graph input x is the RAW v7 decision "
                          "vector; normalization is INSIDE the graph "
                          "(std_eps = std + epsilon, float32)")},
        "feature_version": meta.get("feature_version"),
        "control_mode": meta.get("control_mode"),
        "onnx": {
            "opset": OPSET,
            "ir_version": 8,
            "epsilon_folded_into_std": EPS,
            "graph": ("Sub(mean) -> Div(std+eps) -> Gemm(W1,b1) "
                      "-> Relu -> Gemm(W2,b2) -> logits; "
                      "ArgMax(axis=1, first-max) -> action_idx"),
            "float32_verbatim_weights": True,
            "bytes": size,
            "sha256": sha,
        },
        "export_parity_sweep": stats,
        "boundary_disclosure": (
            "the ONNX graph covers the decision function ONLY "
            "(normalize+MLP+argmax); the perception state machine "
            "(BirdObserverV7, GapTrackerV7, since_flap/flap_run/"
            "last_gc/since_gap) is pure numpy frame processing in the "
            "host (ps1play/learn/visual_only.py Brain._vector) and "
            "carries no learned weights"),
    }
    json.dump(side, open(OUT_JSON, "w"), indent=1)
    print("sidecar written:", OUT_JSON)


if __name__ == "__main__":
    main()
