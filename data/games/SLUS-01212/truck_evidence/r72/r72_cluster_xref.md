# R72 PART 1 — THE PAYMENT-CLUSTER XREF (offline, zero boots)

Round: **R72** · Track: experiment · Method: static (capstone full-text
decode of the lawful local binaries + the committed call graph) ·
Boots: **0** · Machine-readable verdict: `r72_cluster_xref.json`

The R72 capsule lever, lead (2): "the watchpoint clusters — the stack
band 0x1FFD00-0x1FFF00 + the entity rows 0xCA6xx-0xCBDxx + the HUD
neighborhood 0xEE3xx-0xEF4xx — the xref on those cluster addresses
closes the R69 narrowed set to the exact store."

## The verdict — PAYMENT WRITER PINPOINTED (the store instruction)

**The score-word payment store is `0x8005c508: sw $a1, -0x1ce8($a2)`
→ 0x800EE318**, inside the score accumulator whose head is
`0x8005c4b4` (frame 40 B).  The full chain (verified instruction by
instruction in the decode):

```
0x8005c4b4  addiu $sp,$sp,-0x28        ; the frame (40 B)
0x8005c4bc  move  $s0,$a0              ; $a0 = the flag selector
0x8005c4cc  lw    $a2,($a1)            ; the score-base HANDLE (pointer-mediated)
0x8005c4d0  jal   0x8007e8b4           ; the FORMAT call (fmt string @0x80011354)
0x8005c4d8  jal   0x8007e7d4           ; the PARSE call -> $a3 = the numeric delta
0x8005c4e4  andi  $v0,$s0,1            ; the P1 bit
0x8005c4f4  lw    $v1,-0x1ce8($a2)     ; READ the score word
0x8005c4fc  addu  $a1,$v1,$a3          ; score += delta
0x8005c500  slt   ... 0x5f5e0ff        ; the 99,999,999 saturation cap
0x8005c508  sw    $a1,-0x1ce8($a2)     ; THE PAYMENT STORE (P1)
0x8005c54c  sw    $v0,-0x1ce8($a2)     ; the %100 display twin (magic 0x51eb851f)
0x8005c550  andi  $v0,$s0,2            ; the P2 bit
0x8005c578  sw    $a1,8($a2)           ; -> 0x800EE320 (the P2 score word)
```

* The census found **exactly 3 stores to the score word** in the
  whole EXE text (155,136 instructions) and **0 in the overlay**
  (28,850): the two accumulator stores above + the clear twin
  `0x8005c734 sw $zero` (in `0x8005c6d4`, called by the game-reset
  cluster via `jal` from `0x80067254 / 0x80067b14 / 0x80067b6c /
  0x80067f64`).
* **The amount path explains the R69 falsification**: the delta
  arrives through the format-string → parse chain
  (`0x8007e8b4` → `0x8007e7d4`) — the amounts 500/1000 appear in no
  code immediate because the credit amount is formatted from the
  overlay kill-credit tables (`0x8009C134/0x8009C48C/0x8009C91C`)
  and re-parsed.  The R69 "both candidates falsified" finding is now
  fully explained.
* **The dispatch bound (disclosed)**: the accumulator has NO direct
  `jal` xref anywhere — it is reached through a pointer/handle
  dispatch that a static decode cannot see.  The runtime PC
  confirmation stays with the CPU-state oracle (the known beetle
  limit; the PCSX-Redux debugger is the committed follow-up).
* **The stack-band consistency**: the accumulator's 40-byte frame
  fits the churned top band 0x1FFD00-0x1FFF00 at depth ≤ 2 — the
  R71 stack churn is exactly the shallow accumulator call frame.
* **The entity-row consistency**: the churned slots are +1000 →
  {0,3,4,6,7,12,16,18,20,21,24,28,30} and +500 → {3,16,18} — slot 16
  is the R66/R68 capture slot, slot 12 the R66 registration witness;
  the overlay damage tail (the R69 store sites, +0xCC/+0xD0) writes
  the rows BEFORE the accumulator pays — the pay-before-registration
  law, now with both sides identified.

## Honest bounds

* The census is a linear decode: path-dependent bases, pointer-table
  bases and indirect stores are invisible; every reported store site
  is locally verified on a clean `lui` chain (the `verified` flag in
  the JSON; the unverified candidates are listed separately).
* The store site is pinpointed as an INSTRUCTION; the *caller* into
  the accumulator remains a static bound (pointer dispatch).  The
  next runtime confirm belongs to the PCSX-Redux CPU oracle (the R64
  tools-matrix item), not to another beetle boot.
