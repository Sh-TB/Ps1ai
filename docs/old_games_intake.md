# Old-games local-disc intake — `scripts/disc_intake.py` (Issue #6/#9 helper-tool push)

One-shot metadata intake for any local `.cue`/`.bin` disc: track geometry,
license-block + region marker, PSX-flavored PVD parse, full directory walk,
SYSTEM.CNF boot line, PS-EXE inventory (pc0 / t_addr / t_size / exe stamp),
string census (ASCII + Shift-JIS run counts), and a boot-route recommendation
from the `docs/tiny_games_playbook.md` decision tree.

The tool reads local discs only — disc contents never enter the repository.
Committed artifacts are facts: serials, sizes, counts, verdicts.

## Measured findings (10 local retail discs, 2026-10-27)

| game | serial | region | exe path | t_size | pc0 | license | files | ascii runs | sjis runs | boot route |
|---|---|---|---|---|---|---|---|---|---|---|
| FFT6 - World of Ruin | SCUS-94221 | US | SCUS_942.21 | 354,304 | 0x80010A30 | YES | 2487 | 274 | 17 | route 1 |
| Poy Poy (USA) | SLUS-00486 | US | SLUS_004.86 | 581,632 | 0x8005832C | YES | 341 | 795 | 14 | route 1 |
| Trap Gunner (USA) | SLUS-00679 | US | SLUS_006.79 | 1,021,952 | 0x8009E1BC | YES | 87 | 1016 | 59 | route 1 |
| Air Hockey (USA) | SLUS-01467 | US | MAIN.EXE | 688,128 | 0x8006BBC0 | YES | 45 | 187 | 52 | route 1 |
| Ballistic [U] [SLUS-00966] | SLUS-00966 | US | SLUS_009.66 | 1,357,824 | 0x80059F60 | YES | 198 | 878 | 29 | route 1 |
| Buster Bros. Collection | (volume id) | US | CAPCOM.EXE | 186,368 | 0x800147AC | YES | 213 | 165 | 26 | route 1 |
| Crossroad Crisis | SLUS-01342 | US | SLUS_013.42 | 638,976 | 0x80010008 | YES | 138 | 820 | 122 | route 1 |
| Power Play Sports Trivia | SLUS-01445 | US | SLUS_014.45 | 280,576 | 0x80026DB8 | YES | 68 | 497 | 9 | route 1 |
| XS Junior League Football (USA) | SLUS-01554 | US | SLUS_015.54 | 28,672 | 0x00011B3C | YES | 11 | 70 | 0 | route 1 |
| Metal Slug X (USA) | SLUS-01212 | US | SLUS_012.12 | 620,544 | 0x80082A44 | YES | 354 | 971 | 50 | route 1 |

Reading of the table:

* **Every local retail disc ships its license sectors** (route 1 of the
  boot-route tree) — consistent with the earlier boot sweep that brought all
  of them to menu screens. No license-patching work is needed for this class;
  the blocker for real play is game-state understanding, not booting.
* **Serial identity comes from the EXE filename** (`SLUS_004.86` → disc id
  `SLUS-00486`); the region-marker heuristic at LBA 4 is only a fallback.
  Buster Bros. Collection names its EXE `CAPCOM.EXE`, so its serial falls
  back to the volume id.
* **Shift-JIS census is a dialogue-density proxy**: Trap Gunner (59 runs /
  1,016 ASCII) and Crossroad Crisis (122 SJIS runs) carry the most Japanese
  text among local discs; Poy Poy's menu/help text is mostly ASCII (795
  runs) — matching the r16 menu archaeology finding that its on-screen help
  is English while the disc carries SJIS strings.
* **MSX sanity anchor**: t_size 620,544 and pc0 0x80082A44 reproduce the
  canonical EXE identity recorded under `data/games/SLUS-01212/` — the
  reader pipeline agrees with the existing RE corpus.

## Dump-geometry robustness (new reusable facts)

1. **Sector stride must be measured, not trusted from the .cue.** The
   games_small dumps declare `MODE2/2352` but pack a 96-byte P-W subchannel
   after every raw sector — true stride 2448 (measured from sync-pattern
   spacing). Reading them as 2352 silently misaligns the ISO9660 plane.
2. **Cues disagree about the 150-sector pregap** (`INDEX 01 00:02:00` with
   no pregap packed in the bin, vs. `00:00:00` with data at file sector 0).
   `DiscReader.calibrate_pvd()` resolves the file offset that puts a real
   `CD001` PVD at LBA 16 instead of trusting the cue.
3. **MODE2 user data starts at raw offset 24** (sync 12 + header 4 +
   subheader 8), not 16 — the mode byte at offset 15 selects the right one.
4. **The PSX-flavored root-directory record sits at PVD offset 156**
   (r13 finding, now encoded as `find_root_record()` with an ECMA-168
   fallback).

## Unit tests

`tests/test_disc_intake.py` runs against a **self-generated** test disc
(`iso9660_min.build_image`) carrying a synthetic PS-X EXE we authored byte by
byte — no game bytes in CI. Covered: header offsets (pc0/gp/t_addr/t_size at
0x10/0x14/0x18/0x1C), SJIS run detection, stride detection, end-to-end
intake (serial `SLUS-999.99` → `SLUS-99999`, boot line, census counts),
CLI JSON/MD outputs, and the 156/168 root-record tolerance.
