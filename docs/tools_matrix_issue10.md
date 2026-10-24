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
