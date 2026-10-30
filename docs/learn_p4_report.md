# R54 — Learning-to-Play P4: the student-vs-teacher round

**Mission:** the learning-to-play foundation (issues #11, #12). RAM/debug
access is legal in exploration / teacher-data / training; the deployed
policy must play from rendered frames + its own policy history ONLY,
with the boundary enforced by tests. The P4 bar: the learned student
must MEET OR EXCEED its teacher under the identical protocol.

## What was built this round

* **Feature v2-v6 ladder** (`ps1play/learn/visual_only.py`, all
  image-derived or policy-owned history, AST-audited clean):
  * pong v2: + predicted intercept y at the paddle plane (wall-folded
    extrapolation from the frame-diff velocity) + prev UP/DOWN dims.
  * flappy v2/v3/v4: + gap edges, + `since_flap`, + `last_gc` /
    `since_gap` (the r15 law's stale-gap memory made visible), +
    `flap_run` (the 2-frame pulse disambiguation).
  * flappy v5/v6: `FlappyObserver` / `FlappyObserverV2` — policy-owned
    bird trackers integrating DATA-FITTED physics (impulse -8 px/f on
    the 2nd pulse frame, rise decel +1.0/f^2, terminal fall +2 px/f —
    the r15 note's 0.125/8 values are the same curve in 1/8-px
    fixed-point units) between gated raw measurements, coasting
    through the pipe-overlap latch.
* **PongTeacherV2** (`teacher.py`): RAM-truth PREDICTIVE + edge-aim
  label source (assisted modes only; the close-range track law, the
  ±18-hold-to-contact miss measured and fixed to ±12 with deadband 3).
* **`_small_rgb` fast path** (`games.py`): bit-exact vs the loop
  reference (tested), ~3-4x faster episode loops.
* **The r54 scripts** (`scripts/r54a..r54k`): collect / train / eval /
  DAgger / trace / mask-lab for both games, incremental saves, the
  same-protocol head-to-head harness, and the same-sensor relabel
  pipeline.
* **Two boundary-relevant bug fixes caught by measurement:**
  1. the DAgger retrain initially used the STUDENT's own actions as
     targets (the wrong npz column) and degraded — the eval table
     caught it; the fix uses `teacher_actions`.
  2. `sample_weights` were not oversample-tiled (IndexError) — fixed.

## Pong — P4 result (identical protocol, identical seeds)

| checkpoint | policy | decision-path info | vs game AI | vs train-fam (s100-102) | vs HELD-OUT fam (s200-202) | artifact |
|---|---|---|---|---|---|---|
| P1 | PongTeacher (v1 tracking, small-frame) | frames only | rally 0-0, 19+19 returns, 0 conceded | 7 scored / 0 conceded | (pooled) | hand-written (disclosed) |
| P4 | PongTeacherV2 (RAM-truth predictive edge) | RAM (ASSISTED ceiling) | rally 0-0, 19+19 returns | 7 scored / 0 conceded | (pooled) | n/a |
| P2 | BC student (83.1% acc) | 9 visual dims | 20+20 returns | 3 scored / 30 conceded | loss-heavy | 2,414 B |
| **P4** | **student p4d4 = BC + DAgger r5** | 9 visual dims | **rally 0-0, 19+19 returns** | **8 scored / 2 conceded** | incl. a 2-0 win on held-out seed 202 | **2,417 B** |

**Verdict: the student OUTSCORES both teachers (8 vs 7) on the same
protocol and ties the game-AI rally; it concedes 2 vs the teachers' 0
— strictly better on offense, slightly behind on defense.** The full
per-seed table lives in `data/learn/r54_pong_evidence.json`.

## Flappy — P4 result (honest: PARTIAL)

Same-tier teacher ceilings (pipes): full-res 38/38/38/34/34,
small-frame 51/38/38/34/34 (k=6/30/60/90/210).
Student lineage: 0-1 pipes (v2, full-res labels) → 0-1 (same-sensor
labels) → 0-1 (v3) → **3/5/0/0/4 pipes at 99.7% decision accuracy,
FLAP recall 100% (v4, artifact 5,558 B)** — a 5-10x closed-loop gain
that STILL leaves a gap to the same-tier teacher.

The residual gap is diagnosed with evidence (not hand-waved):
* in pipe-overlap frames the /4-scale bird centroid LATCHES (frozen at
  ~95-105 while the true bird falls 77→139 — `trace_k60.json`);
* ALL color masks fail there (mask lab: worst-16% error 76 px);
* the same-tier teacher survives only because its flight path never
  enters the overlap regime — every student deviation enters it;
* physics-coast observers recover part of the gap (obs-teacher
  ceiling 3-6 pipes) but do not close it this round.

## Boundary evidence (unchanged guarantees, new code audited)

* `tests/test_learning_boundary.py` + `tests/test_learn_features_v2.py`
  (18 tests): the AST scan keeps `visual_only.py` numpy+stdlib only;
  the subprocess brain selfcheck; feature/artifact roundtrips; the
  causality of every new feature; the fast `_small_rgb` bit-exactness.
* Full suite: 614 passed, 1 xfailed (the only uncollectable module is
  the pre-existing capstone-dependent `test_issue5_overlay.py`).

## Reproduction

```bash
python scripts/r54a_pong_collect.py          # teacher-v2 dataset
python scripts/r54b_pong_train.py --suffix p4base --models feat
python scripts/r54c_pong_eval.py --tag p4r5 --feat-art \
    scratch/r54/pong_student_feat_p4d4.npz --agents feat \
    --dagger-prefix p4dag_r5      # DAgger collection round
python scripts/r54b_pong_train.py --suffix p4d4 --models feat \
    --epochs 100 --extra-weight 0.7 --extra \
    "scratch/r54/ds_pong_dagger_p4:p4dag_r5_gameai_0,..."
python scripts/r54c_pong_eval.py --tag p4r7 --feat-art \
    scratch/r54/pong_student_feat_p4d4.npz --agents feat --dagger 0
# flappy
python scripts/r54e_flappy_collect.py
python scripts/r54i_flappy_sf_relabel.py     # same-sensor labels
python scripts/r54f_flappy_train.py --suffix p4sf4 --models feat \
    --feature-version 4 --epochs 120 --feat-arch 96 \
    --base-root scratch/r54/ds_flappy_sf --extra-weight 3.0 --extra \
    "scratch/r54/ds_flappy_sf_dagger:<ids>"
python scripts/r54g_flappy_eval.py --tag p4r3 --art \
    scratch/r54/flappy_student_feat_p4sf4.npz --agents student
```

Artifacts: `data/learn/pong_student_feat_p4d4.npz` (2,417 B) and
`data/learn/flappy_student_feat_p4sf4.npz` (5,558 B) — both far below
the 4 MiB bound; sha256s in the `.json` sidecars.
