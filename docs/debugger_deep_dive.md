# Debugger Deep Dive — PCSX-Redux + Ghidra (Issue #9, 2026-10-24)

Directive: "deeply examine the two debugger programs — they must help a lot."
Scope: PCSX-Redux (prebuilt Build 482, headless) and Ghidra 11.4.2 headless with
`ghidra_psx_ldr`. Everything below is TESTED/OBSERVED with artifacts; verdict
changes are explicit.

## Part 1 — PCSX-Redux: the "gameplay park" verdict is OVERTURNED

Mission 2 recorded `ADOPT_DIAGNOSTIC_ONLY (PENDING)`: "Tetrade parks in wait
loops with byte-identical WRAM dumps across input arms". The deep instrumentation
run this session (scripts `redux_deep1b..1n`, artifacts under
`scratch/redux_deep/`) disproves the park:

| Evidence | Reading |
|---|---|
| vblank counter (kernel global at `[gp-0x7fc4]` = 0x800AAB3C) | **+1 per frame** (0x05→0x23→0x41→0x5F over 90 frames) |
| exception-vector exec breakpoint (0x80000080) | **~92 hits / 120 frames** — the ISR chain runs every frame |
| CPU cycle counter | advances ~564k cycles/frame throughout |
| pad button word at 0x800BB122 | **flips with Lua `setOverride`** (see below) |
| PC sampled at the vsync instant | always inside 0x80015410 (Psy-Q `VSync()` poll loop) — a **sampling artifact**: at every frame boundary a normal game IS inside its VSync wait |
| "psxgpu: VSync() timeout" print | once at boot, before the first vblank ISR registration — benign |

The Mission-2 "byte-identical WRAM" observation hashed 0x80010000..0x80020000
(static EXE code + libc data) and the "input arms" used the WRONG pad-override
argument (root cause below).

### Root cause of the false "input causality unreachable": pad API argument semantics

`PCSX.SIO0.slots[1].pads[1].setOverride(n)` takes a **button bit INDEX**
(`button = 1 << n` inside pad.cc:1707-1722); the transmitted word is active-low.
Mission 2 called `setOverride(BTN.START)` where the constant is the **bitmask
0x0008** → `1 << 8` = bit 8 = **L2**, never START. Proof this session:

- `setOverride(3)` (START): scan-diff of u16 0xFFF7 across 1 MB RAM
  held-vs-released → **2 locations: 0x800AAB30 (libc pad mirror),
  0x800BB122 (pad buffer button word)**.
- `setOverride(0x0008)` (L2): no diff.

**Verdict change: pad input delivery under headless Redux is PROVEN working
end-to-end (override → SIO → guest pad buffer).**

### API/engineering gotchas (all source-verified, all hit live)

1. **Breakpoints are one-shot unless the invoker returns `true`**
   (`debug.cc checkBP`: `if (!triggerBP(...)) delete bp;`). Returning `false`
   = DELETE, not "don't pause". All counting watchpoints must return `true`
   and never pause.
2. **`-debugger` is required** or `addBreakpoint` silently never triggers
   (pcsxlua.cc:56-61 warning).
3. **`getScratchPtr()` = `m_hard`**: the hardware register block is reachable
   from Lua FFI — I_STAT at +0x1070, I_MASK at +0x1074 (the Mission-2 probe
   failed because it tried to read 0x1F801070 from the RAM pointer).
4. **CP0 via Lua cdef is `union { r[32] }`**: Status = `r.CP0.r[12]`,
   Cause = `r[13]` (the C++ named-union fields don't exist in the cdef).
5. **Per-frame `getRegisters()` from a GPU::Vsync listener segfaults** the
   emulator (deterministic, deep1i); a 60-frame cadence is safe (deep1h).
6. **Exec breakpoints at kernel-low addresses during the DISC boot crash**
   the emulator (deep1j, deterministic) — breakpoints are safe under
   `-loadexe` (Tetrade evidence) but not during the OpenBIOS CD boot path.
7. **Stale `/dev/shm/pcsx-redux-wram-*` files from SIGKILLed runs SIGBUS the
   next startup** — remove them before each run (added to our harness).
8. Lua cdef for `psxRegisters` exposes `rawPC` (proxy `pc`), `GPR.r[0..33]`,
   `CP0.r[0..31]` only.

### MSX boot blockers — root-caused, both narrow

**Disc boot** (shell path): the boot stalls in OpenBIOS's synchronous CD
command wrapper (RAM kernel, loop at 0x16CC — disassembled from a live RAM
dump, `deep1l_ram.bin`):

```
0x16b0: addiu a0,zero,2        ; expected success value
0x16bc: sb    zero,0x1800(a1)   ; CD index reg
0x16c4: sb    v0(0x0A),0x1801   ; CD command
0x16cc: lw    v0,0x5f74(a3)     ; a3=0: kernel global [phys 0x5F74]
0x16d4: beq   v0,a0 -> ok       ; 2 = done
0x16dc: beq   v0,a1 -> fail     ; 1 = failed
0x16e8: bnez  v1(30000), 0x16cc ; bounded retry, then re-issue forever
```

Under Redux the CD completion IRQ never reaches the guest (I_STAT bit2 never
observed), so `[0x5F74]` stays 0. A memory-only nudger writing `2` was consumed
(90+ commands) but the boot still cannot complete — the command responses/data
themselves are missing, not just the flag. Next step recorded: intercept the CD
result path (watch `[0x5F74]` writers + CD response FIFO reads) or patch the
OpenBIOS CD completion handler — a bounded, known-address task.

**`-loadexe` path**: MSX `pc0` = 0x80082A44 lands on `addiu v1,v1,0x5f44`
whose retail contract is **v1 = 0 (kernel globals base)** — the same globals
block the CD wrapper uses (phys 0x5F44/0x5F74). The shell hijack leaves
v1 = 0x3E8C → `lw v0,(v1)` faults at 0x6DAD (the historical fault). This
session: breakpoint at the entry (safe under -loadexe), **in-RAM patch of the
pc0 word to `lui v1,0` (0x3C030000) succeeded** ("PATCHED new word=3c030000",
`deep1n4`), the stub proceeds past the read — full boot still wedges silently
after; next step: CPU-trace the post-entry flow to find the second gate.
Header note: the SNK PS-EXE variant stores t_addr at +0x18 (Tetrade agrees;
`data_start`=0 in the header is not what Redux parses).

## Part 2 — Ghidra: full ENEMY.BIN overlay decompile + new sensors

Toolchain restored headless in this session: Ghidra 11.4.2 + ghidra_psx_ldr
extension + headless JDK shim (LaunchSupport requires a `javac` executable —
a documented shim step; project `MsxLab4` holds both analyzed programs:
`/SLUS_012.12.full` (3,957 functions) and `/enemy_code_region.bin`
(468 functions, live mapping 0x8009C0E8)).

**Deliverable: `data/games/SLUS-01212/ghidra/overlay_decompiled.json`** —
decompiled C for **468/468 overlay functions (467 with C bodies)**, with
callers/callees per function. This is the enemy-AI codebase the mission has
been probing blind.

### Cross-validated entity geometry (static ↔ live)

The decompiled overlay references the entity root pointer hub `_DAT_800c9a98`
(1,992 reference sites / 1,143 EXE functions reference it) with the SAME field
offsets we verified live: `+0x8E` s16 (HP; matches live HP windows), `+0x92`
u16 (X position; the targeting code compares slot X vs player X through it),
`+0x7E` height word. The target-selection function 0x800A4588 iterates slots
0/1, computes |Δ| in +0x8E and +0x92, and keeps the closer candidate —
thresholds |Δ|<0x21 (same-lane), <0x20; the EXE-side interaction function
0x80067E78 uses ±0x2F (47 px) and <5 px close-range gates plus a
random-per-mille gate (1125/100).

### New agent sensor: the section walker (D7 path)

The decompiled scroll/camera walker FUN_80021898 names the section state
machine the D7 clamp lives in:

| global | meaning (from the decompiled flow) |
|---|---|
| 0x0EB598 / 0x0EB59C | scroll X / Y (live-verified earlier) |
| **0x0EB5F4** | u16 section/state id (walker branches on 0x9, 0xE, 0xF) |
| **0x0EB5D0** | u16 flags: bit0 = advanced-this-step; **0x200 = final state complete** |
| 0x0EB5D4 | u16 progress accumulator (also the step limit) |

Implemented as `scan_section(mem)` in `ps1play/agent/combat.py`
(schema `ps1play-section-scan/1`, 7 tests, suite 427+1xfail green).
Honest labeling: OBSERVED-from-decompile semantics; the state numbering is
per-section and must be correlated live before any policy branch consumes it
(read-only sensor; never a safety assertion).

## What remains (ranked)

1. **Live correlation run** for `scan_section` from `chopper_ckpt`: log
   state/flags/progress across a clamp pin + release; the state that flips at
   release IS the D7 unblock signal.
2. **Redux MSX `-loadexe`**: CPU-trace the post-entry wedge (bounded: the
   trace API + entry patch are both proven this session).
3. **Redux disc boot**: CD result-path interception at the `[0x5F74]` writer.
4. Overlay damage-path decompile quality: the standalone overlay program
   truncates cross-module calls (`halt_baddata` at EXE-call boundaries) —
   merge the overlay bytes into the EXE program at 0x8009C0E8 for one
   unified decompile (bounded Ghidra task).
