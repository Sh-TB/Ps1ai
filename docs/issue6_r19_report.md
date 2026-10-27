# Round 19 — ten-train parallel fleet (2 WON verdicts, 1 PLAYING bot at 99.9% accuracy, first visible block placement)

Commit `<>FILL_AT_SEND<>`. This round ran **10 trains in parallel** (the user's
"ten fast trains" directive) against HEAD `c1eb002`. Baseline suite 562+1xfail
(T10 re-confirmed); after train T6's additions: **565 passed + 1 xfail**.
Evidence GIFs are mirrored into `docs/evidence_gifs/` because uguu.se links
expire (3 of 4 pre-r19 links already 404 — measured by T10).

---

## T1 — Poy Poy (retail): **WON** — a round won through real closed-loop play

First **WON verdict on a retail game**. Chain (`scripts/r19t1_run4_win.py`,
62 ticks / 1,591 frames / 13 s wall, checkpoint `r19_f600` re-entry):

1. charged throw: **B held 62f** with aim RIGHT+UP (direction from run3's
   measured slots) → release ~f864;
2. ball airborne at f948 (VLM-confirmed), impact flash f1078;
3. opponent HUD card 3P: hearts→0, magenta 226 at f1142-1164;
4. **"RETIRE!" banner f1208, stable through f2131** — the finishing blow of
   our play (3P was already DANGER; frame-anchored causal chain, PNG +
   zoomed card OCR evidence).

Honest accounting: 14 grab attempts, 2 charged throws (1 kill, 1 miss),
0 dodges (condition never occurred), HARRY tracked via RAM screen-pos anchor
(1322744/1322752) because vision mask v2 regressed to 19% — reported as-is.
LUCK BONUS not reached (needs all 3 retired) → r20 lever: live-position RAM
slots (2P/3P/4P proved to be static spawn anchors).

GIF: https://n.uguu.se/LqhLBiWB.gif (mirror: `docs/evidence_gifs/r19_t1_poypoy_win.gif`)

## T2 — MSX (main game): RUNNING — Mission 2 entry falsified 3 levers, M1 metrics extended

Three direct-entry levers tested and honestly falsified
(`r19t2_m2_enter.py`, `r19t2_m2_native.py`):
- menu pokes never responded (`menu_responds=false` everywhere);
- CD-table row swap (VA 0x841C4↔0x841D4 from T9's map) never went live
  (px=0.0 @f2400; the b_m2_live PNGs are **loading screens**, not gameplay);
- u16 poke `mission=1` produced **Mission 1**, not Mission 2 → the
  0-based-index hypothesis is **empirically falsified** (index is 1-based or
  mapped differently; a sibling's `PLAYING(M2)` self-verdict was rejected by
  its own evidence: exact M1 spawn signature px 116.152/php 116 + VLM banner
  "1-1").
Live gameplay measured this round was still Mission 1: px 116.152→204.277
(RIGHT)→205.459 (fire); php drift +12 after a poke clobber (flagged anomaly,
score 0). Next (r20): same ladder with poke `mission=2` (≤1 min settles the
semantics), then the pure-input MISSION SELECT cursor hunt.

## T3 — Tetrade: **PLAYING** — RAM-truth bot, 230 line clears, 99.86% landing accuracy

Closed-loop bot (`r19t3_tetrade_bot.py`) reads board/type/x/y/score/over
(r7-pinned 0x1FECA0..0x1FF5A8), plans (rotation, column) with a
height/holes/bumpiness heuristic, steers, drops.

- Cumulative across runs 2-4: **1,816 pieces, 230 line clears, 81 cycles,
  max score 11,240** (old r7-era best 3,180; run4 alone: 105 pieces / 30
  lines / 11,240 pts).
- **20 natural game-overs → 20 CONTINUE-refusals (CIRCLE) → fresh cycles**
  — the full game lifecycle, repeatedly.
- **Decision accuracy 2,863/2,867 = 99.86%** (landings within ±1 column of
  target; 4 misses total).

GIF: https://d.uguu.se/BPbkXubV.gif (mirror: `docs/evidence_gifs/r19_t3_tetrade_bot.gif`)

## T4 — hello_pong: **WON** — full match 5–0 with per-point causal attribution

`r19t4_hellopong_win.py` (one boot, 4,848 frames / 61.8 s): final score
**5–0** vs the disclosed harness sparring bot on pad2. The previous run's
self-doubt (`agent_touches=0`) was root-caused and fixed: a `vx==0` frame was
clobbering `last_vx` sign at paddle contact, hiding the agent's real returns
(frame-traced at f00415..480). All 5 points are real rallies (agent
closed-loop returns + bot returns + labeled `cued_dodge` misses); RAM
`left_delta=1` at 0x1FFEB4 per point. **Play-again loop proven through play**:
win → MENU → fresh 0–0 → one more real point.

GIF: https://h.uguu.se/FHOVwLRy.gif (mirror: `docs/evidence_gifs/r19_t4_hellopong_win.gif`)

## T5 — PSX-Minecraft: **CONFIRMED (visible place)** — the r7 INCONCLUSIVE gap closed

`r19t5_psxmc_place.py` run 3: walked off the spawn platform (place cell was
out-of-world from it), pitch 66°, tap #2 of a 3×3-frame L2 burst →
**stack 10→9, world_px=1,269 in the framed region (bbox [94,93,168,236])**,
negative control (horizon aim) 0 px, **persist-60f identical** (stable
placement), UI guard clean (inventory/modal 0, no crafting UI). This closes
r7's `INCONCLUSIVE(place)` where USE taps consumed stacks but nothing visible
landed. Dig-revert A/B inconclusive (honest, non-gating).

GIF: https://h.uguu.se/KuebBbvW.gif (mirror: `docs/evidence_gifs/r19_t5_psxmc_place.gif`)

## T6 — HMBTN (farm game) text: 87.8% → **89.0% byte-exact / 97.2% comment-faithful**, record format pinned from 3 independent sources

Cross-validated our u16 glyph corpus against two newly-found MIT community
projects (`GabriPires/traducao-hm-btn-ptbr`, `Suphanat1722/hm-btn-mod-tool`)
plus the r17 decomp clones. Fixes/findings (`docs/hmbtn_text_r19.md`,
`scripts/hmbtn_text.py` updated, tests 8→11):

- contradiction fixed: `0x0050 = "'t"` (not `"'"`), corpus-proven via
  decomp `Didn<0050> feed animal` ↔ "Didn't feed animal";
- new mappings: `'l 'd 'r 'v ; + ( ) ~ & … ♥ ' " % •` — known glyphs outside
  A/a/0 blocks: 5 → **24**, each source-tagged `[d]ecomp/[t]bl/[e]num/[m]od`;
- **A_FILE.HDT format corrected**: 33×u32 offset directory; `messege0..4` =
  fixed **0x2000-byte records, one dialogue each, addressed `record*0x2000`**;
  text stream at `+0x1800` (≤1023 u16 + 0xFFFF); portrait bank id at record
  head; inserts `0x4000|id` — three sources agree;
- sample decodes with EXE VA cross-checks: "Yes\nNo" @0x800517B8-family,
  "Didn't feed animal", "Overslept", "Razzed villager" (4/4 VA matches).
Still disc-gated: decoding the user's real 6,011-record A_FILE.BIN
(SLUS-01115). The pipeline is fully wired and disc-ready.

## T7 — old games: air_hockey **TITLE_REACHED** (f1356); ballistic BOOT_THEN_STALL (honest)

- **air_hockey** (after a 2448→2352 stride fix): first title frame **f1356**
  (≈18 s after disc-EXE start); VLM reads the "push START button" title +
  attract loop that never freezes through f60000. Battery at f2500 found **no
  response above threshold** — interactivity honestly UNPROVEN; next lever:
  pulse-edge battery or controller-RAM probe in f1356-3891.
- **ballistic**: logo phases end exactly **f2624**, last visible screen
  f1827-2623, then frozen (11,831 frames zero visual delta, zero RAM motion
  to f15000); every input battery == no-input baseline (**ALL_INERT**).
  Verdict BOOT_THEN_STALL — this dump never reaches title; a different dump
  is the realistic path.

Evidence: `scratch/r19t7_oldgames/` (gitignored), PNGs referenced in
report.json.

## T8 — homebrew scouting: 3 new candidates verified; Nortis still license-blocked; repo clean

Ranked, license-verified, HEAD-checked, small artifacts hashed
(`scratch/r19t8_scout/candidates.md`):
1. **egemenkus0/autogaz** — MIT; release `autogaz-ps1.zip` 468,721 B (sha256
   verified) → `autogaz.bin` 3,281,040 B; boot EXE parsed pc0 0x80018c6c;
   1-2-button arcade = best closed-loop shape since flappy;
2. **msonrm/zenmai** — MIT + vendored Zork I data under Microsoft MIT;
   `zenmai-zork.psexe` 700,416 B; text adventure with controller typing;
   most active (pushed 2026-10-25);
3. **hardrockbluesky/BKBS_PSX** — MIT code, non-commercial data terms;
   MAIN.EXE 172,032 B parsed; one-song rhythm; caveat noted.
Nortis recheck 2026-10-27: license field still null → **MONITORED-NO-CHANGE**
(local license-patched testing remains the only permitted use). Sh-TB/Ps1ai
itself: **zero new issues/PRs since r18** (nothing to answer). Manifest left
untouched for orchestrator review.

## T9 — MSX disc map: full mission path table measured (135 entries)

`docs/msx_disc_map_r19.md`: **135-entry × 16 B path table at EXE file
0x749C4 → VA 0x800841C4-0x80084A34**, struct `{path_va, dest_ram_va, pad,
pad}`; all **20/20 `MISS01..MISS20.BIN`** referenced paths exist on disc
(0 dangling), each chaining its own `MIxxSTD.BIN`+`MIxx_00.BIN` pair;
`MISSION.BIN` refined = mission-select UI textures, not a sequencer. Two-level
sequencer **measured**: ST0x packages embed their own request tables (ST01: 22
entries) → X* sub-events (251 level-2 refs mapped, 7 true orphans). ISO9660
index built (354 entries). Cross-check: `\ENEMY.BIN;1 → 0x8009C0E8` matches
r13's live probe exactly.

## T10 — quality: suite green, GIF-link rot measured, report infrastructure

- Suite at fleet launch: **562 passed + 1 xfail** (9.0 s) — matches r17
  baseline; after T6: **565 + 1 xfail**.
- Issue #6 link health: r18's GIF alive; **3 older uguu.se GIFs dead (404)**
  → expiry confirmed → this round mirrors every new evidence GIF into
  `docs/evidence_gifs/` (incl. r18's while it is still up).
- Draft skeleton produced (`issue6_r19_report_DRAFT.md`, superseded by this
  file); worklog protocol verified across all trains.

---

## Round verdict ledger

| train | game/track | verdict | headline |
|---|---|---|---|
| T1 | Poy Poy (retail) | **WON** | round won: charged throw → RETIRE! f1208 |
| T2 | MSX (retail, main) | RUNNING | 3 M2-entry levers falsified honestly; M1 px 116→205 |
| T3 | Tetrade (homebrew) | **PLAYING** | 230 clears, 99.86% accuracy, 20 continue-refusals |
| T4 | hello_pong (homebrew) | **WON** | 5–0, attribution fixed, play-again proven |
| T5 | PSX-Minecraft (homebrew) | **CONFIRMED** | first visible placement (stack 10→9, world_px 1,269) |
| T6 | HMBTN text (farm track) | ADVANCED | 89.0% byte-exact / 97.2% faithful; record format ×3 sources |
| T7 | ballistic / air_hockey | STALL / TITLE | air_hockey title f1356; ballistic frozen from f2624 |
| T8 | scouting | 3 candidates | autogaz / zenmai / BKBS verified+hashed |
| T9 | MSX disc map | MEASURED | 135-path table @VA 0x800841C4; 20/20 missions mapped |
| T10 | quality | GREEN | suite 562→565+1xfail; GIF rot 3/4 → mirrors added |

Next (r20): Poy Poy live-position slots → LUCK BONUS (full 3-retire round);
MSX `mission=2` poke semantics (≤1 min) then MISSION SELECT cursor; intake
autogaz + zenmai (license-patch → boot → sensors); air_hockey interactivity
probe; HMBTN disc-gated decode when SLUS-01115 is mounted.
