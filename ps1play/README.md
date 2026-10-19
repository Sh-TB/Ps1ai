# PS1Play v0.5 — AI agent that plays PS1 games by reading RAM

> **v0.5 (this session): Mission-1 assault, LEGAL INPUTS ONLY.**
> `scripts/run_mission1_legit.py` = zero cheats / zero memory writes /
> zero rewinds during the run; savestates only for read-only calibration
> probes and checkpoints. 17 policy iterations root-caused six distinct
> blockers (see `download/ps1play_v4_mission1/mission1_report.json` and
> the evidence PNGs):
>   1. noisy entity slots -> perpetual threat-hopping deaths
>   2. 1-frame jump taps cannot clear obstacles (hold B ~13f)
>   3. keepalive false-positive during camera-locked fights -> START = PAUSE
>   4. fixed 3-tap recovery pauses the game right after the continue
>   5. the ATTRACT DEMO mirrors its own inputs + churns 200k+ and fooled
>      every gate -> self-play guard (pad must mirror 0 when idle)
>   6. free-scrolling jumps land the player ON the scenery truck
> Empirically proven with `scripts/zone_lab.py` (identical savestate,
> tactic grid): the soldier truck IS destructible — left-fire + grenades
> shred it in ~1-2s and the camera unlocks. HUD score reached 4300 and
> 2 POWs freed in evidence runs; bot reliably crosses canyon -> market ->
> village (~35% of Mission 1) every life. Remaining wall: surviving the
> village bomber-chopper + soldier-truck section long enough — all
> tactics win in the lab; sustaining them live is the next iteration.


Headless (no GPU / no X11) PS1 emulation + a game-agnostic agent that
**plays by analyzing emulated RAM bytes** (zero pixels for decisions,
zero LLM tokens at runtime), with **real reverse-engineered game
knowledge** and **GameShark-grade perception**.

Proven end-to-end on `Metal Slug X (USA)` (SLUS-01212), Beetle PSX core,
~200-330 fps headless.

## Architecture

```
ps1play/
  core/host.py        libretro ctypes frontend: software rendering, joypad
                      injection (LEGAL input only), live 2MB RAM view,
                      savestates (resume anywhere)
  core/memory.py      MemoryView / digests / diffs
  agent/perception.py PerceptionGuard: finds the gameplay-data cluster
                      live (bombs anchor by grenade event) and keeps the
                      Invincible address freeze-verified
  agent/gameshark.py  FULL PSX GameShark/PAR engine: parse/apply per-frame
                      (hardware behaviour)/freeze/verify with event proofs
  agent/worldmodel.py Universal entity discovery: enemies / bullets /
                      items / player anchor — pure numpy behaviour analysis
  agent/policy.py     SemanticPolicy: dodge bullets > shoot enemies >
                      grenade clusters > eat health > pick items > advance
  agent/memscan.py    RetroArch-style read-only cheat finder
  plugins/base.py     per-game plugin (boot map, features, policy)
  re/                 STATIC RE artifacts (see below)
scripts/
  extract_exe.py      pulls SLUS_012.12 (PS-X EXE) from the .bin
  extract_modules.py  pulls the runtime overlays (ENEMY.BIN, MISSION.BIN...)
  static_re.py        disassembles the exe (capstone), builds the global
                      xref map, infers struct field clusters
  dump_asm.py         dumps the real functions: pad reader, score add,
                      hit-slot/collision
  mission.py          the 'do we actually control the game' gate
                      (pad-mirror toggle + world-churn, reload recovery)
  verify_gs_live3.py  GameShark address verification chain (event proofs)
  run_semantic2.py    THE full session: boot -> enter -> gate -> anchor
                      -> GS assist -> entity discovery -> semantic play
  diag_*.py           focused experiments (action diffs, continue screen)
```

## What the static reverse engineering proved (the game as source)

* `SLUS_012.12`: 606 KB PS-X EXE @ 0x80010000, entry 0x80082A44.
* **Pad array @ 0x800D4948** (16 code xrefs): 8-byte records; P1 buttons
  word = 0x0D4948; live-verified bits: RIGHT=0x0020 LEFT=0x0080
  UP=0x0010 DOWN=0x0040 (exactly the PSX standard). Frozen on menus —
  used as the definitive "are we in control" gate.
* **Score P1 @ 0x800EE318** (9 code xrefs), POW @ 0x80087A78 (4 xrefs).
* The gameplay cluster (hp/ammo/bombs/lives/timer/weapon — the addresses
  the published GameShark codes use) is NOT static in our environment:
  it is dynamically placed and MOVES per boot and per mission-reload.
  The internal layout matches the published codes exactly, so one
  event-verified anchor (bombs: exactly -1 per grenade, twice) plus a
  per-instance delta translates the whole cluster. Player HP gets its
  own freeze-verified anchor (the freeze test: the address that cannot
  drop while the player survives the stab window IS the player's hp).
* Runtime overlays from the ISO: ENEMY.BIN 115KB (loaded verbatim —
  found in live RAM by pattern match), MISSION/BONUS/RANKING/TITLE...
  This is why published addresses miss: overlay placement differs.
* Hit-anywhere GameShark codes target static hitbox tables
  (0x80085870 passed as an argument to a collision function — dumped).

## The GameShark guarantee ("codes must work 100%")

`agent/gameshark.py` implements the real thing:
* parse `8xxxxxxx yyyy` / `3xxxxxxx 00yy` / joker `D0` / `A0` codes
* apply EVERY FRAME while enabled (hardware GS behaviour)
* freeze codes (cheat-engine equivalent) — event-verified:
  bombs frozen -> grenade throws never decrement (proof logged)
* published code-patches are revision-checked before applying
  (pre-patch bytes must be a MIPS branch) — our dump differs from the
  gamehacking.org revision, so data addresses are re-derived live
  (see above) instead of blindly trusted.

## Run it

```
python3 scripts/run_semantic2.py                 # GS-assist semantic run
SEM_ASSIST=0 python3 scripts/run_semantic2.py    # legit play only
SEM_CHUNKS=450 python3 scripts/run_semantic2.py  # longer session
python3 scripts/verify_gs_live3.py               # GS verification chain
python3 scripts/static_re.py                     # rebuild source map
```

Requires: the game .cue/.bin and BIOS SCPH-5501 in ps1-test/emu
(not included here); core `mednafen_psx_libretro.so`.

## Session results (v0.4)

* boot -> adaptive menu navigation -> Mission 1, fully headless
* input gate: pad-mirror + churn (zero false positives in combat)
* perception anchors with self-healing after every mission reload
* GameShark assist: Invincible + Infinite Bombs (freeze codes,
  re-anchored and re-verified after reloads)
* WorldModel: enemies/bullets/items slots discovered live per boot
* SemanticPolicy kills registered on the real score counter (+100 kills)
* checkpoints (savestates) + resume; PNG evidence each 25 chunks

## Honest limitations / next steps

* Mission 1 is not reliably cleared yet: the policy still falls into
  pit sections (y-coordinate dodge/jump planning is the next step) and
  phantom item slots occasionally divert walking.
* Action buttons (Y/A/B) map to a different pad word than the D-pad —
  to be located the same way (probe + disasm around 0x80015714).
* Entity slot classification is heuristic; the static entity-table
  layout (from ENEMY.BIN disasm) will make it exact.
