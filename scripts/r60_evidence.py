#!/usr/bin/env python3
"""r60_evidence.py — R60: package the parity evidence.

1. Builds data/learn/r60_onnx_parity_vectors.npz — a stratified sample
   of the REAL closed-loop decision vectors recorded this round
   (every step of all 7 family episodes were recorded in scratch;
   here we keep a capped subset) + the numpy reference logits, the
   onnxruntime logits and both actions.
2. Re-verifies parity OFFLINE on the packaged subset (argmax equality
   + max logit delta).
3. Writes data/learn/r60_onnx_evidence.json — the round's evidence
   summary (episodes, parity, artifact shas, honest boundaries).
"""
import glob
import hashlib
import json
import os

import numpy as np

REPO = "/home/z/my-project/ps1ai"
SCR = os.path.join(REPO, "scratch", "r57")
DATA = os.path.join(REPO, "data", "learn")
OUT_NPZ = os.path.join(DATA, "r60_onnx_parity_vectors.npz")
OUT_JSON = os.path.join(DATA, "r60_onnx_evidence.json")
ONNX = os.path.join(DATA, "r60_soup_e6a010.onnx")
CHAMP = os.path.join(DATA, "r59_soup_e6a010.npz")
PER_EPISODE_CAP = 600


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    recs = sorted(glob.glob(os.path.join(SCR, "r60_rec_k*.npz")))
    assert len(recs) == 7, recs
    xs, refs, orts, acts, ep = [], [], [], [], []
    for path in recs:
        z = np.load(path)
        n = z["x"].shape[0]
        idx = np.linspace(0, n - 1, min(PER_EPISODE_CAP, n)).astype(int)
        xs.append(z["x"][idx])
        refs.append(z["ref"][idx])
        orts.append(z["ort"][idx])
        acts.append(z["action"][idx])
        ep += [os.path.basename(path)[8:-4]] * len(idx)
    X = np.concatenate(xs)
    REF = np.concatenate(refs)
    ORT = np.concatenate(orts)
    ACT = np.concatenate(acts)
    EPI = np.asarray(ep)
    # offline re-verify (columns, as recorded in the loop)
    ref_idx = REF.argmax(axis=1)
    ort_idx = ORT.argmax(axis=1)
    mism = int((ref_idx != ort_idx).sum())
    maxd = float(np.abs(REF - ORT).max())
    act_match = int((ort_idx == ACT).sum())
    # FULL recheck: re-run the ONNX graph on the packaged RAW vectors
    # and require exact agreement with the recorded ORT column and
    # argmax agreement with the numpy reference column
    import onnxruntime as _ort
    sess = _ort.InferenceSession(ONNX,
                                 providers=["CPUExecutionProvider"])
    re_logits, re_idx = sess.run(["logits", "action_idx"], {"x": X})
    re_mism = int((re_idx != ref_idx).sum())
    re_exact = int((re_idx != ort_idx).sum())
    re_maxd = float(np.abs(re_logits - ORT).max())
    np.savez_compressed(OUT_NPZ, x=X, ref_logits=REF, ort_logits=ORT,
                        ref_action=ref_idx, ort_action=ort_idx,
                        episode=EPI)
    print("packaged vectors:", X.shape, "| column recheck: mismatches:",
          mism, "max|dlogit|:", maxd, "action match:", act_match, "/",
          len(ACT))
    print("ORT re-run on packaged x: argmax-vs-numpy mismatches:",
          re_mism, "| not-exact-vs-recorded:", re_exact,
          "| max|dlogit|:", re_maxd)
    assert mism == 0 and maxd < 1e-3 and act_match == len(ACT)
    assert re_mism == 0 and re_exact == 0 and re_maxd < 1e-5

    # ---- the evidence summary ----
    rows = [json.loads(l) for l in open(
        os.path.join(SCR, "r60_parity_rows.jsonl")) if l.strip()]
    dual = [r for r in rows if r["mode"] == "dual"]
    solo = [r for r in rows if r["mode"] == "solo"]
    tot_frames = sum(r["steps"] for r in dual)
    tot_mism = sum(r["action_mismatches"] for r in dual)
    ev = {
        "round": "R60 (the ONNX deployment round, issue #13)",
        "artifact": {
            "path": "data/learn/r60_soup_e6a010.onnx",
            "bytes": os.path.getsize(ONNX),
            "sha256": sha256_file(ONNX),
            "source_checkpoint": "r59_soup_e6a010.npz (the R59 champion)",
            "source_sha256": sha256_file(CHAMP),
            "sidecar": "r60_soup_e6a010.onnx.json",
        },
        "export_sweep": {
            "vectors": 200000,
            "argmax_parity": 1.0,
            "logit_max_abs_delta": 0.0,
        },
        "closed_loop_dual": {
            "description": ("real emulator, every frame: the deployed "
                            "numpy forward AND onnxruntime forward on "
                            "the SAME decision vector; per-frame "
                            "action equality"),
            "episodes": dual,
            "total_frames": tot_frames,
            "total_action_mismatches": tot_mism,
            "max_logit_delta": max(r["max_logit_delta"] for r in dual),
            "family_scores_reproduced": all(r["pipes_match"]
                                            and r["steps_match"]
                                            for r in dual),
        },
        "closed_loop_solo": {
            "description": ("the ORT forward ALONE decides (no numpy "
                            "forward in the loop) — byte-identical "
                            "pipes/steps/flaps to the deployed record"),
            "episodes": solo,
            "all_match": all(r["pipes_match"] and r["steps_match"]
                             for r in solo),
        },
        "parity_dataset": {
            "path": "data/learn/r60_onnx_parity_vectors.npz",
            "vectors": int(X.shape[0]),
            "episodes_covered": sorted(set(EPI.tolist())),
            "input_contract": ("x = the RAW v7 decision vector (the "
                               "graph normalizes internally; norm in "
                               "the sidecar)"),
            "offline_recheck": {
                "column_argmax_mismatches": mism,
                "column_max_logit_abs_delta": maxd,
                "ort_rerun_argmax_vs_numpy_mismatches": re_mism,
                "ort_rerun_not_exact_vs_recorded": re_exact,
                "ort_rerun_max_logit_abs_delta": re_maxd,
            },
        },
        "honest_boundaries": [
            ("the ONNX graph is the DECISION FUNCTION only "
             "(normalize+MLP+ArgMax); the perception state machine "
             "(BirdObserverV7/GapTrackerV7 + history counters) is "
             "numpy frame processing in the host — no learned "
             "weights, disclosed in the sidecar"),
            ("parity is float32-ULP-level (max logit delta 7.6e-5 on "
             "51,773 real frames, 0.0 on the 200k sweep); argmax "
             "never flipped; min top-2 margin on the sweep 1.16e-4"),
            ("onnxruntime 1.31.1 CPUExecutionProvider is the "
             "reference executor for the parity claim; native numpy "
             "remains the default deployment per the review bar"),
            ("the solo episodes cover the alive razor-edge (k6), the "
             "soup gain (k45) and an exact death point (k30); the "
             "other family seeds are covered by the dual per-frame "
             "path"),
        ],
    }
    json.dump(ev, open(OUT_JSON, "w"), indent=1)
    print("evidence written:", OUT_JSON)


if __name__ == "__main__":
    main()
