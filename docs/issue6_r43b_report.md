# Issue 6 — R43-B report (buzzybee, the 40% track): the CONTACT-TIME TRAJECTORY GUARANTEE reaches DOMINANCE

Round: R43 (the 40% track, buzzybee) · commit `82349da2…` + this commit ·
ledger `scratch/r43b/boots_used.json` (cap 2: entry 1 = the disclosed
filed-but-boot-failed filing, entry 2 = the real boot) · wall 10.3 s ·
schema `ps1play.r43b-evidence/1`.

## Environment rebuild (internet-first rule, sha-verified, disclosed)

The sandbox filesystem rollback had removed the `buzzybee_ntsc_lic` disc
(the same class as the documented mspsx_lic rollback). Rebuilt FIRST, per
the golden rule: upstream `NDR008/BuzzyBee@master` `BuzzyBee.ps-exe`
re-fetched — sha256 `9b0bfc08…c909a8ba` **byte-identical** to the r23/r42b
reference (299,008 B, MIT, flagged per the capsule); the disc rebuilt with
the committed wrap script (`scripts/r23t2_ntsc_patch_and_wrap.py`, the
2-instruction NTSC patch + the license wrap from the user's own retail MSX
disc) — sha256 `042b94bb…` **byte-identical** to the capsule-recorded
artifact. The rebuilt gs1 checkpoint is fresh (settle→START→gs1→serialize,
disclosed); the A/B inside this run shares one checkpoint and is exact.

## The lever, executed

The buzzybee capsule lever: *"a contact-time trajectory guarantee reaches
dominance (0 hits/1500f) — at engage time, simulate (bee gravity/tap
physics × wasp bounce-y) forward to ex=32 and choose the exit (side + tap
schedule) that keeps the bee out of the PREDICTED band for the whole
ex ∈ [-36, 32] window; re-plan on vy-flip or a failed guarantee (bail =
maximize distance from the band center)."*

`bot_policy5` implementation: at every engage-window frame the planner
enumerates (side, target) hold-controllers on an 8 px grid across the full
[18, 172] column, forward-simulates each under the calibrated physics
(impulse −3072 → move v/1024 → gravity +256/f, clamp [18,172], slam guard
bvy > −3000; wasp `predict_wasp_y` bounce model) and accepts the FIRST
controller whose whole simulated trajectory stays outside the predicted
56 px band with a **12 px guarantee margin for every DANGER-WINDOW frame**
(the frames where the wasp is horizontally within contact reach,
ex ∈ [−36, 32] — checking pre-contact frames was the offline-harness bug
the sanity tests caught and fixed before any boot). No guaranteed
candidate → the recorded bail (maximize the distance from the band
center). Re-planning is implicit and closed-loop (every frame replans from
fresh state, so the ~1.3–2.5 px climb-model gap vs the `rise_px`
calibration cannot accumulate).

## Results — DOMINANT (all four oracle legs true)

| metric | Arm A (the recorded bot-A recipe) | Arm B (the guarantee planner) |
|---|---|---|
| enemy_hits (primary: == 0) | 2 (f=1472, f=2274) | **0** |
| dodges / passes | 3 / 5 | **6 / 6** |
| score (≥ A) | 1401 | 1401 |
| hp at cap | 4758 | **5666** (+908) |
| flaps | 98 | **82** (−16) |
| pickups_caused | 0 | **1** (widened attribution window) |
| planner stats | — | 714 replans, 99 bails (86 % planned) |

`dominance_oracle`: v5_hits_zero **true** · v5_no_hit_pass **true** ·
v5_score_ge_A **true** · v5_pickups_ge_A **true** → **DOMINANT true**.

The R42-B failure shape is fixed by name: all four R42-B hits shared "the
wasp arrives at contact-x while the bee is still INSIDE the band" — the
danger-window guarantee plans against the wasp's *predicted position at
contact time* (with bounces), so the bee is never inside the band when the
wasp arrives. Arm B's two A-arm hit frames (f=1472: the bee at by 58
inside a band under ey 15; f=2274: the below-side fallback falling back
in) are exactly the shapes the guarantee rejects.

## Secondary + tertiary (the capsule items)

- **Pickup attribution window widened** (flower-mode seek ≥ 20f OR a
  dodge-mode frame with a flower-seek start ≤ 60f ago): arm B reads
  **caused = 1** (f=3275, seek_dur 8, recent_seek true) vs arm A's 0 —
  the R42-B zero-caused-pickups lesson is resolved.
- **Per-hit timing metric recorded**: arm A's hits at f=1472
  (f_since_pass_start n/a) and f=2274 (f_since_pass_start **99** — the
  hit landed 99 frames into the pass, the late-window fall-back-in
  shape); arm B has no hits to time.

## Honesty

- Legal inputs only (CROSS taps + one START for the gs1 gate); no RAM
  writes; savestates as labeled diagnostic anchors; restores are not
  boots.
- No copyrighted bytes committed (the image stays local under the
  gitignored `emu/`); upstream is MIT (flagged per the capsule).
- The offline planner tests (no boot) caught two real bugs BEFORE the
  emulator ran: the pre-contact-frame check (the guarantee horizon must
  cover only the danger window) and the below-side tap rule (any tap
  rises the bee back INTO the band — the below hold is pure free-fall).
  Both fixes are in the committed script.
- Next lever (recorded in the capsule): dominance → **score superiority**
  (B ties A's score at 1401; the planner inherits the policy3 flower
  logic verbatim — widen the flower seek during the guarantee's safe
  phases between wasp passes) + push caused-pickups (1 → 2+).
