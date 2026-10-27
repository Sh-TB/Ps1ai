# Harvest Moon: Back to Nature (PS1, SLUS-01115) — GitHub tools audit + our decorpus tool

The user flagged the farming game on their list as carrying a rich GitHub
helper-tool ecosystem — "from extracting the game itself to the story and all
its dialogues". This page records the audit (2026-10-27) and the tool we built
on top of it: `scripts/hmbtn_text.py`.

## The five audited repos (shallow-cloned to external_audit/hmbtn/, local only)

| repo | license | what it is | disc needed? |
|---|---|---|---|
| [coalslav/hmbtn-decomp](https://github.com/coalslav/hmbtn-decomp) (53 stars) | CC0-1.0 | **Matching decompilation** of EXE + all 13 code overlays (byte-for-byte, `check` target); documents the text charset, the A_FILE.BIN archive map, the disc layout (`disc/disc.xml`), ships `tools/afile.py` (archive unpack/pack), `tools/ps_x_exe.py`, `tools/psx_disc.py` | yes (for byte-check + data members) |
| [beruanglaut-com/backtonature-decompiled](https://github.com/beruanglaut-com/backtonature-decompiled) | Unlicense | Independent matching decomp of the **main EXE only** (461 C functions, byte-identical target sha1 `07fbcffb...`); explicitly ships no game data | yes |
| [GabrielBigardi/HarvestMoonBTN-Recomp](https://github.com/GabrielBigardi/HarvestMoonBTN-Recomp) | MIT | **Static recompilation** native port (x86-64, no BIOS, no emulator); "bring your own disc" build | yes |
| [gilangjavier/hmbtn-modkit](https://github.com/gilangjavier/hmbtn-modkit) | MIT | Mod kit: write C mods against the decomp source, `python hm.py build <mod> <base>` produces a playable `.cue` in one command | yes |
| [gil-unx/EVENT-EDITOR](https://github.com/gil-unx/EVENT-EDITOR) | MIT | Excel-driven event editor; targets a fan-translation base ISO (not our asset) — useful as event-format documentation only | (different base) |

Reading: every runnable path is **bring-your-own-disc** (the correct legal
stance, matching our hard constraint). The decomp repos are the knowledge
base: they document the exact dialogue encoding and the archive layout of the
dialogue banks — without shipping those banks.

## Where the story/dialogues live (from hmbtn-decomp `disc/a_file.txt`)

`A_FILE.BIN` = 32 members. The game's text assets are members
`02..06 = messege0.bin .. messege4.bin` (the message banks), plus
`12 = event_s.bin` / `13 = evch.bin` (event script chunks) and
`01 = face.bin` (portrait bank). `tools/afile.py unpack` extracts them from
the **user's own disc**.

## Our tool: `scripts/hmbtn_text.py` (tested, no disc required to prove)

Implements the game's u16 glyph text system end to end:

* **Charset** (documented in hmbtn-decomp `text_bank.c` header + `text.h`
  enums): `0x0000..=A-Z`, `0x0020..=a-z`, `0x0040..=0-9`, `0x0FFD` space,
  `0xFFFE` line break, `0xFFFF` end, control ranges `0xFF1-0xFFC`
  (choices/faces/pages), `0xE25-0xE2F` waits, `0xE38-0xFEF` face codes,
  `0x4000+` name/farm/item inserts.
* **`glyphs`** — learns every glyph outside the documented blocks by aligning
  the decomp's own plaintext comments with their encoded arrays
  (353 pairs, **4,098 characters matched with 0 mismatches**) and reports the
  discovered punctuation with vote counts:
  `0x0062='?' (17)`, `0x0063='!' (4)`, `0x0069='-' (1)`, `0x006C='.' (39)`,
  `0x008C=',' (2)`.
* **Contraction glyphs** break 1:1 alignment (multi-char expansions) —
  evidence-recorded separately: `0x0050="'s"→"'"`, `0x0051="'s"`, `0x0054="'m"`,
  `0x0066=":"`, `0x0071="/"` (each backed by 3+ independent contexts).
* **`corpus`** — extracts and decodes every commented plaintext:
  **353 rows, 310 (87.8%) byte-exact against the decomp's own comments**; the
  remainder contain face/wait/insert control codes that decode as documented
  placeholders. Corpus output stays LOCAL (`scratch/`) — game-derived text is
  never committed.
* **`afile`** — disc-mode: parses the A_FILE.BIN container (u32 count +
  offsets), lists members, decodes any member as a u16 stream. Verified by a
  synthetic container round-trip in tests.
* **`decode`** — one-shot u16 stream decoding.

Tests: `tests/test_hmbtn_text.py` (8 tests) — all fixtures are synthetic,
authored from the documented charset facts; zero game data, zero external-repo
dependency in CI.

## Honest status for the game itself

| rung | status |
|---|---|
| Tooling | **READY** — intake (`disc_intake.py`), archive unpack + text decode (`hmbtn_text.py`), boot-route known |
| Boot | **BLOCKED_PENDING_DISC** — no SLUS-01115 disc locally; retail discs ship license sectors (route 1, zero patching expected) |
| Story/dialogue extraction | **BLOCKED_PENDING_DISC** — `messege0..4.bin` are A_FILE.BIN members read from the disc |

When the user provides their disc: `disc_intake.py` verifies identity
(serial SLUS-01115, EXE sha1 `07fbcffb...` per backtonature-decompiled) →
`tools/afile.py unpack` (hmbtn-decomp, CC0) extracts `messege0..4.bin` →
`hmbtn_text.py` decodes the full dialogue corpus → then the standard boot
campaign (route 1) with the plugin skeleton. Every step above is already
tested except the ones that physically need the disc.
