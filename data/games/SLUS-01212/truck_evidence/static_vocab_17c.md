# Task 17-c — Static vocabulary: soldier HP word & the semantics of slot+0x8E

Scope: static-only sweep (no emulator, no file edits). Sources: decompiled corpus
`ghidra/overlay_decompiled.json` (468 fns, keys 0x8009c100..0x800ab1fc), raw modules
`ps1play/re/SLUS_012.12` (EXE text 0x80010000..) and `ps1play/re/ENEMY.BIN`
(file[0xD180..0x1C2C8] → VA 0x800A9268..0x800B83B0), capstone 5.0.7 resync-linear disasm.

---

## Q1 — Soldier HP: where is damage applied and which offset?

**Answer: the damageable HP word is the u16 at slot+0xA4 (NOT +0x8E). Per-hit damage is
applied EXE-side via a scratch accumulator, then committed to slot+0xA4. Soldier-class
HP init = 0x14 (20) — consistent with the behavioral "2 aimed bullets" kill (2×10).**
Confidence: HIGH on the offset+mechanism, MED on the 0x14 init belonging to the soldier
class specifically (init site's class not cross-pinned; no HP=1..0x13 multi-bullet init
exists that would fit better).

Evidence chain:

1. **Soldier HP/next-state init, corpus-decompiled** — `overlay_decompiled.json` key
   `"800a28e0"` (`FUN_800a28e0`, identical code also at ENEMY.BIN VA 0x800ad200):

```c
void FUN_800a28e0(void) {
  iVar1 = _DAT_800c9a98;
  *(undefined2 *)(_DAT_800c9a98 + 0x2c) = 0x104;
  *(undefined4 *)(iVar1 + 0xa8) = 0x800b7e30;   // next-state handler
  *(undefined2 *)(iVar1 + 0xa4) = 0x14;         // HP = 20
  func_0x80043960(0,0); func_0x800ad250();
}
```
   Same pairing `hp = small; +0xa8 = 0x800bxxxx` in `FUN_800a871c` (+0xa4=1),
   `FUN_8009d19c` (+0xa4=1), `FUN_800a9988` (+0xa4=0 + dead-flag `+0x28 |= 0x80`).

2. **Per-hit damage accumulator (EXE side, matches "damage applied EXE-side" in
   docs/truck_blocker_resolution.md §2)** — SLUS_012.12 VA 0x8005e538..0x8005e56c
   (weapon-class jump table at 0x80011394, 12 entries):

```mips
8005e548 lh   $v0, 0x1a($a0)      # accumulated damage
8005e54c lh   $v1, 0x16($a0)      # cap
8005e554 slt  $v0, $v0, $v1
8005e560 lhu  $v0, 0x18($a0)
8005e568 addu $v0, $v0, $a3       # += per-hit damage (lhu ($a1) = bullet word0)
8005e56c sh   $v0, 0x18($a0)
```

3. **Commit to slot+0xA4 (EXE)** — VA 0x8005e0a8 (with 0x8005e090 merging scratch
   +0x18 into +0x1a, then `sh $v0, 0xa4($v1)` where `$v1` = root/current-entity ptr
   `lw -0x6568(0x800d)` i.e. 0x800C9A98):

```mips
8005e0a0 lhu  $v0, 0x1a($a1)
8005e0a4 sh   $zero, 0x18($a1)
8005e0a8 sh   $v0, 0xa4($v1)      # slot+0xA4 = accumulated damage
8005e0ac sll  $v0, $v0, 0x10 ; bnez → death branch 0x8005e0c8
```
   Companion readback `8005de84: lhu $v0, 0xa4($v0); sh $v0, 0x1a($a0)` seeds the
   accumulator from +0xA4. Fuse-style variants: `8005a4c4: lhu 0xa4; addiu -1; sh 0xa4`
   and `80059c88/80059d08: lhu 0xa4; sra 17 (HP/=2); sh 0xa4`.

4. **Soldier death zeroes its own HP (ENEMY.BIN)** — `sh $zero, 0xa4(root)` at
   0x800b34a4 and 0x800b6780 (both preceded by `+0x28 |= 0x80` dead-flag), matching
   `FUN_800a9988` in the corpus.

5. **Ruled out for the soldier:**
   - slot+0x8E: **zero** stores in all 468 corpus fns, **zero** stores in the ENEMY.BIN
     code region; every corpus reference is a read (screen-window culling / dx-to-player).
   - Soldier module never even reads its own HP: ENEMY.BIN has **zero** `lhu ...,0xa4(`
     sites — the soldier is a state-machine whose liveness is the word0 state family
     {0x800B4054, 0x800B41FC} → {0x800B4BE4, 0x800B5CC8} (states are stored handler
     addresses, e.g. corpus `FUN_800aaaa4: *_DAT_800c9a98 = &SUB_800b41fc`).
   - The decompiled overlay corpus contains no damage-subtract store at all (confirms
     truck_resolution.json "field scan" finding); damage lives in the EXE (Q1 evidence #2/#3)
     plus HP-init/death writes in ENEMY.BIN.
   - Behavioral cross-check: HP 0x14=20 / 2 bullets = 10 dmg/hit; chopper hp_a4=300
     died in 3×100 hits on the same +0xA4 word (session-2/6 evidence) — same scale.

---

## Q2 — Semantics of slot+0x8E: screen-x or HP/occupancy?

**Answer: ONE semantics for every entity class — slot+0x8E is the entity's
screen-space x coordinate (i16 read / u16 stored). It is NOT an HP word in any class.**
Confidence: HIGH.

Evidence:

1. **All corpus reads are screen math** (`overlay_decompiled.json`; `_DAT_800c9a98` =
   current-entity pointer variable at 0x800C9A98):

```c
8009d294: if (*(short *)(_DAT_800c9a98 + 0x8e) < 0xa1)            // on-screen culling
8009da08: if (*(ushort *)(_DAT_800c9a98 + 0x8e) - 0x18 < 0x111)   // window [0x18,0x129)
800a2534: if (*(short *)... < -0x1f) ... if (0x15f < ...)         // left/right off-screen
800a4588: iVar4 = (int)*(short *)(iVar7 + 0x8e) - (int)*(short *)(_DAT_800c9a98 + 0x8e); // dx to player
800a8934: iVar1 = (uint)*(ushort *)(iVar1 + 0x8e) - (uint)*(ushort *)(_DAT_800c9a98 + 0x8e);
```
   (`FUN_800a9f5c` — the soldier-approach AI caller chain that ends in soldier state
   `&SUB_800b41fc` — uses these same +0x8E windows, i.e. the SOLDIER itself reads
   +0x8E as a screen coordinate.)

2. **Writes are spawn-position init only (EXE)** — the only 3 `sh ...,0x8e(` sites in
   the whole EXE, all storing 0xa0 (160) paired with screen-y at +0x92:

```mips
8002d3e4 addiu $v0, $zero, 0xa0
8002d3e8 sh    $v0, 0x8e($a1)     ; +0x8E = 160 (screen x)
8002d3ec addiu $v0, $zero, 0x70
8002d3f0 sh    $v0, 0x92($a1)     ; +0x92 = 112 (screen y)
```
   (0x8002db88 and 0x8002f4c8 identical via root pointer). Zero `sh ...,0x8e(` in
   ENEMY.BIN code region; zero in the decompiled corpus.

3. **Scroll maintenance** — camera writer 0x80064674 (verified: `lw/addu/sw` on +0x8C
   and +0x90 with the frame delta) updates the camera screen words; per-entity +0x8E is
   re-derived from world-x − camera-x (see truck_resolution.json: "+0x8E (u16) CONFIRMED;
   zero sh/sw stores to 0x8E in the overlay code region; only init writes are spawn
   positions").

4. **The HP reading is the superseded mislabel** — `ps1play/agent/wagon.py:38`
   `HP_OFF = 0x8E  # verified HP field offset` and `entities.json → entity_table.entity0_hp
   = 0x800CA2F6` (= table base 0x800CA268 + 0x8E) are pre-correction labels; both are
   SUPERSEDED by `truck_resolution.json` (field +0x8E = screen-x). The real HP word is
   **+0xA4** (u16, 22 bytes later), which is why the two got conflated: `+0x8E-as-HP`
   probes watched a soldier's screen-x.

**Conclusion:** not per-entity-class. Every class uses +0x8E = screen-x; every class's
HP lives at +0xA4 (init values differ per class: 0x14 soldier-class, 1 = one-hit classes,
300 truck/chopper, 30 bomb, 0 = corpse/dead).

---

## Method note

- Corpus scan: regex over all 468 decompiled bodies for `+ 0x8e` / `+ 0xa4` (reads vs
  stores separated); state constants are stored handler ADDRESSES (0x800B4054…), not
  bare 16-bit IDs, which is why literal 0x4054 greps fail.
- Binary scan: capstone resync-linear disasm (139,465 EXE instrs / 27,331 ENEMY.BIN instrs);
  fingerprints: `sh ,0x8e(`, `sh/lhu ,0xa4(`, `lhu 0xa4 → subu/addiu/sra → sh 0xa4`.
- ENEMY.BIN VA mapping: VA 0x800A9268 = file 0xD180 (per entities.json overlays.enemy_bin).
