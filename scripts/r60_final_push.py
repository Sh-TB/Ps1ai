#!/usr/bin/env python3
"""r60_final_push.py — the R60 final push via the Git Data API.

Commits (on top of the R59 head 5e0d6d3):
  docs/r60_execution_report.md          — the round report
  data/learn/r60_soup_e6a010.onnx       — the deployment artifact (7.1 KB)
  data/learn/r60_soup_e6a010.onnx.json  — the sidecar (provenance+contract)
  data/learn/r60_onnx_parity_vectors.npz— 4,200 real decision vectors
  data/learn/r60_onnx_evidence.json     — the structured evidence
  scripts/r60_onnx_export.py            — the exporter
  scripts/r60_parity.py                 — the dual/solo closed-loop harness
  scripts/r60_evidence.py               — the evidence packager
  tests/test_r60_onnx.py                — 4 regression tests
  worklog.md                            — the R60 entry

Push + read-back verification per repo practice.
"""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BASE_COMMIT = "5e0d6d3"
BRANCH = "heads/main"
COMMIT_MESSAGE = (
    "R60 EXECUTED: the ONNX deployment round — the last PENDING badge "
    "closed. r60_soup_e6a010.onnx = 7,182 B (opset 17, checker PASS; "
    "float32-verbatim weights/norm from the unchanged R59 champion, "
    "std+1e-6 folded, ArgMax first-max = numpy semantics; input "
    "contract = the RAW v7 vector, normalization inside the graph; "
    "sidecar discloses the decision-function-only boundary). PARITY: "
    "export sweep 200k vectors argmax 1.0 / max logit delta 0.0; "
    "closed-loop dual on the REAL emulator = all 7 family seeds "
    "reproduce the R59 record EXACTLY (87a/76@8798/37@4401/40@4753/"
    "87a/68@7895/42@4966 with flap counts 640/560/281/302/640/512/322) "
    "across 51,773 frames with 0 action mismatches (max logit delta "
    "7.63e-5); ONNX-ALONE solo run (numpy forward deleted from the "
    "loop) k6 87a/640 + k45 40@4753/302 + k30 37@4401/281 "
    "byte-identical; packaged 4,200 real vectors re-run through ORT "
    "= exact vs recorded, argmax-equal vs numpy 4200/4200. SUITE 642 "
    "passed + 2 skipped + 1 xfailed (4 new tests). hello_pong "
    "regression PASS (refetch bin sha a592f7ed... verified): teachers "
    "7/0 each, student 8/2 — exact R54/R59 record, student still "
    "outscores 8v7. HONEST: parity claimed for float32 CPU executors "
    "only; native numpy stays the default deployment per the review "
    "bar; champion unchanged (deployment, not capability)"
)

FILES = [
    "docs/r60_execution_report.md",
    "data/learn/r60_soup_e6a010.onnx",
    "data/learn/r60_soup_e6a010.onnx.json",
    "data/learn/r60_onnx_parity_vectors.npz",
    "data/learn/r60_onnx_evidence.json",
    "scripts/r60_onnx_export.py",
    "scripts/r60_parity.py",
    "scripts/r60_evidence.py",
    "tests/test_r60_onnx.py",
    "worklog.md",
]

REPODIR = "/home/z/my-project/ps1ai"


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
