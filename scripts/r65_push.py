#!/usr/bin/env python3
"""r65_push.py — the R65 push via the Git Data API (the r58..r64
practice): pushes the LOCAL R65 commit's tree (7e99689) by uploading
every changed blob with SHA read-back verification, creating the tree
+ commit, and moving main.  Then re-reads the remote HEAD and
re-verifies every key path byte-for-byte."""
import base64
import hashlib
import subprocess
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

# the paths to push: whatever differs between the local HEAD and its
# parent (the R65 main commit and this follow-up both used this)
LOCAL_HEAD = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPODIR,
                            capture_output=True, text=True).stdout.strip()
FILES = subprocess.run(
    ["git", "diff", "--name-only", LOCAL_HEAD + "^", LOCAL_HEAD],
    cwd=REPODIR, capture_output=True, text=True).stdout.split()


def local_blob_sha(path):
    data = open(path, "rb").read()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def git_mode(path):
    out = subprocess.run(["git", "ls-tree", LOCAL_HEAD, "--", path],
                         cwd=REPODIR, capture_output=True, text=True)
    line = out.stdout.split("\n")[0]
    return line.split()[0] if line else "100644"


def main():
    s, ref = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert s == 200, ref
    head = ref["object"]["sha"]
    s, base_c = req(f"/repos/{REPO}/git/commits/{head}")
    assert s == 200, base_c
    base_tree = base_c["tree"]["sha"]
    # safety: the remote tree must match our local parent's tree
    # (API-created commits carry their own timestamps, so the parent
    # SHAs legitimately differ — content is what must match)
    local_parent_tree = subprocess.run(
        ["git", "rev-parse", LOCAL_HEAD + "^^{tree}"], cwd=REPODIR,
        capture_output=True, text=True).stdout.strip()
    assert base_tree == local_parent_tree, \
        f"remote tree {base_tree} != local parent tree " \
        f"{local_parent_tree} — refusing to push"

    tree_items = []
    for rel in FILES:
        full = f"{REPODIR}/{rel}"
        content = open(full, "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        assert s == 201, (rel, s, blob)
        assert blob["sha"] == local_blob_sha(full), rel
        tree_items.append({"path": rel, "mode": git_mode(rel),
                           "type": "blob", "sha": blob["sha"]})
    print(f"uploaded+verified {len(tree_items)} blobs")

    s, tree = req(f"/repos/{REPO}/git/trees", method="POST", payload={
        "base_tree": base_tree, "tree": tree_items})
    assert s == 201, tree
    msg = subprocess.run(
        ["git", "log", "-1", "--pretty=%B", LOCAL_HEAD], cwd=REPODIR,
        capture_output=True, text=True).stdout
    s, commit = req(f"/repos/{REPO}/git/commits", method="POST", payload={
        "message": msg, "tree": tree["sha"], "parents": [head]})
    assert s == 201, commit
    s, u = req(f"/repos/{REPO}/git/refs/{BRANCH}", method="PATCH",
               payload={"sha": commit["sha"], "force": False})
    assert s == 200, u
    print("pushed commit:", commit["sha"][:12])

    # read-back: remote HEAD + every key path byte-identical
    s, ref2 = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert ref2["object"]["sha"] == commit["sha"]
    bad = []
    for rel in FILES:
        full = f"{REPODIR}/{rel}"
        s, r = req(f"/repos/{REPO}/contents/{rel}?ref="
                   f"{commit['sha']}")
        if s != 200:
            bad.append((rel, "missing"))
            continue
        remote = base64.b64decode(r["content"])
        if hashlib.sha1(b"blob " + str(len(remote)).encode() +
                        b"\x00" + remote).hexdigest() != \
                local_blob_sha(full):
            bad.append((rel, "sha mismatch"))
    print(f"read-back: {len(FILES) - len(bad)}/{len(FILES)} "
          f"byte-identical")
    if bad:
        print("MISMATCHES:", bad[:10])
        sys.exit(1)
    print("REMOTE VERIFIED — main =", commit["sha"][:12])


if __name__ == "__main__":
    main()
