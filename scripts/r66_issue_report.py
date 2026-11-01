#!/usr/bin/env python3
"""r66_issue_report.py — post the R66 evidence-grade updates to the
five open issues (#4 #5 #6 #9 #10) and verify each by read-back
(the R63/R64/R65 practice). No issue is closed; no duplicate issues.
"""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSHED = "5105131 / a9568fe / 04c395a (remote main 4434ba54a733, " \
         "tree-verified)"
PKG_SHA = "cc5af6c65433dd4272e386fe13336b4988510406653695f4ba7af1f935817976"

C4 = f"""**R66 (product path + the truck status) — the fourth runtime game; Mission 1 still OPEN.** Commits `{PUSHED}`.

**What changed for #4:** `metal_slug_x` is now a REGISTERED runtime game: `python3 -m ps1play play metal_slug_x` runs the deterministic Mission-1 rules policy through the standard engine (preflight disc pin `45cde149…` → boot → input-ownership gate → mission gate → episodes → per-episode records). Two independent runs are **byte-identical**: ep1 death 1666f score 1100 (px ~1164, the armored-truck encounter — the death screenshot shows the truck + 2 soldiers + PRESS START), ep2 388f score 1300. Legality: legal pad inputs only, zero RAM writes, no save-state rewinds, no training, screenshots are evidence only.

**Mission 1 clear: NOT achieved** — the truck fight is the next concrete blocker (the R38-R52 evidence: hp_a4 300, grenades −100 each; the current policy has no truck-sequencing behavior). The acceptance bar of this issue (a real interactive clear with control ownership, legal input, a genuine completion indicator, reproducible evidence, an independent repeat, zero hidden writes) remains unmet and unclaimed.

Evidence: `data/games/SLUS-01212/truck_evidence/r66/r66_product_run.json` + `product_run/` (episode records + screenshots) · `reports/r66/R66_GAMEPLAY_RESULTS.md` · tests `tests/test_r66_msx_adapter.py` (19, incl. isolation). The issue STAYS OPEN."""

C5 = f"""**R66 (the two primary blockers) — the starvation ROOT-CAUSED and de-starved; the +500 captured AT the pay frame.** Commits `{PUSHED}`.

1. **Corridor-gate starvation — ROOT CAUSE (OBSERVED, n=13 skips):** the new per-skip `GATE_DIAG` dump shows the R50/R51 predicate counted entities that can neither absorb a player bullet nor register a payment as blockers — the bullet-TRANSPARENT `0xab94` wasp (slot30, 8 rejections; the n=4 piercing evidence) and in-flight `projectile_air` rows (`0xbdf8/0x1be0/0x2950/0x9558/0xac64`) — and the player NEVER advanced (a single px value 1255.2 across all skips). A protocol-predicate defect, not an observer/runtime defect.
2. **The fix (TESTED in-game):** blockers must ABSORB the bullet or REGISTER the payment (mortal ground rows only; corpses/airborne/`0xab94` never block; `0xae7c` still blocks — it registered kills). Pass B (corrected gate + the bounded advance) immediately captured what R48-R52 never reached.
3. **The +500 capture (OBSERVED, n=1):** slot16 st_pre `0x1e38` dx +20.3 — score 7702→8202 at tail f1 (the bullet-impact frame, victim still pre-hit); `0x5b0c` registration at tail f3; the `slot12@0xa0` pulse (257→2, rec 4) co-timed. **The magnitude table is now +500 ×4 vs +1000 ×7** (two more +1000s: `0x42bc` pay tail f3; `0x3f48` pay tail f4). **The pay-frame law:** the accumulator pays on the internal damage event ~2 frames BEFORE the visible death registration (all three captures). The +500 class is NOT confined to surviving 0x42bc connects; freshness-spread SUPPORTED not proven; kills do not always pay (`0xa718→0x515c`, dscore=0).
4. **The accumulator candidate resolved:** slot12@0xa0 is the REGISTRATION witness (pulses on every kill registration, n=2 replicated), NOT a magnitude discriminator — its instant pay-frame value is churn phase (a banked +1000 pay frame also shows 257). The zero-overlap discriminator stays PENDING (n=1 vs n=4; 19 candidate offsets; the delay signature is the lead).

Discipline: the offline dry-run (20/20) before every boot; the ledger cap 5 disclosed pre-run, 4 boots spent; the frontier rebuild re-proven **6-for-6** (px 1224.9/1254.8 byte-exact again). Evidence: `truck_evidence/r66/` (r66_boot3_s2a/r66_boot4_s2b JSONLs + r66_analysis.json) · `reports/r66/R66_MISSION1_FINDINGS.md`. The smallest next experiment (R67, in the capsule): n≥2 +500 captures from the r66 frontiers → the widened zero-overlap test. The issue STAYS OPEN."""

C6 = f"""**R66 (architecture) — the fourth runtime game + the isolation proof.** Commits `{PUSHED}`.

`metal_slug_x` joined flappybird/tetrade/buzzybee in the registry: adapter `ps1play/adapters/metal_slug_x/adapter.py` (0.2.0 — the verified anchor map, the read-only 21-float observation, the ownership/mission gate, the bounded continue recovery) + the deterministic `Mission1Policy` with the R66 corridor predicate. The R64 recipe executed a THIRD time with zero core edits (the registry seam held). Isolation: ALL MSX semantics live in the game package — enforced by `tests/test_r66_msx_adapter.py::TestIsolation` (no cross-game imports; no MSX addresses in `ps1play/runtime/*.py`); the other three games' behavior unchanged (their packages untouched; the release gate re-ran 15/15 with the flappy R61 records byte-exact). Known architecture debt (recorded, not fixed this round): `ps1play/agent/route.py` + `combat.py` still carry legacy MSX semantics in the shared agent package — migrating them into the game package is future work under this issue. The issue STAYS OPEN."""

C9 = f"""**R66 (decision-loop discipline) — the rules held and paid off.** Commits `{PUSHED}`.

* The offline contract dry-run ran BEFORE any experiment boot (`scripts/r66_dryrun.py`, 20/20: the union net, the frame-row contract, the gate_diag classification, the ledger gate, the disclosed goals) — and it caught one harness defect before it could waste a boot (the ledger-patching bug; also 2 phantom ledger entries refunded with a disclosure, zero core loads).
* The boot ledger: cap 5 disclosed pre-run, 4 boots spent for TWO primary experiments + environment validation — 4 boots is what the same experiments cost R52 for LESS information (R52 got no +500; R66 got the root cause + the capture + the runtime game).
* Determinism dividend: the frontier rebuild reproduced 6-for-6 (px 1224.9/1254.8 byte-exact) — the fifth consecutive sandbox rollback survived by the anchor + rebuild protocol.
* Tooling lesson recorded: the GitHub Contents API read-back truncates files >1 MB (empty content) — the push verification now ALSO does a tree-level blob-sha comparison (the Git Data API), which is authoritative; a Contents-API mismatch on big blobs is a tool limit, not a push failure.

Evidence: `reports/r66/` + the boot ledger. The issue STAYS OPEN."""

C10 = f"""**R66 (closed-source recovery) — the pay-frame law + the capsule updated.** Commits `{PUSHED}`.

The capsule is at **56 events** (`data/knowledge/msx/capsule.json`), now including: the starvation root cause (the GATE_DIAG dump, OBSERVED), the +500 pay-frame capture with the full causal chain (bullet impact → accumulation at tail f1 → death registration at tail f3 → the slot12@0xa0 registration pulse), the pay-frame LAW (the accumulator pays on the internal damage event ~2 frames before the visible registration — established on 3 independent captures), the accumulator-candidate resolution (slot12@0xa0 = registration witness, not a payment discriminator), and the zero-payment kill (`0xa718→0x515c`, dscore=0). The magnitude table: **+500 ×4 vs +1000 ×7**. `next_experiment` = R67 (n≥2 +500 captures → the widened discriminator; then the truck campaign). The honest statuses stay OBSERVED/PENDING where n is small — nothing was promoted to VERIFIED without repeat evidence. The knowledge ships in `metal_slug_x.ps1game` v0.2.0 (GAMEPLAY_VERIFIED, sha256 `{PKG_SHA[:16]}…`). The issue STAYS OPEN."""

for num, body in ((4, C4), (5, C5), (6, C6), (9, C9), (10, C10)):
    s, cm = req(f"/repos/{REPO}/issues/{num}/comments", method="POST",
                payload={"body": body})
    assert s == 201, (num, s)
    s2, got = req(f"/repos/{REPO}/issues/comments/{cm['id']}")
    assert s2 == 200 and got["body"] == body, num
    print(f"#{num}: comment posted + read back byte-identical "
          f"({len(body)} chars)")
print("all issue updates verified")
