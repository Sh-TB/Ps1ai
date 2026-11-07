# R68 ROUND REPORT — the +500 n≥2 goal MET, the zero-overlap
# discriminator RESOLVED, the R67 truck-kill claim corrected

Round: **R68** · the capsule lever R68 executed verbatim · the
evidence-driven loop (no WSP/Qwen — the owner-rejected method stays
rejected; the post-mortem is on issue #9).

## 1. The experiment track — the third +500 attempt (the ledger cap
3, disclosed pre-run, 3/3 spent)

* **Boot 1 — the env probe** (`scripts/r68_env_probe.py`): the
  anchor `issue5_m1_start` (Oct 20) restores alive on this machine
  (px 258.6, score 0 — the R66/R67 record values).  The SIXTH
  sandbox-rollback disclosure: the r66_frontier_a/b states are
  LOST (never committed — no-game-bytes); the capsule contingency
  (a rebuild boot, disclosed) applies.
* **Boot 2 — the stage-1 frontier rebuild** (`scripts/r68_rebuild.py`):
  the R47/R66 recipe verbatim through `r66t1.do_stage1` (the
  output paths re-pointed at the r68 evidence tree — the disclosed
  harness patch).  Outcome `frontiers_saved`, frontier_px
  **1254.8 = the R66 record EXACTLY** — the determinism dividend
  is now **7-for-7** across the sandbox rollbacks (px 1224.9 /
  1254.8, score 6702).
* **Boot 3 — the pass-B hunt** (`scripts/r68_passb_hunt.py`):
  `r66t1.do_stage2(only="b")` — THE R66 PASS-B CODE PATH ITSELF,
  the corridor gate as committed (combat.CORPSE_ST = {0x4BE4,
  0x5CC8}; the amendment-G exclusion NOT applied — combat.py
  untouched this round).

### THE CAPTURE

> tap 6: score +500 — slot16, st_pre 0x1e38, pay frame tail f1.

The causal chain is **BYTE-IDENTICAL** to the R66 capture (slot16 /
0x1e38 / tail f1), and the tap-kind sequence is **IDENTICAL to the
R66 pass-B end to end**.  The amendment-G lesson is CONFIRMED BY
REPRODUCTION: the R67 divergence was the gate variant; the tap
order IS part of the experiment.

Honest note: the CONNECT/KILL counters read 0/0 (the 0x42bc wound
registration never appeared inside the tap windows) while the score
PAID at tap 2 (+1000) and tap 6 (+500) — the pay-before-
registration law (the accumulator pays ~2 frames before the visible
registration) is now observed from the missing-registration side
too.

## 2. The widened-set zero-overlap test — **RESOLVED**

`scripts/r68_analysis_correct.py` (offline, zero boots; the r67
reusable core verbatim):

| set | vectors |
|---|---|
| +500 | n=**2** (R66 passB t6, R68 passB t6) |
| +1000 | n=**7** (2 R52 + 2 R66 + 2 R67) |

* **19 union-net offsets** separate EVERY +500 pay-frame vector
  from EVERY +1000 vector (the intersection: 0x60, 0x62, 0x6c,
  0x70, 0x74, 0x78, 0x7a, 0x8c, 0x8e, 0x94, 0x96, 0xc6, …).
* The **delay law is two-class**: +500 pays at tail f1 (2/2 — the
  bullet-impact frame), +1000 pays at tail f3/f4 (the wound-
  recovery class).
* Magnitude table: **+500 ×5 vs +1000 ×9**.
* The R67 PENDING items are BOTH closed: the +500 class stands
  **n=2**; the class discriminator is **RESOLVED** on the widened
  set.  The 19 offsets are the payment = f(wound_state)
  fingerprint candidates for the R69 source-first xref.

## 3. The product path — the failure-mode map (four probe-pinned
policy variants)

The read-only product-stack probe (`scripts/r68_postkill_probe.py`:
the real adapter + the shipped policy, the every-frame entity table
in the fight window; the probe's action map includes BACK — the
R67 probe map lacked it).

### THE R67 CORRECTION (the honest-registry law)

The R67 event "THE ARMORED TRUCK KILLED ON THE PRODUCT PATH (T2
3-lobs vs hp_a4 300, score 2300)" is **REFUTED**: the truck row sat
at **a4=160** (0x9E88, x 937.5, h 64, slot 14) from f1160 to the
v1.4.2 death at f1462 — the truck was NEVER killed.  The three lobs
(f875/f972/f1063) landed ONE connect (−100) + chips (−40); the
score 2300 came from the wave kills + chip events.  The "truck
AIRBORNE" death-shot reading is likewise corrected (the airborne
object is the encounter's follower).  The player died PINNED at px
1164 (the section pin) with the parked truck BEHIND at dx −226.5.

### The four variants

| policy | ep1 (the product run) | the probe finding |
|---|---|---|
| v1.5.0 W8/W9 (the kill transition + the hazard retreat) | 1462f / 2300 / 91 acts — **the trace BYTE-IDENTICAL to the R67 v1.4.2 run** (the same trace_sha256) | the W8/W9 chain never fires: the truck never dies, the row never leaves the observation |
| v1.6.0 T2' unlimited lobs + T6' the chase | 1318f / **2800 = the RECORD** (prior best 2300) | the lobs LAND in the band (dx −133.5 from px 1071): a4 300→230→110→100→**80**, then FROZE when the truck crossed the band edge (−135.4) and the chase pressed BACK against the scroll (px 1071→1105.8) |
| v1.6.1 T6' stand-ground chip-fire (the R38 sustained-fire model, \|dx\| ≤ 220) | 1218f / 1400 — a REGRESSION | the a4 sat at **300 FROZEN through five 12f chip windows** — the bullets DO NOT reach a truck behind the pin (the wave soldiers + the pin scenery eat the shot); the R38 chip model requires a CLEAR LINE |
| v1.6.2 T6' the chase restored + the R38 **gre40** cadence (TRUCK_GRENADE_CD=40, the encounter2 "max DPS on truck" evidence) | 1318f / 2800 (the record tied) | the same band window, the same a4 floor 80: the **CONNECT RATE (~1/10, the R38 evidence)** is the named R69 blocker — not the cadence |

Adapter 0.4.0: the truck dead family {0xA304, 0xA44C, 0xA45C} joins
CORPSE_ST (the capsule-verified death/wreck states never absorb a
bullet or pay) + the `dead_truck_x` kill signature (a vanishing
truck WITH a dead-family sighting = the kill; WITHOUT = a drive-off).
Policy 1.5.0→1.6.2; the W8 kill transition carries a 12-frame
gone-confirmation window (a scan flicker never fires the chain) and
the W9 hazard retreat sits at the WRECK's own x.  Mission 1 NOT
cleared (not claimed).

## 4. Discipline ledger

* Experiment boots: 3/3 disclosed pre-run (the env probe + the
  rebuild + the pass-B hunt), the ledger `scratch/r68/
  boots_used.json`.  The product-path diagnostic probes + the
  product runs are the separate gameplay track (the R67/R68
  precedent), disclosed in the evidence files.  No new dry-run
  script this round (the harness IS the committed r66t1 code path
  verbatim; the ledger was the pre-run disclosure).
* No RAM writes anywhere; legal pad inputs only; no training; no
  runtime LLM; the m2_gate note unchanged.
* The intermediate probe artifacts (the v1.5.0/v1.6.0 runs) were
  overwritten in place by the fixed-path probe — disclosed; their
  pinned numbers live in this report and the capsule; the v1.6.1
  artifact survives (`r68_postkill_probe_v161_chipstand.jsonl`).
* Every script: `scripts/r68_*.py`; every artifact:
  `data/games/SLUS-01212/truck_evidence/r68/`; the full suite
  **864 passed + 9 skipped + 1 xfailed** (zero weakened; 9 new
  offline tests).

## 5. R69 (the next capsule lever)

Product path: the connect-window policy — hold the measured throw
posture (px ~1071, |dx| 125..140) and lob on the gre40 cadence ONLY
inside that window (up to 7 throws in the ~280f band window at the
measured connect rate ⇒ the kill inside the window).  Experiment
track: the 19-offset +500 fingerprint xref'd in the ENEMY.BIN
overlay @0x8009C0E8 + the EXE (offline, zero boots) to find the
payment writer; one restore-only hunt pass if the writer is found
(the R66 gate verbatim, the R68 disclosure pattern).
