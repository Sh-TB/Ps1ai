# Round 23 — two train wins (MSPSX RUNNING, BuzzyBee GAMEPLAY_CONFIRMED) + a PAL display-path root cause

Date: 2026-10-28 · Policy: 60% very-simple / 40% baseline. Internet research
authorized by the user; upstream sources/maps were the decisive accelerators
this round. Suite stayed 565 passed + 1 xfailed throughout.

## Simple-game track

### MSPSX (Minesweeper Plus) → RUNNING (1/1 boot, game #9 closes its rung)
R22 left exactly one rung: a CROSS reveal. Both disclosed failure causes
were fixed in one boot: (a) the correct button — ps1play "B" = PSX CROSS on
the beetle map (r22 pressed "X" = Triangle), (b) hold 40 frames > the ~33f
SPI poll cadence of the spicyjpeg driver. Result at cursor (1,1):
`revealed_total 0→1`, board byte flip @0xCD, cursor cell revealed under
layout **B_y192_x12** (off 0xCC: mine 0, neighbors 3), lost=0,
control_disable=0. No BFS cascade (single-cell reveal) — the honest minimal
closed loop. Image rebuilt from the v0.1 release, sha256 re-verified
bit-identical (d35a189b…a4c5fa), license sectors local-only. Verdict:
**RUNNING**. GIF: docs/evidence_gifs/r23_mspsx_reveal_running.gif.

### BuzzyBee (NDR008, MIT) → GAMEPLAY_CONFIRMED (game #10) + PAL root cause
The round's biggest train. Four boots of honest diagnosis before the win:

1. **Boot 1** (repo-EXE image): OpenBIOS shell cube → BLACK screen. Verdict
   honestly FAILED (the r23 script's BOOTED=True was shell-only and was
   retracted in the log).
2. **Boot 2 forensics**: EXE **is loaded** (main.c strings @0x8001FD10
   physical = 0x8001FD10 KUSEG; "PS-X EXE" header stripped as expected) and
   34 words tick — but the text-region check initially read ZERO because of
   an **indexing bug**: host `ram[]` is PHYSICAL (0x10000 == 0x80010000
   KUSEG); the 0x80010000 slice was out-of-bounds-empty. Corrected and
   disclosed.
3. Static RE (capstone + upstream map): `setScreenMode` compiles into
   **PAL-only code** — SCREEN_HEIGHT=256 stored unconditionally
   (@0x80011C24) and `SetVideoMode(1)` (@0x80011C44). Boot 1's repo image
   also lacked the CDDA track 2 the game plays at init (main.c:52
   `tracks[]={2,0}` → DsPlay(2,…)); the author's v1.1 scene image (sha256
   d5d7a629…f7acc32d re-verified) has it — **boot 3** on that image: still
   black, BUT the input state machine anchored cleanly (gameState 0x80058830:
   0→1 on START, 1→99 on SELECT, back on resume) — the game was alive behind
   a black display.
4. **Boot 5 (decisive)**: two-instruction game-side NTSC patch
   (SCREEN_HEIGHT 256→240; SetVideoMode 1→0), byte-verified in-disc,
   fully disclosed; rebuilt image with a 60s silence CDDA track 2. Result:
   **SCREEN_H=240 live (patch verified in-game), gameplay scene renders
   (vis-diff 122.4 on START), bee moves (vis-diff 20.6 on flap), score
   0x8005883C climbs +1/frame (143→205), gameState/bestScore map symbols
   cross-validate boot 3's set-algebra anchor exactly.** Verdict:
   **GAMEPLAY_CONFIRMED**. GIF:
   docs/evidence_gifs/r23_buzzybee_gameplay_ntsc.gif.

**Backend finding**: BuzzyBee is the program's first PAL-forcing game; the
PAL display path (SetVideoMode(1) + 256-line buffers) renders black on
beetle+OpenBIOS **while game logic and input keep running**. Any future PAL
game needs this same one-line NTSC patch or a backend-side investigation.
Patch and boot history are disclosed in manifest accepted[buzzybee]
(boots_used.json: 5 boots, every cap amendment — 2→3, 3→4, 4→5 — logged
BEFORE the run; boot 4's script crash after 400 real frames counted
honestly).

## Baseline track

### MSX stage-loader (r22 falsifiable plan) → PARTIAL: pause-UI hypothesis falsified
Boot 1-2: the r19 attract timings fired early (PRESS START lands ~f7000 on
this backend, not f4920); boot 2 still walked into M1 (NOW LOADING →
cutscene). Boot 3 (cap amended, disclosed): ladder hit M1 live (px 846,
php 136) — but the gate fired **during the opening cutscene** (moving Slug)
and the pause/census ran on the TIME OVER screen (the r18 mission-timer
death path; HUD countdown visible). Boot 4 (cap amended, disclosed; v2
gate = sustained php>0 + stable px): **real PAUSE reached** (php 120 held,
timer frozen at 59).

Findings:
- The visible pause screen is minimal ("PAUSE" + "PRESS START") — **no
  mission list**. The r18 hypothesis "the pause menu offers MISSION
  SELECT" is now **falsified for the arcade pause screen**; the
  RETRY/MISSION SELECT/CONTINUE/MISSION 1..6 string cluster must belong to
  another screen (next candidates: the post-TIME-OVER CONTINUE screen or
  OPTION paths).
- The r22 prime cluster still reacts to pause-screen DOWN: u16@0x800D4A6C
  280→490 then **+60 per DOWN** (scroll/cursor-y), byte 0x800D4A68 toggles
  0x54↔0x4C correlated with the "PAUSE" label visibility. Semantics:
  partial (UI layer), the r22 step-3 banner-prediction experiment stays
  pending until the real mission-select screen is located.
- Disc identity re-verified: MD5 37d9e1179a32661800e74858009a4f8b.
Boots: 4 for this train (caps 2→3→4, each disclosed before the run; one
boot-3 counter write-back bug repaired with a log note).

## Process record
- Third filesystem rollback wiped scratch/; every consumed artifact was
  re-fetched and **SHA-256 re-verified against the r21/r22 scout hashes**
  (MSPSX d35a189b…, BuzzyBee EXE 9b0bfc08…, v1.1 image d5d7a629…) — all
  bit-identical. MSX retail disc MD5 re-verified.
- The r22 discipline upgrades held: boot caps asserted inside scripts,
  orchestrator-only manifest writes (buzzybee accepted[] entry +
  round23_addendum), evidence written incrementally, three self-caught
  accounting bugs disclosed in the boot logs (indexing bug, crashed boot
  counted, stale counter literal).
- T4 (BKBS offsets + servo presses) was queued but not started — honestly
  deferred to r24 rather than half-run against the session budget.
- Suite: 565 passed + 1 xfailed. No game bytes committed.

## R24 plan
1. BKBS: one boot — active/hit/desat offsets + servo presses → PLAYING.
2. MSX: locate the real MISSION-SELECT screen (CONTINUE-after-TIME-OVER
   path first), then the r22 step-3 banner experiment.
3. PAL backend investigation (beetle source) — the BuzzyBee finding
   generalizes; PCSX-Redux cross-check as the oracle.
4. LostPlumber (MIT, 86 KB EXE, same BIOS pad class as BuzzyBee) — cheap
   next intake on the NTSC-patch recipe.
5. Poy Poy vision-first aimer + hearts counter → clean retire → WON bout.
