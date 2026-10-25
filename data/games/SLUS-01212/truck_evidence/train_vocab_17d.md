# Train-phase vocabulary — Task 17-d (raw telemetry mining, post-banner RIGHT walk)

Source of truth: **raw JSONLs exist** at `/home/z/my-project/work/msx_recomp/evidence/issue5_lives_variant/`:
`lives5_133557.jsonl`, `lives6_133851.jsonl`, `lives7_134007.jsonl` (200 rows each),
`lives1_131735.jsonl`/`lives2_132136.jsonl` (122), `lives3_132630.jsonl` (75), `lives4_133222.jsonl` (80),
plus `report_lives*_*.json`. `/tmp/my-project/emu/ws/` holds **savestates only** (no telemetry).
Curated copy: `truck_resolution_session6.json` (consistent with everything below).

**Bit-identity (lives5/6/7):** row-by-row JSON equality over all 200 rows; the ONLY diffs are
`boot.run` (5/6/7) and `RUN_DONE.wall_s` (6.0/6.0/6.1), `RUN_DONE.run`, `RUN_DONE.wall_total_s`
(69.6/…/70.3). Every M-walk row, M_DEATH row, M_done and post_banner payload is identical
⇒ **all line numbers below are valid for lives5, lives6 and lives7 simultaneously.**

Walk mechanics: the M phase is a 30f-chunk RIGHT-hold walk; `M` rows are logged every 10th chunk
(=300f) plus at each "anomaly_paused" chunk (the walk freezes while sec (0,\*)/px 0 persists).
Walk `i` = chunk index; 1 chunk = 30 frames @60fps.

---

## 1. RIDE SPEED (M2 train phase: i ≥ 106)

| row | file line | chunk i | px | Δpx | interval | px/frame | px/s @60fps | px/1000f |
|---|---|---|---|---|---|---|---|---|
| M i=106 (spawn) | 195 | 106 | 74.6 | — | — | — | — | — |
| M i=107 | 196 | 107 | 76.4 | +1.8 | 30f | 0.060 | 3.6 | 60 |
| M i=110 | 197 | 110 | 162.5 | +86.1 | 90f | 0.957 | 57.4 | 957 |
| M_done final | 198 | 120 | 404.1 | +241.6 | 300f | 0.805 | 48.3 | 805 |
| **whole M2 (106→120)** | | | 74.6→404.1 | **+329.5** | **420f** | **0.785** | **47.1** | **785** |

- Reference free-walk speed on foot (pre-train scene, unobstructed RIGHT): i=50→60 (l.183→184)
  +391.8/300f = **1.306 px/f** (78.4 px/s); i=60→70 (l.184→185) +351.9/300f = **1.173 px/f** (70.4 px/s).
- **Not uniform** at 300f granularity: 0.957 vs 0.805 px/f (−16% between the two measurable windows).
  All M2 deltas are forward (no backward px sample). Net rate ≈ 60–73% of free-walk speed ⇒
  consistent with a leftward-drifting platform (train) under the walker and/or intermittent
  ride pauses (car-boarding, rescue moments). **Sampling is too coarse to split train-car motion
  from player walking** — a frame-granular (≤10f) re-probe is required before modeling ride physics.
- Spawn-in is nearly stationary: +1.8 px over the first 30f (0.060 px/f).

## 2. WALKER / SEC SERIES during M2

| chunk i | line | px | sec | flags | score | php | gren | meaning |
|---|---|---|---|---|---|---|---|---|
| 106 | 195 | 74.6 | (0,0) | 255 | 0 | 74 | 10 | M2 spawn — walker state still blank |
| 107 | 196 | 76.4 | **(0xB,9)=(11,9)** | 255 | 0 | 76 | 10 | walker live, train section |
| 110 | 197 | 162.5 | **(0,0)** | 255 | 200 | 138 | 10 | transient blank DURING gameplay |
| 120 final | 198 | 404.1 | **(0xB,9)** | 255 | 3800 | 136 | 20 | end of walk |

- The (0xB,9)↔(0,0) oscillation: sampled twice per state. The (0,0) at i=110 does **not** sit on a
  px threshold — it coincides with the **score +200 / php +62 event window** (see §3), i.e. a
  rescue/pickup moment blanks the walker tuple for at least one sampled frame.
- sec (0,0) with px>0 is NOT rare in active gameplay: **27 rows** in lives5 (12 main-loop `chunk`
  rows c7–c29 in the D7/endzone px≈996–1135 while score climbs 2000→3300, lines 9–51; 9
  `zone_census` (e.g. line 11: px 1101.7, score 2100); 1 `hold_census` (line 50); 5 `M` rows:
  i=40@1164.0, i=50@120.3, i=60@512.1 (score 400, php 149), i=106, i=110).
  ⇒ **the harness "abort on any (0,\*)" guard is over-broad**; (0,0) alone is not a
  teardown/loading/death signature.
- Spawn cannot be keyed on sec either: the M2 spawn row (i=106) still reads (0,0); the walker
  tuple only goes live 1 chunk later. Spawn fingerprint = px 74.6 + php 74 + gren 10 + score 0.

## 3. PHP / GREN / SCORE timeline during M2

| window (chunks) | px range | php | gren | score |
|---|---|---|---|---|
| 106 (spawn) | 74.6 | 74 | 10 | 0 |
| 106→107 | 74.6→76.4 | 74→**76** (+2) | 10 | 0 |
| 107→110 | 76.4→162.5 | 76→**138** (**+62 RISE**) | 10 | 0→**200** (+200) |
| 110→120 | 162.5→404.1 | 138→**136** (**−2 drop**) | 10→**20** (**+10**) | 200→**3800** (**+3600**) |

- **Hypothesis "php only drops during M2" is FALSE**: php rises +62 (item/heal pickup, in the same
  window as the first +200 score) and drops −2 (chip damage) later.
- The **gren +10 and score +3600 share the single un-sampled window (110,120]** — consistent with
  POW rescue(s) granting grenades + points together; cannot be split further at 300f sampling.

## 4. SCORE EVENTS

- M2: 0 → 200 by px 162.5 (window i=107→110 — confirms the "+200 near 162.5" lead) → 3800 between
  px 162.5 and 404.1 (+3600, interior un-sampled).
- Pre-train scene walk (i=50→100, l.183–188) for calibration: 0 → 400 → 700 → 2900 → 7100 → 7800;
  deltas +400 (50–60), +300 (60–70), +2200 (70–80), **+4200 (80–90, px 1052.2→1099.3)**, +700 (90–100);
  php oscillates 120→149→144→180→110→179 (rises AND falls) with gren flat 10 — active pickup/kill
  scoring while merely holding RIGHT. This scene ends at px 1483.3 (l.188) before the MSX-logo
  loading (i=103–104), so the transition into the train happens there (PNG `session6/m2_transition_msx_logo.png`).

## 5. ENTITY / DEATH / ANOMALY rows in the M2 phase

- **None.** All `zone_census` (19) and `hold_census` (34) rows sit at chunks 9..27 (main M1 phase);
  all `death`/`death_frame` rows at c43/c67 (tally artifacts, §6). No `CK_CYCLE`, no `ck_scan`,
  no other anomaly ev exists in any of the 7 files. **No row anywhere has px>5000** (max px 1483.3,
  lives5 line 188) — no transition garbage values.
- The M2 phase (lines 195–198) contains only M i=106/107/110 + M_done (+post_banner/RUN_DONE echoes).
- One M1-endzone anomaly worth remembering when validating px monotonicity: M i=30 (l.175)
  px **1028.0** vs the 1164.0 clamp (−136 knockback/dip) with php **156** vs 291 (−135), fully
  recovered by i=40 (1164.0/291, l.176).

## 6. TRANSITION PRECISION (i=103..110) — bit-identical across lives5/6/7

| i | line | px | php | gren | flags | sec | score | prog (M_DEATH echo) |
|---|---|---|---|---|---|---|---|---|
| 103 | 189 (echo 190) | 0.0 | 0 | 10 | **0** | (0,0) | **7800** | 0 |
| 104 | 191 (echo 192) | 0.0 | 0 | 10 | **0** | (0,0) | **7800** | 0 |
| 105 | 193 (echo 194) | 0.0 | 0 | **0** | **255** | (0,0) | **0** | 0 |
| 106 | 195 | **74.6** | **74** | 10 | 255 | (0,0) | 0 | — |
| 107 | 196 | 76.4 | 76 | 10 | 255 | (11,9) | 0 | — |
| (108,109 not logged) | | | | | | | | |
| 110 | 197 | 162.5 | 138 | 10 | 255 | (0,0) | 200 | — |

Earlier break (same files): i=45 (l.177, echo 178): px 0.0, php 0, gren 0, flags 255, sec (0,0),
score **3301**; i=46/47 (l.179/181, echoes 180/182): px 0.0, php 0, gren 0, **flags 0**, sec (11,1),
score 3301.

### ALL distinct (px == 0.0) row signatures seen anywhere in the 7 files

| sig | exact scalars (px0.0 rows only) | ev / where | class |
|---|---|---|---|
| **S-A** | php 0, gren 0, flags 255, sec (11,1), score 3300, prog 65535 | `chunk` + `hold_census` + `death` + `death_frame` i=0 at c43 (lives5 l.70–73) and c67 (l.111–114); lives1/2 l.44–45; lives3 l.70–72; lives4 l.70–73 | **tally teardown** (false-positive "death"; session-6 SUPERSEDED finding) |
| **S-B** | identical scalars to S-A | `W` step 0–5 (lives5 l.163–168; lives1/2 l.112–117) | **continue screen** wait |
| **S-C** | php 0, gren 0, flags 255, sec (0,0), score 3301 | `M` i=45 (l.177) + `M_DEATH` echo (l.178, prog 65535) | **tally teardown onset** (score not yet torn down) |
| **S-D** | php 0, gren 0, flags **0**, sec (11,1), score 3301 | `M` i=46,47 (l.179,181) + echoes (l.180,182) | **loading** (flags-0 window #1) |
| **S-E** | php 0, gren **10**, flags **0**, sec (0,0), score **7800** | `M` i=103,104 (l.189,191) + echoes prog 0 (l.190,192) | **loading** (MSX-logo window #2; score NOT yet reset) |
| **S-F** | php 0, gren 0, flags 255, sec (0,0), score **0** | `M` i=105 (l.193) + `M_DEATH` echo (l.194, prog 0) | **score-reset** row (mission data cleared) |
| **S-G** | — | **never observed** | **real-death forensics**: every `death` row in all 7 files is the S-A tally artifact; a genuine death signature is still uncharacterized |

Adjacent non-zero trap: `M` i=106 (px 74.6, php 74, score 0, sec (0,0)) — spawn frame with blank
walker sec; and `death_frame` i=1..4 (lives5 l.74–77, l.115–118; lives4 l.74–77) read
**px 992.0, php 120, gren 10, flags 255, sec (11,1), score 3300** — the tally scene's own world
values ≈80f after teardown, indistinguishable from live gameplay by scalars alone.

## 7. alive() false-positive census (test vectors)

- **px==0.0 ⇔ php==0 with zero counterexamples**: in every file, 0 rows have px==0.0 with php>0 and
  0 rows have php==0 with px>0. Counts of px==0.0 rows: lives5/6/7 = **26** each (l.70–73, 111–114,
  163–168, 177–182, 189–194); lives1/2 = 8 (l.44–45, 112–117); lives3 = 3 (l.70–72); lives4 = 4
  (l.70–73).
- Therefore `alive()` keyed on `php>0` alone OR `px>0` alone misfires on **all** of S-A…S-F
  (6 distinct signature families, up to 26 rows/run), and keyed on `(px>0 & php>0)` alone still
  misfires on the post-teardown tally world (death_frame i=1–4: px 992/php 120) and cannot
  distinguish it from gameplay.
- Robust liveness discriminator must use the **flags-0 loading window** (S-D/S-E), the
  **score-reset transition** (3301→ / 7800→0), and/or **sec stability** — never sec (0,\*) alone
  (27 active-gameplay (0,0) rows, §2), never php/px alone.

## Ride-speed takeaway for the vocab model

Train-phase net advance ≈ **0.79 px/f average (47 px/s; 785 px/1000f)** over px 74.6→404.1 with
window rates 0.96/0.81 px/f vs free-walk 1.17–1.31 px/f — model the M2 baseline as *free walk minus
platform drift/pauses*, NOT as uniform motion, and expect transient sec (0,0) + score/php events
(POW rescues) inside the ride.
