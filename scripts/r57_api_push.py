#!/usr/bin/env python3
"""r57_api_push.py — R57 intake round push via the Git Data API.

Commits (base f5a47a6):
  docs/r57_mission.md               — canonical verbatim R57 mission text
  docs/r57_mission_review.md        — line-by-line audit (22 findings)
  docs/small_games_status_report.md — += section 6 (R57 intake)
  scripts/r57_issue_report.py       — issue creation + #12 cross-link
  scripts/r57_api_push.py           — this script

Every round of this repo pushes through the Git Data API
(blobs -> tree -> commit -> ref) and verifies the remote by reading the
commit and each file's blob SHA back. Run from the repo root:
  python3 scripts/r57_api_push.py
"""
import base64
import hashlib
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BASE_COMMIT = "f5a47a6a6310"          # R56 reported commit — verified below
BRANCH = "heads/main"
COMMIT_MESSAGE = (
    "R57 intake: canonical mission text + line-by-line review (22 findings) "
    "+ status report section 6 + round scripts (issue split from #12 by "
    "owner directive)"
)

FILES = [
    "docs/r57_mission.md",
    "docs/r57_mission_review.md",
    "docs/small_games_status_report.md",
    "scripts/r57_issue_report.py",
    "scripts/r57_api_push.py",
]

STAGING = "/home/z/my-project/r57work"


def local_sha(path):
    return hashlib.sha1(
        b"blob " + str(len(open(path, "rb").read())).encode()
        + b"\x00" + open(path, "rb").read()
    ).hexdigest()


def main():
    # 0. verify base
    s, ref = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    head = ref["object"]["sha"]
    print("remote main:", head[:12])
    assert head.startswith(BASE_COMMIT), f"remote moved: {head} != {BASE_COMMIT}"
    s, base_c = req(f"/repos/{REPO}/git/commits/{head}")
    base_tree = base_c["tree"]["sha"]
    print("base tree:", base_tree[:12])

    tree_items = []
    for rel in FILES:
        local = f"{STAGING}/{rel}"
        content = open(local, "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        assert s == 201, (rel, s, blob)
        tree_items.append({"path": rel, "mode": "100644",
                           "type": "blob", "sha": blob["sha"]})
        print(f"blob {rel}: {blob['sha'][:12]} (local git-sha {local_sha(local)[:12]})")

    # 1. new tree on top of the base tree
    s, tree = req(f"/repos/{REPO}/git/trees", method="POST", payload={
        "base_tree": base_tree, "tree": tree_items})
    assert s == 201, ("tree", s, tree)
    print("new tree:", tree["sha"][:12])

    # 2. commit
    s, commit = req(f"/repos/{REPO}/git/commits", method="POST", payload={
        "message": COMMIT_MESSAGE, "tree": tree["sha"], "parents": [head]})
    assert s == 201, ("commit", s, commit)
    print("new commit:", commit["sha"][:12])

    # 3. update ref
    s, _ = req(f"/repos/{REPO}/git/refs/{BRANCH}", method="PATCH", payload={
        "sha": commit["sha"], "force": False})
    assert s == 200, ("ref", s)
    print("main updated.")

    # 4. verify by reading back
    s, ref2 = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert ref2["object"]["sha"] == commit["sha"], "ref read-back mismatch"
    s, c2 = req(f"/repos/{REPO}/git/commits/{commit['sha']}")
    got = {t["path"]: t["sha"] for t in c2["tree"]["tree"]}
    ok = True
    for rel in FILES:
        want = next(i["sha"] for i in tree_items if i["path"] == rel)
        status = "OK " if got.get(rel) == want else "MISMATCH"
        if got.get(rel) != want:
            ok = False
        print(f"  read-back {status} {rel} {got.get(rel, 'MISSING')[:12]}")
    s, comm = req(f"/repos/{REPO}/commits/{commit['sha']}")
    print("remote commit page:", s, "| files changed:",
          [f["filename"] for f in comm.get("files", [])])
    print("VERIFY:", "PASS" if ok and s == 200 else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
