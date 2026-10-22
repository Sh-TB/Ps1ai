# Tool capability matrix — measured on the actual environment (Issue #6, Phase B)

Measured 2026-10-22, host: CPU-only headless Linux x64, no GPU, no X server
except `Xvfb` + Mesa software GL (`swrast`). Existing backend = in-process
`mednafen_psx_libretro.so` (Beetle PSX 0.9.44.1 df2b53b) driven by
`ps1play/core/host.py`.

| Capability | Existing backend (beetle/libretro) | emucap | PCSX-Redux | Ghidra + psx_ldr |
|---|---|---|---|---|
| Input/frame control | `TESTED` — frame-exact `core.run(n, buttons)`; deterministic replay proven bit-identical on Tetrade | `BLOCKED` (as control layer) — no libretro PSX frontend; standalone patched Mednafen only | `TESTED` — `-no-ui -run -iso`, Lua `GPU::Vsync` hooks (900-frame scripted session on real MSX) | N/A |
| Screenshot/observation | `TESTED` — `frame_rgb()`, RAM snapshots | Untested (needs its own process) | `PARTIAL` — Lua can read VRAM; not exercised this session | N/A |
| Checkpoint/replay | `TESTED` — `StateManager` save/restore; determinism control `ctrl=0` | Advertised (`save_state`/`load_state`) | Untested | N/A |
| RAM/register inspection | `TESTED` — `MemoryView` 2MB | Advertised | `TESTED` — Lua FFI `PCSX.getMemPtr()` read of 0x800CA2F6/0xEE518 on live MSX | `TESTED` (static) |
| Execute/read/write breakpoints | None (no debugger interface in our host) | Advertised (Mednafen PSX adapter) | Advertised (Lua breakpoints + GDB server) — `PENDING` next session | Static xrefs `TESTED` |
| Function/call graph | Existing index (re_index.sqlite, 15k records) | N/A | Runtime tracing possible | `TESTED` — **3,957 functions (EXE) + 468 functions (ENEMY.BIN overlay), callers/callees extracted** |
| Setup/build cost | Already integrated | Rust >=1.88 build or prebuilt core packages; separate process + patched Mednafen + retail PSX BIOS needed | `TESTED` — prebuilt Linux x64 zip (87MB, distrib.app Build 470); needs Xvfb+Mesa software GL; extracted + running in ~10 min | Ghidra 11.4.2 (437MB) + full JDK 21 (user-space) + psx_ldr extension; BinaryLoader import path ~4 min analysis |
| CPU/RAM overhead | Low (in-process) | Unknown | Software-GL GUI stack runs headless; 900 frames in <240 s wall | One-shot analysis; cached by hash |
| License | beetle GPL-2.0-or-later (unmodified external core) | GPL-2.0-or-later | GPL-3.0-or-later | Ghidra Apache-2.0; psx_ldr custom-free (verify before code reuse) |
| **Decision** | **Keep as normal gameplay backend** | **REJECT as control layer; possible future oracle** (differential vs beetle) | **INTEGRATE as debugging oracle** (external process; Lua/GDB watchpoints for MSX boss-HP hunt) | **INTEGRATE as static-analysis oracle** (per-hash cache) |

## Detailed results

### emucap — `REJECT` as control layer (`BLOCKED` for libretro)
- Rust toolkit with MCP control; PSX support = patched **standalone Mednafen 1.32.1** via NDJSON/TCP — no libretro adapter, cannot drive our in-process core.
- Would require: separate Mednafen process + retail PSX BIOS + rebuilding the control stack. No practical advantage over our proven in-process harness for gameplay; possible future differential oracle.
- Source-verified capability list (memory R/W, breakpoints, frame step, screenshots) — https://github.com/mcpads/emucap (adapters/mednafen README).

### PCSX-Redux — `TESTED`, decision: integrate as debugging oracle
- Prebuilt: https://distrib.app/pub/org/pcsx-redux/project/dev-linux-x64 (JS app; real asset URL extracted via headless browser; Build 470, 87 MB zip).
- Headless: `-no-ui -run -testmode -stdout -lua_stdout -iso <cue> -archive <zip(autoexec.lua)>`; requires `Xvfb` + Mesa software GL (SDL dummy driver rejected: "OpenGL support ... not available in current SDL video driver").
- Proof run on the real MSX disc: Lua autoexec executed, `GPU::Vsync` fired 900 frames, FFI read of validated HP word `0x800CA2F6` and flags word `0xEE518` (both 0 pre-gameplay — correct), `pcsx_exit()` clean shutdown under `-testmode`.
- Next: Lua/GDB watchpoints to capture the FIRST instruction writing the Iron Nokana boss HP store (Issue #5 BLOCKED line).

### Ghidra + ghidra_psx_ldr — `TESTED`, decision: integrate (static oracle)
- Ghidra 11.4.2 + user-space Temurin JDK 21 (apt only has JRE-style 21; Ghidra needs `javac`).
- Extension zip for 11.4.2 downloaded but its loader was NOT picked up by headless import even after install attempts (`Extensions/Ghidra/`, user `Extensions/` + marker). Worked via `-loader BinaryLoader -loader-baseAddr 0x80010000 -loader-fileOffset 2048 -processor MIPS:LE:32:default` instead. `PENDING`: get native loader working for EXE-header/PSYQ-GDT conveniences (psyq420.gdt etc. ship in the extension).
- EXE import+analysis: SUCCEEDED (622,592 B, sha256 `1508b532…`) — 3,957 functions; anchor `0x8002DB48` (spawn writer from death_path.json) confirmed as `FUN_8002db48` with caller `0x80030A9C` — cross-validates the existing static DB.
- ENEMY.BIN overlay: extracted from disc (LBA 2758, sha256 `809170c7…` = manifest match), code region file-off `0xD180..0x1C2C8` imported at live-verified VA `0x8009C0E8` — 468 functions. Probes: `FUN_800a41d8` (damage entry) exists exactly at the death_path.json address; `FUN_800a87f8` (dispatch) has **8 in-overlay callers** (`8009fafc, 8009fcb4, 8009fdcc, 8009f170, 8009edec, 800a0ab0, 8009f304, 8009f494`) — new evidence extending the death-path graph.
- Evidence: `/home/z/my-project/emu/tools/ghidra_evidence/` (functions JSONs + anchor probes; committed copies under `data/games/SLUS-01212/`).

## Backend compatibility finding (from the homebrew vertical slice)
beetle-psx + OpenBIOS never completes a kernel low-level pad poll for
PSn00bSDK homebrew (Tetrade): padbuff never appears in ANY state (unfilled
`ff ff…`, success `00 41 ff ff`, aborted `ff 41…`) after 600+ frames; no
button byte ever flips FF→F7 under any held button. OpenBIOS source
(`openbios/sio0/pad.c`): `alterUserPadData` only copies data for pad IDs
`0x41/0x23` (high-level path), and low-level `readPad` aborts on tight IRQ
timeouts. Retail-pad games (MSX) unaffected. Classified: **shared
backend/BIOS compatibility defect**, protected by an xfail regression test.

**Cross-backend reproduction (`TESTED` 2026-10-22):** the same Tetrade disc
under PCSX-Redux (which ships its own OpenBIOS build) with Lua
`PCSX.SIO0.slots[1].pads[1].setOverride(BTN.START)` held for two 300-frame
windows still shows no real padbuff (`SCAN held300f/held2_300f`: only
coincidental `00 04 xx xx` data bytes, btn values stable across press
phases — not `0xFFF7`). The defect is therefore **in the OpenBIOS kernel
low-level pad path itself (vs emulated SIO ACK timing), reproduced across
two independent emulators** (beetle 0.9.44.1 AND PCSX-Redux HEAD).
PCdrv-era/retail pad reading (MSX) is unaffected in both. Candidate future
fixes: OpenBIOS-side timing patch, or a plugin-declared compatibility patch
(patched-copy policy: local-only, never redistributed), or retail-BIOS
runners where legally available.

---

## Addendum 2 (2026-10-22) — boot gate SUPERSEDES the pad-defect diagnosis

**Root cause found (OBSERVED, decisive A/B):** every "no padbuff / no button
flip" negative above was produced by a game that had never actually run.
Unpatched homebrew discs (Tetrade, Nortis, PSXMC) **boot-loop inside the
OpenBIOS shello CDChecker**: identical cube animation and bit-identical frame
timelines across three different discs, game EXE never reaches RAM (~72 KB
nonzero after 900+ frames). Copying the 16 license sectors (0..15) from the
user's own retail disc into a LOCAL copy of each homebrew image unblocks all
of them (RAM 72 KB -> 555 KB; game loads; title screens render).

**With the game actually running, the beetle+OpenBIOS pad path works:**
- padbuff fills: `00 41 ff ff` at 0xBB120 / 0xBB142 (Tetrade's own buffers)
- buttons deliver: held libretro X -> btn word `ff ef` = `0xEFFF` = TRIANGLE
  (beetle mapping: RETRO X -> PSX TRIANGLE); START -> `f7 ff` = `0xFFF7`
- full input causality chain proven for Tetrade: START -> title -> menu,
  CROSS -> Marathon gameplay, piece responds to LEFT/RIGHT (visual diffs
  21.75 / 0.62 / 0.54; screenshots in the Issue #6 report)
- PSXMC (MIT) and Nortis (license-blocked) also boot and respond to input
  after the same local patch

Status changes:
- `SUPERSEDED`: "OpenBIOS kernel low-level pad defect on beetle" — the
  padbuff absence was a boot-gate symptom, not a pad-path defect.
- `STALE, PENDING re-test`: the PCSX-Redux-side scan (game ran there, yet no
  padbuff) — re-test under the license fix before drawing conclusions.
- `IMPLEMENTED`: scripts/make_homebrew_lic.py (local-only patched images;
  never committed) + tests/test_plugins_contract.py::test_real_tetrade_lic_
  input_causality (subprocess-isolated: beetle holds global emulator state,
  one clean boot per process).

Practical rule for the lab: **one beetle boot per process**; boot-gated
discs must be license-patched locally before any input-causality claim.
