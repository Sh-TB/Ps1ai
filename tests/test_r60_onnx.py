"""R60: the ONNX deployment artifact — model validity + decision
parity against the numpy reference on the committed real-frame
vectors. Skipped cleanly when onnxruntime is not installed (the
native-numpy deployment stays the review-bar default)."""
import json
import os

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data", "learn")
ONNX = os.path.join(DATA, "r60_soup_e6a010.onnx")
SIDECAR = ONNX + ".json"
VECTORS = os.path.join(DATA, "r60_onnx_parity_vectors.npz")

ort = pytest.importorskip("onnxruntime")
onnx = pytest.importorskip("onnx")


def test_artifact_files_exist_and_are_small():
    assert os.path.exists(ONNX)
    assert os.path.exists(SIDECAR)
    assert os.path.exists(VECTORS)
    # the mission artifact bar: <= 4 MiB
    assert os.path.getsize(ONNX) <= 4 * 1024 * 1024


def test_model_passes_onnx_checker_and_matches_sidecar():
    model = onnx.load(ONNX)
    onnx.checker.check_model(model)
    side = json.load(open(SIDECAR))
    assert side["source_checkpoint"] == "r59_soup_e6a010.npz"
    assert side["arch"] == {"n_in": 10, "hidden": 128, "n_out": 2}
    assert side["classes"] == ["HOVER", "FLAP"]
    ins = {i.name: i for i in model.graph.input}
    outs = {o.name: o for o in model.graph.output}
    assert set(ins) == {"x"} and set(outs) == {"logits", "action_idx"}


def test_decision_parity_on_real_closed_loop_vectors():
    z = np.load(VECTORS)
    sess = ort.InferenceSession(ONNX,
                                providers=["CPUExecutionProvider"])
    o_logits, o_idx = sess.run(["logits", "action_idx"], {"x": z["x"]})
    # the committed ORT logits must reproduce exactly (same runtime
    # class of executor), and the numpy reference must agree on argmax
    assert np.array_equal(o_idx, z["ort_action"])
    assert np.array_equal(o_idx, z["ref_action"])
    assert float(np.abs(o_logits - z["ort_logits"]).max()) < 1e-5
    assert float(np.abs(o_logits - z["ref_logits"]).max()) < 1e-3


def test_solo_episode_rows_recorded():
    """The solo (ONNX-only decision) family episodes are recorded in
    the evidence json with byte-exact family scores."""
    ev = json.load(open(os.path.join(DATA, "r60_onnx_evidence.json")))
    assert ev["closed_loop_dual"]["total_action_mismatches"] == 0
    assert ev["closed_loop_dual"]["family_scores_reproduced"] is True
    assert ev["closed_loop_solo"]["all_match"] is True
    solo_seeds = {r["seed"] for r in ev["closed_loop_solo"]["episodes"]}
    assert {"k6", "k45", "k30"} <= solo_seeds
