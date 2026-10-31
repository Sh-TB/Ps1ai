# R60 Execution Report — the ONNX deployment round: the champion's
# decision function ships as a verified artifact

> Round R60, 2026-10-31, Issue #13 (the R57 workstream continued). Base
> `5e0d6d3` (the R59 head). Primary: FlappyBirdPSX; hello_pong
> regression re-verified. All gameplay numbers are REAL emulator
> measurements (Beetle PSX 0.9.44.1 + OpenBIOS; the FlappyBirdPSX
> v0.1.0 ISO re-fetched after the sandbox recycle, sha256 `b45871d3…`
> verified, license sector + CD001). Budget 10000 frames. No RAM
> anywhere in the student pipeline (AST-scanned, import-blocked, hashed
> `no_teacher_trace` per process). **The last PENDING badge from
> R57–R59 — ONNX — is closed this round.** No new training, no new
> policy: the R59 champion `r59_soup_e6a010` is unchanged; this round
> ships its VERIFIED deployment artifact.

## The question this round answers

The R57–R59 rounds promoted `r59_soup_e6a010.npz` (7.1 KB, tiny MLP
10→128→2) to champion, with native numpy as the deployment per the
review bar. The disclosed gap: **no portable decision artifact** —
every deployment consumer had to reimplement the numpy forward. R60
exports the champion's decision function to ONNX and proves, on the
real emulator, that the ONNX path is decision-identical to the
deployed numpy path — frame for frame, and then ALONE.

## R60-A: the artifact (float32 verbatim, epsilon folded)

`data/learn/r60_soup_e6a010.onnx` — **7,182 bytes**, opset 17, IR 8,
`onnx.checker` PASS:

```
x[N,10] -> Sub(mean) -> Div(std+1e-6) -> Gemm(W1,b1) -> Relu
        -> Gemm(W2,b2) -> logits[N,2]
                                     -> ArgMax(axis=1, first) -> action_idx[N]
```

- Weights/norm are the champion npz + meta bytes **verbatim**
  (float32); the deployed line `(x - self.mean) / (self.std + 1e-6)`
  is preserved by folding `std_eps = std + 1e-6` into the Div
  constant (numpy-2 NEP50 float32 semantics reproduced).
- `ArgMax(..., select_last_index=0)` = numpy `argmax` first-max
  semantics; classes `[HOVER, FLAP]`.
- **Input contract** (sidecar-disclosed): `x` is the RAW v7 decision
  vector — the graph normalizes internally. The perception state
  machine (BirdObserverV7, GapTrackerV7, `since_flap/flap_run/
  last_gc/since_gap`) is pure numpy frame processing in the host
  (`visual_only.Brain._vector`) and carries **no learned weights**.
- Sidecar `r60_soup_e6a010.onnx.json`: provenance (source sha256
  `72c79f30…`, the soup formula), arch, classes, the norm contract,
  the graph text, export parity, boundaries.

**Export-time parity** (200,000 synthetic vectors around the recorded
norm distribution): argmax parity **1.0**, max logit |Δ| **0.0**
(bit-identical logits), min top-2 margin 1.16e-4.

## R60-B: closed-loop parity on the REAL emulator (dual decision)

Every frame of every family episode: the deployed FlatPolicy state
machine computes the decision vector ONCE; BOTH forwards run on it —
the numpy reference (the deployed path) and onnxruntime 1.31.1 CPU on
the ONNX artifact. Per-frame action equality asserted live.

**All 7 family seeds reproduce the R59 record EXACTLY** (same pipes,
same steps, same flap counts):

| seed | record | this round | flaps | mismatches / frames |
|---|---|---|---|---|
| k6 | 87 alive | 87 alive @10000 | 640 | 0 / 10000 |
| k12 | 76 @8798 | 76 @8798 | 560 | 0 / 8798 |
| k30 | 37 @4401 | 37 @4401 | 281 | 0 / 4401 |
| k45 | 40 @4753 | 40 @4753 | 302 | 0 / 4753 |
| k60 | 87 alive | 87 alive @10000 | 640 | 0 / 10000 |
| k90 | 68 @7895 | 68 @7895 | 512 | 0 / 7895 |
| k210 | 42 @4966 | 42 @4966 | 322 | 0 / 4966 |

**51,773 frames, 0 action mismatches, max logit |Δ| = 7.63e-5**
(float32 ULP-level; the argmax never flipped).

## R60-C: the ONNX path ALONE drives the loop (solo)

`SoloPolicy` deletes the numpy forward from the decision: the ORT
forward on the artifact is the ONLY decider. Byte-exact family
record reproduction:

| seed | record | ONNX-solo | flaps |
|---|---|---|---|
| k6 | 87 alive (640 flaps) | 87 alive @10000 | 640 |
| k45 | 40 @4753 (302) | 40 @4753 | 302 |
| k30 | 37 @4401 (281) | 37 @4401 | 281 |

The k6 razor-edge, the soup's +7 seed and an exact death point all
hold under the artifact alone.

## R60-D: packaging + regression tests

- `data/learn/r60_onnx_parity_vectors.npz` — 4,200 REAL closed-loop
  decision vectors (stratified from all 7 episodes) + the numpy
  reference logits + the recorded ORT logits + both action columns.
- Offline recheck: ORT re-run on the packaged RAW vectors = **exact**
  vs the recorded ORT column (max Δ 0.0) and argmax-equal vs the numpy
  reference column (4200/4200).
- `tests/test_r60_onnx.py` (4 tests, `importorskip(onnxruntime)`):
  artifact size ≤4 MiB, checker + sidecar consistency, decision
  parity on the committed vectors, solo rows recorded. Suite:
  **642 passed + 2 skipped + 1 xfailed** (638 + 4 new).

## hello_pong regression — PASS

Artifact re-fetched through the documented r12 procedure (bin sha256
`a592f7ed…` verified, license sectors from the user's own retail MSX
disc). The R54 head-to-head protocol: teachers v1/v2 **7 scored / 0
conceded** each; student `pong_student_feat_p4d4` **8 scored / 2
conceded**, gameAI returns [19, 19] — the exact R54/R59 record; the
student still outscores both teachers (8 vs 7).

## Honest limitations

- The ONNX graph is the **decision function only**; the perception
  state machine is numpy host code (disclosed in the sidecar). A
  from-scratch consumer must reimplement that state machine (pure
  frame processing, no weights).
- Parity is claimed for **float32 CPU** executors (onnxruntime 1.31.1
  CPUExecutionProvider; numpy/BLAS reference). GPU or other runtimes
  are NOT claimed.
- Native numpy remains the default deployment per the review bar;
  the ONNX artifact is the verified portable alternative.
- The champion is UNCHANGED — this round ships deployment, not
  capability. The R59 aggregate-only TEST claim stands as published.
- One chunked run used the default `--dagger 1` (the assisted relabel
  writes only scratch-side DAgger data; the game protocol and scores
  are unaffected — scores match the record exactly).

## Reproduction

```
python3 scripts/r60_onnx_export.py                    # artifact + sidecar
python3 scripts/r60_parity.py --mode dual             # 7 family seeds
python3 scripts/r60_parity.py --mode solo --seeds k6,k45,k30
python3 scripts/r60_evidence.py                       # package + recheck
python3 -m pytest tests/test_r60_onnx.py -q
python3 scripts/r54c_pong_eval.py --agents v1,v2,feat \
    --feat-art data/learn/pong_student_feat_p4d4.npz
```

Evidence: `data/learn/r60_soup_e6a010.onnx` (+ sidecar) ·
`data/learn/r60_onnx_parity_vectors.npz` ·
`data/learn/r60_onnx_evidence.json` · scripts r60_* · worklog entry
R60.
