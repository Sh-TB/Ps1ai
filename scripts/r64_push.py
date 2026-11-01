#!/usr/bin/env python3
"""r64_push.py — the R64 push via the Git Data API (the r58..r63
practice): commits the R64 second-runtime-game delivery (tetrade
adapter + policy, the generic registry/engine/config/session/
telemetry amendments, tests, acceptance evidence, docs, scripts,
worklog) in ONE coherent commit; verifies every blob by SHA
read-back, then re-verifies the remote HEAD."""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

COMMIT_MESSAGE = (
    "R64 EXECUTED — Tetrade is the SECOND RUNTIME GAME "
    "(Issue #15): `python3 -m ps1play play tetrade` works exactly "
    "like `play flappybird` — the R62 architecture's second-game "
    "recipe executed on the fresh R63 evidence. ps1play/adapters/"
    "tetrade/: the full GameAdapter (RAM-read perception over the "
    "TetradeGame struct, base 0x1FECA0 = the round-10 prior AND "
    "R63's, now three independent boots; entry with the <=4f START "
    "taps per the PAUSED key-repeat trap; state-driven recovery — "
    "budget-alive episodes are legally finished with UP hard-drops "
    "to a natural game over before the CIRCLE continue-refusal and "
    "re-entry; entry retried up to 3 attempts with telemetry) + the "
    "R63 Dellacherie 2-ply policy ported verbatim behind the Policy "
    "contract (per-frame realization with the game's cooldowns, "
    "identity = sha256 of the policy source). TWO GENERIC CORE "
    "AMENDMENTS, zero game knowledge in the core: "
    "registry.policy_for_game (built-in policy factory vs frozen "
    "RuntimePolicy) and engine BOOT RETRY (config.boot_retries=2; "
    "beetle's in-process boot can stick at the OpenBIOS cube — "
    "diagnosed with screenshots, scripts/r64_diag_polluted_boot*.py "
    "— wait_ready is now the VERIFIED ready state and a failed "
    "verification re-boots a fresh core); config whitelist "
    "registry-driven; per-game disc pins (tetrade 7eb38eda...); "
    "manifest v2 per-game components; CLI progress label (tetrade: "
    "lines). ACCEPTANCE (real product run, one launch, committed): "
    "boot attempt 0, ready 0x1FECA0; ep1 death 2038f/124 presses/23 "
    "pieces/0 lines; ep2 death 2831f/165 presses/33 pieces/1 "
    "VERIFIED line clear (single 0->1; score +26 = hard-drop cells "
    "at 2/cell, the SINGLE adds 0 at level 0 exactly per "
    "SINGLE_LINE_SCORE*level); NEXT-promotion cross-check 53/53 "
    "(100%) frame-accurate from the committed traces; restart flow "
    "exercised (ep2 start_frames=1058, fresh start verified). "
    "Evidence: data/r64/ + evidence GIFs/PNGs + "
    "r64_acceptance_summary.json (scripts/r64_verify_run.py). "
    "TESTS: +53 (49 offline + 4 real-emulator through the real "
    "engine); suite 782 passed + 2 skipped (owner-local exe) + 1 "
    "xfailed — R62's 731+1 preserved, zero weakened; the 7 "
    "flappy-disc tests restored by re-fetching the FlappyBirdPSX "
    "v0.1.0 ISO (sha b45871d3... = the committed record). RELEASE "
    "GATE re-run 15/15 PASS incl. the byte-exact R61 family records "
    "(k30=37@4401, 3xk45=40@4753) — the generic amendments changed "
    "nothing for flappybird. DOCS: docs/r64_tetrade_second_game.md "
    "+ architecture recipe + user guide + README. HONEST: Tetrade "
    "perception is RAM-read-based (the loop Issue #8 itself "
    "documents; R63 precedent); the heuristic policy is legal but "
    "weak (1 clear / 56 pieces) — the DoD bar is a verified clear + "
    "natural game over, not a score target; seed_k is labeling-only "
    "(zero-writes forbids seeding the game RNG); boot flakiness is "
    "MITIGATED (verified-ready + boot retry), not eliminated. "
    "TRAINING STAYS CLOSED — no model, no training anywhere."
)

FILES = [
    "ps1play/adapters/tetrade/__init__.py",
    "ps1play/adapters/tetrade/adapter.py",
    "ps1play/adapters/tetrade/policy.py",
    "ps1play/adapters/flappybird/adapter.py",
    "ps1play/runtime/registry.py",
    "ps1play/runtime/engine.py",
    "ps1play/runtime/config.py",
    "ps1play/runtime/session.py",
    "ps1play/runtime/telemetry.py",
    "ps1play/__main__.py",
    "tests/test_r64_tetrade.py",
    "tests/test_r64_integration.py",
    "data/r64/episodes.jsonl",
    "data/r64/events.jsonl",
    "data/r64/trace_ep001_k6.jsonl",
    "data/r64/trace_ep002_k12.jsonl",
    "data/r64/r64_acceptance_summary.json",
    "data/r64/evidence/video_ep001_k6.gif",
    "data/r64/evidence/video_ep002_k12.gif",
    "data/r64/evidence/ep001_k6_end_death.png",
    "data/r64/evidence/episode_001.json",
    "data/r64/evidence/episode_002.json",
    "data/r64/evidence/runtime_manifest.json",
    "docs/r64_tetrade_second_game.md",
    "docs/r62_architecture.md",
    "docs/r62_user_guide.md",
    "README.md",
    "scripts/r64_issue_create.py",
    "scripts/r64_verify_run.py",
    "scripts/r64_diag_polluted_boot.py",
    "scripts/r64_diag_polluted_boot2.py",
    "scripts/r64_push.py",
    "reports/r62_release_gate.json",
    "reports/r62_release_gate.log",
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
