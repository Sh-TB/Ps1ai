# Round 21 — six trains under the 60/40 policy (4 very-simple games + 2 baseline)

Date: 2026-10-28 · Policy: 60% of train capacity on very simple games, 40% on our
baseline games (user directive). Every verdict below is graded on the honest ladder
(RUNNING < PLAYING < WINNING; boot ladder BOOTED_* / INPUT_RESPONSIVE). Nothing is
inflated, failures and deadline overruns are disclosed.

## Simple-game track (4 trains)

### r21t1 — BKBS intake → RUNNING (new game #8)
hardrockbluesky/BKBS_PSX ("Bambi's Knees", one-song rhythm, MIT code / NC data). No GitHub
release + API rate-limit → artifact taken from the repo tree (prebuilt PS-X EXE 172,032 B,
sha256 recorded). New wrapper `r21t1_bkbs_wrap.py`: iso9660_min data track + dummy pad to
LBA 2335 + 150-sector pregap + 2 CDDA tracks with TRACK 02 INDEX 01 pinned at MSF
00:22:55 — a source-derived hard requirement (`PlaySyncedTrack()` hard-waits status 0x82
otherwise). Boot: padbuff 0xB008/0xB02C, per-button pad bits proven (SELECT 0xFFFE /
CROSS 0xEFFF / START 0xFFF7 / UP 0xFFEF), frame counter @0x80038C8C. VLM: 3D house →
tatami-room cine tour with arrow notes in flight. 2/2 boots used (boot1 lost to a script
logging bug — disclosed). GIF mirrored: docs/evidence_gifs/r21t1_bkbs_rhythm.gif.
Not proven: note HITS (timing-dependent) → PLAYING not claimed.

### r21t2 — autogaz input → INPUT_RESPONSIVE, PROVEN (root cause decoded)
r20's seven probes failed because **none of them pressed ps1play "B" = PSX CROSS** — the
only button that acts at state 0 of autogaz's 4-state meme slideshow. Proven chain:
CROSS held → game padbuf u32 @0x800BE548 flips 0xFFFFFFFF→0xFFFFFFBF the same frame →
state word @0x800BC7EC 0→1→2 → screen MAD 121.3→133.7 (VLM: neutral → smiling meme);
state 2→3 fires when timerVal @0x800BC7F0 hits **exactly 476** (source constant);
CIRCLE at state 3 → state 3→0 and screen MAD **0.0** vs baseline = reversal proven.
RE: PadRead @0x80017a88 returns `~(u32)@0x800BE548` (inverted, active-high); PadInit
@0x80017a3c via B0-stubs (corrects r20's "zero BIOS calls" scan artifact). 2/2 boots.

### r21t3 — zenmai input → INPUT_RESPONSIVE at menu level (*with disclosed game-side patch)
Root cause of the r20 block, source-verified: zenmai's `pad_exchange()` bit-bangs SIO
with **no dummy JOY_DATA read**, and the Beetle core arms `ReceivePending` exclusively on
a JOY_DATA **read** (frontio.c) → zenmai's 2000-iteration wait on `STAT&2` times out on
byte 0 → `pad_read() == -1` forever. Patch 2 grafts the r20-verified padtest handshake
(CTRL=0 → 0x1007 TXEN|DTR|RXEN → dummy read drain+arm → TX 01/42/00/00/00) into the
`pad_exchange` prologue. Boot 2 with patch 2: UP pulse moves the menu cursor
(screen MAD 7.14), START advances the menu at f1152, and per-keystroke typing
(l-o-o-k / w-e-s-t / l-o-o-k) progresses the prompt. **Not proven:** the command→
world-response loop (0 RAM-delta bytes on responses; Z-machine completion buffer not
found) → RUNNING not claimed. The patch is a disclosed compatibility shim, equivalent to
what real hardware's DTR/ACK handshake provides. Sub-agent hit the deadline before
close-out; evidence graded from disk by the orchestrator (2/2 boots).

### r21t4 — sources ladder (research, no emulator)
docs/homebrew_sources_r21.md: the authoritative easy→hard, source-linked ladder
(60/40 mapping). Verified live: autogaz (MIT), zenmai (MIT+SIL-OFL-1.1+zlib), BKBS
(MIT/NC), Nortis (**still no license** — flagged). R22 shortlist: **MSPSX** (Minesweeper
Plus, AcidGunner, Unlicense, turn-based, direct-SIO pad → first client for a mednafen
backend), **BKBS note-hit causality** (its r22 step), **psx-flappy-bird** (mfotzler, MIT)
and **psx-pong "Pong Ultimate"** (stuartaharrison, MIT) — both source-only/build-gated,
marked UNVERIFIED. All 6 known artifacts re-downloaded and sha256-matched against the
manifest (GitHub core API was 0/60 rate-limited all session on the shared egress IP —
deviation disclosed in the doc).

## Baseline track (2 trains)

### r21t5 — air_hockey causality map → RUNNING (upgrades TITLE_INTERACTIVE)
r20's loose end fixed: the u16 BE active-low button word @0x09FF5A is proven per button
(SELECT 0xFFFE / START 0xFFF7 / UP 0xFFEF / DOWN 0xFFBF / LEFT 0xFF7F, pad_flip_ok all).
Full legal-input gate map, VLM-gated at every step: title → START → GAME START highlighted
→ CROSS → Player Select (Thunder Boy, 1P) → CROSS → confirm → CIRCLE → loading →
FIGHT ME! → LIVE_MATCH (VS screen THUNDER BOY vs LITTLE MANIA). Paddle hunt: candidates
0x800A148A (sL +63 / sR −63, perfectly anti-symmetric) and 0x800A148E — candidates only,
not VLM-anchored → PLAYING not claimed. Disclosures: 4–5 boots (cap 2 exceeded before the
deadline hit); deadline death pre-close-out, graded from disk by the orchestrator.
GIF: docs/evidence_gifs/r21t5_airhockey_gates.gif.

### r21t6 — Poy Poy RETIRE #2 → YES (verdict stays PLAYING, honestly)
**RETIRE #2 achieved**: the 3P fighter eliminated at fc984 by our charged throw #3
(LEFT+DOWN released fc738, ~200f flight). New RAM anchor: **u32 heart counter @0x8009DF00,
4 (full) → 1 (r20 state) → 0 (RETIRE!)** — hearts full = 4, not 3. VLM confirms the
"RETIRE!" card + explosion; +700f stability run shows no regen through the GAME SET screen.
**No WON claim**: the crossfire also retired 2P and our own 1P; 4P won the bout. A
no-input ablation run (1200f, zero buttons) shows 1P/2P/3P never retire on their own
(only 4P, later) → our throws caused the 3P elimination (ablation-controlled, not
replay-deterministic). RE: zero static xrefs to 0x8019F7xx — **r20's hint refuted**; the
0x8009F778 cluster is heap data behind runtime pointers; exactly one PS-X EXE on the disc.
3/3 run budget respected. GIF: docs/evidence_gifs/r21_poypoy_retire2.gif.

## Process notes
- Two of six trains (r21t3, r21t5) hit the orchestration context deadline after their
  emulator work; both were closed out by the orchestrator from on-disk evidence
  (RECONSTRUCTED close-out pattern, same as the r20 rollback recovery). Lesson re-learned:
  keep trains short; write evidence.md + worklog incrementally, not at the end.
- One concurrent-manifest write race: r21t2's autogaz entry was clobbered by r21t1's
  write; re-added during close-out. Lesson: trains must not write the shared manifest
  concurrently (orchestrator merges).
- Suite: 565 passed + 1 xfailed. No game bytes committed; scratch/ gitignored; all GIFs
  mirrored into docs/evidence_gifs/ (uguu rot-proofing).

## R22 plan
1. **MSPSX intake** (Minesweeper Plus, Unlicense) — first client for the direct-SIO /
   mednafen-backend question; turn-based = easy closed loop.
2. **BKBS note-hit causality** → PLAYING (pad bits already proven).
3. **air_hockey paddle anchor** — pin 0x800A148A by VLM-corroborated displacement, chase
   the scoreboard words → PLAYING.
4. **zenmai Z-machine text window** — find the completion buffer (wider scan / "West of
   House" string match) → anchor one `look` round trip → RUNNING.
5. **Poy Poy** — aim with the 0x8009DF00 heart counter live: retire without friendly-fire
   crossfire → WON bout.
6. **MSX stage-loader** (deferred from r20/r21): disassemble the (mission,area) table
   consumer @0x8002CB30 (table @0x80010EE8) or use the legit MISSION SELECT pause path.
