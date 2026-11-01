#!/usr/bin/env python3
"""r61_reverify_push.py — the R61 post-recycle re-verification push via
the Git Data API (the r58/r59/r60/r61 practice: blobs -> tree(base_tree)
-> commit -> ref PATCH -> per-file blob SHA read-back).

Commits ONLY the re-verification evidence: the refreshed release-gate
JSON (9/9 PASS at head 14be0cd, emulator restored) and the worklog
re-verification entry. No model, code, or doc changes.
"""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

COMMIT_MESSAGE = (
    "R61 RE-VERIFIED post-recycle: the full closure re-proven on a "
    "fresh sandbox — pinned deps reinstalled (onnxruntime 1.19.2 / "
    "numpy 2.1.3, onnx + capstone for test-env modules), the "
    "FlappyBirdPSX v0.1.0 ISO re-fetched (sha b45871d3... = the "
    "committed R56/R58/R59 record), the R57 tb_manifest restored from "
    "the committed dataset meta; suite 668 passed + 1 xfailed (the "
    "recorded emulator-assets skip now PASSES with the disc restored; "
    "669 collected unchanged); RELEASE GATE re-run LIVE 9/9 PASS at "
    "head 14be0cd incl. the real-emulator smoke through the deployment "
    "package (k6 = 87-alive/640 flaps, the byte-exact family record) "
    "+ clean-room install PASS (fresh venv, pinned deps only: CLI "
    "smoke + example + API + version reporting). No model/code/doc "
    "changes — TRAINING_STATUS: CLOSED stands as published."
)

FILES = [
    "data/learn/r61_gate_result.json",
    "worklog.md",
    "scripts/r61_reverify_push.py",
]


def local_sha(path):
    data = open(path, "rb").read()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def main():
    s, ref = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert s == 200, ref
    head = ref["object"]["sha"]
    print("remote main:", head[:12])
    s, base_c = req(f"/repos/{REPO}/git/commits/{head}")
    assert s == 200, base_c
    base_tree = base_c["tree"]["sha"]

    tree_items = []
    for rel in FILES:
        content = open(f"{REPODIR}/{rel}", "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        assert s == 201, (rel, s, blob)
        assert blob["sha"] == local_sha(f"{REPODIR}/{rel}"), rel
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
