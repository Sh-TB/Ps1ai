#!/usr/bin/env python3
"""r59_api_push.py — R59 pre-collection push via the Git Data API.

Commits (on top of the R58 head d5b6c52):
  data/learn/r59_seed_splits.json    — the fresh TEST split, committed
                                       BEFORE any TEST collection
  data/learn/r59_soup_e6a010.npz     — the soup candidate (7.1 KB)
  data/learn/r59_soup_e6a010.npz.json— its meta (norm/arch verbatim
                                       from the base artifact)
  data/learn/r59_linpath_results.json — the R59-A probe table (dev
                                       evidence on TRAIN/VAL seeds only)
  scripts/r59a_linpath.py            — the linear-path probe
  scripts/r59_prep.py                — split/artifact prep
  scripts/r59b_test.py               — the chunked TEST runner
  scripts/r59_api_push.py            — this script

Every round of this repo pushes through the Git Data API
(blobs -> tree -> commit -> ref) and verifies the remote by reading the
commit and each file's blob SHA back.
"""
import base64
import hashlib
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BASE_COMMIT = "d5b6c52ee7f0"          # the R58 reported head — verified below
BRANCH = "heads/main"
COMMIT_MESSAGE = (
    "R59 pre-collection: fresh TEST split committed BEFORE collection "
    "(multiples-of-4 rule, every prior use excluded: r53-r56 history, "
    "R57+R58 TEST, R58/R59 dev) + the soup candidate r59_soup_e6a010 "
    "(r58_dir2p_true + 0.10*(si_v2_e6 - base); family strictly dominates "
    "the base: k45 33->40, every other seed identical incl. both "
    "razor-edges 87-alive and VAL 68/42; regression gate PASS) + "
    "linear-path probe scripts + dev evidence. NO TEST frames yet."
)

FILES = [
    "data/learn/r59_seed_splits.json",
    "data/learn/r59_soup_e6a010.npz",
    "data/learn/r59_soup_e6a010.npz.json",
    "data/learn/r59_linpath_results.json",
    "scripts/r59a_linpath.py",
    "scripts/r59_prep.py",
    "scripts/r59b_test.py",
    "scripts/r59_api_push.py",
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
        local = f"{REPODIR}/{rel}"
        content = open(local, "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        assert s == 201, (rel, s, blob)
        assert blob["sha"] == local_sha(local), \
            f"local/blob sha mismatch {rel}"
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

    # --- read-back verification ---
    s, ref2 = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert ref2["object"]["sha"] == commit["sha"]
    s, c2 = req(f"/repos/{REPO}/git/commits/{commit['sha']}")
    print("commit read-back OK:", c2["sha"][:12],
          "| files:", len(c2.get("files", [])))
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
