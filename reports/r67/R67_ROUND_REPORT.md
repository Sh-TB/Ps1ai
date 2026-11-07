# R67 ROUND REPORT — the +500 hunt, the widened-set test, the truck campaign

Round: **R67** · Owner directive: the WSP/Qwen method REJECTED (the
owner never approved it; the post-mortem is on issue #9), the loop
back on the evidence-driven track, the capsule lever R67 executed
verbatim.

## 1. The experiment track — the +500 hunt (restore-only, ledger cap 3)

* Offline contract dry-run BEFORE any boot (`scripts/r67_dryrun.py`,
  24/24): it caught and pinned ONE real gate-contract defect — the
  R66 experiment gate used `combat.CORPSE_ST = {0x4BE4, 0x5CC8}`
  while the committed PRODUCT adapter contract includes the
  death-registration terminal `0x5B0C`.  The R67 hunt disclosed the
  alignment as amendment G (the R66 script untouched).
* Boot 1 (env probe): the anchor + BOTH r66 frontiers restore alive
  on this machine (px 1246.2 / 1254.8, alive, score 6702) — the
  restore-only budget line holds.
* Boots 2-3 (the hunt passes): **0 NEW +500 captures** — the goal
  (n≥2) NOT met, honestly recorded.  The +1000 class replicated ×2
  (0x42bc → pay tail f3; 0x3f48 → pay tail f4 — the exact R66
  signature).  The ledger: 3/3 spent, every purpose disclosed.
* THE AMENDMENT-G LESSON: on the byte-exact frontier_b the tap
  trajectory diverged EXACTLY at tap 6 (R66: slot16 0x1e38 +500;
  R67: slot18 0x540c +100) — **the +500 capture is a
  trajectory-sensitive posture**, not a standing property of the
  frontier.  The tap order is part of the experiment.
* The frontier landscape: both frontiers are target-starved past
  the spawner-cluster edge (the de-starve advance walked to px
  ~1540 with NO targetable enemy rows); fresh 0x4054 soldiers exist
  only at restore time and churn out of the fresh class before the
  tap lands.

## 2. The widened-set zero-overlap test (offline, zero boots)

* +500 n=1 pay-frame vector vs +1000 n=6 vectors (2 R52 + 2 R66 +
  2 R67): **19 union-net offsets** separate the single +500 vector
  from all six +1000 vectors — but at n=1 the intersection IS that
  capture's own set (identity words dominate).  The class
  discriminator stays **PENDING** (honest).
* ESTABLISHED: the +1000 delay signature reproduces ACROSS ROUNDS
  (0x42bc → tail f3 in R66 AND R67; 0x3f48 → tail f4 in both) —
  the st_pre→delay law is the strongest live lead.
* Magnitude table: **+500 ×4 vs +1000 ×9**.

## 3. The gameplay track — the product-path truck campaign

Policy `msx_mission1_rules` 1.1.0 → **1.4.2**, adapter 0.2.0 →
**0.3.0**, 40 offline tests green, the full suite 858 passed +
3 skipped + 1 xfailed (zero weakened).

* **THE ARMORED TRUCK KILLED ON THE PRODUCT PATH** — the T2
  grenade sequencing (3 lobs × −100 vs hp_a4 300, the capsule
  semantics verbatim) took it to zero; the death screenshot shows
  the truck AIRBORNE.  ep1 score **2300 = the RECORD** (previous
  best 1300, R66).  Mission 1 still NOT cleared — the post-kill
  death (the second truck / the death animation) is the named
  next blocker.
* The evidence-driven rule chain (each step a measured lesson):
  * **T1** the truck identity = the 0x9E88 state word (code 7).
    The v1.1.0 (sc=6, h=64) identity was a FALSE-POSITIVE TRAP:
    ground soldiers in walk/throw animation states also present
    (6, h=64) — the hold froze at px 493 on a scenery row (ep2
    stuck 10000f).  The read-only truck-zone probe read the REAL
    truck live: 0x9E88 at x 937.5, h=64, a4=300 (the capsule's
    parked-truck posture verbatim).
  * **T3** soldiers before the truck gun: a clear-line escort
    holds the lob; a corridor-blocked escort does not (the R49
    bullet-steal model).
  * **The REAR FIGHT** (v1.4.0): the loop-probe evidence — at the
    section pin (px 1164) the soldier wave AND the parked truck
    are BEHIND the player (dx<0); a forward-only policy stands
    pinned facing right while the rear kills it (three identical
    v1.0.0-v1.3.0 deaths).  The adapter gained the BACK action
    (the legal LEFT button) and the policy gained facing tracking
    + mirrored engagement.
  * **T5** the outer-edge hold (90..135): the dx-52 hold stood in
    the truck gun's line and LOST the duel (the probe: php 202 →
    death while holding).
  * **T7** the blast retreat: the 3-lobs kill exploded the player
    standing in the band (the v1.4.0 death shot); after the budget
    is spent the player leaves the blast radius.
* **THE CADENCE LAW** (v1.2.0's regression, restored in v1.3.0):
  the fire cadence is part of the deterministic wave trajectory —
  the top-tick 12f cadence starved the wave (0 kills, the truck
  never entered — zero a4≥100 rows in the probe), while the
  v1.0.0 13f rhythm reproduced the R66 record BYTE-EXACT
  (1666f/1100/87 and 388f/1300/13).

## 4. Discipline ledger

* Experiment boots: 3/3 disclosed pre-run (env probe + two hunt
  passes); product-path boots (the separate gameplay track) + the
  read-only diagnostic probes disclosed in the evidence files.
* No RAM writes anywhere; legal pad inputs only; no training; no
  runtime LLM; the m2_gate note unchanged.
* Every script: `scripts/r67_*.py`; every artifact:
  `data/games/SLUS-01212/truck_evidence/r67/`.

## 5. Honest status

| item | status |
|---|---|
| the +500 hunt (n≥2) | NOT MET (0 new; the R66 capture stands n=1) |
| the widened-set discriminator | PENDING (single-capture separation, 19 offsets) |
| the st_pre→delay law | REPLICATED across rounds (+1000 class) |
| the truck kill (product path) | ACHIEVED (T2 sequencing; score record 2300) |
| the T1 identity fix | TESTED (the false-positive trap pinned by tests) |
| the rear fight | TESTED + product-verified (the wave resolved) |
| Mission 1 clear | NOT achieved (the post-kill phase is next) |

## 6. R68 (the next capsule lever)

Product path: a wreck-aware policy extension (the wreck 0xA44C /
death state 0xA304 are capsule knowledge) that retreats through the
truck-kill and re-engages the SECOND truck with the same T2
sequencing until the roadblock section clears.  Experiment track:
ONE restore-only boot replaying the R66 pass-B tap sequence VERBATIM
(the amendment-G gate reverted for the hunt only) for the third +500
attempt; the zero-overlap test re-runs on any new capture.
