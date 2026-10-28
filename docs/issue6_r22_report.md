# Round 22 — the infra-cut round: 7 trains, 9 boots total, 3 honest corrections

Date: 2026-10-28 · Policy: 60% very-simple / 40% baseline. The sub-agent launch
layer failed 7/7 at start (adapter timeouts) and cut 2 relays mid-boot; every
close-out was graded from on-disk evidence by the orchestrator. What survived
is some of the best science of the project — including two self-retractions.

## Simple-game track

### MSPSX (Minesweeper Plus) intake → INPUT_RESPONSIVE (new game #9)
The pre-boot source decode (upstream clone) predicted a missing-RXEN stall
(phantom 0xFFFF held → auto-START → inert board) and prepared a 2-instruction
patch. **Boot 1 refuted the prediction**: pad_buff = `41 5A FF FF` (healthy
idle), title stable 1,078 frames, no auto-exit. Root cause of the
non-stall found in beetle `frontio.c:805-820` — the TXEN trigger route admits
the ReceivePending branch, so MSPSX's dummy-read + TX latch aligns RX bytes;
RXEN is unnecessary on core 0.9.44.1. The patch artifact was built, gated
shut, and disclosed as never booted. **Boot 2 proved input**: START pulse →
board init @f665 (mine_count=32, FIRST_CLICK=1 — the decode's symbol map
confirmed live); RIGHT → cursorX 0→1 (pad SW1=0xDF, RAM+VLM); DOWN → cursorY
0→1. The CROSS reveal probe failed for two disclosed reasons (libretro "X" =
Triangle on this core; SPI poll cadence ≈33 frames swallowed a 2-frame hold)
→ the single remaining rung to RUNNING is a ≥35-frame CROSS hold. Verdict:
**INPUT_RESPONSIVE**, 2/2 boots, nothing inflated.

### BKBS → RUNNING holds; note-pool locked live; relay died before the hits
The static decode (upstream source) gave the full judgment model: 30 Hz game,
window y∈(83,102), lane→button map, desaturation accumulator, **no score
counter exists in the game**. The relay locked the pool live (30 slots,
stride 0x28, first spawn @f785, y += 2/Update, separate 60 Hz frame counter),
ran a clean deliberate-miss control — and died before the servo-press phase.
Three honest discrepancies logged: active/hit flag offsets unresolved,
desaturation @0x80038CA0 reads 0 (decode says init 80), x-field not at the
expected offset. Verdict stays **RUNNING**; the next relay is one boot.

### zenmai → honestly DEMOTED to INPUT_DEAD_AT_MENU
The best correction of the round. The relay's forensic census proved r21's
"opening @f910" was a **false positive** — f910 was still the language menu;
the default cursor sits on 日本語, ENGLISH is *below* it (selection key =
DOWN, not UP), and START never launched the Z-machine despite 3 pressed
windows. The r21 menu-level INPUT_RESPONSIVE claim is retracted. What r22
added: patch2 bytes verified in-disc (after 2352-byte de-interleaving) and
live in RAM @0x8001B360; libretro input delivery verified from source; and
the stall **source-proven with line numbers** — beetle `frontio.c`: a JOY_DATA
*write* only sets TransmitPending (:861-865), a *read* arms ReceivePending
(:959-966), so zenmai's TX-only-wait-RXRDY class can never see RXRDY on this
core; **PCSX-Redux drives the pad off the WRITE side** (`sio.cc:108-111`) and
is the clean fix candidate for the whole zenmai class (live re-test queued).
The r22t3 host simulation (zero boots) had already extracted the exact sread
buffer addresses (story+0x27E8/0x251E), the exact response texts ("West of
House" = 131 B), and the corrected T9 typing chords (r21's were wrong — that
is why the r21 completion-buffer hunt found 0 candidates).

### Web scout (r22t4) — 196-line addendum despite the cuts
`docs/homebrew_sources_r21.md` gained the Round 22 addendum: new candidate
**BuzzyBee** (MIT, artifact held + hashed); MSPSX full source map; BKBS
timing constants; **Nortis = BIOS InitPAD class** (would land on the current
backend with zero input work if the license gap is ever cured); and the
direct-SIO world split into two classes (TX-only-wait-RXRDY vs
read-per-byte full-duplex) with core-source line numbers. r23 shortlist:
BuzzyBee, MSPSX (finish the reveal), psx-snake.

## Baseline track

### MSX stage-loader (r22t7, research-only, zero boots) — docs/msx_stage_loader_r22.md
Static map delivered: BSS 0x800C9A50..0x800FA6B0; gp=0x80010000; setter
@0x8002CB30 writing via runtime pointer [0x800D9A98] (+0x130/+0x9E); two
state structs 0x800CA268/0x800CA3B4; the 20-entry cutscene filename blob
(stride 0x18); "STAGE %d" @0x80011160; and the **menu BSS cluster
0x800D496C..0x800D4A72** (7 candidates, same page as the r20-retracted unlock
counter). The r23 plan is one falsifiable boot: per-frame diff of the cluster
while selecting MISSION 2 in the pause menu; positive signal = MISS06/ST02
file opens; refutation = banner stays "1-1" → diff the two structs instead.

### air_hockey → RUNNING holds + a self-retraction
Boot 2's auto-verdict printed "PLAYING" and the agent **retracted it itself**:
the pin phase had false-passed on the pre-match dialogue screen (the clamp
"paddle at edges" VLM was a hallucination on two dialogue portraits). Valid
results kept: the full legal gate walk reproduced, the real match runs ~90
bursts with a game clock and goals on both sides, and the score-scan yielded
a clock-like cluster (0x8009BE11/3B/53/55/57) + goal-flag-like flips
(0x800A1385/0x800A13BD). Key timing fact: the match starts a few hundred
frames AFTER the FIGHT ME dialogue. 2/3 boots.

### Poy Poy → PLAYING holds + two belief overturns (1/3 boots)
The mapping boot over turned two assumptions: **our own 1P was at 0 hearts at
the r20t4_retire checkpoint** (one hit from death all along), and 4P was
retired by AI crossfire during the r21 ablation. Heart-cell map corrected:
0x8009DF00 = 3P (causally confirmed), 0x8009E29E = 1P candidate, 2P/4P are
heap-per-round; the r19 i32 slots are **dead outside their lineage** — r21's
KO was directional luck (its aim came from a dead slot). New mechanic:
**hearts regen during live play**. Aimer decision: vision-first. The clean
retire → WON attempt is queued for r23 with the hearts counter live.

## Process record
- Infra: 7/7 initial launches failed (backend adapter timeouts); 5 trains
  still delivered work before dying; 2 research trains initially left no
  trace — r22t7 was re-run by the orchestrator (this doc's author) and r22t4
  turned out to have completed its document before dying.
- Second filesystem rollback to 6b97fbe mid-round: recovered via origin
  (remote intact at 2f425b8) + /tmp asset mirror (mspsx/poy_poy/air_hockey
  assets restored; sha256 spot-checks passed).
- Discipline upgrades held: boot caps asserted inside scripts
  (no overruns this round), orchestrator-only manifest writes (no repeat of
  the r21 write race), evidence written incrementally.
- Suite: 565 passed + 1 xfailed throughout. No game bytes committed.

## R23 plan
1. MSPSX: one boot — ≥35f CROSS hold at (2,1) → RUNNING (reveal anchored).
2. zenmai: PCSX-Redux backend re-test (write-side pad drive) or per-frame
   SIO instrumentation of the synchronous exchange.
3. BKBS: one boot — resolve active/hit/desat offsets, servo presses → PLAYING.
4. BuzzyBee intake (new candidate, artifact already held + hashed).
5. air_hockey: scene-guarded paddle pin → PLAYING.
6. Poy Poy: vision-first aimer + hearts counter → clean retire → WON bout.
7. MSX: the single instrumented MISSION-2-selection boot per the r22 doc.
