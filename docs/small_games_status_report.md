# Small-Games Completion Report — the honest per-game ladder

> **Round R53 open, 2026-10-30.** Written on the owner's direct question:
> *"Did you actually complete a game fully? We agreed not to focus on one
> game only — the small games: could you run them to completion? Give a
> report on the other games so we can complete them."*
> This report is the honest answer from the repo's own evidence (worklog,
> capsules, issue threads, evidence GIFs). No new boots were spent.

## 0. The direct answer

**Yes — for the small homebrew games, four of them are WON with full
evidence chains** (Tetrade, hello_pong, mspSX, FlappyBirdPSX): the run
reached the game's OWN win state, measured and GIF-anchored.

**No — for the two main games of the current phase:**
- **Metal Slug X (SLUS-01212, the 60% track)** is NOT completed. Mission 1
  interactive progression was FALSIFIED (deterministic deaths at the c86/87
  wall on every clean rebuild); the track pivoted to the wound/pay-frame
  mechanism campaign (R44-R52).
- **BuzzyBee (Issue #6, the 40% track)** is NOT completed — it is the most
  deeply *researched* game in the library (score law exact across six caps,
  five consecutive caused-replications, the wave-phase mechanism found),
  but no win/ending state of the game has ever been discovered. Whether one
  EXISTS is an open unknown (§3, item 2).

The 60/40 split rule (MSX 60% / BuzzyBee 40%) has been in force since r22
and held through R52; the small-games completions below came from the
earlier r14-r35 library trains and the transfer playbook
(`docs/tiny_games_playbook.md`).

## 1. The full library ladder (every game ever accepted, current rung)

Status taxonomy per `docs/tiny_games_playbook.md` §0:
RUNNING < PLAYING < WINNING. "WON" = the game's own win state reached.

| # | Game | Type | Current honest rung | Evidence anchor |
|---|------|------|--------------------|-----------------|
| 1 | **Tetrade** | homebrew | **WON — full playthrough** (Issue #8) | 40 pieces, 11 singles verified per-increment, score 0→218, natural game over, CONTINUE refused, 2 bit-identical runs; later 99.86% landing PLAYING (r28) |
| 2 | **hello_pong** | homebrew | **WON 5-0** | r28 library ladder "WON 5-0"; win screen GIF r19_t4 |
| 3 | **FlappyBirdPSX** | homebrew | **WINNING** (deep-complete) | 10 RAM-anchored pipe passes, score digits "10" drawn at the win frame, bird alive; 2,176 f, 1 real death + restart (r15) |
| 4 | **mspSX** (minesweeper) | homebrew | **WON — full board** (R35-C, first full board win in project history) | 32 mines validated, WinCheck after every reveal, 59/59 flood predictions match the 8-neighborhood sim, "YOU WIN!" rendered, REVT 0→160, 14,665 f ≈ 54 s wall |
| 5 | **autogaz** | homebrew | FULL_CYCLE_CAUSAL | r27 full fuel cycle verified end-to-end (its verifiable whole) |
| 6 | **air_hockey** | retail (SLUS-01467) | COMPLETE_LOOP_OBSERVED | match → natural end → CONTINUE? → new match in a new arena (r28); win-vs-AI superiority not attempted |
| 7 | **PSX-Minecraft** | homebrew | place-confirmed sandbox | No win state EXISTS in the game (infdev; fall-void halts the game beyond 7 blocks from spawn — observed 2×). Honest ceiling: cannot be "completed" by design |
| 8 | **DoukutsuPSX** | homebrew port | GAMEPLAY_CONFIRMED | title → NEW GAME → movement GIFs (r24/r25). Full cave playthrough = long-horizon, unscheduled |
| 9 | **BuzzyBee** | homebrew (Issue #6) | GAMEPLAY_CONFIRMED → dominance-researched | score = survival_frames − 99 EXACT across SIX caps (1401→2301); 9 wasp passes; FIVE consecutive caused-replications (R48-R51) then honestly broken (R52); wave-phase mechanism: PASS-BOUNDARY-LOCKED at f_since_pass_start 112 |
| 10 | **Poy Poy** | retail | PLAYING | boot + input causality verified (owner source), RETIRE #2 YES with the hearts counter live (r21t6); RAM entity mapping pending |
| 11 | **Metal Slug X** | retail (SLUS-01212) | NOT COMPLETED — mechanism campaign | M1 interactive progression FALSIFIED (3/3 deaths at c86/87, px≈951.1, clean rebuilds); tainted frontier px 1224.9/1254.8 (5 deterministic rebuilds); pay-frame classes: +100 kill-locked n=6, +500×3 vs +1000×7 connects, piercing n=4, controls never pay ×5 rounds, accumulator candidate slot12 +0xa0 |
| 12 | **Trap Gunner** | retail | BOOTED candidate | boot + input causality verified; RAM mapping pending |
| 13 | **Ballistic** | retail (SLUS-00966) | TITLE_NOT_REACHED | the r16 "BOOTED" RAM-churn verdict CORRECTED in r18: publisher logos → long load → static; SLOW_INIT measured |
| 14 | **zenmai** | homebrew | PARKED — INPUT_DEAD_AT_MENU | user directive: do not get stuck |
| 15 | **BKBS_PSX** | homebrew | SHELVED (T4) | user directive R24-33 |
| 16 | **Nortis** | homebrew | LICENSE-BLOCKED | no LICENSE file anywhere (API-verified); 35,270 f local play-test only; integration refused |

## 2. What the four WON games actually prove

These are not showcase GIFs — each win carries the measured chain the
playbook demands (the r14 fraud retraction is the reason the bar is high):

- **Tetrade**: every one of the 11 line clears verified per-increment on
  the localized matrix words (base 0x1FECA0), score 0→218, a NATURAL game
  over (no savestate shortcut), and 2 bit-identical runs for determinism.
- **mspSX**: the full board decoded offline FIRST (32 mines validated), a
  click plan simulated offline (59/59 flood predictions matched), THEN
  executed; the game's own WinCheck() agreed after every reveal and the
  game rendered its own "YOU WIN!". REVT 0→160 monotone.
- **FlappyBirdPSX**: 10 pipe passes each anchored by the pipe pool's RAM
  x-position crossing the game's scoring gate, and the game's own score
  digits drawing "10" at the win frame — vision and RAM agree.
- **hello_pong**: 5-0 to the agent on the localized score words, win screen
  reached ("WINS! / PRESS X TO PLAY AGAIN").

Transfer value: `docs/tiny_games_playbook.md` (boot-route decision tree,
controller truth table, input-edge discipline, the RUNNING/PLAYING/WINNING
taxonomy) cut hello_pong's rounds-to-real-play from 4 to 1 (flappy).

## 3. The R53 win-state survey — ANSWERED same-round (internet-first, zero boots)

The standing question behind "complete the game" for BuzzyBee is now settled
from the SOURCE, not guessed: the game is open-source
(github.com/NDR008/BuzzyBee, MIT, EXE sha 9b0bfc08… matches the capsule
identity), and `main.c` (v1.0, fetched 2026-10-30, evidence:
`scratch/r53/buzzybee_main.c`) has **NO win state**:

- The state machine is exactly `gameState ∈ {0 intro, 1 gameplay,
  5 gameOver, 99 debug}` — there is no victory/ending state anywhere.
- The ONLY exit from gameplay is death: `mainHealth.level < 0` → health 0,
  bestScore update, `gameState = 5` → `gameOver()` prints "Your Last
  attempt / Your Best score / Credits", then auto-resets to the intro
  after 6 s.
- The readme confirms the design: *"The goal is to work for as long as you
  can to make the Queen Bee happy"* — an endless Flappy-Bird-like survival
  scorer.

**The source also explains the six rounds of measured law** (R46-R52):
- `score++` once per `gameMode()` frame → the EXACT measured law
  **score = survival_frames − 99** (the −99 = intro frames before
  `gameMode` starts). The law was never a fit — it is the game's code.
- Health: start 5999, −3 per frame (flight drain), **−1500 per wasp-hit
  edge**, +1000 per flower-pickup edge, hard cap 5999 (a pickup at full
  health is WASTED by the clamp — planner-relevant).
- Flowers ride the rocks (`flowers[i]` share `rocks[i].x_vel`, spawn on
  rock tops) — the geometry the R43/R44 bail analysis measured.
- Death threshold arithmetic: survival needs
  `effective_pickups ≥ ceil((3·CAP_F + 1500·hits − 5999)/1000)` —
  at 2400 f with 1 hit that is ≥ 3 total pickups, while caused 2 + the
  unattributed opportunistic pickups is exactly how arm B survived R52.
  (Source-derived arithmetic, not yet re-measured in vivo — flagged as an
  R53 offline check.) This also predicts the CAP_F ladder's next rungs:
  2600 f / hits 0 needs 2 effective pickups (margin 199 health),
  3000 f needs 4.

**Completion definition, owner decision requested**: since BuzzyBee cannot
be "finished" by design, the honest completion program is (a) the R53
wave-phase pre-position (full oracle @2400), (b) the CAP_F ladder upward
under the survival arithmetic above, and (c) the bestScore axis — the only
"100%" the game itself offers is a maximal survival run.

## 4. The ≥10-item work list (standing owner directive; carried here)

Ordered by the 60/40 discipline. Items 1-4 are the R53 round plan.

1. **[MSX, R53] Gate diagnostics + the +500 capture** — the per-skip
   blocking-occupant dump (offline first, the r52 dry-run precedent), then
   one capture boot for the missing +500 pay-frame class → the magnitude
   discriminator (+500×3 vs +1000×7) closes or the accumulator model dies.
2. **[BuzzyBee, R53] The wave-phase pre-position predictor** — the capsule
   next_experiment verbatim: pre-position the bee BEFORE the wave frame
   (f_since_pass_start 112, e=[32,31,3]); restore-only from the r52b gs1
   checkpoint; full-oracle@2400 (hits 0 AND caused ≥ 2) predicted.
3. **[BuzzyBee] The WIN-STATE SURVEY — DONE this round (§3)**: answered
   internet-first from the source, zero boots — NO ending exists; the
   completion redefinition (survival-max / oracle-dominance) is filed for
   the owner and the survival arithmetic is added to the R53 offline
   checks. Residual: verify the pickup arithmetic in vivo once.
4. **[MSX] The M1 wall decision memo** — after item 1: tainted-lineage M1
   progress (px 1254.8, 5× deterministic) vs the HP-word fallback (a)
   (0x4054 read-out) — needs a fresh budget disclosure to the owner.
5. **[BuzzyBee] R54+ CAP_F extension if R53 lands clean** (2600; the 6th
   caused-replication + the 10th pass watch; score ≥ 2501 predicted).
6. **[MSX] M2 readiness stays parked** until the M1 decision memo lands.
7. **[Poy Poy] Entity-table RE campaign opening probe** (categories 2-4
   acceptance gate) — one bounded probe train, never at the expense of 1-5.
8. **[Ballistic] One bounded title-unstick probe** per the r18 suspects
   list (manual PNG census at the exact title frame) — one boot max.
9. **[Tetrade] Landing-polish train (99.86% → 100%)** — parked, lowest.
10. **[PSXMC] The bounded final experiment** (dig-crash gate) — parked.
11. **[Nortis] No action** without an owner licensing decision (stays out
    of the committed matrix).
12. **[Housekeeping, every round] push-per-round + capsule schema
    validation** — the discipline that survived three sandbox rollbacks.

## 5. Honest gaps that keep the main games incomplete

- **MSX**: the game is NOT beaten and no live-gameplay completion claim has
  ever been filed. The only past-wall path found so far is TAINTED
  (restart-leak lineage). What IS real: five deterministic tainted rebuilds,
  the pay-frame measurement rig, and the mechanism table — instrumented
  knowledge that makes the next attempt cheaper, not a completed game.
- **BuzzyBee**: deep dominance knowledge with an exact score law; the
  "what does finishing look like?" question is now answered (§3: nothing
  to finish — a survival scorer) — what remains is pushing the survival
  frontier and the owner's sign-off on the redefined completion.
- **Retail deep games** (Poy Poy, Trap Gunner, Ballistic): all stopped at
  the RAM-mapping/boot gate; none playable to a goal state by the agent.

## 6. R57 intake — the autonomous student round (2026-10-31)

**Trigger:** the owner filed the R57 MASTER MISSION ("the student must
learn beyond the teacher") and directed a line-by-line review plus a
dedicated issue. Both landed this round at base `f5a47a6`:

- `docs/r57_mission.md` — the canonical verbatim mission text.
- `docs/r57_mission_review.md` — the line-by-line audit: 22 findings
  (0 blockers, 9 GAPs with proposed resolutions, 5 RISKs with
  mitigations, 8 OK-with-notes), all numbers recomputed (C1 173 and
  teacher 194 verified; C3's regression ≈ 107 added to the audit's
  correction of the header's "C2 and C4" summary).
- The R57 workstream issue (cross-linked from #12) carries the
  condensed work plan, the numeric regression gate, the seed-split and
  boot-budget rules, and the 29-item deliverables checklist.

**Why a separate issue:** PART 17 of the mission says "do not create a
duplicate Flappy issue unless a genuinely separate root problem exists."
The owner directed a new issue; the R57 autonomous-learning workstream
(20-pipe teacher cutoff → teacher-off self-improvement → unseen-seed
evaluation) is a genuinely separate root workstream from #12's general
visual-learning track, so both conditions are satisfied. #12 remains the
parent evidence thread; nothing is duplicated between them.

**Carried into R57 from this report's standing rules:** the ≥10-item
work list discipline, push-per-round with verified read-back, honest
status labels, and the 60/40 focus rule (R57 is a Flappy primary round
under Issue #12's game; Pong regression stays green via the existing
suite).

**R57 execution order (from the review, evidence-grounded):** P0 audit +
seed splits → P1 capped bootstrap + clean BC → P2 teacher-off
enforcement (AST + import-hook + hashed trace) → P3 learner bake-off
(ES/ARS first, correct-PPO second, confidence-aware exploration layer
third, self-imitation last) → P4 the pipe-overlap perception latch fix →
P5 numeric-gated promotion + 20 unseen TEST seeds × 3 boots.
