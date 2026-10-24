# Mission 2 Final Value Report (Deliverables J + H, Issue #9 §15-16)

## §15-J answers, with evidence

**1. What objective can PS1Play now achieve that it could not demonstrably achieve
before?**
The MSX clamp-zone armored-truck encounter no longer one-shots the agent. Before:
4/4 passes died to the −291 pin ram at px ~1164 (sessions 2-5). Now: the agent holds
position and fights the wave (arm B: **0 deaths in 5400 frames**, truck chipped
340→214 under standing fire; post-fix policy pass: no ram, max_px 1083.8). Also: the
Tetrade complete game loop is now **reproduced from clean setup twice, bit-identical**
(marathon fc 1770 → 40 pieces → 11 line clears → natural game over fc 7890 → refuse
CONTINUE → title), converting a historical claim into current-HEAD verified fact.

**2. How much faster was diagnosis or completion compared with the manual baseline?**
The truck-zone root cause took 3 checkpoint arms (≈26 s emulator wall time + analysis)
versus three sessions of full-level replays that never isolated it. Cost per
hypothesis test dropped from minutes (level replay) to seconds (checkpoint arms).

**3. Which tool saved the most time, and in what specific task?**
The **prebuilt PCSX-Redux binary** (distrib.app Build 482): bypassed the session-long
cmake blocker in ~4 minutes and produced the first verified second-emulator
capability statement (headless boot, Lua automation, pad override, RAM FFI, shell
hijack — all live-tested). Its gameplay-park finding then *saved further wasted
effort* by re-directing diagnosis to the proven Beetle differential method. In
absolute gameplay terms, the in-process checkpoint differential harness (arms from
one savestate) was the workhorse.

**4. Which tool was not worth its cost?**
emucap — blocked on one exact prerequisite (retail `scph5501.bin`, which we do not
possess and will not download); zero of its capabilities were reachable. jev-game-agent
as a dependency — paid API + no license; only its three mechanisms were adopted
(lookahead gate, action-ban/walk-back concept, factual death episodes), implemented
as original code.

**5. Which decision-loop change produced a measurable improvement?**
`armor_hold` (stop-and-shoot ahead-armored foes instead of advancing into their
charge path): survival 0 deaths/5400 frames (hold arm) vs 4/4 one-shot deaths; live
post-fix pass eliminates the ram entirely. Secondary: `validate_scan` makes silent
observation corruption impossible; the lookahead filter shows 8/11 prediction
accuracy and accepted 2 alternatives in its first paired run (survival value not yet
proven — honest PENDING).

**6. Did the improvement transfer to another scenario or game?**
`armor_hold` is deliberately MSX-plugin-scoped (per the no-game-specifics-in-shared-core
rule). The game-agnostic pieces transferred by construction: DecisionLog/scorecard ran
unmodified on Tetrade AND MSX runs; `validate_scan` contains no game addresses and is
unit-tested offline; the harness's compare_runs/first-divergence worked across both
games' logs unchanged.

**7. What remains unverified?**
(a) whether the truck can be *killed* from the hold position (chip rate ~14 hp/s
observed; grenade escalation owed a long run); (b) attrition survival inside the hold
(63/29/28 chip damage killed the post-fix pass); (c) D7 section-pin traversal;
(d) vertical targeting against a *visible* flyer (per-chunk scan cannot see them —
per-frame h-trace owed); (e) lookahead survival value beyond one paired run;
(f) PCSX-Redux gameplay execution (vblank-wait park).

**8. What is the single highest-value next experiment?**
A **long armor_hold kill run**: stand at the verified-safe hold band and let the
grenade escalation finish the armored wave. If the truck dies there, Mission-1
progress past the truck zone becomes a policy matter, not a mystery.

## Deliverable H — ranked next actions (≤5)

| # | Action | Expected gameplay benefit | Confidence | Cost | Reuse |
|---|---|---|---|---|---|
| 1 | Long armor_hold kill run (hold band + grenade escalation vs the truck) | Direct: clears the wave that ends every pass | high (kill path 254→207×3 already verified) | 1 checkpoint run | MSX |
| 2 | Attrition survival in armor_hold (reposition-while-holding; target soft shooters) | Stops the 63/29/28 chip deaths | medium | small policy change + tests | MSX |
| 3 | Per-frame slot h-trace over one chopper phase (find the flyer encoding) | Unlocks §9-B vertical targeting vs the chopper | medium | 1 instrumented run | MSX, general flyer sense |
| 4 | PCSX-Redux vblank-park investigation via its own gdb-server/Lua breakpoint | Unlocks the only breakpoint-capable PSX oracle in this environment | medium | 1-2 h | all future RE work |
| 5 | Matched-repetition lookahead campaign (≥5 paired runs) | Settles whether Track D improves survival | low-medium | 5×2 checkpoint runs | all games |

## Tool adoption ledger (final for this mission)

| Tool | Decision | One-line reason |
|---|---|---|
| Beetle PSX in-process (existing) | ADOPT (unchanged default) | proven gameplay path; mission forbids replacement |
| PCSX-Redux prebuilt | ADOPT_DIAGNOSTIC_ONLY (PENDING) | capabilities proven to game-init; gameplay park documented |
| emucap | BLOCKED | exact prerequisite: legal scph5501 BIOS absent |
| jev-game-agent | REJECT as dep / ADOPT mechanisms | paid API, no license; 3 mechanisms ported as original code |
| MSX-Recomp metadata | ALREADY ADOPTED (Task 5-a) | 15,125 records merged; re-verified identity |
| Decision harness (this mission) | ADOPT | used by every run in this report |

## Definition-of-success checklist (§16)

- [x] Small game objective completed and independently verified (Tetrade ×2 clean)
- [x] Repeatable run reproducing the result (bit-identical)
- [x] Controlled comparison demonstrating tool/algorithm value (armor A/B, lookahead A/B, tool matrix)
- [x] Real diagnosis eliminating a concrete failure (clamp one-shot: root cause + live fix)
- [x] Workflow reusing checkpoints, state evidence, failure memory, regression replay
- [x] MSX improvement supported by before/after (4/4 ram → 0 ram)
- [x] No emulator replacement, no paid dependency, no speculative framework
- [x] Short evidence-ranked next-step list (above)
