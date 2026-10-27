# MSX disc map (round 19) — mission sequencer & CD path table

Task r19-t9. Pure static analysis of our own retail disc
`emu/game/Metal Slug X (USA).bin` (104,315,904 B) + the r18 extraction
`emu/msx_extract_r18/` (355 files, 90,064,086 B). No emulator runs.
Tooling proven in r17: `psx_disc.py extract`, `PsxExeHeader.parse`
(anchor re-verified: pc0 `0x80082A44`, t_addr `0x80010000`, t_size `0x97800`).

**VA mapping rule (MEASURED):** `VA = 0x80010000 + (file_offset − 0x800)`
(holds for every cross-check below; EXE = 2,048-byte header + 620,544-byte text).

**Disc geometry (MEASURED):** raw 2,352-byte MODE2 sectors, user data at +24,
PVD at LBA 16. Full ISO9660 index (354 entries, LBA + byte offset per file):
`scratch/r19t9_msxdisc/iso9660_index.json`.

---

## 1. File inventory (MEASURED)

Per top-level directory of the extraction (full per-file CSV:
`scratch/r19t9_msxdisc/inventory.csv`):

| dir | files | bytes | what it is (MEASURED, from headers/strings) |
|-----|-------|-------|---------------------------------------------|
| (root) | 13 | 35,819,759 | SLUS_012.12 (622,592), MISSION.BIN, BONUS.BIN ('pQES' music seq), ENDING.BIN (result screen), ENEMY.BIN, LOADING.BIN, MCARD.BIN, RANKING.BIN, TITLE.BIN (menu labels), X09.BIN (4.98MB **MPEG-1 L3 audio**), X801.BIN (29.9MB **MPEG-1 L3 audio**), SYSTEM.CNF, license |
| ANG | 89 | 13,194,150 | "another mission"/movie engine: `M1..M4/MISS01..MISS20.BIN` scripts + `MIxxSTD.BIN`/`MIxx_00.BIN` asset pairs (20 pairs), MISSMN.BIN (demo player: `M%02d-%s`, `PERFECT!`, `GREAT!`, demo names), MIMN.BIN, CSCHOOL.BIN, CSC/CSC00/CSC01, SND/ (SEQ_M1..M63 + VAB_M1..M7) |
| ART | 6 | 11,809,960 | art gallery (ARTGAL.BIN 7.47MB, ARTVAB.BIN 3.99MB; ART.BAK = literal backup) |
| LD | 17 | 432,712 | `WAIT_S1..S6` (stage load screens), `WAIT_T1..T9`, `WAIT_C` (combat school), `WAIT_M` (mission select) |
| PL | 8 | 270,264 | player sprite banks PAT1A..PAT4B |
| ST01 | 25 | 2,671,568 | Mission 1: ST01.BIN 275,284 + X1* sub-events + SEQ01/VAB01 |
| ST02 | 29 | 3,708,321 | Mission 2: ST02.BIN + `_2/` `_3/` sub-stages (X21/X22/X23) |
| ST03 | 42 | 3,693,556 | Mission 3: ST03.BIN + `_0/` `_1/` (X3*) |
| ST04 | 40 | 3,000,458 | Mission 4: ST04.BIN + `_0/` `_1/` (X4*) |
| ST05 | 29 | 3,857,290 | Mission 5: ST05.BIN + `_1/ _2/ _3/` (X51/X52/X53) |
| ST06 | 31 | 4,504,136 | Mission 6: ST06.BIN + `_1/ _2/ _3/` (X61/X62/X63) |
| STD | 26 | 7,101,912 | shared bank: STD00..STD04/FAT/MUM/CAM, ED00..ED04, TI00/TI01, GO00, _VHIECLE |

**Mission files found:** `MISS01..MISS20.BIN` — 20 referenced, **20 present on disc**
(0 dangling refs). Plus top-level `MISSION.BIN` (21,252 B) which is **not** a
sequencer: same VRAM-coordinate texture-bank header as MI01STD/MIMN/STD00
(`08 00 00 00 | size | vram_x | vram_y | …` then 4bpp pixel data) — it is the
MISSION SELECT screen's UI textures (refines r18's "mission metadata" guess).

## 2. The CD path table in the EXE (MEASURED)

* **136** CD-path strings (`\…;1`) live at file `0x97F–0x14A9`
  (VA `0x8001017F–0x80010CA9`).
* A **single 16-byte pointer table** references 135 of them:
  **file `0x749C4–0x75234`, VA `0x800841C4–0x80084A34`**,
  135 entries × 16 B = 2,160 B, struct `{u32 path_va, u32 dest_ram_va, u32 pad, u32 pad}`.
  (The 136th string `\M0\S00F.XA;1` is an XA audio stream with no slot — played
  by CD hardware, not file-read. INFERRED.)
* Binary snippet: `/home/z/my-project/emu/msx_r19_t9/exe_cd_file_table_0x749C4_0x75234.bin`.
* Full machine dump: `scratch/r19t9_msxdisc/cd_table_dump.json`.

Cross-check (MEASURED): row 16 gives `\ENEMY.BIN;1 → 0x8009C0E8`, exactly the
address where r13's live probe saw ENEMY.BIN loaded verbatim.

Code consumers (MEASURED): 18 sites do `lui 0x8008` + `addiu` into
`0x41C4..0x4A34` — table-base hits at `0x8001E060`, `0x80026720`, `0x800285A0`,
`0x80028D5C`, `0x80028E08`, `0x80044B08`, `0x80045BBC`, `0x80045E4C`,
`0x800460D0`, `0x80046338` (+ tail/entry hits `0x800147D4`, `0x80012EF4`).
Menu array `0x80083518..0x8008355C` referenced at `0x80013504`.

### Table dump (index | EXE file off | CD path | dest RAM VA | disc LBA | bytes)

| # | file off | path | dest VA | LBA | bytes |
|---|----------|------|---------|-----|-------|
| 0 | 0x 749C4 | `\ST01\ST01.BIN;1` | 0x800FA6B0 | 19067 | 275,284 |
| 1 | 0x 749D4 | `\ST02\ST02.BIN;1` | 0x800FA6B0 | 25618 | 91,368 |
| 2 | 0x 749E4 | `\ST02\ST02A.BIN;1` | 0x8009C0E8 | 25663 | 15,624 |
| 3 | 0x 749F4 | `\ST02\_2\ST02B.BIN;1` | 0x8009C0E8 | 26124 | 52,613 |
| 4 | 0x 74A04 | `\ST02\_3\ST02C.BIN;1` | 0x8009C0E8 | 26514 | 83,812 |
| 5 | 0x 74A14 | `\ST03\ST03.BIN;1` | 0x800FA6B0 | 23812 | 244,076 |
| 6 | 0x 74A24 | `\ST03\ST03A.BIN;1` | 0x8013C000 | 23932 | 32,476 |
| 7 | 0x 74A34 | `\ST04\ST04.BIN;1` | 0x800FA6B0 | 22302 | 162,762 |
| 8 | 0x 74A44 | `\ST05\ST05.BIN;1` | 0x800FA6B0 | 20391 | 125,184 |
| 9 | 0x 74A54 | `\ST05\_1\ST05A.BIN;1` | 0x8011A000 | 20703 | 99,460 |
| 10 | 0x 74A64 | `\ST05\_2\ST05B.BIN;1` | 0x8011A000 | 21083 | 114,196 |
| 11 | 0x 74A74 | `\ST05\_3\ST05C.BIN;1` | 0x8011A000 | 21429 | 124,358 |
| 12 | 0x 74A84 | `\ST06\ST06.BIN;1` | 0x800FA6B0 | 27455 | 74,434 |
| 13 | 0x 74A94 | `\ST06\_1\ST06A.BIN;1` | 0x80110000 | 27747 | 122,668 |
| 14 | 0x 74AA4 | `\ST06\_2\ST06B.BIN;1` | 0x80110000 | 28563 | 135,045 |
| 15 | 0x 74AB4 | `\ST06\_3\ST06C.BIN;1` | 0x8010E000 | 28971 | 364,332 |
| 16 | 0x 74AC4 | `\ENEMY.BIN;1` | 0x8009C0E8 | 2758 | 115,400 |
| 17 | 0x 74AD4 | `\PL\PAT1A.BIN;1` | 0x800B83B0 | 15412 | 32,632 |
| 18 | 0x 74AE4 | `\PL\PAT1B.BIN;1` | 0x800C0F00 | 15428 | 32,632 |
| 19 | 0x 74AF4 | `\PL\PAT2A.BIN;1` | 0x800B83B0 | 15444 | 32,892 |
| 20 | 0x 74B04 | `\PL\PAT2B.BIN;1` | 0x800C0F00 | 15461 | 32,892 |
| 21 | 0x 74B14 | `\PL\PAT3A.BIN;1` | 0x800B83B0 | 15478 | 33,944 |
| 22 | 0x 74B24 | `\PL\PAT3B.BIN;1` | 0x800C0F00 | 15495 | 33,944 |
| 23 | 0x 74B34 | `\PL\PAT4A.BIN;1` | 0x800B83B0 | 15512 | 35,664 |
| 24 | 0x 74B44 | `\PL\PAT4B.BIN;1` | 0x800C0F00 | 15530 | 35,664 |
| 25 | 0x 74B54 | `\BONUS.BIN;1` | 0x801E0000 | 2866 | 59,980 |
| 26 | 0x 74B64 | `\STD\STD00.BIN;1` | 0x80180000 | 17846 | 80,712 |
| 27 | 0x 74B74 | `\STD\STD01.BIN;1` | 0x80192000 | 17886 | 210,676 |
| 28 | 0x 74B84 | `\STD\FAT01.BIN;1` | 0x80162C00 | 17529 | 96,680 |
| 29 | 0x 74B94 | `\STD\MUM01.BIN;1` | 0x80177700 | 17746 | 49,560 |
| 30 | 0x 74BA4 | `\STD\CAM01.BIN;1` | 0x80189000 | 15549 | 18,284 |
| 31 | 0x 74BB4 | `\STD\STD02.BIN;1` | 0x80192000 | 17989 | 218,036 |
| 32 | 0x 74BC4 | `\STD\FAT02.BIN;1` | 0x80162C00 | 17577 | 96,680 |
| 33 | 0x 74BD4 | `\STD\MUM02.BIN;1` | 0x80177700 | 17771 | 49,560 |
| 34 | 0x 74BE4 | `\STD\CAM02.BIN;1` | 0x80189000 | 15558 | 18,284 |
| 35 | 0x 74BF4 | `\STD\STD03.BIN;1` | 0x80192000 | 18096 | 203,300 |
| 36 | 0x 74C04 | `\STD\FAT03.BIN;1` | 0x80162C00 | 17625 | 96,680 |
| 37 | 0x 74C14 | `\STD\MUM03.BIN;1` | 0x80177700 | 17796 | 49,560 |
| 38 | 0x 74C24 | `\STD\CAM03.BIN;1` | 0x80189000 | 15567 | 18,284 |
| 39 | 0x 74C34 | `\STD\STD04.BIN;1` | 0x80192000 | 18196 | 221,940 |
| 40 | 0x 74C44 | `\STD\FAT04.BIN;1` | 0x80162C00 | 17673 | 96,680 |
| 41 | 0x 74C54 | `\STD\MUM04.BIN;1` | 0x80177700 | 17821 | 49,560 |
| 42 | 0x 74C64 | `\STD\CAM04.BIN;1` | 0x80189000 | 15576 | 18,284 |
| 43 | 0x 74C74 | `\ANG\M1\MISS01.BIN;1` | 0x80102000 | 10576 | 41,532 |
| 44 | 0x 74C84 | `\ANG\M1\MISS02.BIN;1` | 0x80102000 | 10597 | 14,272 |
| 45 | 0x 74C94 | `\ANG\M1\MISS03.BIN;1` | 0x80102000 | 10604 | 43,172 |
| 46 | 0x 74CA4 | `\ANG\M1\MISS04.BIN;1` | 0x80102000 | 10626 | 43,336 |
| 47 | 0x 74CB4 | `\ANG\M1\MISS05.BIN;1` | 0x80102000 | 10648 | 13,788 |
| 48 | 0x 74CC4 | `\ANG\M2\MISS06.BIN;1` | 0x80102000 | 11201 | 19,136 |
| 49 | 0x 74CD4 | `\ANG\M2\MISS07.BIN;1` | 0x80102000 | 11211 | 40,392 |
| 50 | 0x 74CE4 | `\ANG\M2\MISS08.BIN;1` | 0x80102000 | 11231 | 43,340 |
| 51 | 0x 74CF4 | `\ANG\M2\MISS09.BIN;1` | 0x80102000 | 11253 | 19,768 |
| 52 | 0x 74D04 | `\ANG\M2\MISS10.BIN;1` | 0x80102000 | 11263 | 29,212 |
| 53 | 0x 74D14 | `\ANG\M3\MISS11.BIN;1` | 0x80102000 | 12063 | 26,816 |
| 54 | 0x 74D24 | `\ANG\M3\MISS12.BIN;1` | 0x80102000 | 12077 | 68,400 |
| 55 | 0x 74D34 | `\ANG\M3\MISS13.BIN;1` | 0x80102000 | 12111 | 34,708 |
| 56 | 0x 74D44 | `\ANG\M3\MISS14.BIN;1` | 0x80102000 | 12128 | 23,696 |
| 57 | 0x 74D54 | `\ANG\M3\MISS15.BIN;1` | 0x80102000 | 12140 | 52,272 |
| 58 | 0x 74D64 | `\ANG\M4\MISS16.BIN;1` | 0x80102000 | 13010 | 39,904 |
| 59 | 0x 74D74 | `\ANG\M4\MISS17.BIN;1` | 0x80102000 | 13030 | 22,140 |
| 60 | 0x 74D84 | `\ANG\M4\MISS18.BIN;1` | 0x80102000 | 13041 | 44,616 |
| 61 | 0x 74D94 | `\ANG\M4\MISS19.BIN;1` | 0x80102000 | 13063 | 37,612 |
| 62 | 0x 74DA4 | `\ANG\M4\MISS20.BIN;1` | 0x80102000 | 13082 | 41,772 |
| 63 | 0x 74DB4 | `\ANG\MISSMN.BIN;1` | 0x800FA6B0 | 9739 | 11,600 |
| 64 | 0x 74DC4 | `\ANG\CSCHOOL.BIN;1` | 0x800FA6B0 | 9536 | 177,670 |
| 65 | 0x 74DD4 | `\MISSION.BIN;1` | 0x800FA6B0 | 2815 | 21,252 |
| 66 | 0x 74DE4 | `\ART\ARTG.BIN;1` | 0x800FA6B0 | 2944 | 30,704 |
| 67 | 0x 74DF4 | `\TITLE.BIN;1` | 0x800FA6B0 | 2853 | 26,328 |
| 68 | 0x 74E04 | `\STD\TI00.BIN;1` | 0x80130000 | 18305 | 558,812 |
| 69 | 0x 74E14 | `\STD\TI01.BIN;1` | 0x80141DEC | 18578 | 513,776 |
| 70 | 0x 74E24 | `\RANKING.BIN;1` | 0x801D0000 | 2826 | 53,872 |
| 71 | 0x 74E34 | `\LOADING.BIN;1` | 0x801F0000 | 2910 | 4,084 |
| 72 | 0x 74E44 | `\STD\GO00.BIN;1` | 0x801E0000 | 17721 | 49,696 |
| 73 | 0x 74E54 | `\ENDING.BIN;1` | 0x8009C0E8 | 2896 | 28,582 |
| 74 | 0x 74E64 | `\STD\ED00.BIN;1` | 0x80100000 | 15585 | 704,336 |
| 75 | 0x 74E74 | `\STD\ED01.BIN;1` | 0x8011B2C8 | 15929 | 817,632 |
| 76 | 0x 74E84 | `\STD\ED02.BIN;1` | 0x8011B2C8 | 16329 | 817,632 |
| 77 | 0x 74E94 | `\STD\ED03.BIN;1` | 0x8011B2C8 | 16729 | 817,632 |
| 78 | 0x 74EA4 | `\STD\ED04.BIN;1` | 0x8011B2C8 | 17129 | 817,632 |
| 79 | 0x 74EB4 | `\MCARD.BIN;1` | 0x801C0000 | 2912 | 27,456 |
| 80 | 0x 74EC4 | `\ST01\SEQ01.BIN;1` | 0x80140000 | 19032 | 69,884 |
| 81 | 0x 74ED4 | `\ST01\VAB01.BIN;1` | 0x80160000 | 19202 | 513,664 |
| 82 | 0x 74EE4 | `\ST02\SEQ021.BIN;1` | 0x80118000 | 25580 | 76,976 |
| 83 | 0x 74EF4 | `\ST02\_3\SEQ023.BIN;1` | 0x80127D88 | 26505 | 18,232 |
| 84 | 0x 74F04 | `\ST02\VAB02.BIN;1` | 0x80150000 | 25671 | 519,392 |
| 85 | 0x 74F14 | `\ST03\SEQ03.BIN;1` | 0x80140000 | 23750 | 125,536 |
| 86 | 0x 74F24 | `\ST03\VAB03.BIN;1` | 0x80160000 | 23948 | 519,808 |
| 87 | 0x 74F34 | `\ST04\SEQ04.BIN;1` | 0x80120000 | 22256 | 93,660 |
| 88 | 0x 74F44 | `\ST04\VAB04.BIN;1` | 0x80140000 | 22382 | 499,376 |
| 89 | 0x 74F54 | `\ST05\_1\SEQ051.BIN;1` | 0x80140000 | 20697 | 10,656 |
| 90 | 0x 74F64 | `\ST05\_2\SEQ052.BIN;1` | 0x80140000 | 21075 | 16,076 |
| 91 | 0x 74F74 | `\ST05\_3\SEQ053.BIN;1` | 0x80140000 | 21415 | 26,880 |
| 92 | 0x 74F84 | `\ST05\VAB05.BIN;1` | 0x80160000 | 20453 | 496,448 |
| 93 | 0x 74F94 | `\ST06\SEQ06.BIN;1` | 0x80130000 | 27406 | 99,420 |
| 94 | 0x 74FA4 | `\ST06\VAB06.BIN;1` | 0x80150000 | 27492 | 519,648 |
| 95 | 0x 74FB4 | `\ANG\SND\VAB_M1.BIN;1` | 0x80140000 | 13477 | 513,664 |
| 96 | 0x 74FC4 | `\ANG\SND\SEQ_M1.BIN;1` | 0x80120000 | 13104 | 69,884 |
| 97 | 0x 74FD4 | `\ANG\SND\VAB_M2.BIN;1` | 0x80140000 | 13728 | 519,392 |
| 98 | 0x 74FE4 | `\ANG\SND\SEQ_M2.BIN;1` | 0x80120000 | 13139 | 64,904 |
| 99 | 0x 74FF4 | `\ANG\SND\SEQ_M21.BIN;1` | 0x8012FD88 | 13171 | 12,072 |
| 100 | 0x 75004 | `\ANG\SND\SEQ_M23.BIN;1` | 0x8012FD88 | 13177 | 18,232 |
| 101 | 0x 75014 | `\ANG\SND\SEQ_M2B.BIN;1` | 0x8012FD88 | 13186 | 16,328 |
| 102 | 0x 75024 | `\ANG\SND\VAB_M3.BIN;1` | 0x80140000 | 13982 | 519,808 |
| 103 | 0x 75034 | `\ANG\SND\SEQ_M3.BIN;1` | 0x80120000 | 13194 | 125,536 |
| 104 | 0x 75044 | `\ANG\SND\VAB_M4.BIN;1` | 0x80140000 | 14236 | 499,376 |
| 105 | 0x 75054 | `\ANG\SND\SEQ_M4.BIN;1` | 0x80120000 | 13256 | 93,612 |
| 106 | 0x 75064 | `\ANG\SND\VAB_M5.BIN;1` | 0x80140000 | 14480 | 496,448 |
| 107 | 0x 75074 | `\ANG\SND\SEQ_M5.BIN;1` | 0x80120000 | 13302 | 66,364 |
| 108 | 0x 75084 | `\ANG\SND\SEQ_M51.BIN;1` | 0x8013033C | 13335 | 10,656 |
| 109 | 0x 75094 | `\ANG\SND\SEQ_M52.BIN;1` | 0x8013033C | 13341 | 16,076 |
| 110 | 0x 750A4 | `\ANG\SND\SEQ_M53.BIN;1` | 0x8013033C | 13349 | 2,180 |
| 111 | 0x 750B4 | `\ANG\SND\VAB_M6.BIN;1` | 0x80140000 | 14723 | 519,648 |
| 112 | 0x 750C4 | `\ANG\SND\SEQ_M6.BIN;1` | 0x80120000 | 13351 | 69,396 |
| 113 | 0x 750D4 | `\ANG\SND\SEQ_M61.BIN;1` | 0x80130F14 | 13385 | 30,024 |
| 114 | 0x 750E4 | `\ANG\SND\SEQ_M62.BIN;1` | 0x80130F14 | 13400 | 11,280 |
| 115 | 0x 750F4 | `\ANG\SND\VAB_M7.BIN;1` | 0x80140000 | 14977 | 430,736 |
| 116 | 0x 75104 | `\ANG\SND\SEQ_M7.BIN;1` | 0x80120000 | 13419 | 118,368 |
| 117 | 0x 75114 | `\LD\WAIT_S1.BIN;1` | 0x801E8000 | 15209 | 29,448 |
| 118 | 0x 75124 | `\LD\WAIT_S2.BIN;1` | 0x801E8000 | 15224 | 29,480 |
| 119 | 0x 75134 | `\LD\WAIT_S3.BIN;1` | 0x801E8000 | 15239 | 29,448 |
| 120 | 0x 75144 | `\LD\WAIT_S4.BIN;1` | 0x801E8000 | 15254 | 29,480 |
| 121 | 0x 75154 | `\LD\WAIT_S5.BIN;1` | 0x801E8000 | 15269 | 29,448 |
| 122 | 0x 75164 | `\LD\WAIT_S6.BIN;1` | 0x801E8000 | 15284 | 29,448 |
| 123 | 0x 75174 | `\LD\WAIT_T1.BIN;1` | 0x801E8000 | 15299 | 21,320 |
| 124 | 0x 75184 | `\LD\WAIT_T2.BIN;1` | 0x801E8000 | 15310 | 19,176 |
| 125 | 0x 75194 | `\LD\WAIT_T3.BIN;1` | 0x801E8000 | 15320 | 25,352 |
| 126 | 0x 751A4 | `\LD\WAIT_T4.BIN;1` | 0x801E8000 | 15333 | 20,584 |
| 127 | 0x 751B4 | `\LD\WAIT_T5.BIN;1` | 0x801E8000 | 15344 | 21,352 |
| 128 | 0x 751C4 | `\LD\WAIT_T6.BIN;1` | 0x801E8000 | 15355 | 27,304 |
| 129 | 0x 751D4 | `\LD\WAIT_T7.BIN;1` | 0x801E8000 | 15369 | 31,432 |
| 130 | 0x 751E4 | `\LD\WAIT_T8.BIN;1` | 0x801E8000 | 15385 | 27,464 |
| 131 | 0x 751F4 | `\LD\WAIT_T9.BIN;1` | 0x801E8000 | 15399 | 23,368 |
| 132 | 0x 75204 | `\LD\WAIT_C.BIN;1` | 0x801E8000 | 15189 | 17,224 |
| 133 | 0x 75214 | `\LD\WAIT_M.BIN;1` | 0x801E8000 | 15198 | 21,384 |
| 134 | 0x 75224 | `\STD\_VHIECLE.BIN;1` | 0x80100000 | 18829 | 412,004 |

## 3. Menu / mission-select strings (MEASURED)

Strings at file `0x840–0x9A0`: `PAUSE`, `EXIT`, `RETRY`, `CONTINUE`,
`MISSION SELECT`, `MISSION 6`…`MISSION 1` (VA `0x80010040–0x800100CC`).
Pointer array **file `0x73518–0x7355C`** (VA `0x80083518–0x8008355C`),
one u32 per slot; the six slots `0x80083538, 0x8008353C, 0x80083540,
0x80083544, 0x80083548, 0x8008354C` point at `MISSION 1`…`MISSION 6`
**in ascending order** — the direct mission-select submenu.
`TITLE.BIN` carries the top-menu labels: `ARCADE MISSION`, `ANOTHER MISSION`,
`ART GALLERY`, `COMBAT SCHOOL`, `OPTION`, `SAVE LOAD`.
Snippet: `emu/msx_r19_t9/exe_menu_ptr_table_0x73500_0x73570.bin`.

## 4. Reference graph: EXE → packages → sub-events (MEASURED)

Level-1 = 135 EXE-table paths. Level-2 = **251** paths embedded as
`{dest_ram_va, ptr→20-byte path record}` request tables *inside* level-1 files
(all resolve on disc; full map `scratch/r19t9_msxdisc/embedded_path_refs.json`):

* `ST01.BIN` (dest `0x800FA6B0`): 22 entries @ file `0x32F44`
  (`{dest, &rec}` × 8 B; recs = 20-byte `\ST01\X1*.BIN;1` strings,
  `X1_999` → `X1.BIN`). Same pattern in `ST02.BIN` (22, file `0xD544`),
  `ST03` (38), `ST04` (36), `ST05` (20), `ST06` (25).
* `MISS01.BIN` embeds `\ANG\M1\MI01_00.BIN;1` + `\ANG\M1\MI01STD.BIN;1`
  (2 each ×20); `MISSMN.BIN` embeds `\ANG\MIMN.BIN;1` and the demo-name list;
  `CSCHOOL.BIN` embeds 43 paths; `ARTG.BIN` embeds 4.
* **Orphans (never referenced at any level): 7** — `ANG\CSC.BIN`,
  `ANG\SND\SEQ_M63.BIN`, `ART\ART.BAK`, `ST04\_0\X4_04.BIN` (4 B!),
  `ST05\SEQ05.BIN`, `X09.BIN`, `X801.BIN`. The two big MP3s are INFERRED to be
  reached via dynamically built names (the ANG engine uses `%02d` format strings).

## 5. Mechanism — how a mission gets selected (labels: M = MEASURED, I = INFERRED)

1. [M] TITLE.BIN provides top-menu labels; EXE provides pause/exit strings and
   the `MISSION SELECT` + `MISSION 1..6` submenu with an ascending pointer array.
2. [I] Main menu → `ARCADE MISSION` → `MISSION SELECT` → highlight `MISSION n`
   → CROSS → confirm → the loader indexes the 135-entry CD table (rows are
   ordered stage-first: 0=ST01…12=ST06, then overlays/player/UI, then MISS
   demos, then audio) and issues file reads to the per-row dest VA.
3. [M] Each `ST0x.BIN` package carries its own second-level request table and
   pulls its `X*` sub-event files; audio rows (`SEQ0x/VAB0x`) load to fixed
   VAs (`0x80140000/0x80160000`-family). Load screens come from `LD\WAIT_*`.
4. [I] `ANOTHER MISSION` (title menu) runs the 20 `MISSxx.BIN` scripts
   (dest `0x80102000`), titled `M%02d-<name>` by MISSMN.
5. [I] The r17-pinned menu cursor RAM `0x800957D8–0x800957F8` holds the
   highlight/selection state feeding the `0x80083538..0x8008354C` array.

## 6. Levers for entering Mission 2 directly (r19+)

1. **Menu lever (pure input, safest).** Ladder:
   boot → START → main menu → `ARCADE MISSION` → `MISSION SELECT` →
   DOWN ×5 (or navigate highlight to `MISSION 2`; array order is MISSION 1→6
   ascending, so exactly one DOWN from MISSION 1) → CROSS → `OK? YES` →
   SOLDIER SELECT. Watch RAM `0x800957D8–0x800957F8` (cursor) and the loading
   screen identifier (`LD\WAIT_S2.BIN` row 118) to confirm.
2. **CD-table row swap (binary, low risk).** Row 0 `\ST01\ST01.BIN;1`
   (VA `0x800841C4`) and row 1 `\ST02\ST02.BIN;1` (VA `0x800841D4`) are
   adjacent, same format, **same dest `0x800FA6B0`**. Swap the two 16-byte rows
   in RAM after EXE load (or on-disc inside the EXE's sectors at LBA 2454,
   file offsets `0x749C4/0x749D4`) → any Mission-1 start boots Mission-2
   stage data. Caveat: audio rows 80/82–84 and `LD\WAIT_S1` stay Mission-1.
3. **Offline perception lever.** Mission 2 data is fully pre-readable without an
   emulator: `ST02.BIN` at disc byte 60,253,560 (LBA 25618, 91,368 B), its
   request table at package file `0xD544–0xD568` (22 entries: X21/X22/X23
   sub-events, e.g. `X23_999.BIN` 222,424 B). Parse spawn/entity tables from
   those files to pre-build the m2 scene model (px/front-line priors).

## 7. Artifacts

| what | where |
|------|-------|
| full per-file CSV | `scratch/r19t9_msxdisc/inventory.csv` |
| CD table machine dump (135 rows) | `scratch/r19t9_msxdisc/cd_table_dump.json` |
| structured mission-paths report | `scratch/r19t9_msxdisc/mission_paths.json` |
| ISO9660 LBA index (354 entries) | `scratch/r19t9_msxdisc/iso9660_index.json` |
| level-2 embedded-ref map | `scratch/r19t9_msxdisc/embedded_path_refs.json` |
| evidence narrative | `scratch/r19t9_msxdisc/evidence.md` |
| run report | `scratch/r19t9_msxdisc/report.json` |
| binary snippets (outside repo) | `/home/z/my-project/emu/msx_r19_t9/` |
