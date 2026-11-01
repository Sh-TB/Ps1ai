#!/usr/bin/env python3
"""r64_issue_close.py — close the R64 tracking issue #15 with the
evidence-grade closure comment (the #14/#8 pattern): post -> read
back byte-identical -> close as completed -> read back state."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R64 EXECUTED — the second runtime game shipped; closing as completed.**

The R62 architecture's "adding a second game" recipe is executed for real on the R63 evidence (commit `c708c03`): **`python3 -m ps1play play tetrade` works exactly like `play flappybird`** — same engine, controller, telemetry, lifecycle, CLI, exit codes. Remote HEAD `d0fb11f` read back; all 8 key R64 paths verified in the remote tree; every pushed blob read back byte-identical.

**What shipped** (`ps1play/adapters/tetrade/`): the full `GameAdapter` (RAM-read perception over the `TetradeGame` struct at **0x1FECA0 — the round-10 prior AND R63's, now three independent boots**; entry with the ≤4f START taps per the PAUSED key-repeat trap; state-driven recovery: budget-alive episodes are legally finished with UP hard-drops to a natural game over before the CIRCLE continue-refusal and re-entry; entry retried up to 3 attempts, every attempt in telemetry) + the R63 **Dellacherie 2-ply policy ported verbatim** behind the runtime `Policy` contract (identity = sha256 of the policy source). **Two generic core amendments, zero game knowledge in the core:** `registry.policy_for_game` (built-in policy factory vs frozen `RuntimePolicy`) and `engine.boot` **boot-retry** (`config.boot_retries=2`) — beetle's in-process boot can stick forever at the OpenBIOS cube (diagnosed with screenshots this round; the #5 worklog recorded the same) — the adapter's `wait_ready` is now the VERIFIED ready state and a failed verification re-boots a fresh core. Config whitelist registry-driven; per-game disc pins (Tetrade `7eb38eda…`); manifest v2 per-game components; CLI progress label (tetrade: `lines`).

**Acceptance (real product run, one launch, committed under `data/r64/`):** boot attempt 0, ready base `0x1FECA0`; ep1 (k=6) death at 2038 frames / 124 real button presses / 23 pieces / 0 lines; ep2 (k=12) death at 2831 frames / 165 presses / 33 pieces / **1 VERIFIED line clear** (`single` 0→1; score forensics: +26 = hard-drop cells at 2/cell — the SINGLE itself adds 0 at level 0, exactly per `SINGLE_LINE_SCORE * level`, the R63 finding through the product path). **NEXT-promotion cross-check 53/53 (100%)** frame-accurate from the committed traces. **Restart flow exercised**: ep2 started via recovery + refusal + entry (`start_frames=1058`) and played fresh. GIFs + end screenshot + per-episode records + runtime manifest committed.

**Per the DoD:** (1) adapter with the full contract — PASS; (2) built-in policy, no model — PASS; (3) generic wiring (registry-driven config, per-game disc pins, progress label) — PASS; (4) tests — PASS: +53 (49 offline + 4 real-emulator through the real engine); full suite **782 passed + 2 skipped (owner-local exe) + 1 xfailed** — R62's 731+1 preserved, zero weakened; the 7 flappy-disc tests restored by re-fetching the FlappyBirdPSX v0.1.0 ISO (sha `b45871d3…` = the committed record); (5) acceptance evidence through the product path — PASS (above); (6) no regression — PASS: the **R62 release gate re-run 15/15** incl. the byte-exact R61 family records (k30 = 37@4401; 3×k45 = 40@4753) — the generic amendments changed nothing for flappybird. TRAINING STAYS CLOSED (Tetrade's policy is hand-written; no model touched).

Honest notes: Tetrade perception is RAM-read-based (the loop this issue's text inherits from #8's own documented loop; R63 precedent) — the flappy vision model does not generalize; the heuristic policy is legal but weak (1 clear / 56 pieces) — the DoD bar is a verified clear + natural game over, not a score target; `seed_k` is labeling-only (zero-writes forbids seeding the game RNG); beetle's boot flakiness is MITIGATED (verified-ready + boot retry), not eliminated. Closing as completed."""

s, c = req(f"/repos/{REPO}/issues/15/comments", method="POST",
           payload={"body": BODY})
print("comment POST:", s, c.get("id"))
cid = c.get("id")
s2, c2 = req(f"/repos/{REPO}/issues/comments/{cid}")
m = s2 == 200 and c2.get("body") == BODY
print("comment read-back:", s2, "match:", m)
s3, i = req(f"/repos/{REPO}/issues/15", method="PATCH",
            payload={"state": "closed", "state_reason": "completed"})
print("close:", s3, i.get("state"), i.get("state_reason"))
s4, i2 = req(f"/repos/{REPO}/issues/15")
m2 = (s4 == 200 and i2.get("state") == "closed"
      and i2.get("state_reason") == "completed")
print("read-back: state=", i2.get("state"), "comments=",
      i2.get("comments"), "ok:", m2)
sys.exit(0 if (m and m2) else 1)
