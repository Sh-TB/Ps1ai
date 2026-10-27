# MSX disc map (round 18) — measured from our own retail disc

Tool: `external_audit/hmbtn/hmbtn-decomp/tools/psx_disc.py extract` (the same
tool that passed the round-17 cross-check) on
`emu/msx_usa/Metal Slug X (USA).bin` → **355 files** (same count as round 17).

Output tree (local-only, no game bytes committed):
`ANG/ ART/ LD/ PL/ ST01..ST06/ ST05 sub-dirs/ STD/` + top-level
`MISSION.BIN BONUS.BIN ENDING.BIN ENEMY.BIN LOADING.BIN MCARD.BIN TITLE.BIN
X09.BIN X801.BIN SLUS_012.12 SYSTEM.CNF license_data.dat`.

## Stage inventory (bytes, files)

| dir | files | total bytes | notes |
|-----|-------|-------------|-------|
| ST01 | 25 | 2,671,568 | SEQ01.BIN 69,884 (VAB-prefixed audio seq), ST01.BIN 275,284, VAB01.BIN, X1_00..X1_043.BIN |
| ST02 | 8 | 1,116,688 | |
| ST03 | 7 | 1,377,488 | |
| ST04 | 5 | 763,990 | |
| ST05 | 6 | 710,940 | sub-stages `_1 _2 _3` (SEQ051/052/053) |
| ST06 | 6 | 705,790 | |
| STD  | 26 | 7,101,912 | shared/common bank |
| LD   | 8+ | — | `WAIT_M/C/T1..T9.BIN` load overlays |

## EXE strings (SLUS_012.12, 622,592 B = 2048 hdr + 620,544 code — matches
## our disc_intake anchor pc0 0x80082A44)

- `RETRY`, `MISSION SELECT`, `CONTINUE`, `MISSION 6` … `MISSION 1` at
  0x860–0x8c8 — the main menu has DIRECT mission select (no need to sequence
  through missions); plus a pointer table right after (0x8001a5xx range).
- Full CD path table at ~0xc80–0xe00: `\ST06\VAB06.BIN;1`,
  `\ST05\_3\SEQ053.BIN;1`, `\ST05\_2\SEQ052.BIN;1`, `\ST05\_1\SEQ051.BIN;1`,
  `\ST04\...`, `\ST03\...` etc. — per-stage audio/map banks.
- `\LD\WAIT_M.BIN;1`, `\LD\WAIT_C.BIN;1`, `\LD\WAIT_T9..T1.BIN;1` at
  0x9a0+ — load-overlay paths.

## MISSION.BIN (21,252 B)

Not a PS-X EXE; starts `08 00 00 00 4C 00 00 00 C0 03 A8 01 …` — a data table
(mission metadata / file lists). Decoding it is a follow-up, not needed for
the menu route.

## Actionable for round 19

`MISSION SELECT` + `MISSION 1..6` strings mean the r17 menu ladder
(START → main menu) should offer direct `MISSION 2` entry — the round-19
lever: navigate main menu → MISSION SELECT → MISSION 2, then measure the
Mission-2 train scene (px ~747 front line from the issue #5 work).
