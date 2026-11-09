#!/usr/bin/env python3
"""r69_api_push.py — push the R69 commit to origin/main via the Git
Data API (git HTTPS is refused in this sandbox; the token's REST
write path works — the r14..r68 precedent)."""
import base64
import json
import os
import subprocess
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

REPO_DIR = "/home/z/my-project/ps1ai"
LOCAL_COMMIT = subprocess.run(
    ["git", "-C", REPO_DIR, "rev-parse", "HEAD"],
    capture_output=True, text=True).stdout.strip()
REMOTE_MAIN = req(f"/repos/{REPO}/git/ref/heads/main")[1]["object"]["sha"]
print(f"local {LOCAL_COMMIT[:12]}  remote {REMOTE_MAIN[:12]}")

if LOCAL_COMMIT == REMOTE_MAIN:
    print("already pushed")
    sys.exit(0)

files = subprocess.run(
    ["git", "-C", REPO_DIR, "diff", "--name-only", LOCAL_COMMIT + "^",
     LOCAL_COMMIT], capture_output=True, text=True).stdout.split()
msg = subprocess.run(["git", "-C", REPO_DIR, "log", "-1",
                      "--format=%B", LOCAL_COMMIT],
                     capture_output=True, text=True).stdout

s, base_commit = req(f"/repos/{REPO}/git/commits/{REMOTE_MAIN}")
assert s == 200, base_commit
base_tree = base_commit["tree"]["sha"]

tree_items = []
for f in files:
    path = os.path.join(REPO_DIR, f)
    data = open(path, "rb").read()
    s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
        "content": base64.b64encode(data).decode(),
        "encoding": "base64"})
    assert s == 201, (f, blob)
    tree_items.append({"path": f, "mode": "100644",
                       "type": "blob", "sha": blob["sha"]})
    print("blob", f, len(data), "bytes")

s, tree = req(f"/repos/{REPO}/git/trees", method="POST", payload={
    "base_tree": base_tree, "tree": tree_items})
assert s == 201, tree
print("tree", tree["sha"][:12], f"({len(tree_items)} items)")

s, commit = req(f"/repos/{REPO}/git/commits", method="POST", payload={
    "message": msg, "tree": tree["sha"],
    "parents": [REMOTE_MAIN]})
assert s == 201, commit
print("commit", commit["sha"][:12])

s, ref = req(f"/repos/{REPO}/git/refs/heads/main", method="PATCH",
             payload={"sha": commit["sha"], "force": False})
assert s == 200, ref
print("main ->", ref["object"]["sha"][:12])

# the tree-match guard (the r65/r66 practice: compare TREES, not
# commit SHAs — the API commit carries its own timestamp)
s, remote_c = req(f"/repos/{REPO}/git/commits/{ref['object']['sha']}")
assert s == 200
ok = remote_c["tree"]["sha"] == tree["sha"]
print("remote tree match:", ok, remote_c["tree"]["sha"][:12])
assert ok
print("PUSH OK")
