#!/usr/bin/env python3
"""r59f_final_push.py — the R59 final report push via the Git Data API.

Commits (on top of the R59 pre-collection head 21f3e0d3):
  docs/r59_execution_report.md          — the round report
  data/learn/r59_flappy_evidence.json   — the structured evidence
  worklog.md                            — the R59-continue entry
  scripts/r59c_stats.py                 — the TEST statistics
  scripts/r59_evidence.py               — the evidence assembler
  scripts/r59f_final_push.py            — this script

Push + read-back verification per repo practice.
"""
import base64
import hashlib
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BASE_COMMIT = "21f3e0d3c8d1"
BRANCH = "heads/main"
COMMIT_MESSAGE = (
    "R59 EXECUTED: linear-path soup probe (e4 path: no soup point — "
    "gains and collapses share the region; e6 path: SOUP POINT at "
    "alpha=0.10 — r59_soup_e6a010 strictly dominates the base on the "
    "family: 6 seeds byte-identical, k45 33->40 (+7, closes the R58 "
    "k45 -1 vs the teacher), both razor-edges 87-alive intact, VAL "
    "exactly base; regression gate PASS with zeros) + FRESH TEST "
    "(split pre-committed 21f3e0d3; 100 episodes, reps byte-identical): "
    "aggregate WIN mean 57.55 vs base 53.65 vs C1 55.00, median 52.5, "
    "floor 24 — claimed at the aggregate level ONLY (15/20 seeds "
    "byte-identical to the base; divergent seeds swing both ways: "
    "k64 +48 / k76 10->87alive vs k80 -26 / k140 -18; C1 keeps the "
    "alive-depth count 6v5) + hello_pong regression PASS (exact R54 "
    "reproduction: teachers 7/0, student 8/2, student still outscores "
    "8v7) + suite 638 passed + 2 skipped + 1 xfailed"
)

FILES = [
    "docs/r59_execution_report.md",
    "data/learn/r59_flappy_evidence.json",
    "worklog.md",
    "scripts/r59c_stats.py",
    "scripts/r59_evidence.py",
    "scripts/r59f_final_push.py",
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
