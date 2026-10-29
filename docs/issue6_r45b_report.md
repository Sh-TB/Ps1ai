# R45 (buzzybee, the 40% track) — the tiered-margin pre-position round: honest NEGATIVE, the third consecutive score tie

**Round**: the capsule R45 lever executed — the tiered guarantee margin (GM 8 pre-danger / GM 12 in-window) with the policy6 flower-proximity selection. **Verdict: NEGATIVE for score superiority; the 0-hit dominance is PRESERVED and the looser tier is proven safe at this checkpoint.**

## Environment rebuild (disclosed, 0 boots)

The sandbox rollback lost both the local disc and `scratch/r43b/state_r43b_gs1.bin`. Before the boot, internet-first rebuild sha-verified both:

- `BuzzyBee.ps-exe` re-fetched from upstream `NDR008/BuzzyBee@master` — sha256 `9b0bfc08…c909a8ba` = **byte-identical** to the r23/r42b/r44b reference;
- the disc rebuilt with the committed `r23t2_ntsc_patch_and_wrap.py` — sha256 `042b94bb…bb093` = **byte-identical** to the capsule-recorded artifact.

Boot 1 (cap 1/1, disclosed) rebuilt the gs1 checkpoint in-process (settle 900f → START → gs1 → serialize; the r42b precedent — the rebuilt checkpoint is not frame-identical to r35b's; cross-run comparisons to r35 are qualitative only, and the A/B inside this run shares one checkpoint and is exact).

## The arms (1500 f each, restore-only, shared checkpoint)

| arm | policy | hits | dodges | score | hp | flaps | caused | notes |
|---|---|---|---|---|---|---|---|---|
| A | `bot_policy5` (the R43-B dominance recipe) verbatim | 0 | 6/6 | 1401 | 5666 | 82 | 1 | reference |
| B | `bot_policy7` tiered 8/12 | 0 | 6/6 | **1401 TIE** | 5666 | 81 | 1 | GM8 held **453** dodge frames, GM12 264; 91 bails / 717 replans |

The tiered margin genuinely engaged (453 pre-danger frames filtered at GM 8) and **never produced a hit** — the capsule's safety question is answered YES at this checkpoint. The margin-floor revert (arm B2) therefore never fired.

## The constructive finding: 1401 is a structure, not a policy

The score is now **invariant across four policy families**: the bot-A recipe (1401), `bot_policy5` (1401), `bot_policy6` (1401), `bot_policy7` (1401) — while the flowers drive **HEALTH** (+997 per pickup), not score. The 1401 line is the checkpoint's fixed reward structure (6 wasp passes per 1500 f), so no dodge-axis policy variant can break the ≥ 1550 goal. The score-source mechanism must be identified first: `0x8005883C` is readable per frame, so R46 instruments the runner with per-frame score telemetry, localizes every score delta, and only then picks the lever (a longer horizon = more passes, or the discovered source directly).

## Oracle (the capsule) — not met

- `b_hits_zero`: **TRUE** (dominance preserved)
- `b_score_ge_1550`: FALSE (1401)
- `b_caused_ge_2`: FALSE (1)

`SCORE_GOAL: false`. Capsule +1 event; `next_experiment` = **R46** (the per-frame score-source telemetry, restore-only, 0–1 boots).
