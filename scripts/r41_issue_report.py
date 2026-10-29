#!/usr/bin/env python3
"""r41_issue_report.py — post the R41 addendum comments to Issues #5,
#9 and #10 and VERIFY each via the list endpoint (never claim a post
without a read-back)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSH_SHA = "94d1d9ec2063209ffcf9b77d2662aa5c25cf576f"

BODY_5 = f"""## R41 addendum — **the pending-node release hypothesis is CONTRADICTED by direct readout; the end-of-mission chain fired from the checkpoint posture; the remaining gap is post-banner handling**

Base `7ee5f8c` (R40 close-out) → push [`94d1d9e`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · suite **611 passed + 1 xfailed** (unchanged — R41 was instrumentation + readout, no policy-behavior change) · boot ledger `scratch/r41/boots_used.json` (**3 boots, cap 3 disclosed pre-run**; boot 1 of the session = the r38t1 reach, own ledger) · evidence bundle `data/games/SLUS-01212/truck_evidence/r41/r41_boot_reports.json` (2 static + 3 boot reports + jsonl) · internet-first (the golden rule): Mednafen netplay/movie-replay docs + r/EmuDev divergence-point debugging threads reviewed — deterministic replay divergence is debugged exactly the way we do it here (find the first differing frame/state, bisect inputs); GitHub has no prior SLUS-01212 automation to reuse.

### 1. The static decode (zero boots) — the walker from CODE, not guesswork

`r41t0/r41t1` disassembled the section-VM queue walker `0x80020444` and the dispatcher handlers: node fields come from the code itself — **`lw $v0, 0x5c($a0)`** @`0x800205d4` (node→0x5C per the session-3 F6 decode), jals `0x80021830` (handler) / `0x80024584` / `0x800216bc` (the done-path, `$a1=1 → jal 0x800216bc(0)`). The node-list **body at `0x80084dcc`** decodes as a flat array of opcode-like u16 script entries (0x8, 0x1, 0xC, 0x9, … — all inside the 13-opcode vocabulary) with **no internal pointers and no ASCII descriptors**: a script list, not a linked chain.

### 2. Boot-2 — the kill reproduced, then the readout KILLED the hypothesis

The full 1200-chunk v3.1 kill campaign ran first (20 throws, **2 verified hp_a4 drops**, the chopper **resolved at c421**, 2 deaths + 1 continue, score 5601 — the deterministic chain holding). Then the recorded lever executed: **the walker cursor @`0x800EB5F8` = `0x80084dcc` with `handle_at_cursor = 0x0`** — the END-OF-LIST marker. `pending` INVALID. Exactly **2 processed handles behind** the cursor (`0x800ec9a0`, `0x800eb928`; node→0x5C subs `0x8012d890`/`0x8012d86c`, sub→0x8 `0x0`/`0x800fa6b0`), zero ahead. **Nothing is pending.** The walker stands on the done-path and the section STILL holds `[state 0xB, flags 0x1, prog 0xFFFFFFFF]` for the remaining ~778 post-kill chunks. **"A pending node blocks the release" is CONTRADICTED** — recorded in-code and in the capsule.

### 3. Boot-3 — the end-of-mission chain fired FROM the checkpoint

From `r38_ckpt`: CHOPPER_RESOLVED at c100 → **RELEASE_SIGNATURE at c100** (flags 75 = 0x4B, prog UNMOVED — **not** the F1 signature) → the `mission_end → prebanner → hold` chain → RESTART_SEEN the same chunk (banner_expired_restart). Headline: **the mission-end path is reachable from the D7 checkpoint posture, and it is DECOUPLED from the section-VM F1 release** — the banner chain ran while the walker stayed latched [0xB].

### 4. Boot-3-final — hardened sensors isolate the leak

`r41t4` (ledger BOOT3-FINAL) re-ran from a post-kill savestate with per-burst death sensors, a restart-leak detector and the fixed release predicate: RELEASE_SIGNATURE at c1 (the savestate carries it), the mission_end chain by c74, **RESTART_LEAK at c78**. Final walker flags = **9 (bit 0x8 PRESENT)** with prog UNMOVED at 0xFFFFFFFF — a **PARTIAL F1 signature** (the flags bit sets, the progress word never flips to 0xFFF38B4A). The remaining gap is **post-banner handling** — the known-good trajectory holds NO-INPUT through the banner (c28) — not the release.

### 5. Status labels

| item | status |
|---|---|
| node-list body decode (walker from code) | **OBSERVED** (static, zero boots) |
| pending-node release blocker (the R41 lever hypothesis) | **CONTRADICTED** (cursor at end-of-list, handle 0x0, nothing pending) |
| chopper killed in-policy from `r38_ckpt` | **VERIFIED** (resolved c421; 2 verified hp_a4 drops; score agrees) |
| end-of-mission chain from the checkpoint posture | **OBSERVED** (boot-3: release+c100 → mission_end/prebanner/hold) |
| mission-end ≡ section-VM F1 release | **CONTRADICTED** (decoupled: banner fired while [0xB] latched; flags partial 0x9, prog unmoved) |
| post-banner harness handling | **BLOCKED** — R42: the c28-style no-input hold through the banner + the 0x4054 soft-soldier HP word + the partial-F1 watch |

Legitimacy: legal inputs only; savestates as labeled diagnostic anchors; the boot cap (3) disclosed pre-run and held; `+0x8E` never in any oracle; no game bytes committed."""

BODY_9 = f"""## R41 cross-link — instrumentation/decision-loop changes (Issue #5 has the gameplay evidence)

Push [`94d1d9e`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · suite 611+1xfail (no behavior change — this round is sensors + readout).

1. **The node-readout sensor block** (the R40 lever, executed): at CHOPPER_RESOLVED and every VM dump the harness now reads the walker cursor (`0x800EB5F8`), the handle word AT the cursor, the node chain (node→0x5C, sub→0x8, node→0x8), the surrounding handle array (backward 64 + forward 8, KUSEG-classified) and the full section-VM word set (runner s16, gate u16, flags u16, prog u32, state u16, gate bytes) — read-only diagnostics that answered the pending-node question in one boot.
2. **The release predicate fixed**: boot-3's RELEASE_SIGNATURE keyed on the resolve + the live walker words (flags 0x4B observed — NOT the F1 signature); boot-3-final hardened it further so a carried-savestate release reports at c1 honestly instead of masquerading as a fresh in-run release.
3. **The restart-leak detector**: per-burst death sensing + RESTART_LEAK distinct from banner_expired_restart — the R39-era harness correction (banner/restart checks require alive()) now has a dedicated leak event that fired at c78 and was recorded, not hidden.
4. **Post-kill savestate**: boot-3-final restored the resolved posture directly (no re-campaign), which is what exposed the partial F1 signature (flags bit 0x8 set, prog unmoved) as a stable property of the resolved state rather than a transient.
5. Capsule `next_experiment` replaced (R42): the c28-style NO-INPUT hold through the banner (success = the banner predicate + NO restart events through the hold), then — conditionally — the 0x4054 soft-soldier HP word read (+0x8E/+0xA4/+0x9E candidates under aimed fire at slots 13/16). The section-VM watch continues: does the walker ever reach 0xC, or does the mission-end path bypass it entirely?"""

BODY_10 = f"""## R41 cross-link — knowledge/provenance changes (Issue #5 has the gameplay evidence)

Push [`94d1d9e`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · capsule `data/knowledge/msx/capsule.json` validates (**25 events**, ok).

1. **+4 events appended, each with provenance**:
   - the static decode (walker node fields from code: `lw $v0, 0x5c($a0)` @0x800205d4; done-path jal `0x800216bc(0)`; the node-list body = a flat opcode-like u16 script array, no pointers, no ASCII) — OBSERVED;
   - **the pending-node release hypothesis — CONTRADICTED** (boot-2: cursor `0x80084dcc`, handle 0x0 = end-of-list, pending INVALID, 2 processed handles behind; the walker on the done-path and the section STILL [0xB, 0x1, prog 0xFFFFFFFF] for ~778 chunks);
   - the end-of-mission chain from the checkpoint posture (boot-3: resolve c100 → release c100 flags 0x4B → mission_end/prebanner/hold) — OBSERVED;
   - boot-3-final (hardened sensors): the mission_end chain by c74, RESTART_LEAK c78; flags 0x9 = a **PARTIAL F1 signature** (bit 0x8 set, prog UNMOVED) — OBSERVED.
2. **The decoupling fact is the round's knowledge yield**: mission-end is NOT gated by the section-VM F1 release (flags 0x1→0x8 + prog → 0xFFF38B4A per F1) — the banner chain fired while the walker stayed latched [0xB]; the F1 "release" signatures remain unobserved even at mission_end.
3. **`next_experiment` replaced** (R42): the c28-style no-input hold through the banner (the harness-leak hypothesis), the 0x4054 soft-soldier TRUE HP word (aimed fire at slots 13/16 produced ZERO verified hp drops — soft soldiers do not use +0xA4), and the 0xC-state watch; budget 2 boots (savestate restores, no full campaign — the boot-3-final post-kill savestate carries the resolved posture).
4. **Provenance discipline kept**: the kill keyed on the verified identity (st 0xAA94/0xABDC, airborne, hp_a4); the boot cap 3 disclosed pre-run and held (the session's boot 1 = the r38t1 reach, own ledger); `+0x8E` never in any oracle; no game bytes committed.
5. Internet-first (the golden rule): Mednafen netplay/movie docs (save-state + input-stream replay semantics) and r/EmuDev divergence-point debugging practice reviewed — both corroborate the earliest-divergence methodology R38–R41 already uses; no prior SLUS-01212 automation exists on GitHub to reuse."""


def post(issue, body, tag):
    s, c = req(f"/repos/{REPO}/issues/{issue}/comments", method="POST",
               payload={"body": body})
    assert s == 201, (issue, c)
    cid = c["id"]
    # read-back verification
    s, lst = req(f"/repos/{REPO}/issues/{issue}/comments?per_page=5")
    assert s == 200
    ok = any(x["id"] == cid and x["body"] == body for x in lst)
    print(f"issue #{issue}: comment {cid} posted; read-back "
          f"{'VERIFIED' if ok else 'MISMATCH'} ({tag})")
    return cid


def main():
    ids = {}
    ids["5"] = post(5, BODY_5, "gameplay")
    ids["9"] = post(9, BODY_9, "decision-loop")
    ids["10"] = post(10, BODY_10, "knowledge")
    print(json.dumps(ids))
    with open("/home/z/my-project/ps1ai/scratch/r41/issue_comment_ids.json",
              "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
