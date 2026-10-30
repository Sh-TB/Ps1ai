#!/usr/bin/env python3
"""r57z_push.py — generic Git Data API push for the R57 execution round.

Usage: python3 scripts/r57z_push.py "<commit message>" file1 file2 ...
Verifies base, creates blobs/tree/commit, moves main, reads everything
back (blob SHA equality) and prints VERIFY PASS/FAIL.
"""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"


def git_sha1(path):
    data = open(path, "rb").read()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def main():
    msg = sys.argv[1]
    files = sys.argv[2:]
    s, ref = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    head = ref["object"]["sha"]
    print("base:", head[:12])
    s, c = req(f"/repos/{REPO}/git/commits/{head}")
    base_tree = c["tree"]["sha"]
    items = []
    for rel in files:
        data = open(rel, "rb").read()
        s, blob = req(f"/repos/{REPO}/git/blobs", method="POST", payload={
            "content": base64.b64encode(data).decode(),
            "encoding": "base64"})
        assert s == 201, (rel, s, blob)
        items.append({"path": rel, "mode": "100644", "type": "blob",
                      "sha": blob["sha"]})
        print(f"  blob {rel} {blob['sha'][:10]} (local {git_sha1(rel)[:10]})")
    s, tree = req(f"/repos/{REPO}/git/trees", method="POST", payload={
        "base_tree": base_tree, "tree": items})
    assert s == 201, ("tree", s, tree)
    s, comm = req(f"/repos/{REPO}/git/commits", method="POST", payload={
        "message": msg, "tree": tree["sha"], "parents": [head]})
    assert s == 201, ("commit", s, comm)
    s, _ = req(f"/repos/{REPO}/git/refs/{BRANCH}", method="PATCH",
               payload={"sha": comm["sha"], "force": False})
    assert s == 200, ("ref", s)
    print("commit:", comm["sha"][:12])
    # read back
    s, ref2 = req(f"/repos/{REPO}/git/ref/{BRANCH}")
    assert ref2["object"]["sha"] == comm["sha"]
    s, t2 = req(f"/repos/{REPO}/git/trees/{tree['sha']}?recursive=1")
    remote = {t["path"]: t["sha"] for t in t2["tree"]}
    ok = True
    for it in items:
        good = remote.get(it["path"]) == it["sha"]
        ok &= good
        print(f"  readback {'OK ' if good else 'FAIL'} {it['path']}")
    print("VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
