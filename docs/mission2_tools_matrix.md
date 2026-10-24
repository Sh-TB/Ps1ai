# Mission 2 Tool Research Matrix (Issue #9 §2 — Deliverable B)

Method: source-first (cloned repos, cited files), plus **live experiments in this
environment**. Ranked by *measured expected value for PS1Play*, not stars/features.

## A. emucap — verdict: `BLOCKED` (exact prerequisite documented)

- Architecture: Rust control server + patched Mednafen fork (37 patches, `emucap.cpp`
  socket client compiled in) + MCP tracking layer. Adapters: `adapters/mednafen/emucap.cpp`.
- PSX operations actually implemented (wire dispatch `adapters/mednafen/emucap.cpp:3447-4382`):
  frozen launch (pre-first-instruction), `set_input`/`press_buttons`/`tap`/`hold_until`,
  `run_frames`, `step_instructions`, pause/resume, atomic `probe` (load→advance→read),
  screenshot (PNG/base64), `read_memory(_batch)`/`write_memory`/`find_pattern`/`dump_memory`,
  `get_state`, digest-checked `save_state`/`load_state`, **value-conditioned exec/read/write
  breakpoints with pc filters + write-value injection**, MIPS `disassemble`, `watch_register`,
  `set_trace`, `call_stack`, experiment records (`run/log_evidence/log_intervention/compare_runs`).
- Client: no pip package; MCP stdio or a ~50-line stdlib TCP NDJSON client
  (auth off unless `EMUCAP_SESSION_TOKEN`+`EMUCAP_LAUNCH_ID`, `emucap.cpp:578-626`). Headless: yes.
- Build: needs its fork (g++/make/perl present) + `libsdl2-dev liblzo2-dev libmpcdec-dev
  gettext` (apt-available). Stock apt mednafen 1.32.1 is **not** compatible.
- **Hard blocker: retail `scph5501.bin` (NTSC-U BIOS) — the Mednafen PSX adapter cannot
  boot without it** (adapter README:48,62). Workspace has OpenBIOS + scph1001 (hash
  `c3dd31b3…` ≠ retail `924e392e…`, provenance unverified) + scph7502. We do not possess
  a legal scph5501 image; per operating constraints we do not download BIOS dumps.
- License: GPL-2.0-or-later (`LICENSE:4`). Running as a separate tool = no obligation on
  Ps1ai; copying code = GPL contamination.
- Setup cost estimate: ~90-120 min (fork compile dominant) **once BIOS exists**.
- Smallest future experiment (recorded for the day the prerequisite appears): write-breakpoint
  hunt on the MSX camera/entity-table candidates (`0x800C9A98`-relative overlay refs,
  pc-filtered) — the capability our Beetle in-process path structurally lacks.

## B. PCSX-Redux — verdict: `ADOPT_DIAGNOSTIC_ONLY (PENDING)` — live-tested this session

- **No GitHub releases/tags** (API count = 0); prebuilt Linux x64 zip distributed at
  distrib.app (Build 482, `PCSX-Redux-805e6dfa-linux-x86_64.zip`, 87.14 MB,
  sha256 `b22bda9b9b4d14cd…`). **Runs headless in our sandbox with zero missing libs** —
  the cmake blocker from the Task 5-a audit is bypassed by the prebuilt binary.
- CLI: `-no-ui -testmode -safe -interpreter -softgpu[-threaded] -bios -iso -loadexe
  -dofile -run -gdb[port]`. Lua: LuaJIT; API is the `PCSX.*` table (introspection dump:
  `mission2/pcsx-redux-bin/introspect_result.lua.txt`, 85 entries) — breakpoints
  (`addBreakpoint`), savestates (`createSaveState`/`loadSaveStateFromFile`), registers
  (`getRegisters`/`setGPR`), `getMemPtr` FFI (full RAM R/W), pad `setOverride`/`clearOverride`
  (`src/core/pad.cc:1623-1740`), events (`createEventListener("GPU::Vsync"|"Quitting"|…)`,
  `src/core/eventslua.cc:173-232`), CPU trace, VRAM/GPU dump, gdb server.
- Live capability proof (this session, scripts `redux_smoke.py` → `redux_adapter_probe5.py`,
  `redux_probe6_park.py`):
  - headless boot with OpenBIOS ✅ (`OpenBIOS detected (15e27ce3)`)
  - retail MSX CD mount ✅ (`CD-ROM ID: SLUS01212`)
  - shell disc-boot of both retail and homebrew images ✗ — OpenBIOS validates the disc
    (`*** Data is acceptable, booting now. ***`) then parks at PC `0x16C4`; same discs boot
    fine under Beetle+OpenBIOS → OpenBIOS-disc-boot gap specific to PCSX-Redux
  - `-loadexe` shell hijack ✅ (`Hijacked shell, loading … Successful: new PC = 80017970`);
    Tetrade game init runs (`PS-X Control PAD Driver`, `Game Start!`) at ~60 fps headless
    (interpreter + threaded softgpu, 1020 frames in 17.3 s wall)
  - gameplay execution PENDING: Tetrade parks in wait loops with **byte-identical WRAM
    dumps across input arms** (`wram_a_idle…d_end` sha256 `e99e4cc663e3501f` ×4 — pad
    `setOverride` causality not reachable through the parked loop); pcsx logs
    `psxgpu: VSync() timeout` → vblank-IRQ delivery to the guest is the prime suspect
  - MSX via `-loadexe`: PS-EXE parses (`t_addr 80010000, pc0 80082A44`), PC reaches the
    entry stub then faults `Unaligned address 0x00006dad in LW from 0x80082a4c` — the
    Psy-Q `_start` reads `($v1+0x5f44)`, i.e. the **retail-kernel Exec() v1 record** that
    the OpenBIOS hijack path does not provide (disassembly evidence recorded)
- License: GPL-2.0. Separate-tool use = no obligation; never copy code into Ps1ai.
- Setup cost measured: download 91 MB + extract ≈ 4 min (vs "cmake build blocked" before).
- Next smallest experiment: attach `gdb`-server (`-gdb`) or a Lua breakpoint/watchpoint on
  the Tetrade wait-loop PC to name the awaited signal; try a retail BIOS if ever available.

## C. jev-game-agent — verdict: `REJECT as dependency` / `ADOPT ideas (mechanisms only)`

- Target: Super Mario Bros. PAL/NES on BizHawk 2.11.1 (Lua bridge); platform table has **no PSX**.
- **Paid API dependency: YES** (`api.typesafe.ai/v1/systemone`, `TYPESAFE_API_KEY`,
  `run_lookahead.py:39`, `campaign.py:595,872-874`) — excluded by operating constraints.
- **License: NONE** ("No project license has been selected", README.md:400) — mechanisms
  only, never copy code.
- Transferable mechanisms (all verified in source):
  1. **Shadow-emulator lookahead + predicted-death filtering** — `src/jev_games/lookahead.py:56-133`
     (per-candidate savestate replay in 4-frame slices with RAM fingerprints,
     first-landing/death stop, 8-frame neutral coast test) + `:18-20,124-125` eligibility gate.
     Maps to `ps1play.save_state/load_state` + verified sensors: simulate candidates,
     execute only non-fatal ones. → implemented in M8 (Track C algorithm).
  2. **Checkpoint action-ban + repeat-death walk-back** — `campaign.py:297-302` (banned
     actions per node), `campaign.py:314-353` (`death_checkpoint`: same checkpoint + same
     inputs + same death ⇒ re-plan ≥128 px earlier). Maps to our death recovery.
  3. **Bounded factual death episodes + frame-accounted stall watch** — `death_memory.py:15-108`,
     `recovery.py:5-30` (600 executed-frames / 24-px window). → upgrades our JSONL ledger (M3).

## D. Metal Slug X Recomp projects — verdict: `ALREADY ADOPTED (Task 5-a)`, evidence re-verified

- `TechnicallyComputers/Metal-Slug-X-Recomp` (eddccb54): same serial SLUS-01212 + same disc
  MD5 `37d9e117…` as the user's disc; analysis JSONs (edges 7,720 / refs 5,501 / indirect 261 /
  symbol_addrs 1,642 / widescreen sites with evidence) merged into
  `data/games/SLUS-01212/psxrecomp_external.json` (15,125 metadata records, commit `6351d70`).
  Pipeline ingests functions.tsv only — the JSONs are *unused headroom* for M5/M6.
  No LICENSE file — facts-only reuse, never copy files.
- `alexbeavs-ps1-ports/metal-slug-x-recomp` (4fb558b, GPL-3.0): same serial+MD5; seeds 1,640
  rows merged as seeds. Identity cross-check only.
- Use in this mission: symbol/edge metadata accelerate M5/M6 root-cause targeting (function
  neighborhoods around known addresses), no runtime is built (mission forbids a recomp project).

## E. Other candidates screened

| Candidate | Verdict | Reason |
|---|---|---|
| ps1recomp `tools/pcsx_redux_mcp` (GPL-3) | `KEEP_AS_OPTIONAL` | MCP+Lua driver for Redux — useful only once Redux gameplay path matures |
| ps1recomp `psyq_signatures.toml` (1.1MB/3,463 hashes) | `ALREADY ADOPTED` (Task 5-a) | `scripts/psyq_hash_match.py` → `psyq_labels.json` (5 matched, 4 ambiguous) |
| ghidra_psx_ldr | `BLOCKED` | Ghidra not installed (Java 21 present; ~400MB + build) |
| ps1toolkit | `KEEP_AS_OPTIONAL` | disassembly QA scripts, no LICENSE |
| psx_ret_toolchain | `REJECT` | README-only link map, nothing integrable |
| Beetle PSX libretro (current) | `ADOPT` (unchanged default) | proven gameplay path; mission §0 forbids replacement |

## Ranked by measured value for the remaining mission

1. **Beetle in-process + differential RAM forensics** (existing) — proven, drives M5/M6.
2. **PCSX-Redux prebuilt** — diagnostic-only; the ONLY zero-build source of real
   breakpoints/watchpoints/symbols/VRAM for PSX in this environment; unblocked this session.
3. **jev mechanisms** — lookahead/ban/walk-back ported as pure Python on our savestates (M8).
4. **emucap** — highest potential capability ceiling, blocked on a legal scph5501 BIOS.
5. **MSX-Recomp metadata** — accelerates targeting; already merged.

Tool-value ledger (§4 format, measured this session):

| Track | Task | Cost | Result |
|---|---|---|---|
| Manual baseline (Beetle) | boot+input+state causality on 5 games | done in prior sessions (evidence preserved) | works, no breakpoints |
| Assisted (Redux) | headless boot + Lua automation + hijack + pad API | ≈ 3 h wall this session | works up to game init; gameplay park PENDING |
| Assisted setup | cmake build of Redux (Task 5-a plan) | blocked before; **now bypassed** by prebuilt zip (4 min) | capability delta: breakpoints/symbols/trace |
| `Net tool value` | — | — | positive **only** in diagnostic role until the IRQ/v1 gaps are closed |
