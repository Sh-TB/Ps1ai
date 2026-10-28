#!/usr/bin/env python3
"""r38_issue10_report.py — post the R38 addendum to Issue #10 and VERIFY
it via the list endpoint (never claim a post without a read-back)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """## R38 addendum — knowledge contradictions resolved; the truck killed by the shipped policy; the D7 blocker isolated to the chopper

Base `8ac9a645` (R37 close-out) → push [`364089c`](https://github.com/Sh-TB/Ps1ai/commit/364089c1e328d68cd32cc9e62a4372b47aad6c4f) · suite **594 passed + 1 xfailed** (was 577+1) · full report: `docs/issue10_r38_addendum.md` · boot ledger `scratch/r38/boots_used.json` (5 boots, every cap amendment disclosed pre-run).

### 1. The `+0x8E` contradiction — fixed at the schema level

The R37 MSX capsule shipped `P1_entity_HP (base+0x8E)` as VERIFIED — a silent regression of the label the truck campaign had already SUPERSEDED. Resolution, chosen by evidence not intuition:

- **Chronology reconstructed**: the Issue #5 pair-freeze A/B froze the **PAIR** `0x800CA2F6`+`0x800CA2FE` (the mediator word was never isolated); the Issue #10 Gate B no-fire control decayed 148→2 without fire, 3/3; the writer disasm (`0x80064674`) keeps `+0x8C/+0x90` as per-entity camera deltas; pincorr1 re-analysis shows px−scroll ≈ 0..16 while `+0x8E` swings 291→81 with regen-like recoveries — so **slot-0 semantics stay UNRESOLVED, honestly**, and the field is excluded from all success oracles.
- **New reader census (R38)**: all 5 EXE readers of `+0x8E` disassembled — pairwise ordering (`func_80063794`), 3-entity abs-difference arithmetic (`func_8004B950`), aim-flag-keyed consumption (`func_80056564` reads the `+0xEA` byte that `FUN_8009de68` writes), copy-out serializer (`func_8002ACE4`), arg-pass-through (`func_80051D88`, honest UNKNOWN). **Zero damage patterns; zero direct halfword stores to `+0x8E` in the EXE** (`death_path.json` re-analysis).
- **Machine enforcement**: `ps1play.capsule/1` now has a contradiction guard — a `CONTRADICTED` event with `supersedes_role` blocks any field retaining that role as VERIFIED (`validate()` raises; re-promotion requires `resolved_by` → a provenance-mandatory VERIFIED event; ground-truth queries on the dead role fail loudly). Artifacts are repo-relative with `verify_artifacts()` hash re-checks. 8 new tests. Consumer audit: no reward/termination/progress path reads `+0x8E`; the armor/truck paths key the verified `+0xA4`.
- Every status change is itemized in the capsule provenance; unrelated facts were not downgraded.

### 2. Function shortlist (10 candidates, no plausibility claims)

`data/games/SLUS-01212/r38_function_shortlist.json` — S1 `FUN_800a41d8` (overlay, 84 B: damage-ELIGIBILITY gate `+0x28 & 0x80`, retarget `0x800151DC`), S2 `FUN_8009de68` (overlay, 500 B: `+0x8E` pairwise compare → `+0xEA/EB` aim latch; **else-branch dead-code proof sharpened** — dispatch value `(unkEB & 0x80) >> 4 ∈ {0,8}` is always < 9), S3 `FUN_800151DC` (EXE 48 B shared death handler, 4 addr-taken refs), S4–S7 the four reader decodes, S8 `func_80051D88` (UNKNOWN; next static step: `0x8004938c`'s arg use), S9 the camera-delta writer, S10 the section-VM trio. The `+0xA4` damage-delivery write site remains UNLOCATED and is labelled as such.

### 3. The D7 experiment — 5 disclosed boots, deterministic

Rebuilt the pre-encounter checkpoint with the proven recipe (`r38_ckpt`: px 810.3, grenades 10 — every earlier checkpoint was wiped by rollback #8). 15-frame micro-chunks, cap 480. Oracle = score events + walker `0xC`/pre-banner + banner PNG; `+0x8E` never in the oracle.

| arm | outcome | chunks | deaths | score | truck evidence |
|---|---|---|---|---|---|
| A1/A2 — shipped policy | death→restart wall | 268 | 0 | **4600** | **KILLED**: hp_a4 240 → −10 fire chips → 150 → grenade −100 → 50 → wreck `0xA44C`, gone by c95 (×2 deterministic) |
| B — pure-RIGHT control | death→restart wall | 45 | 0 | 0 | hp_a4 = **300 frozen** every chunk (no self-decay → damage is input-caused) |
| AA v0/v2 — new `aa_kill` rule | death→restart wall | 227 | 0 | 4100 | **chopper CONNECTED once per run** (hp_a4 300→200, the −100 grenade signature, ×2 deterministic) |
| AA v1 — \|dx\|≤40 throw gate | death→restart wall | 161 | 0 (php 291→0 one-shot) | 3400 | **gate FALSIFIED** (0/6 connects) — reverted with the in-code falsification note |

- **GAMEPLAY-VERIFIED**: the shipped policy kills the armored truck with ordinary legal inputs (hp_a4 trajectory + grenade-counter decrement + score events + wreck state + frozen control arm all agree). The Oct-23 "forward fire can't kill armor (254→254)" note is corrected: that field was `+0x8E` screen-x; the real `hp_a4` DOES chip under sustained fire.
- **The D7 release blocker is now isolated with live evidence**: at EVERY pin observation across 5 runs, slot 4 = the chopper (`st 0xAA94/0xABDC`, hp_a4 300, h 207–210) is the last live pending-queue entity — the truck is a wreck, the soldier wave is dead, the walker cycles `(0xA,0x43) ↔ (0,0)`, and no `0xC` appears. The new plugin-level `aa_kill` rule (the session-3 J1 hop+UP-lob recipe, verbatim) fires only in the pin context, never on fallers/corpses, keeps soldier priority, bails after 6 thrown-and-missed cycles, and keeps the rain-hop (its first build dropped it → a one-shot bomb death — recorded, fixed, regression-tested).
- The connect rate (~1/10 throws; the chopper patrols dx −9..−51 vs the proven 7–29 band) is the single remaining blocker: three connects kill it (session-3 F4), the queue clear releases the pin (F1), and the banner path is proven.

### 4. Status labels

| item | status |
|---|---|
| `+0x8E` contradiction fix + guard + tests | IMPLEMENTED, TESTED |
| reader census + shortlist | OBSERVED (static) |
| truck killed by the shipped policy | **GAMEPLAY-VERIFIED** (×2 deterministic, control-isolated) |
| Oct-23 "forward fire can't kill armor" reading | CONTRADICTED (corrected) |
| chopper = the D7 release blocker | OBSERVED (live, 5 runs) |
| aa_kill live connect (300→200) | OBSERVED (×2 deterministic) |
| \|dx\|≤40 throw gate | CONTRADICTED (live falsification, reverted) |
| D7 pin release from the rebuilt phase | BLOCKED (chopper kill rate) |
| cheat-anchor validation | PENDING (menu ladder still unwalked post-rollback; no cheats near any success claim) |

### 5. Highest-value next experiment (R39)

A **positioning sub-rule** that walks/holds the player to keep the tracked chopper inside the |dx| 7–29 band at throw time, then the unchanged J1 pattern — matched ×2 against this round's recorded aa trials (2 boots, ~20k frames; oracle: chopper hp_a4 300→0 + walker `0xC` + banner PNG). Secondary levers: locate the `+0xA4` damage-delivery write site EXE-side; disassemble `0x8004938c`'s use of the `+0x8E` argument; re-walk the menu ladder with cursor-struct polling (`0x957D8–0x957F8`) to unblock the cheat-anchor windows.

*Cross-link: Issue #9 (gameplay improvement — the truck kill and the aa_kill rule are policy-layer evidence there).*
"""

s, r = req(f"/repos/{REPO}/issues/10/comments", method="POST",
           payload={"body": BODY})
print("POST status:", s, "id:", r.get("id"), "url:", r.get("html_url"))
assert s == 201, r

# --- verification: independent list read-back ---
s2, lst = req(f"/repos/{REPO}/issues/10/comments?per_page=100")
ids = [c["id"] for c in lst]
print("LIST status:", s2, "comments:", len(ids))
ok = s2 == 200 and r["id"] in ids and any(
    "R38 addendum" in c.get("body", "") for c in lst if c["id"] == r["id"])
print("VERIFIED:", ok)
assert ok
