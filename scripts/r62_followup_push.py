#!/usr/bin/env python3
"""r62_followup_push.py — the R62 follow-up push via the Git Data API
(the r58..r62 practice): commits scripts/r62_issue_update.py and the
worklog addendum, then verifies every pushed blob by SHA read-back."""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

COMMIT_MESSAGE = (
    "R62 follow-up: the issue-update script (the final closure comment "
    "posted to #14 + read back byte-identical + the issue closed as "
    "completed, state read back) — completes the r62_* script set"
)

FILES = [
    "scripts/r62_issue_update.py",
    "worklog.md",
]


def local_sha(path):
    data = open(path, "rb").read()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def main():
    s, ref = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert s == 200, ref
    head = ref["object"]["sha"]
    assert head.startswith("e6faee0"), f"unexpected remote head {head}"
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
