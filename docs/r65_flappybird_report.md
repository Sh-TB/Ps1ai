# R65 FlappyBird Report — the frozen champion, fresh product-path evidence

Round: **R65** · Date: 2026-11-01 · Champion: `flappybird_policy`
(R61 frozen, ONNX sha256 `4dd592a7118a5c4d…`, UNCHANGED — no retraining,
no replacement, no mutation).

## 1. What was run

The product path, exactly as a user runs it:

```bash
python3 -m ps1play play flappybird --episodes 5 --seed-start 343 --seed-step 7
python3 -m ps1play play flappybird --episodes 5 --seed-start 378 --seed-step 7
```

Seeds: the **10 reserve seeds** `[343, 350, 357, 364, 371, 378, 385, 392,
399, 406]` from the committed pre-registered split
(`data/learn/r61_validation_split.json`). These were listed as reserves in
R61 and were never used for any evaluation or selection before R65; the 30
R61 validation seeds are retired by the split file. Budget: the standard
10,000 frames/episode, n=1 per seed.

## 2. Fresh results (data/r65/r65_flappy_fresh_summary.json)

| k | result | pipes | frames | flaps |
|---|--------|-------|--------|-------|
| 343 | death | 13 | 1691 | 110 |
| 350 | **ALIVE** | **87** | 10000 | 636 |
| 357 | **ALIVE** | **87** | 10000 | 638 |
| 364 | death | 43 | 5076 | 322 |
| 371 | **ALIVE** | **87** | 10000 | 640 |
| 378 | death | 16 | 2031 | 128 |
| 385 | death | 30 | 3616 | 232 |
| 392 | death | 14 | 1803 | 116 |
| 399 | death | 42 | 4965 | 316 |
| 406 | death | 38 | 4507 | 288 |

* **Mean 45.70 · median 40.0 · min 13 · max 87 · alive at budget 3/10.**
* The 87-pipe record is **REPRODUCED on 3 fresh seeds** (k=350, 357, 371),
  each ALIVE at the 10,000-frame budget with 636–640 flaps — the same
  signature as the R61 family records (k6/k60: 87 pipes, 640 flaps).
* Cross-process determinism held: k=343 ran three independent times this
  round (a smoke run, a killed background attempt, and the protocol run) —
  all three byte-identical (13 pipes, 1691 frames, 110 flaps).

Honest comparison with R61's evaluation (mean 52.30, median 48, 6/30
alive): the R65 numbers are on a DIFFERENT, much smaller seed set
(10 pristine reserve seeds vs the retired 30) — no significance claim is
made across the sets. Both evaluations agree on the shape: heavy-tailed
seed variance, the 87-pipe ceiling reached when the policy survives to
the budget, and early deaths on roughly a third of seeds.

## 3. How many pipes can it pass?

* On seeds where it survives: **87 pipes is the ceiling** — that is the
  10,000-frame budget's limit (640 flaps at ~1.5625 decisions/pipe), not
  a skill limit. The policy has never died ON a pipe above 76 (k12: 76
  @8798 frames in R61); every sub-record death is a mid-run collision on
  the heavy tail.
* On the tail seeds it dies between 10 and 43 pipes.

## 4. What limits performance (the R65 reading)

1. **Seed-tail perception degradation.** The champion's 10-feature vector
   (BirdObserverV7 + GapTrackerV7) is frozen; the R61 closure already
   documented that the trajectory diverges on ~1/4 of seeds and that no
   significance was claimable for the champion-vs-C1 gap. The R65 fresh
   tail (13–16-pipe deaths on k=343/378/392) shows the same signature —
   the gap tracker loses or mis-times the first tight pair.
2. **The budget, not the policy, defines 87.** The three ALIVE episodes
   all end at the frame budget with the identical flap cadence — the
   policy is stable at its operating point; the ceiling is the protocol.
3. **Flap timing margins.** The recorded deaths are single-frame collisions
   (the passage counter's band-x edge vs the bird-y envelope at pipe gap
   edges). The R61 challenger analysis (C1 at 53.37 mean) showed a
   different-policy trade in the same tail — i.e. the tail is a
   perception/timing problem, not a model-capacity problem.
4. **No retraining.** Per the standing rule the champion is frozen; the
   R61 training record (`docs/r61_training_record.md`) documents why any
   challenger path would require a new pre-registered protocol, which is
   out of scope for R65.

## 5. The downloadable package

`flappybird.ps1game` (v1.0.0, maturity PARTIAL_AUTONOMOUS_PLAYER) ships:
the runtime adapter, the INDEPENDENT frozen policy package (model +
authority manifest), the game-specific perception module, the disc pin
(disc sha `b45871d3…` — the game is Unlicense homebrew; users fetch
their own copy), the R61 + R65 records, and the contract tests.
Verified: export → validate → install → `ps1play test flappybird`
(see `docs/r65_downloadable_knowledge_packages.md`).

## 6. Evidence index

* `data/r65/r65_flappy_fresh_summary.json` — the fresh run summary.
* `data/learn/r61_validation_split.json`, `data/learn/r61_validation_rows.jsonl`
  — the R61 protocol and records (untouched).
* `deployment/flappybird_policy/` — the frozen champion package (sha-pinned).
* `docs/r61_final_closure.md` — the R61 closure (byte-exact family records).
