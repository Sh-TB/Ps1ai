#!/usr/bin/env python3
"""r66_push.py — push ONE local commit to remote main via the Git Data
API (the r58..r65 practice, parameterized): uploads every changed
blob with SHA read-back verification, creates the tree + commit on
top of the remote HEAD, moves main, then re-reads the remote state
and re-verifies every pushed path byte-for-byte.

usage: python3 scripts/r66_push.py <local-commit-sha>
"""
import base64
import hashlib
import subprocess
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

LOCAL_HEAD = sys.argv[1] if len(sys.argv) > 1 else None
assert LOCAL_HEAD, "usage: r66_push.py <local-commit-sha>"
FILES = subprocess.run(
    ["git", "diff", "--name-only", LOCAL_HEAD + "^", LOCAL_HEAD],
    cwd=REPODIR, capture_output=True, text=True).stdout.split()
assert FILES, f"no diff for {LOCAL_HEAD}"


def local_blob_sha(path):
    data = open(path, "rb").read()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def git_mode(commit, path):
    out = subprocess.run(
        ["git", "ls-tree", commit, "--", path],
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
    local_parent_tree = subprocess.run(
        ["git", "rev-parse", LOCAL_HEAD + "^^{tree}"], cwd=REPODIR,
        capture_output=True, text=True).stdout.strip()
    # API-created commits carry their own timestamps, so the guard
    # compares TREES, not commit SHAs (the r65 lesson)
    assert base_tree == local_parent_tree, \
        f"remote tree {base_tree} != local parent tree " \
        f"{local_parent_tree} — refusing to push"

    tree_items = []
    for rel in FILES:
        full = f"{REPODIR}/{rel}"
        content = open(full, "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST",
                      payload={"content":
                               base64.b64encode(content).decode(),
                               "encoding": "base64"})
        assert s == 201, (rel, s, blob)
        assert blob["sha"] == local_blob_sha(full), rel
        tree_items.append({"path": rel, "mode": git_mode(LOCAL_HEAD,
                                                         rel),
                           "type": "blob", "sha": blob["sha"]})
    print(f"uploaded+verified {len(tree_items)} blobs")

    s, tree = req(f"/repos/{REPO}/git/trees", method="POST", payload={
        "base_tree": base_tree, "tree": tree_items})
    assert s == 201, tree
    msg = subprocess.run(
        ["git", "log", "-1", "--pretty=%B", LOCAL_HEAD], cwd=REPODIR,
        capture_output=True, text=True).stdout
    s, commit = req(f"/repos/{REPO}/git/commits", method="POST",
                    payload={"message": msg, "tree": tree["sha"],
                             "parents": [head]})
    assert s == 201, commit
    s, u = req(f"/repos/{REPO}/git/refs/{BRANCH}", method="PATCH",
               payload={"sha": commit["sha"], "force": False})
    assert s == 200, u
    print("pushed commit:", commit["sha"][:12])

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
