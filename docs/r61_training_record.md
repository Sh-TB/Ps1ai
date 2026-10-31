# R61 Final Training Record — the complete training history of the
# FlappyBirdPSX learning workstream, closed

> R61, 2026-10-31/11-01, Issue #13. Base `d8bcbd3` (the R60 head).
> This record is the Section 3 deliverable of the R61 final-closure
> mission: what was learned, what was not, which methods were retained
> or rejected, which checkpoint won, whether the process is
> reproducible, and whether further training is justified by evidence.

`TRAINING_STATUS: CLOSED`

## 1. The training timeline (all stages, all rounds)

| stage | round | what happened | outcome |
|---|---|---|---|
| Foundation | R53-learn | `ps1play/learn/` built: role-tagged datasets with episode splits + digests, TinyMLP (numpy Adam/CE), `visual_only.py` decision boundary (numpy+stdlib only, AST-scanned), BrainClient subprocess, 5 observation modes | infra green; both games boot + anchored |
| pong student | R53–R54 | BC → class-weighted BC → +DAgger (1,010 teacher-relabeled student-state steps) on hello_pong | student `pong_student_feat_p4d4` OUTSCORES both teachers 8/2 vs 7/0 (the P4 bar met) |
| flappy teacher ladder | R53–R55 | r15 play-loop law ported to full-res, then to SMALL frames (same-sensor discipline) | small-frame law teacher: 194 pipes / 5 seeds, 4/5 budget-ALIVE (k6/k60/k90/k210) |
| flappy student v7 | R55 | feature_version 7 + BirdObserverV7/GapTrackerV7 (5 death mechanisms fixed at the pixel level; measured physics correction: rise decel +1 px/f², fall +0.125 px/f², half-up rounding) | lineage 60 → 65 → 140 → 123 → **155** (`p6v7h128`) |
| surgical mining | R56 | failure-mining oracle + counterfactual relabels (offline sim lab, zero boots) | **173** (`flappy_student_feat_r56_c1.npz`, the frozen C1 reference) |
| bootstrap + bake-off | R57 | 15 capped teacher episodes (20-pipe cutoff, the cutoff step's own action excluded, `cutoff_proof` hashed) → BC bootstrap → ES/ARS vs CORRECT PPO bake-off on the real emulator, teacher-off enforced (AST + import-blocker + hashed no-teacher traces) | ES/ARS won; PPO (importance ratios with the ε-mixture behavior log-prob, GAE, ratio guard) **died at 0–8 pipes and froze on the ratio guard** — the honest negative that replicated R55/R56 PPO failures under a correct implementation |
| provenance forensics | R58 | the saved R57 champion npz provenance-BROKEN (32.7% energy in the ARS subspace); reconstructed the TRUE candidate offline from the committed seeded stream (`r58_dir2p_true`) — k6=87 AND k60=87 budget-alive, exactly the recorded pair; self-imitation SI v2 line added | `r58_dir2p_true.npz` = provenance-clean champion; the mis-save incident documented, never hidden |
| linear-path soup | R59 | theta(alpha) = base + α·(donor − base) mapped on the razor seeds; SOUP POINT at α=0.10 | **`r59_soup_e6a010.npz`**: strictly dominates the base on the family (6 seeds byte-identical, k45 33→40), regression gate PASS with zeros; fresh-TEST (20 seeds × n=3, pre-registered split): aggregate WIN (mean 57.55 vs 53.65 base / 55.00 C1; median 52.5 vs 49.0; floor 24 vs 10), aggregate-only claim with per-seed divergence disclosed |
| ONNX deployment | R60 | champion exported to ONNX (opset 17, float32 verbatim, ε folded), dual-path parity on the real emulator (51,773 frames, 0 mismatches, max logit Δ 7.63e-5), ONNX-solo run byte-identical, 200k-vector export sweep exact | champion UNCHANGED; the deployment artifact verified |

## 2. What was learned (evidence-backed)

- A **pure-vision** FlappyBirdPSX policy (10 features from 60×80×3
  frames + the policy's own action history; NO RAM, NO teacher at
  inference) that flies 87 pipes budget-alive on the k6/k60 razor
  seeds, 76/37/40/68/42 on k12/k30/k45/k90/k210, and wins the R59
  fresh-TEST aggregate (mean +3.90 over the base, median 52.5 vs 49.0,
  min 24 vs 10) on 20 pre-registered unseen seeds.
- The decision function is a 1,466-parameter MLP (10→128→2, ReLU) —
  7.1 KB of weights, deployable as numpy OR as the verified ONNX
  artifact.
- hello_pong: the student genuinely exceeds both teachers under the
  identical R54 protocol (8 scored/2 conceded vs 7/0 each).

## 3. What was NOT learned / known limits

- The policy does NOT generalize beyond the flappy dynamics it saw; no
  cross-game claim is made (hello_pong is a separate policy, a
  regression gate — not evidence of generalization).
- Per-seed behavior is heavy-tailed: 15/20 TEST seeds byte-match the
  base; divergent seeds swing BOTH ways (k64 +48, k76 10→87-alive vs
  k80 −26, k140 −18). C1 keeps the alive-depth count (6 vs 5 seeds
  ≥85). No universal-superiority claim is made.
- Known perception hard case: the pipe-overlap centroid latch
  (R57 k-analysis, `r57_latch_analysis.json`) — all color-mask
  observers degrade when the bird overlaps the pipe column; mitigated
  by the GapTrackerV7 constant-gap pinning, never fully solved.
  Frames-only fix paths (per-column template matching or a tiny CNN
  observer) are documented as FUTURE work, outside the closed scope.
- The ONNX artifact covers the DECISION FUNCTION ONLY; the perception
  state machine is host-side numpy (no learned weights), disclosed in
  the sidecar and the deployment interface contract.

## 4. Methods retained vs rejected

**Retained (in the final lineage):** behavior cloning on capped
teacher demonstrations; same-sensor label discipline; ES/ARS V2
(linear utility, paired ± rollouts) for self-generated improvement;
self-imitation on student-generated lives; linear-path weight soup
with a pre-registered regression gate; VAL-selected early stopping.

**Rejected (with the measured reason):**
- PPO — twice failed (R55/R56 attempts, then the CORRECT
  implementation in R57): 0–8 pipes under ε=0.08, froze on the ratio
  guard every update; saturated BC logits + tiny on-policy batches on
  a 6 fps-effective emulator. Filed as an honest negative.
- DAgger for flappy — relabels at the student's drift states
  reproduced the teacher's own failing actions (R55 negative; helped
  pong, did not transfer).
- Mined-counterfactual x3 oversampling — DEGRADED 140→91 (kept only
  x1 at 123 in the intermediate lineage, later superseded).
- One-shot weight moves (any single checkpoint swap) — proven useless
  or destructive on the razor seeds (R58/R59 path maps); only the
  linear-path soup at α=0.10 survived its gates.

## 5. The winning checkpoint, and why

`data/learn/r59_soup_e6a010.npz`
(sha256 `72c79f3091ed14e8dd497ddc52570bb4660bfc6367e6b50eb8a8aa1eff8a28f4`)
= `r58_dir2p_true + 0.10 * (r58_si_v2_e6 − r58_dir2p_true)`, float64
math → float32 cast (re-derived bitwise in R61, see
`FINAL_MODEL_MANIFEST.json`). It won because it strictly dominates its
own base on the 7-seed family (never worse anywhere, +7 on k45),
passes the pre-registered regression gate with zeros, and wins the
R59 fresh-TEST aggregate. The deployment artifact is
`data/learn/r60_soup_e6a010.onnx`
(sha256 `4dd592a7118a5c4de7b44166b42b8d09d53fbb59330d36d0ba2746393dc11044`).

## 6. Split hygiene (no leakage)

- TRAIN: bootstrap episode seeds k ∈ {6,60,30,12,45,...} (the
  committed `r57_seed_splits.json` + dataset meta); ARS/SI dev seeds
  k6/k60 etc. disclosed per round.
- VAL: k6/k30/k60/k90/k210 (the family) + the dev seeds — used for
  every selection (bootstrap epoch, ES early stop, soup α, gates).
- TEST: R59 fresh 20 seeds
  [4,32,44,52,56,64,68,76,80,88,92,104,112,116,124,128,136,140,144,148]
  (multiples-of-4 rule, ALL prior uses excluded; split committed
  `21f3e0d3` BEFORE collection) — used ONCE for the final aggregate,
  then RETIRED permanently.
- R61's fresh validation set is a NEW pre-registered split
  (`data/learn/r61_validation_split.json`), excluding every seed above
  plus all dev/history seeds; committed BEFORE its collection.
- No TEST/VAL seed was ever trained on; the final policy saw no
  evaluation seed during any training step.

## 7. Teacher-off enforcement (verified, not assumed)

Every student-side training/eval entry point since R57 enforces:
(a) the AST denylist scan over the student modules (no teacher/RAM
imports — `tests/test_learning_boundary.py`, extended in R57);
(b) the per-process import blocker + `NoTeacherTrace` hashed JSONL
runtime proof (crash on any teacher capability import);
(c) the final policy at inference imports NO teacher module, NO
training code, NO dataset — the R61 deployment package
(`deployment/flappybird_policy/`) re-proves this from outside the
training tree (import-isolation test in `tests/test_r61_deployment.py`).

## 8. Reproducibility

- Deterministic emulator: two identical episodes produce
  byte-identical frame streams (R61 smoke, sha-verified); episode
  records reproduce byte-exactly across processes when the
  (checkpoint, k, budget) triple is fixed — replicated in R58/R59/R60
  and again in R61.
- Every artifact carries a sha256 + a meta sidecar; every round's
  claims carry the script + command in the worklog; every push is
  read back (blob SHAs).
- One known UNFIXABLE loss: the R57 save incident (the mis-saved
  `r57_es2_dir2p.npz`) — its cause died with the wiped scratch; the
  incident is documented, its candidate was reconstructed offline, and
  the final champion lineage is provenance-clean from committed bytes
  (R58 forensics + R61 bitwise re-derivation).

## 9. Is further training justified by evidence?

**No.** The remaining known gaps (per-seed heavy tails, the
pipe-overlap latch) are PERCEPTION and EVALUATION-DEPTH problems, not
optimization problems: R58/R59 measured that one-shot weight moves
collapse razor-edges, the soup already harvested the safe linear-path
gain, and the TEST aggregate win is within the disclosed per-seed
divergence. A new optimizer run would burn emulator boots for a
cosmetic aggregate delta while risking the razor-edge family record —
the exact trade the mission forbids. Future work belongs to
deployment and other-game integration, not further FlappyBird
training.

`TRAINING_STATUS: CLOSED`
