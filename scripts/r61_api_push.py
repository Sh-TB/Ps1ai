#!/usr/bin/env python3
"""r61_api_push.py — the R61 final push via the Git Data API (the
r58/r59/r60 practice: blobs -> tree(base_tree) -> commit -> ref PATCH
-> per-file blob SHA read-back).

Commits the complete R61 closure: the frozen-model manifest, the
independent deployment package (code + model + manifest + docs), the
parity/profile/validation/pong evidence, the pre-registered split, the
R61 scripts + tests, both closure documents, and the worklog entry.
"""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BASE_COMMIT = "d8bcbd3"
BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

COMMIT_MESSAGE = (
    "R61 EXECUTED — FINAL CLOSURE: the training phase ends. Model "
    "frozen + provenance-proof (r61a 14/14 PASS: champion npz "
    "72c79f30... bitwise re-derived as r58_dir2p_true + 0.10*"
    "(r58_si_v2_e6 - r58_dir2p_true); ONNX 4dd592a7... initializers "
    "bitwise-equal; topology/opset/dtype/action-mapping verified; "
    "FINAL_MODEL_MANIFEST.json read-only, shipped into the package). "
    "INDEPENDENT DEPLOYMENT PACKAGE deployment/flappybird_policy/ "
    "(numpy+onnxruntime only, zero training/teacher imports — AST + "
    "fresh-subprocess isolation proof; strict enforced input contract; "
    "CLI smoke; pinned deps; README/INSTALL/INTERFACE/MODEL_CARD/"
    "KNOWN_LIMITATIONS/TROUBLESHOOTING/REUSE_BOUNDARY). PARITY: 220,522 "
    "deterministic vectors, 3-way (numpy reference / bare ORT / the "
    "package as external consumer): argmax 100%, max |dlogit| 0.0, min "
    "top-2 margin 4.23e-4; 6/6 malformed classes rejected; R60's 4,200 "
    "REAL vectors rechecked exact. EMULATOR: family 7/7 byte-exact "
    "through the package (k6 87-alive/640 ... k210 42@4966/322); fresh "
    "pre-registered 30-seed validation (k%7 rule, all prior uses "
    "excluded, split on disk 9.5 min before collection) x deploy n=2 + "
    "base n=1 + C1 n=1 = 180 episodes / 719,714 frames; champion reps "
    "byte-identical on all 30 seeds; 37 cross-process dup groups "
    "byte-identical. COMPARISON: deploy 52.30 mean / 48.0 median vs "
    "base 46.87 / 38.0 (W/T/L 6/23/1) vs C1 53.37 / 50.0 (7/11/12, "
    "disclosed trade-off, no retraining — the stop rule held). "
    "ROBUSTNESS: fault injection green; two incidents disclosed + "
    "fixed + regression-tested (runner reset_obs omission; parallel "
    "workspace race). PROFILE: 10k sustained calls p50 0.037 ms "
    "(~22.5k/s), perception adapter 1.11 ms/frame dominates; CPU-only "
    "suitable. CLEAN-ROOM install PASS (fresh venv, pinned deps only). "
    "REGRESSIONS: suite 667 passed + 1 skipped + 1 xfailed; hello_pong "
    "PASS — teachers 7/0 each, student 8/2, gameAI [19,19] (the exact "
    "R54/R59/R60 record). RELEASE GATE 9/9 PASS (r61_final_verify.py "
    "-> r61_gate_result.json). TRAINING_STATUS: CLOSED. HONEST: "
    "decision-only ONNX boundary, numpy host dependency, float32-CPU "
    "parity scope, Linux-only portability claim, no screenshots for "
    "grid episodes (trace hashes + byte-identity + live re-runs are "
    "the evidence)"
)

FILES = [
    # the frozen model + evidence
    "data/learn/FINAL_MODEL_MANIFEST.json",
    "data/learn/r61_validation_split.json",
    "data/learn/r61_validation_rows.jsonl",
    "data/learn/r61_validation_summary.json",
    "data/learn/r61_family_rows.jsonl",
    "data/learn/r61_parity_evidence.json",
    "data/learn/r61_parity_worstcase.npz",
    "data/learn/r61_profile.json",
    "data/learn/r61_pong_regression.json",
    "data/learn/r61_runner_incident.json",
    "data/learn/r61_gate_result.json",
    "data/learn/r61_final_closure.json",
    # the deployment package
    "deployment/flappybird_policy/flappybird_policy/__init__.py",
    "deployment/flappybird_policy/flappybird_policy/policy.py",
    "deployment/flappybird_policy/flappybird_policy/schema.py",
    "deployment/flappybird_policy/flappybird_policy/version.py",
    "deployment/flappybird_policy/flappybird_policy/__main__.py",
    "deployment/flappybird_policy/examples/minimal_example.py",
    "deployment/flappybird_policy/models/r60_soup_e6a010.onnx",
    "deployment/flappybird_policy/models/r60_soup_e6a010.onnx.json",
    "deployment/flappybird_policy/models/FINAL_MODEL_MANIFEST.json",
    "deployment/flappybird_policy/requirements.txt",
    "deployment/flappybird_policy/README.md",
    "deployment/flappybird_policy/INSTALL.md",
    "deployment/flappybird_policy/INTERFACE.md",
    "deployment/flappybird_policy/MODEL_CARD.md",
    "deployment/flappybird_policy/KNOWN_LIMITATIONS.md",
    "deployment/flappybird_policy/TROUBLESHOOTING.md",
    "deployment/flappybird_policy/REUSE_BOUNDARY.md",
    # scripts + tests
    "scripts/r61a_model_audit.py",
    "scripts/r61_restore_tb_manifest.py",
    "scripts/r61b_parity_suite.py",
    "scripts/r61c_validation_split.py",
    "scripts/r61d_validation_stats.py",
    "scripts/r61e_deploy_loop.py",
    "scripts/r61f_profile.py",
    "scripts/r61_final_verify.py",
    "scripts/r61_api_push.py",
    "scripts/r61_cleanroom.sh",
    "scripts/r61_parallel_chunk.sh",
    "scripts/r61_run_validation.sh",
    "tests/test_r61_deployment.py",
    # docs + worklog
    "docs/r61_final_closure.md",
    "docs/r61_training_record.md",
    "worklog.md",
]


def local_sha(path):
    data = open(path, "rb").read()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def main():
    s, ref = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    head = ref["object"]["sha"]
    print("remote main:", head[:12])
    assert head.startswith(BASE_COMMIT), f"remote moved: {head}"
    s, base_c = req(f"/repos/{REPO}/git/commits/{head}")
    base_tree = base_c["tree"]["sha"]

    tree_items = []
    for rel in FILES:
        content = open(f"{REPODIR}/{rel}", "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        assert s == 201, (rel, s, blob)
        assert blob["sha"] == local_sha(f"{REPODIR}/{rel}")
        tree_items.append({"path": rel, "mode": "100644",
                           "type": "blob", "sha": blob["sha"]})
        print("blob", rel, blob["sha"][:12])

    s, tree = req(f"/repos/{REPO}/git/trees", method="POST", payload={
        "base_tree": base_tree, "tree": tree_items})
    assert s == 201, tree
    s, commit = req(f"/repos/{REPO}/git/commits", method="POST", payload={
        "message": COMMIT_MESSAGE, "tree": tree["sha"],
        "parents": [head]})
    assert s == 201, commit
    s, _ = req(f"/repos/{REPO}/git/refs/{BRANCH}", method="PATCH",
               payload={"sha": commit["sha"], "force": False})
    assert s == 200, s

    s, ref2 = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert ref2["object"]["sha"] == commit["sha"]
    print("commit read-back OK:", commit["sha"][:12])
    ok = True
    for rel in FILES:
        s, item = req(f"/repos/{REPO}/contents/{rel}?ref={commit['sha']}")
        good = (s == 200 and item.get("sha") == local_sha(
            f"{REPODIR}/{rel}"))
        ok &= good
        print(("  OK  " if good else "  FAIL"), rel,
              item.get("sha", "?")[:12])
    print("PUSH_VERIFIED" if ok else "PUSH_FAILED")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
