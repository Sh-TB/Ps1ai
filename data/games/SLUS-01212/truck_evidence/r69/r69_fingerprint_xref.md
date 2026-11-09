# R69 — the +500 fingerprint xref (experiment track, OFFLINE, ZERO BOOTS)

Round: R69 · track: experiment (the R69 capsule hypothesis, lead 1
SOURCE-FIRST) · commit at run time: `eb186be` (origin/main) ·
machine-verifiable artifact: `r69_fingerprint_xref.json` (this dir).

## Inputs (all lawful local copies; binaries NOT committed)

| input | identity |
|---|---|
| the 19 fingerprint offsets | `r68/r68_analysis.json` `zero_overlap_test.intersection` (n=19, the R68 RESOLVED discriminator) |
| SLUS_012.12 | sha256 `1508b532…` = the canonical EXE (match) |
| ENEMY.BIN | sha256 `cab64009…` (match), load VA `0x8009C0E8` |
| function tables | `ghidra_functions.json` (3957 EXE) + `ghidra_overlay_functions.json` (468 overlay) |

## Method

Full-text capstone MIPS32 decode of the EXE text (155,136 insns) and
the overlay (28,850 insns); every load/store whose displacement is one
of the 19 offsets bucketed into the Ghidra functions; the score word
`0x800EE318` xrefs from the committed `source_map.json`; the amounts
500/1000 hunted as code immediates AND as u16/u32 data tables.

## Findings

1. **The record offsets are heavily consumed.** 750 EXE functions and
   132 decompiled overlay functions touch the 19 offsets.
2. **The score word has exactly 9 direct code xrefs** (all in the EXE
   HUD/score cluster `0x800472c0..0x80052820`).  The cluster's
   `FUN_800472c0` ("score_add" annotation) reads the entity record
   `+0xCC/+0xD0/+0xD4` — **`+0xD0` IS a fingerprint offset** — and
   calls `0x8001c028` with the score value: the presentation/credit
   path.
3. **The amounts 500/1000 exist in NO code immediate and NO EXE
   table.**  Both code-immediate candidates are falsified by their
   own bytes:
   * `0x800b03cc addiu $v1,$v1,0x3e8` — `lui $v1,0x800b` two insns
     earlier ⇒ `$v1 = 0x800B03E8` = the next state-handler ADDRESS
     (the state-machine `sw $v1,($v0)` dispatch — a function pointer,
     not the constant 1000);
   * `0x80088e8c addiu $a1,$zero,0x1f4` — inside `FUN_80088df4`, a
     value-clamp ladder; `0x1f4` is a range bound.
4. **THE KILL-CREDIT TABLES FOUND — overlay data head.**  Three u16
   runs contain BOTH 500 and 1000:
   * `0x8009C134` (43 entries): 420,450,200,400,400,400,800,880,300,
     600,600,600,**500**,600,300,500,500,500,**1000**,1100,400,700,…,1100
   * `0x8009C48C` (44 entries): 350,350,600,700,…,**500**,600,300,
     500,500,900,**1000**,750,400,**1000**,**1000**,470,510,750,…,1100
   * `0x8009C91C` (23 entries): 350,620,320,580,250,**500**,400,700,
     500,700,300,**1000**,400,650,360,600,300,**1000**,500,800,600,800,400
   (+ three more runs with 500 only).  These are the enemy
   kill-credit tables; the +500 class = the `0x1F4` entries.
5. **The overlay TAIL is the payment-writer region.**  The committed
   Ghidra pass decompiled 468 functions ending `0x800ab1fc`; the tail
   (`0x800AB230..0x800B83B0`) was never decompiled — and the damage
   dispatch chain (`enemy_800A41D8` → `func_0x800ae794` /
   `func_0x800ae7cc`) runs THERE.  Tail census: **207
   fingerprint-offset accesses (72 stores) covering 14 of the 19
   offsets**, with concrete record writes
   (`0x800ab450 sh $v0,0xda($v1)` … `0x800ac15c sh $v0,0x60($v1)`;
   `0x800ac154 lw $v1,0xdc($a0)` shows `+0xDC` is a sub-record
   pointer whose `+0x60` is then written).

## Verdict

**The payment writer is NARROWED, not pinpointed (static).**
The credit amounts live in the overlay kill-credit tables; the record
writes concentrate in the undecompiled overlay tail that the damage
dispatch enters; the score word itself is only touched by the EXE
HUD/credit cluster (which reads fingerprint offset `+0xD0` of the
entity record).  The exact store instruction that credits
`0x800EE318` at the impact frame is a RUNTIME fact — the R69
restore-only hunt pass (the capsule lever verbatim: the R66 gate, the
R68 disclosure pattern; the SEVENTH-rollback contingency disclosed —
the r66 frontiers were lost again and the R68 rebuild is byte-exact)
watches `0x800EE318` with the harness watch primitive to log the
writer PC.  The pay-before-registration law (pay at the impact frame,
the `0x5b0c` registration ~2 frames later) pins the expected write
order.

## Honesty ledger

* Zero boots spent (offline scan only).
* Zero RAM writes, no training, no runtime LLM; legal inputs only.
* The 468-function decompilation set does not cover the overlay tail;
  no new Ghidra run was performed this round (headless Ghidra absent
  in this sandbox — disclosed, the R2 tools-matrix precedent).
* The fingerprint set is re-validated against
  `r68_analysis.json` at run time (the assert in `load_fingerprint`).
