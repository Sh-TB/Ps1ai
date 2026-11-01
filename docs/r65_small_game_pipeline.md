# R65 Small-Game Pipeline — discovery, ranking, the one active game, and the queue

Round: **R65** · Part E deliverable.

## 0. Process state

```
DISCOVER -> VERIFY SOURCE AND LICENSE -> BUILD -> CREATE ISOLATED PLUGIN
   -> CREATE ITS OWN KNOWLEDGE -> INTEGRATE INTO RUNTIME
   -> AUTONOMOUS GAMEPLAY TEST -> VERIFY OBJECTIVE
   -> EXPORT DOWNLOADABLE PACKAGE -> CLOSE CURRENT GAME -> SELECT NEXT
```

* **Active game this round:** BuzzyBee — taken through the FULL pipeline
  to its acceptance gate (below).
* **Completed games (integration closed):** Tetrade (R63/R64, re-verified
  + improved this round), FlappyBirdPSX (R61, re-verified this round).
* **Next game selected:** none started — the pipeline rule is one active
  game at a time, and R65's active game consumed the round's integration
  budget. The ranked queue below names the next candidate and its exact
  unblocking condition.
* **No half-completed integrations:** every candidate below is either
  integrated+verified, refused with evidence, or queued with a concrete
  blocker.

## 1. Candidate catalog (verified sources, licenses, artifacts)

| candidate | source / license | local artifact | boot | objective | decision |
|---|---|---|---|---|---|
| Tetrade | github.com/Logan-Campbell/Tetrade, MIT | TETRADE_PSX.bin 3,196,368 B sha `2f41feba…` (+ LOCAL license-patched image, sha `7eb38eda…`) | VERIFIED (3 boots) | Marathon survival, lines cleared | **INTEGRATED (R64)**; R65: anchor-corrected policy, 1.0 → 23.83 lines/life |
| BuzzyBee | github.com/NDR008/BuzzyBee, MIT (in-header, flagged) | BuzzyBee.ps-exe 299,008 B sha `9b0bfc08…` → wrapped NTSC disc sha `042b94bb…` (user license sectors, disclosed 2-instruction NTSC patch) | VERIFIED (renders; PAL renders black — documented) | endless survival, score = play frames | **INTEGRATED (R65)** — the active game |
| FlappyBirdPSX | github.com/IcePanorama/FlappyBirdPSX, Unlicense | flappybirdpsx-v0.1.0.iso 571,536 B sha `b45871d3…` (direct boot, no patching) | VERIFIED | endless survival, pipes | **INTEGRATED (R61/R62)**; R65: fresh product-path re-verification |
| PSX-Minecraft | github.com/EngineersBox/PSX-Minecraft, MIT | PSXMC.bin 329,280 B (+ LOCAL license-patched image) | VERIFIED + input-responsive (issue #6 A6) | sandbox — NO discrete verifiable goal | QUEUED (blocked on an objective definition; not integrable as a verifiable-objective game) |
| Nortis | github.com/jbreckmckye/nortis — **NO LICENSE FILE** (API re-verified: 0 license files) | local license-patched image boots to gameplay | VERIFIED locally | gameplay HUD observable | **REFUSED** (redistribution rights unverified — standing refusal since r21) |
| hello_pong | github.com/marconvcm/ps1_dev, MIT | **no release artifact exists** (0 releases; CI publishes only on tags; none pushed) | n/a | smallest input-latency probe | **BLOCKED** (needs a maintainer tag or a Docker+PSn00bSDK build; Docker absent from this CPU-only sandbox) |
| ButtonMasher / RPS-PS1-v1 | no license, no releases; Windows-only 2012 PSXSDK toolchain | none | n/a | n/a | **REJECTED** (standing, r21) |
| zenmai | homebrew (Z-machine) | local wrapped image | BOOTS to title | input UNPROVEN on this backend (direct-SIO pad) | PARKED (r26, timeboxed 8-boot investigation; recorded, not restarted) |
| MSPSX | github.com/AcidGunner/MSPSX | local | PLAYING_BOT accepted (r29) | out-of-scope vs small-game ladder | not queued this round |
| Poy Poy / Trap Gunner (USA) | owner-supplied retail discs (local-only) | local | BOOTED + input-causal | need entity-table RAM mapping | QUEUED behind the RE gates (retail, not small-game pipeline) |

## 2. Ranking rules applied (E2)

Small build size → clear license → buildable source → low dependencies →
short boot → simple controls → observable gameplay changes → clear
objective → real-emulator compatibility → low integration cost.
BuzzyBee ranks first among the un-integrated candidates: 299 KB EXE,
MIT, source available, zero extra dependencies, ~seconds to boot, ONE
button, per-frame score, anchors ALREADY VERIFIED (14 capsule fields),
and a proven policy from the R45-B→R52-B line — the lowest integration
cost with the highest prior evidence. PSX-Minecraft loses on "clear
objective" (no discrete goal → nothing verifiable to claim). Nortis
loses on license regardless of everything else.

## 3. The active game's acceptance gate (all PASSED)

1. **License verified:** MIT (c) 2021 NDR008, in-header (flagged as
   such since r23 — the flag is honest, the license is real).
2. **Artifact verified:** upstream EXE sha `9b0bfc08…`; wrapped disc
   rebuilt this round byte-identical to the committed record
   (`042b94bb…`).
3. **Isolated plugin:** `ps1play/adapters/buzzybee/` (adapter + policy
   + package spec) — zero shared-core edits, zero cross-game imports.
4. **Own knowledge:** the capsule + the R65 discoveries (gs=5 game-over
   characterization; the 2-frame flap press requirement) + the disc pin.
5. **Runtime integration:** registered as `buzzybee` with
   `progress_label="score"`; disc pin in `session.py`.
6. **Autonomous gameplay test:** `python3 -m ps1play play buzzybee` —
   real product runs committed (see §4).
7. **Objective verified:** the score law (score = play_frames −
   offset) verified EXACT on every episode; natural game overs reached;
   the restart flow exercised through the product engine.
8. **Downloadable package:** `buzzybee.ps1game` v1.0.0
   (PARTIAL_AUTONOMOUS_PLAYER) — export/validate/install verified, tests
   included, disc-build tools included.

## 4. Actual gameplay outcomes (data/r65/r65_buzzybee_acceptance.json)

| episode | result | score | frames | law check |
|---|---|---|---|---|
| ep1 (k=6) | ALIVE at 6000f budget | 5904 | 6000 | 6000−96 = 5904 EXACT |
| ep2 (k=12) | death (natural game over) | 7537 | 1633 (continuation) | 5904+1633 EXACT |
| ep3 (k=18) | death (fresh run after restart) | 2808 | 2906 | 2906−98 EXACT |

Plus the discovery record: a flap press must be held exactly 2 frames
(one-frame presses left the bee pinned at the floor through 389
presses — measured), and gs=5 is the hp-depletion game over (resolves
the capsule's score-cap-1000 UNKNOWN; no score cap exists).

## 5. The next game

**PSX-Minecraft** is the selected next candidate IF its objective
problem is solved first: it is the only remaining ACCEPTED, LICENSED,
BOOTED candidate. Its blocker is definitional, not technical: no
discrete verifiable objective exists (a sandbox). The concrete next
step is to define one measurable objective from the game's own state
(e.g. a block-placement count or a movement-distance challenge through
verified RAM fields — a small RE increment on the already-verified
input-responsiveness evidence) BEFORE any plugin work. Per the pipeline
rule, no plugin code is written until that definition exists.

**hello_pong** remains the cheapest UNBLOCK-by-external-action
candidate (a maintainer tag or Docker would integrate it in hours —
its plugin shape was already designed in R54's pong regression).
