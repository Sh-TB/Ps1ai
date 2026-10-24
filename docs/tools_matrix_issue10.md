# Issue #10 — Tool Matrix Addendum (decompilation / recompilation / debugger benchmark)

Scope: this addendum extends `docs/tools_matrix_issue6.md` and Issue #9's Deliverable B matrix with the measurements made during the Issue #10 mission (Gates A-C). Ranked recommendation per mission §5/§12. Evidence: comments on Issue #10, `scripts/issue10_gateb_probe.py`, `work/msx_recomp/evidence/issue10_gateB/` (local), commits `6580c21`/`68c079a`/`24bf036` (debugger deep-dive + D7 pin) and `fab6538` (Gate B/D).

| # | Tool | Category | License | Headless (CPU-only) | Tested on | Time to first useful result | Measured value | Recommendation |
|---|------|----------|---------|--------------------|-----------|----------------------------|----------------|----------------|
| 1 | Ghidra 11.4.2 + ghidra_psx_ldr (headless) | static decomp | Apache-2.0 / MIT mix | YES (project reopen + script) | SLUS_012.12 EXE + ENEMY.BIN overlay | minutes when the built project is reused; ~1 h one-time (download + import + analysis, #6) | full overlay decompile 468/468 funcs; writers of the system bitmask identified (FUN_80072950/FUN_8006d0cc); entity comparator FUN_80067e78 with thresholds 0x21/0x2F/5 cross-validated vs live probes | **ADOPT** (primary static tool) |
| 2 | PCSX-Redux HEAD (AppImage, Lua API) | dynamic debugger | GPL-2.0 | YES (proven on real disc) | MSX real disc; Poy Poy menu; park verdict experiment | first result in one session (#6 Phase B: Vsync 900f + FFI HP read) | park verdict OVERTURNED (guest alive, pad delivery proven end-to-end incl. setOverride bitmask-vs-bit-index bug); MSX disc-boot blocker root-caused (OpenBIOS sync-CD poll of kernel global @phys 0x5F74); -loadexe v1=0 convention patched+verified | **ADOPT** (primary dynamic tool) |
| 3 | re_index.sqlite + gkb_query/overlay_index (in-repo KB) | pipeline glue | repo-internal | YES | SLUS-01212 + overlay | instant (already built) | 4,915+331 functions, 9,664 edges, 11,515 data refs queried per-question in seconds | **ADOPT** (already integrated) |
| 4 | Observe-only savestate probe harness (Beetle, in-repo) | runtime sensor validation | repo-internal | YES | issue5_m1_start anchor | minutes per question | 3/3 bit-identical runs (SHA f01726561815); no-input control exposed the '+0x8E=HP' mislabel; menu-freeze vs stuck discrimination now unit-tested | **ADOPT** (evidence workhorse) |
| 5 | PsyQ signature DB (ps1recomp toml, 3,463 hashes) | symbol recovery | GPL-3 (data reused as facts) | YES | SLUS_012.12 | minutes (script exists, #5) | 5 matched + 4 ambiguous labels; low yield but zero-build | KEEP AS AUXILIARY |
| 6 | m2c / maspsx / psyq2elf | decomp quality | OSS | not yet tested | - | - | candidate for readability upgrade of the damage/AI functions; bounded experiment next | EXPERIMENT FURTHER |
| 7 | radare2 + r2ghidra | quick static queries | GPL | not installed | - | - | would cut per-question latency vs headless re-runs; install blocked only by package availability | EXPERIMENT FURTHER |
| 8 | PS1Recomp analyzer (function extraction, no port) | recomp tooling | GPL-3 | partially (cmake absent) | SLUS-01212 (metadata merged #5) | minutes for metadata | analyzer outputs (edges/refs/indirect 15,125 records) already feeding the KB; full recomp build REJECTED (cmake + runtime patches + no time-box justification) | KEEP AS AUXILIARY (metadata) / REJECT (full port) |
| 9 | PSXRecomp / RecompOne (full native port) | recomp | OSS | NO (cmake missing) | - | - | hours-to-days of patching for no gameplay decision value today | **REJECT** (documented per §11) |
| 10 | emucap | capture | OSS | n/a | - | - | no libretro PSX backend (#6) | **REJECT** |
| 11 | DuckStation / no$psx | debuggers | GPL-2 / proprietary | n/a | not installed / ineligible | - | dynamic work rides on PCSX-Redux; revisit only if a Redux blocker appears | KEEP AS AUXILIARY (future) |

Workflow comparison (Gate C, same question family: entity-field semantics + stuck-vs-menu discrimination):

| Condition | Emulator frames consumed | Emulator launches | Wall-clock | Correctness outcome |
|---|---|---|---|---|
| A: runtime-only (historical, #3-#5 records) | >=60,000 across sessions (entity_probe 18,810 f + route runs 21,000 f each + A/B runs) | many | multiple sessions | '+0x8E=HP' label survived untested; flags read coarsely (0xFF/0x1); v1 progress test false-rejected the camera word |
| B: static-assisted (today, Issue #10) | 3,260 (3 probes x ~1,087 f) | 3 | ~40 min incl. tool re-verification | bitmask structure identified; no-input control contradicted the HP-only explanation; scroll label retired; sensor validated 3/3 |
| C: dynamic-debugging (session of `6580c21`) | bounded (park experiment + pad probes) | few | one session | park verdict overturned; disc-boot root cause; -loadexe convention fixed |
| D: combined (sensor -> policy -> live A/B) | pincorr1: 40 chunks live-validated, 0 deaths, +400 score | 1 per trial | one session | D7 instrument pin wired + live-validated (`24bf036`) |

Honest caveats: condition A wall-clock is reconstructed from committed evidence timestamps (historical, not re-measured); today's probes are deterministic from a savestate anchor and re-runnable via the committed script; the '+0x8E' decay-without-fire signature is CONFIRMED as a runtime signature (3/3 identical) but its semantics (HP vs per-entity timer) remain OBSERVED and must be reconciled with the hp re-confirmation from `6580c21` (slot 14 vs slots 0-3 may behave differently).

## Addendum 2 — m2c measured head-to-head (source-recovery readability benchmark)

The user asked how much the "convert the game to source" tools actually help read the game, with time/cost/reliability measured. Executed per §11 (smallest discriminating experiment): `scripts/m2c_overlay_decompile.py` regenerates capstone-based GNU-as for every ENEMY.BIN overlay function (live-verified mapping VA 0x8009C0E8 ↔ file offset 0xD180) and runs matt-kempster/m2c on it. Committed outputs: `data/games/SLUS-01212/m2c/` (7 showcase functions + metrics JSONs; full-corpus C kept local, sha256 recorded in `full_corpus.json`).

Same-corpus (468 overlay functions), same machine, CPU-only:

| Metric | m2c (+ capstone emitter) | Ghidra headless (committed corpus) |
|---|---|---|
| Functions decompiled to usable C | **405/468 (86.5%)** after delay-slot repair (was 323/468 before; 63 residual failures are cross-function branch targets) | 73/468 clean (15.6%); 276 with WARNING comments; 119 contain `halt_baddata` (broken control flow) |
| Time | 145.8 s total, 0.31 s/function, re-runnable | one-time ~1 h setup + batch analysis (earlier session); re-runs need project reopen |
| Setup cost | `git clone m2c` (1 s) + 150-line Python emitter (committed) | ~400 MB download + ghidra_psx_ldr extension + project import/analysis |
| Correctness spot-check | FUN_800a41d8 output matches raw bytes exactly (verified instruction-by-instruction) | FUN_800a41d8 output is `halt_baddata` garbage (misaligned analysis) |
| Output shape | compact C with `unkXX` field offsets, real control flow (if/else, no gotos in targets) | verbose; often truncated control flow on this overlay |
| What the other does better | - | caller/callee graph, xref browser, interactive renaming, EXE-wide view |

Game-reading yield from the m2c pass (new semantic evidence, all OBSERVED/static, needs runtime confirmation before policy use):

- FUN_8009de68 (damage path): compares entity field +0x8E between two entity-table entries, encodes the comparison into +0xEA/+0xEB, then dispatches on the result — `< 9` → handler call with arg 0x11, else sets +0xF4 |= 2, calls with arg 0x12, writes state-handler pointer +0x0 = 0x800AB094 and tail-calls it. This is a damage/transition state machine using the SAME +0x8E field the runtime probes watch.
- FUN_800a41d8 (damage-entry anchor): reads entity +0x28 flag bit 0x80 → early-exit handler pair; else calls 0x800af1b0 and on success retargets +0x0 = 0x800151DC (EXE-region handler).
- FUN_800a4588: initializes entity fields (+0xB6=0, +0x26=0xFF, +0x66=0x100, +0xA8=0, +0x7A-=8, +0x7E+=0x12) and retargets +0x0 = 0x800B179C — per-entity state transition.
- The entity hub pointer `*(void**)0x800C9A98` is referenced by 361/468 overlay functions — now directly readable per-function in C instead of via raw `lw -0x6568($s0)` patterns.

Answer to "which tool converts the game to source": no tool recovers real source; m2c emits clean per-function C for 86.5% of the overlay in 146 s at zero cost and is the best readability tool for targeted questions; Ghidra remains ADOPTED for cross-references and the EXE; full native recomp ports stay REJECTED (no decision value). New candidates logged from the October 2026 landscape sweep (not installed): TDR (PSX-EXE→ELF + PsyQ .SYM converter for Ghidra, GPLv3), DrMefistO/OriginalPSP PSX Loader (Ghidra alternative loader), RetDec (usable via ELF conversion), decomp.wiki PS1 platform page (maspsx/psyq2elf/psyq-obj-parser/xsig), and 214 public PS1 decomp/disassembly projects catalogued by the community lists — the open-source ones (REDRIVER2, SotN, Silent Hill) remain calibration references only, closed-source titles stay the priority.
