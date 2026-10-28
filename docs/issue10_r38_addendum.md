# R38 — Knowledge contradictions resolved; the truck killed by the shipped policy; the D7 blocker isolated to the chopper

Base `8ac9a645` (origin/main, R37 close-out) · suite **594 passed + 1 xfailed** (was 577+1) · boot ledger `scratch/r38/boots_used.json`: **5 boots, every cap amendment disclosed pre-run**

## TL;DR

Three results this round. **(1)** The R37 MSX capsule's `P1_entity_HP (base+0x8E)` VERIFIED claim — a silent regression of the label the truck campaign had already SUPERSEDED — is corrected with a schema-level contradiction guard (a `CONTRADICTED` event now structurally blocks that role from ever being re-promoted without explicit new evidence; 8 new tests). A new reader census (all 5 EXE readers of `+0x8E` disassembled) adds independent support: pairwise position comparisons, 3-entity distance arithmetic, aim-flag-keyed consumption, copy-out serialization — **zero damage patterns and zero direct stores to the field**. **(2)** In a matched live trial from a rebuilt checkpoint, **the shipped policy killed the armored truck with ordinary legal inputs** (hp_a4 240 → 150 under sustained fire, one grenade −100 → 50, wreck `0xA44C`; the pure-RIGHT control held hp_a4 = 300 frozen) — score 0 → 4600, 0 combat deaths, deterministic ×2. The Oct-23 "forward fire does not kill armor" note is corrected: that field was `+0x8E` screen-x. **(3)** The D7 pin still does not release from the rebuilt phase — and the blocker is now isolated with live evidence: **the chopper (slot 4, st `0xAA94/0xABDC`, hp_a4 300) is the last live pending-queue entity at every pin observation**. The new `aa_kill` policy rule (the session-3 J1 hop+UP-lob recipe) **connected once per live run** (hp_a4 300 → 200, the −100 grenade signature), but the kill needs 3 connects and the connect rate is ~1/10 throws. A |dx|≤40 pre-throw gate was tried and **falsified live** (0/6, plus an earlier one-shot bomb death caused by the build dropping the rain-hop). Everything is recorded; cheats stayed out of all success claims.

## Task 1 — reconcile (what was reproduced before new work)

- `git fetch` → fast-forward `6b97fbeb` → **`8ac9a645`** (R37); clean tree before/after, no local work lost. Capstone reinstalled (env rollback). Suite green **577+1xfail** before changes.
- Assets verified: MSX cue+bin (`M1_GAME`), beetle core (`M1_CORE`), OpenBIOS, workspace `emu/ws` with the Oct-20 savestates; **all MSX checkpoints (chopper_ckpt/pin_ckpt/r35a_ckpt) remain wiped** (rollback #8, as R37 recorded) — every gameplay number below comes from this round's boots.
- Prior-evidence chronology rebuilt from committed records only: pincorr1 (`download/mission2_section_pin/pincorr1/result.json`, commit `ce3c393`) = 40 chunks, 0 deaths, **+400 inside the pin window** (3500→3900), pin chunks [25,26,35,37,38]; the "254" truck field = the 2026-10-23 series' `+0x8E` reading; Gate B's no-fire decay 3/3 survives as a committed record (`docs/tools_matrix_issue10.md` caveat, `fab6538`, the combat.py note) — its raw JSON was local-only and is gone, which the capsule provenance now states plainly.
- R37 artifacts re-verified on the current commit: capsule-validate OK (msx 7,950 B), CLI delegation OK, external TSV/edges queryable (2,930 fns / 7,720 edges), `pincorr1` report intact.

## Task 2 — the +0x8E contradiction, fixed at the schema level

**The contradiction, exactly:** the R37 capsule shipped `P1_entity_HP (base+0x8E)` as `VERIFIED` (provenance: the Issue #5 pair-freeze A/B), although (a) the truck campaign had marked that label SUPERSEDED (`docs/truck_blocker_resolution.md`: "+0x8E is the screen-x"), (b) the Issue #10 Gate B no-fire control had observed decay without fire 3/3, and (c) the capsule itself elsewhere carries the corrected +0xA4 evidence.

**The evidence chronology, reconstructed (and now embedded in the capsule):**

| date | evidence | what it actually showed |
|---|---|---|
| r-b256b17 (Issue #5) | pair-freeze A/B: baseline 56 dmg + death vs treatment held | freezing the **PAIR** `0x800CA2F6` + `0x800CA2FE` suppressed the damage outcome — the mediator word was **never isolated**; "HP" was an over-attribution from day one |
| 8ff8482 era | truck "hp 254→254" under standing Y-bursts | that field is `+0x8E` (screen-x); it stayed constant because the truck was parked |
| `fab6538` (Gate B) | no-input control: `+0x8E` decays 148→2 without fire, 3/3 | inconsistent with HP; consistent with camera-relative position |
| truck campaign (Oct 25) | disasm `0x80064674` (per-entity camera deltas at `+0x8C/+0x90`); truck hp **`+0xA4`** 300→0 under grenades, 8/8+5+3 kills | `+0x8E = HP` SUPERSEDED; real armored HP = `+0xA4` |
| **R38 (this round)** | **reader census**: all 5 EXE readers disassembled; `death_path.json` re-analysis | 5 read-hits, **ZERO halfword stores** to `+0x8E` in the EXE; uses = pairwise ordering (`func_80063794`), 3-entity abs-difference (`func_8004B950`), aim-flag-keyed consumption (`func_80056564` reads the `+0xEA` byte that `FUN_8009de68` writes), copy-out serializer (`func_8002ACE4`), arg-pass-through (`func_80051D88`, UNKNOWN). **No damage-subtract pattern exists** |
| **R38 live** | pincorr1 re-analysis: px − scroll ≈ 0..16 at every chunk while `+0x8E` swings 291→81 with regen-like recoveries | naive "screen-x relative to scroll" fails for slot 0 — **slot-0 semantics stay UNRESOLVED**, honestly |

**Resolution (no intuition, per the mission):** the address observation stays (`entity_field_+0x8E`, OBSERVED, full provenance); the semantic label "**+0x8E = entity HP**" is recorded as a `CONTRADICTED` event with `supersedes_role`; slot 0 is explicitly NOT distinguished (pair-freeze A/B limitation) and the field is excluded from all success oracles. The truck-campaign facts missing from the R37 capsule are added as VERIFIED (`armored_entity_HP (entity_base+0xA4)`; the D7 release condition with its phase caveat).

**Machine enforcement:** `ps1play/knowledge/capsule.py` gains a contradiction guard — while an unresolved `CONTRADICTED` event names a role via `supersedes_role`, `validate()` raises on any field retaining that role as VERIFIED (re-promotion requires `resolved_by` → a VERIFIED event, i.e. full provenance), and `fields_by_role(role, min_status=True)` fails loudly at query time. Artifacts are now stored **repo-relative** (portable) with `verify_artifacts()` recomputing hashes — all three shipped capsules validate with hash checks (`test_capsule_contradictions.py`, 8 tests).

**Consumer audit (all code that touches the field):** `combat.py` uses `hp_a4` for every engagement decision (`armor_hold`, `find_truck`, `truck_kill_segments`); `+0x8E` survives only as the honest `sx` alias, a scan-window filter, and the `decide(hp=...)` dodge-reflex indicator — now documented as "damage INDICATOR for a defensive hop only, never an oracle". `wagon.py`'s stale "verified HP" comment corrected (occupancy telemetry, semantics-agnostic). **No reward, termination, or progress path reads `+0x8E`.**

## Task 3 — the function shortlist (10 candidates, no plausibility claims)

`data/games/SLUS-01212/r38_function_shortlist.json` (schema `ps1play.r38-shortlist/1`): S1 `FUN_800a41d8` (overlay, 84 B, damage-ELIGIBILITY gate: `+0x28 & 0x80` early-exit, retarget `0x800151DC`), S2 `FUN_8009de68` (overlay, 500 B, `+0x8E` pairwise compare → `+0xEA/EB` aim latch; **else-branch dead-code proof sharpened**: the dispatch value is `(unkEB & 0x80) >> 4 ∈ {0,8}`, always < 9), S3 `FUN_800151DC` (EXE, 48 B, shared death handler; 4 address-taken refs), S4-S7 the four reader functions above (all NEW R38 decodes), S8 `func_80051D88` (the honest UNKNOWN; 10 callers, static next step = disassemble `0x8004938c`'s arg use), S9 `FUN_80064674` (the camera-delta writer anchor), S10 the section-VM trio (`0x80021128`/`0x800230E0`/`0x80022500`). Each entry: VA, size, artifact, callers/callees, excerpt, hypothesis, status (`OBSERVED`/`UNKNOWN`), smallest discriminating experiment. Explicitly guarded: **the `+0xA4` damage-delivery write site remains UNLOCATED** — no function is claimed to be the truck's damage handler on plausibility.

## Tasks 4/5 — the D7 experiment (5 disclosed boots, deterministic)

Commands (each persisted, re-runnable):

```
python3 scripts/r38t1_reach.py     # boot 1: proven R35 recipe -> r38_ckpt (px 810.3, gren 10)  [REACH OK, 32.4 s wall]
python3 scripts/r38t2_trials.py    # boot 2: trialA1/A2 (shipped policy) + trialB (pure-RIGHT control)
python3 scripts/r38t3_aa_trial.py  # boots 3-5: aa_kill v0/v1(gate)/v2(ungated+rain-hop), x2 each
```

Starting state every run: savestate `r38_ckpt` (px 810.3, gren 10, flags 0xFF), 15-frame micro-chunks, cap 480 chunks. Oracle: score events + walker 0xC / pre-banner `(0,8)→(0xC,9)` + banner PNG — **`+0x8E` never in the oracle**.

| arm | outcome | chunks | deaths | score | key telemetry |
|---|---|---|---|---|---|
| trialA1/A2 (pre-patch shipped policy) | death→restart wall | 268 | 0 | **4600** | pin ×3, release ×2, truck hp_a4 240→150 (−10 fire chips) → grenade −100 → 50 → 30 → 10 → gone by c95; wreck `0xA44C` slot 9 |
| trialB (pure-RIGHT control) | death→restart wall | 45 | 0 | **0** | truck hp_a4 = **300 frozen** at x 937.5 for every observed chunk — no self-decay; the A/B isolates the damage cause to the policy's inputs |
| trialAA1/A2 v0 (aa_kill ungated) | death→restart wall | 227 | 0 | 4100 | **aa_connect=1** (chopper 300→200), aa_miss=10, bail ×1, pin ×3 / release ×2 |
| trialAA1/A2 v1 (|dx|≤40 gate) | death→restart wall | 161 | 0 (php 291→0 one-shot at c161) | 3400 | **aa_connect=0**, aa_miss=6 — gate falsified; the first build had also dropped the rain-hop |
| trialAA1/A2 v2 (ungated + rain-hop) | death→restart wall | 227 | 0 | 4100 | identical profile to v0 — the stable configuration |

**Truck damage = GAMEPLAY-VERIFIED through the shipped policy** (success criterion 2 of the mission): the hp_a4 trajectory, the grenade-counter decrement, the score events, the wreck state word, and the frozen control arm agree. **D7 release: NOT released from the rebuilt phase** — the pin cycles `(0xA,0x43) ↔ (0,0)` and the chopper remains at hp_a4 300 (v0/v2) or 200 (connected once) at every pin observation while everything else in the queue is dead. Distinctions the telemetry makes explicit: real pin-release events (none — no 0xC), temporary progress (the −10 hp chips = real damage, attributed), player respawn churn (the F6 respawn — px 992, **grenades refill 8→10**, new observation), camera movement without progress (n/a — the pin is state-machine evidence), truck damage vs a lookalike field (the disputed `+0x8E` excluded; every damage claim is hp_a4 + score + wreck-state).

**Policy trials recorded honestly:** the aa_kill rule fires in the pin context only, never on fallers/corpses, keeps soldier priority, bails after 6 thrown-and-missed cycles (bounded recovery), and the v1 gate experiment — including the rain-hop regression my first build introduced (php 291→0 one-shot) — is documented in the code and the falsification note, not hidden.

## Task 6 — what changed in the plugin (and what didn't)

`ps1play/agent/combat.py` (plugin layer, zero core edits): `find_chopper()` (identity: st ∈ {0xAA94, 0xABDC} + airborne + hp_a4 > 0), mode `aa_kill` in the pin context with the verbatim J1 pattern (B×3 → neutral×8 → UP+A+aim×8 → cooldown with the rain-hop restored), connect/miss bookkeeping on hp_a4, bounded bail, quiet resolution when the chopper dies. 9 unit tests (`tests/test_aa_kill_policy.py`) including the falsified-gate negative control and the rain-hop regression test. The existing `section_pin` logic and its tests untouched (574 pre-existing tests stay green unchanged). **Not claimed:** a pin release, a banner, or a chopper kill — the rule connected once per run and that is all the evidence supports.

## Task 7 — cheat anchors

Not exercised: the D7/damage work consumed the boot budget and the cheat windows still require the menu ladder that R37 could not re-walk. Cheat-DB addresses remain INFERRED/PENDING in the capsule; the cursor-struct clue (`0x957D8–0x957F8`) remains the recorded observation hypothesis for a future ladder re-walk. No cheat code was applied anywhere near a success claim.

## Task 8 — measured against the baseline

| metric | pincorr1 (Oct 24 baseline) | R38 trialA (same corridor, rebuilt phase) |
|---|---|---|
| chunks / deaths | 40 / 0 | 268 / 0 |
| score | +400 in the pin window (3900 total) | **4600 total**, 25+ kill events |
| truck | field "254" (screen-x) unchanged under fire | **hp_a4 240→0 killed** (fire + grenade), control 300 frozen |
| pin | instrument engaged c26, never released | engaged ×3, self-released ×2 (pin-state exits), never 0xC |
| wall cost | one session | reach 32.4 s + 3 trial boots ≈ 3.5 min emulator wall total |

Success criteria met: **#2** (normal legal action causes independently verified truck damage — hp_a4 + grenade counter + score + wreck state + frozen control) and **#4** (strong falsifiable root cause isolated: the chopper is the release blocker; the minimal experiment — the aa_kill rule — proved it connectable and disproved the throw-gate refinement). Not met: #1/#3 (no release, no new stage).

## Task 9 — suite and system protection

- Full suite before: **577+1xfail**; after: **594 passed + 1 xfailed** (17 new: 8 contradiction-guard, 9 aa-policy; the pre-existing xfail preserved untouched).
- All three shipped capsules validate; MSX capsule 14,325 B (< 64 KiB); artifact hashes verified via `verify_artifacts()`; paths repo-relative.
- Cache invalidation demonstrated: fingerprint-keyed misses on config change + `invalidate(game)` (in-line demo + `test_cache_hit_miss_and_invalidation`).
- CLI delegation unchanged (`capsule-validate` via `ps1play_cli.py` still exit 0); gameplay command surface untouched.
- No game bytes, BIOS, or disc images committed; scratch evidence stays local, compact reports + PNGs committed under `data/games/SLUS-01212/truck_evidence/r38/`.

## Status labels

| item | status |
|---|---|
| +0x8E contradiction fix + guard + tests | IMPLEMENTED, TESTED |
| reader census + shortlist (S1-S10) | OBSERVED (static), UNIT-TESTED where applicable |
| truck killed by shipped policy (control-isolated) | **GAMEPLAY-VERIFIED** (×2 deterministic) |
| Oct-23 "forward fire can't kill armor" reading | CONTRADICTED (corrected in the capsule) |
| chopper = the D7 release blocker | OBSERVED (live, every pin observation, 5 runs) |
| aa_kill rule live connect (300→200) | OBSERVED (×2 deterministic) |
| |dx|≤40 throw gate | CONTRADICTED (live falsification, reverted) |
| D7 pin release from the rebuilt phase | BLOCKED (chopper kill rate) |
| MISSION 1 banner from a rebuilt checkpoint | BLOCKED (same cause) |
| cheat-anchor validation | PENDING (ladder; no boots left this round) |

## Remaining unknowns and the single highest-value next experiment

The connect rate (~1/10) is the only blocker between the current policy and a likely release: three connects kill the chopper (session-3 F4), the queue then clears (session-3 F1), and the banner path is proven. **Next experiment (R39):** a positioning sub-rule that walks/holds the player to keep the tracked chopper inside the |dx| 7–29 band at throw time, then the unchanged J1 pattern — matched ×2 against this round's recorded aa trials from a rebuilt `r38_ckpt` (budget: 2 boots, ~20k frames; oracle: chopper hp_a4 300→0 + walker 0xC + banner PNG). Secondary levers recorded: locate the `+0xA4` damage-delivery write site EXE-side; disassemble `0x8004938c`'s use of the `+0x8E` argument (S8's UNKNOWN); re-walk the menu ladder with cursor-struct polling to unblock the cheat-anchor windows.
