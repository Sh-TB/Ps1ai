# MSX stage-loader RE (r22t7) — findings and the r23 plan

Task: r22t7 (research-only, zero emulator boots). Target: Metal Slug X (USA),
main EXE SLUS_012.12;1 (PS-EXE, t_addr 0x80010000, t_size 0x97800 → image ends
0x800A7800; MIPSel). Extracted EXE: local-only `emu/msx_usa/SLUS_012.12`.
Script: `scripts/r22t7_msx_re.py` (capstone). Context: r20 RETRACTED the
1-based-index hypothesis and proved u16@0x800D4210 = unlock counter with only
menu-only readers — the true stage selector was never found. This document is
the static half; the dynamic half (one instrumented boot) is queued for r23.

## Established facts (source/disassembly-verified)

### Memory map
- Entry pc0 0x80082A44 clears BSS **0x800C9A50..0x800FA6B0**, then sets up the
  heap. Everything at 0x800C9A50+ is runtime RAM (not in the file): the r20
  unlock counter 0x800D4210, the pointer 0x800D9A98 and the two state structs
  below are all in this range.
- gp = **0x80010000** (set at 0x80082AC0). Most data references are
  base+disp from per-function page registers, not raw lui+addiu pairs — this
  is why naive pair-scans find nothing.

### Two game-state structs + a setter
- **0x8002CB30** = `setter(selector a0, value a1)`: loads a runtime pointer
  from BSS **[0x800D9A98]** and writes `value → ptr+0x130` when `a0==0`, else
  `value → ptr+0x9E`. No direct jal callers found (reached via function
  pointers/jump tables).
- A neighbouring function selects between two BSS structs **0x800CA268** and
  **0x800CA3B4** (same selector semantics, `a0==0` → 0x800CA268) and reads
  fields 0x28 (bit7), 0x12C (u16), 0x135 (bit2), 0x13D (bit2) — these two
  structs are the "current game session" state (mission/area live here with
  high probability, exact field offsets still unpinned).

### Mission/stage content layout (static strings, in-image)
- Menu strings: RETRY @0x8001006C, **MISSION SELECT @0x80010074**, CONTINUE
  @0x80010084, **"MISSION 6".."MISSION 1" @0x80010090..0x800100C0** (6 top-level
  missions — matching the 6 stage packs \ST01..\ST06).
- Cutscene blob: `\ANG\M1\MISS01.BIN;1` .. `\ANG\M4\MISS20.BIN;1`
  @0x8001075C..0x80010940, fixed stride **0x18** (20 entries; group M1→M4).
  MISSyy = per-mission intro/ANG files (r19's disc map: 20/20 on disc).
- Stage packs: `\ST01\ST01.BIN;1` .. `\ST06\ST06.BIN;1` (+_1/_2/_3 variants).
- Suspected **(mission,area) byte table** starts at 0x80010C8E (right after
  the filename blob): pairs (01,01)(01,02)...(01,16), then u16 constants
  (0x0040/0x004A/0x0060/0x0036...), then per-stage index sequences
  (01..0b, 0b 0b 0b 00 0c, ...). This is very likely the two-level sequencer
  table r19 measured at runtime.
- HUD format string **"STAGE %d" @0x80011160** — whoever formats it holds the
  current stage number.

### The pause/menu BSS cluster (prime suspects)
The code around the RETRY/CONTINUE/MISSION SELECT references
(0x80015300..0x80016200) writes a tight cluster of menu-state variables:
**0x800D496C, 0x800D4A48, 0x800D4A68, 0x800D4A6C (u16), 0x800D4A6E (u16),
0x800D4A70 (u8), 0x800D4A71 (u8), 0x800D4A72 (u8)** — same 0x800D4xxx page as
the unlock counter. One of these (most plausibly a byte among 0x4A70-72 or a
u16 among 0x4A6C-6E) is the selected mission/state index; static analysis
alone cannot disambiguate them because they are accessed through shared page
registers across several menu screens.

## r23 plan (single instrumented boot, falsifiable)
1. Boot → attract → enter_gameplay (r20 route) → pause → open MISSION SELECT.
2. Per-frame diff the cluster **0x800D496C..0x800D4A80** while walking the
   selection MISSION 1 → MISSION 2 (and back). The word/byte that tracks the
   selection monotonically (and survives the pause-exit) is the selector.
3. Confirm causally: set it to 2 (and 3 as a second data point), resume,
   predict the VLM banner "2-1" (or "3-1"). Refutation criterion: banner stays
   "1-1" → the cluster is menu-cosmetic and the true loader is one of the two
   structs (0x800CA268/0x800CA3B4) fields 0x12C/0x130/0x9E — diff those the
   same way.
4. Fallback (if menu-walking is flaky): the setter @0x8002CB30 gives a
   writable path (`ptr=[0x800D9A98]; ptr+0x9E / ptr+0x130`) — hook-read both
   fields during a live M1 to learn their M1 values, then poke candidate
   M2 values and watch the loader's file open (the disc map predicts
   `\ANG\M2\MISS06.BIN;1` + `\ST02\ST02.BIN` reads for Mission 2 — an observed
   read of MISS06/ST02 is itself a positive stage-loader signal).

Confidence: layout/strings/BSS map = source-verified; the cluster members'
semantics = inferred (bounded, falsifiable by step 3).
