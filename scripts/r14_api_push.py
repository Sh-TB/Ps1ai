#!/usr/bin/env python3
"""r14_api_push.py — push the local round-14 commit to origin/main via
the Git Data REST API (the fine-grained token's git-HTTPS path is
refused while Contents RW works via API).

Steps: list changed files vs origin/main -> create blobs (base64,
binary-safe) -> create tree (base_tree=main's tree) -> create commit
(parent=main) -> fast-forward refs/heads/main."""
import base64
import json
import os
import subprocess
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req

REPO = "/home/z/my-project/ps1ai"
API = "/repos/Sh-TB/Ps1ai"


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def main():
    # files changed vs origin/main (including new)
    files = git("diff", "--name-status", "origin/main..HEAD")
    entries = []
    for line in files.splitlines():
        st, path = line.split("\t", 1)
        if st.startswith("R"):
            old, new = path.split("\t")
            entries.append({"path": old, "mode": "100644",
                            "type": "blob", "sha": None})  # deletion marker
            path = new
        full = os.path.join(REPO, path)
        if not os.path.exists(full):
            entries.append({"path": path, "mode": "100644",
                            "type": "blob", "sha": None})
            continue
        with open(full, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        c, blob = req(f"{API}/git/blobs", method="POST",
                      payload={"content": content,
                               "encoding": "base64"})
        if c not in (200, 201):
            print("blob fail", c, path, str(blob)[:200])
            return 1
        entries.append({"path": path, "mode": "100644", "type": "blob",
                        "sha": blob["sha"]})
        print("blob", path, blob["sha"][:10])
    if not entries:
        print("nothing to push")
        return 0
    c,mtree = req(f"{API}/git/trees", method="POST", payload={
        "base_tree": git("rev-parse", "origin/main^{tree}"),
        "tree": entries})
    print("tree:", c, mtree.get("sha"))
    c, mcommit = req(f"{API}/git/commits", method="POST", payload={
        "message": git("log", "-1", "--pretty=%B"),
        "tree": mtree["sha"],
        "parents": [git("rev-parse", "origin/main")]})
    print("commit:", c, mcommit.get("sha"))
    c, ref = req(f"{API}/git/refs/heads/main", method="PATCH",
                 payload={"sha": mcommit["sha"],
                          "force": False})
    print("ref update:", c, str(ref)[:120])
    return 0 if c == 200 else 2


if __name__ == "__main__":
    sys.exit(main())
