#!/usr/bin/env python3
"""r63_push.py — the R63 push via the Git Data API (the r58..r62
practice): commits the R63 Tetrade re-delivery (runner + probe +
diagnostic scripts, evidence digest + trace, docs report, worklog
entry) in ONE coherent commit; verifies every blob by SHA read-back."""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

COMMIT_MESSAGE = (
    "R63 EXECUTED — Tetrade full-loop re-delivery (Issue #8): the "
    "complete game loop re-proven on the current stack with fresh "
    "committed evidence — the Oct-26 round-10 artifacts were lost to "
    "the repo rewrites/rollbacks, so R63 re-delivers: boot -> "
    "title -> START -> menu -> CROSS(Marathon) -> START taps (the "
    "60f-hold PAUSED key-repeat trap disclosed) -> struct located by "
    "signature at 0x1FECA0 (exactly the round-10 prior: isGameOver "
    "0x1FF5A8 = base+2312; first-scan window cut + the transient "
    "type=-1 respawn state diagnosed and fixed, disclosed) -> anchor "
    "map from the MIT source verified live (matrix@+0, tetrimino "
    "type@+800/x@+868/rot@+880, nextTetriminos[14].type@+896+92k — "
    "the struct+896 prior, score@+2276, single@+2280 .. "
    "isGameOver@+2312, isGamePaused@+2316; UP=hard drop, CIRCLE/B "
    "rotate, CIRCLE refuses continue) -> Dellacherie 2-ply policy "
    "(board+current+NEXT from RAM READS ONLY, zero writes, zero core "
    "edits) -> 28 pieces, 1 VERIFIED line clear (single 0->1; score "
    "+0 at level 0 exactly per SINGLE_LINE_SCORE*level) -> natural "
    "game over (spawn overlap, isGameOver 0->1) -> CONTINUE refused "
    "with CIRCLE -> restart verified fresh (counters zeroed, board "
    "empty); NEXT-promotion cross-check 28/28 (vs 150/152 in round "
    "10). Evidence: data/r63/tetrade_full_loop_summary.json + "
    "trace.jsonl (committed) + docs/r63_tetrade_redelivery.md; PNGs "
    "local per hygiene. Boot ledger 7/7 disclosed (probe1 x4, diag "
    "x1, full_loop x2). HONEST: the heuristic policy is legal but "
    "weak (1 clear / 28 pieces; the stronger round-10 policy is gone "
    "and recorded as lost); perception is RAM-read-based per Issue "
    "#8's own documented loop; no training anywhere. TRAINING STAYS "
    "CLOSED."
)

FILES = [
    "scripts/r63_tetrade_probe1.py",
    "scripts/r63_tetrade_diag.py",
    "scripts/r63_tetrade_full_loop.py",
    "scripts/r63_push.py",
    "data/r63/tetrade_full_loop_summary.json",
    "data/r63/tetrade_full_loop_trace.jsonl",
    "docs/r63_tetrade_redelivery.md",
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
