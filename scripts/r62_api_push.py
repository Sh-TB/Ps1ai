#!/usr/bin/env python3
"""r62_api_push.py — the R62 push via the Git Data API (the
r58/r59/r60/r61 practice: blobs -> tree(base_tree) -> commit -> ref
PATCH -> per-file blob SHA read-back).

Commits the complete R62 foundation in ONE coherent commit: the
runtime package, the adapter, the CLI, the release gate, the tests,
the docs, the evidence summaries, and the worklog entry.
"""
import base64
import hashlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BRANCH = "heads/main"
REPODIR = "/home/z/my-project/ps1ai"

COMMIT_MESSAGE = (
    "R62 EXECUTED — AUTONOMOUS GAME PLAYER FOUNDATION: the product "
    "ships as ONE command (`python3 -m ps1play play flappybird`). "
    "RUNTIME CORE ps1play/runtime/ (typed errors w/ exit codes "
    "2/3/4/5/6/7/8/130; FrameSource/GameAdapter/Policy/Controller/"
    "Emulator contracts; RuntimeConfig fail-early + safety caps + "
    "no-unbounded-run; TelemetryLog ordered JSONL + latency "
    "percentiles + per-run runtime manifest; EnvSession boot-deadline "
    "+ ordered captures with staleness via frames_run + idempotent "
    "close + same-process re-boot; Lifecycle state machine + "
    "RestartPolicy episode/time/failure caps). FLAPPY ADAPTER wraps "
    "BirdObserverV7/GapTrackerV7/features_flappy_v7 + the r15 "
    "seed-press start + beige game_over + PassageCounter (vendored, "
    "200-sequence equivalence test vs r57_lib) — the EXACT R61 state "
    "machine. CONTROLLER: the only input sender — legality, "
    "sequencing, stop latch, release-all on every failure. POLICY "
    "BOUNDARY: the R61 independent package ONLY, authority-manifest "
    "hash check before the first decision, NO fallback. THE DECISIVE "
    "PROOF: the new runtime reproduces the R61 evidence path "
    "BYTE-EXACTLY (k6 alive/87/640/10000 trace d510e758 == R61; k30 "
    "37@4401 ==; 3 consecutive k45 in ONE launch all == 40@4753; "
    "integration 2x k45 ==; Stage-B family seeds 6/12/30/60/90 all "
    "==). ACCEPTANCE: Stage A recorded (89 shots + 834-frame GIF + "
    "trace); Stage B 20/20 episodes k=6..120 preregistered (104,737 "
    "frames, 20 videos, 929 screenshots; 4 launches x 5 consecutive "
    "— sandbox kills processes between tool calls ~10 min, "
    "disclosed); Stage C 3 separate OS launches all byte-match + "
    "identity verified + zero leaked processes; Stage D missing-model "
    "exit 3 / wrong-model-hash exit 3 (never runs) / SIGINT exit 130 "
    "+ stopped record + release + no leaks. PROFILE: 10,000-cycle "
    "episode at 110.8 FPS (9.03 ms/cycle); policy p50 0.041 ms "
    "(~23.4k/s); perception p50 4.89 ms is the bottleneck (ONNX "
    "inference 0.4% of the loop); CPU-only suitable. TESTS +63 "
    "(50 offline contracts + 4 real-emulator integration + 9 CLI) -> "
    "suite 731 passed + 1 xfailed (R61's 668+1 preserved, zero "
    "weakened). RELEASE GATE 15/15 PASS (python3 -m ps1play verify "
    "--profile final -> reports/r62_release_gate.json). DOCS: "
    "baseline audit / architecture (+ second-game recipe) / runtime "
    "contracts / installation / user guide / troubleshooting / "
    "testing / final report md+json. HONEST: headless-only (watch = "
    "--record GIFs); Stage B = 4 launches x 5 consecutive (sandbox "
    "wall limit) with same-launch continuity proven byte-exactly at "
    "3xk45/2xk45; Linux/x86-64 only; clean-install gate needs "
    "network. TRAINING STAYS CLOSED — no retraining, no policy "
    "changes."
)

FILES = [
    # the runtime package
    "ps1play/runtime/__init__.py",
    "ps1play/runtime/errors.py",
    "ps1play/runtime/interfaces.py",
    "ps1play/runtime/config.py",
    "ps1play/runtime/telemetry.py",
    "ps1play/runtime/session.py",
    "ps1play/runtime/controller.py",
    "ps1play/runtime/policy_runtime.py",
    "ps1play/runtime/lifecycle.py",
    "ps1play/runtime/engine.py",
    "ps1play/runtime/recorder.py",
    "ps1play/runtime/scoring.py",
    "ps1play/runtime/registry.py",
    "ps1play/adapters/__init__.py",
    "ps1play/adapters/flappybird/__init__.py",
    "ps1play/adapters/flappybird/adapter.py",
    # CLI + gate
    "ps1play/__main__.py",
    "ps1play/release_gate.py",
    # tests
    "tests/test_r62_runtime.py",
    "tests/test_r62_integration.py",
    "tests/test_r62_cli.py",
    # scripts
    "scripts/r62_stage_b.py",
    "scripts/r62_stage_c.py",
    "scripts/r62_stage_d.py",
    "scripts/r62_profile.py",
    "scripts/r62_api_push.py",
    # docs
    "docs/r62_baseline_audit.md",
    "docs/r62_architecture.md",
    "docs/r62_runtime_contracts.md",
    "docs/r62_installation.md",
    "docs/r62_user_guide.md",
    "docs/r62_troubleshooting.md",
    "docs/r62_testing.md",
    "docs/r62_final_report.md",
    "docs/r62_final_report.json",
    "requirements-r62.txt",
    # evidence
    "data/r62/r62_stage_b_summary.json",
    "data/r62/r62_stage_c_summary.json",
    "data/r62/r62_stage_d_summary.json",
    "data/r62/r62_profile.json",
    "data/r62/evidence/stage_a_k6_start.png",
    "data/r62/evidence/stage_a_k6_pipe12_score.png",
    "data/r62/evidence/stage_a_k6_end_alive.png",
    "reports/r62_release_gate.json",
    "reports/r62_release_gate.log",
    # worklog
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
