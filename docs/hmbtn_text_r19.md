# HMBTN text round 19 — community cross-validation, disc-free

Round 19 pushed the Harvest Moon: Back to Nature (SLUS-01115) dialogue/story
extraction further **without the disc** by cross-validating our glyph table and
format knowledge against community projects on GitHub. Result: the glyph map is
now confirmed by **three independent community codebases plus our own corpus
statistics**, one r16 mapping error was found and fixed, corpus coverage rose
from 87.8% to **89.0% byte-exact (97.2% in the decomp's own comment style)**,
the A_FILE dialogue record format is documented from decomp source, and
`scripts/hmbtn_text.py` gained a disc-ready record decoder.

## Sources found and used (all cloned/fetched OUTSIDE the repo, 2.9 MB total)

| repo | license | what we took from it |
|---|---|---|
| [GabriPires/traducao-hm-btn-ptbr](https://github.com/GabriPires/traducao-hm-btn-ptbr) | MIT | **The centerpiece find**: `tables/hmbtn.tbl` (129-line glyph table), `docs/01-disco-e-texto.md` + `docs/02-dialogos.md` (full dialogue record format), `tools/hmbtn/dialog.py`/`table.py` (reference parser), `translation/*.json` (6,011 mapped dialogue ids: 02=1850, 03=2061, 04=651, 05=1393, 06=56 records), `tables/personagens.tsv` (portrait codes → 40+ named characters), `translation/exe.json` (EXE text bank keyed by real VAs) |
| [Suphanat1722/hm-btn-mod-tool](https://github.com/Suphanat1722/hm-btn-mod-tool) | MIT | Third independent glyph table (`src/hm_btn_tool/text.py`) + third confirmation of the record constants (`MESSAGE_RECORD_SIZE = 0x2000`, `MESSAGE_TEXT_OFFSET = 0x1800`, `A_FILE_SIZE = 133,935,104`) |
| [Fragrant-radish/HM-back-to-nature-plus](https://github.com/Fragrant-radish/HM-back-to-nature-plus) | — (mod) | context only (a shipping mod built on the same formats) |
| coalslav/hmbtn-decomp (cloned r17) | CC0-1.0 | ground truth: `src/main/text/text.c` (control codes, `TextGlyph` enum, `TEXT_BANK_STRIDE 0x1800`, insert flag), `src/main/cd/afile.c` (HDT directory + member table), `src/main/ui/menu_window.c` + `name_entry.c` (`text_load_record`), `src/main/text/text_bank.c` (the 353-pair corpus) |
| beruanglaut-com/backtonature-decompiled (cloned r17) | Unlicense | `src/text/text_bank.layout.json`: the in-EXE text bank layout — 354 named entries, base `0x8005175C`, 13,406 bytes → real byte offsets for decoded lines |

## 1. Glyph cross-validation — agreements, one contradiction fixed, new mappings

Method: decode the hmbtn-decomp comment↔array corpus (353 real game-text rows,
the only real HMBTN text available disc-free) under each candidate mapping and
count byte-exact rows (`scratch/r19t6_hmbtn/xval_glyphs.py`, results in
`glyph_xval.json`).

**Agreements** (two to three independent sources): A-Z@0x0000, a-z@0x0020,
0-9@0x0040, `0x0062=? 0x0063=! 0x0066=: 0x0069=- 0x006C=. 0x0071=/ 0x0076=&
0x008C=,` and contractions `0x0051='s 0x0054='m`. The decomp's own
`text.c` enum `TextGlyph` independently confirms `0x62 ? 0x63 ! 0x69 - 0x6A (
0x6B )`.

**Contradiction found and fixed — `0x0050`:** r16 had `0x0050 = "'"`. The
PT-BR table (and hm-btn-mod-tool) say `0x0050 = "'t"` — one glyph draws
apostrophe+letter. The decomp corpus proves it: the array for comment
"Didn't feed animal" is `D i d n <0050> _ f e e d` (10 values for 11 comment
chars — exactly the missing `t`), and the same pattern holds in mg3
("can<0050> throw" ↔ "can't throw"). The r16 test fixture had encoded the
wrong hypothesis and was corrected. Empirical effect: +2 corpus rows for this
fix alone, zero rows broken.

**New mappings adopted** (font-rendered by PT-BR, several also corpus-proven):
`0x0052='l 0x0053='d 0x0055='r 0x0056='v` (ligature family; 0x0055 proven by
mg3 "You<55>e" ↔ "You're"), `0x0067=';' 0x0068='+' 0x006A='(' 0x006B=')'
0x0074='~' 0x0076='&' 0x007F='…' 0x0080='♥' 0x008D="'" 0x008E='"' 0x008F='%'
0x0065='•'` (mod-tool only; 0 corpus occurrences, low confidence). The PT-BR
accented letters (0x001A..0x005F) are **project-drawn**, not original charset —
documented as such by the PT-BR repo and NOT adopted.

**Source disagreements, resolved by corpus votes:** hm-btn-mod-tool lists
`0x6C=','`/`0x7F='.'`/`0x80='…'`; PT-BR lists `0x6C='.'`/`0x7F='…'`/`0x80='♥'`.
Our corpus votes `0x6C='.'` with 39 independent votes (vs 0x008C=','), and
`0x80` appears as "See you later <80>" / "Hi, I'm back <80>" where a heart fits
(and PT-BR derived it from the font bitmap) — PT-BR wins on both.

**Coverage numbers** (`hmbtn_text.py corpus` on the decomp source):

| metric | r16 (before) | r19 (after) |
|---|---|---|
| corpus rows byte-exact (friendly placeholders) | 310/353 = 87.8% | **314/353 = 89.0%** |
| byte-exact when control codes render in the decomp comments' own style | n/a | **343/353 = 97.2%** |
| known glyphs outside A/a/0 blocks | 5 (+5 vote-learned) | **24 mapped, each with source tags** |

The remaining 10 non-exact (faithful) rows are all cases where the *decomp
comment itself* writes a raw `{71}`-style code for a glyph that the PT-BR
font-rendering identifies — i.e. glyph knowledge is complete for every code
that occurs in the corpus; only comment style differs (`/`, `♥`, `&`, `%`, `…`).

## 2. A_FILE.BIN dialogue format — documented from decomp source + two communities

All three projects agree; the decomp C source is the authoritative description:

* **Directory**: `A_FILE.HDT` = 33 little-endian u32 byte offsets into
  `A_FILE.BIN` (132 bytes; last entry = archive size, 133,935,104 B per
  mod-tool). Member *i* = `BIN[offs[i]:offs[i+1]]`; every member is zero-padded
  to 2048-byte sectors. There is **no** embedded directory inside the .BIN (our
  r16 `afile` parser assumed one — fixed this round; it now takes `--hdt`).
  Read path: `afile_init()` (`src/main/cd/afile.c`) loads HDT and finds
  `A_FILE.BIN;1`'s first sector.
* **Members** (`disc/a_file.txt`, 32): 0 gf.bin, 1 face.bin, **2–6
  messege0..4.bin = the dialogue banks**, 7 Font_all.tex, 9 sound.stm,
  12 event_s.bin / 13 evch.bin (event scripts), 14 Status.Bin, 16 Slp.Bin,
  18/20/22/24/26 MG*.Bin, 29 MesEv.Bin, …
* **Dialogue records** (messege0..4): a flat sequence of fixed-size records,
  **0x2000 bytes each, one dialogue per record, no index** — the game computes
  `record * 0x2000` (`menu_data_index << 13`, `menu_window.c`; menu ids 0–4 map
  to members 2–6 via `menu_window_values = {2,3,4,5,6}`). Record layout:
  * `+0x0000`: s32 portrait bank id (−1 = none) + portrait texture pack
    (`text_load_record`, `name_entry.c`; portrait banks = 0x1800-byte texture
    packs in `face.bin`, member 1, `TEXT_BANK_STRIDE`)
  * `+0x1800`: u16 glyph stream, up to **1023 values + 0xFFFF**, zero padding
    (`menu_text = sector + 0x1800`)
  * per-record budget: 1023 values, 31 chars/line, 4 lines/page (PT-BR
    measurements; medians: EN 71 values, 99th pct 705)
* **Record counts** (PT-BR, from the real disc): 02=1850, 03=2061, 04=651,
  05=1393, 06=56 → **6,011 dialogues**, every record ending in a single 0xFFFF.
* **Control codes** (`text.c enum TextControlCode`): 0xFFB page end,
  0xFFC page mark, 0xFF8–0xFFA choice lists (4/3/2 rows), 0xFF7/6/5/4 face
  window ops, 0xFF3 no-scroll, 0xFF1 scroll-hold, 0xE25–0xE2F waits
  (wait = 0xE2F − code frames), 0xE38–0xFEF face codes (**bank = 0xFEF −
  code**, `text_code_to_bank`), 0xFFD space, 0xFFFE line break, 0xFFFF end.
  Dialogue records open with a prefix of these (e.g. `{0FE4}{0FF7}{0FF4}
  {0FF5}{0E2E}` = portrait + window setup).
* **Inserts**: `0x4000 | id` (low 12 bits; `TEXT_INSERT_FLAG`). PT-BR mapped
  the ids from the jump table at EXE `0x800100DC`: 0x400A player name, 0x400B
  horse, 0x400C dog, 0x400D farm, 0x400E child, 0x400F wife's nickname
  ("Honey"@0x80054396 / "Darling"@0x800543A2), 0x401B–0x4020 dead-animal lists.
* **Event scripts**: member 12 (`EVENT_SCRIPT_AFILE = 0xC`), cut into 50 chunks
  (`EVENT_CHUNK_COUNT`), indexed by an in-EXE `event_script_offsets[]` table;
  MesEv.Bin (29) is read via `afile_read_range(0x1D, 0x1E, …)`.

## 3. Sample decoded lines (real game text, with byte offsets)

Full evidence: `scratch/r19t6_hmbtn/samples_evidence.json` (9 corpus lines +
2 synthetic record-mode records + 4 three-way address cross-checks). The in-EXE
text bank is real USA-dialogue text committed as CC0 source comments; byte
offsets come from backtonature-decompiled's bank layout (base 0x8005175C),
cross-checked against PT-BR `exe.json` keys at the same VAs (4/4 match, e.g.
0x800517B8 = "Didn't feed animal" ↔ PT-BR "Não dei ração"):

| EXE VA (byte offset) | decoded (faithful render) |
|---|---|
| 0x8005175C | ` Yes\n No` (messages.promptYesNo) |
| 0x800517B8 | `Didn't feed animal` (0x0050='t proven here) |
| 0x80051798 | `Razzed villager` (messages.razzedVillager) |
| 0x80051820 | `Overslept` |
| 0x8005189C | `Coveted another's girl` (0x0051='s) |
| — (text_bank.c) | `Your name : <400a>\nBirthday  :\nFarm's name: <400d>\nDog's name : <400c>\n\nIs this OK?` |
| — | `Buy\nDon't buy` (0x0050) |
| — | `See you later <80>` → `♥` |
| — | `Earnings <76>\nexpenses` → `Earnings & expenses` |

Record-mode demo (synthetic fixture built from the documented format, zero game
bytes): `hmbtn_text.py afile --afile … --hdt … --member-index 1 --records`
decodes `01-0001 @0x2000 prefix={fe4}{ff7}{ff4}{ff5}{e2e}
text="Didn't feed the animal <400a>"` and `02-0001 @0x4000 text='Yes\nNo'`
(bank id 3 at record head) — the exact pipeline that will run on the disc's
`messege0..4.bin`. The r17 `flat_A_FILE.BIN/HDT` fixture also parses now via
`--hdt` (5 members); the legacy embedded-directory parse fails on it,
confirming the format fix was needed.

## 4. Tool changes (`scripts/hmbtn_text.py`, only this script touched)

1. `DEFAULT_OTHER` rewritten: 0x0050 corrected to `'t`; 19 new mappings with
   per-entry source tags `[d]ecomp corpus / [t] PT-BR table / [e] TextGlyph
   enum / [m] mod-tool`.
2. `decode_stream(..., faithful=)` — renders placeholders exactly like the
   decomp comments (`<400a>` inserts, `{ffa}` ctrl) to measure true coverage.
3. `afile` mode fixed to the real format: `--hdt` directory argument
   (u32 offsets, sector-aligned), legacy embedded layout kept as fallback.
4. New record layer: `RECORD_SIZE/RECORD_TEXT_OFFSET/RECORD_MAX_VALUES`,
   `DIALOGUE_MEMBERS`, `split_prefix()` (leading 0x0E00–0x0FFF run),
   `record_u16_stream()`, and `afile --records [--limit]` which decodes
   messege members record-by-record with ids (`NN-NNNN`, PT-BR convention),
   A_FILE byte offsets, prefix and text (stdout + `--json-out`).
5. `corpus` now reports both exact and comment-faithful percentages.

Tests: `tests/test_hmbtn_text.py` 8 → 11 tests (contraction fixture corrected,
faithful rendering, HDT directory format, dialogue record decode + prefix
split); suite **565 passed + 1 xfail**.

## 5. What remains disc-gated (honest list)

* Decoding the actual 6,011 `messege0..4.bin` records — needs `A_FILE.BIN` +
  `A_FILE.HDT` from the user's SLUS-01115 disc (everything is wired:
  `disc_intake.py` → `afile.py unpack` → `hmbtn_text.py afile --records`).
  The PT-BR repo proves the path works end-to-end (6,011/6,011 mapped,
  encode-check byte-exact) but ships no game text.
* Portrait rendering (RLE font/portrait codec is documented by PT-BR
  `docs/04-fonte.md` + decomp `texture_pack.c`) — implementable disc-free, but
  only verifiable against the disc's face.bin.
* Remaining glyph unknowns (rare, none in the decomp corpus): 0x0064 (raised
  ellipsis?), 0x006D–0x0070 (controller button icons), 0x0081–0x008B (music
  notes / map arrows), 0x001B/0x001E (menu brackets?), 0x0087–0x008F tails —
  all flagged with raw-code placeholders; PT-BR `docs/02` table is the
  reference.
* Boot/runtime anything (HMBTN-Recomp, modkit builds) — unchanged from r17.
